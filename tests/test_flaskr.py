import pytest
import os
import sqlite3
import tempfile
from flask import g
from flaskr import app, init_db, get_db


class TestFlaskr:

    def test_close_db(self):
        """
        Test that close_db() does not attempt to close the database connection
        when the 'sqlite_db' attribute is not present in the application context.
        """
        with app.app_context():
            # Ensure 'sqlite_db' attribute is not present
            assert not hasattr(g, 'sqlite_db')

            # Call close_db() and verify it doesn't raise any exceptions
            app.teardown_appcontext_funcs[0](None)

        # No assertion is needed here as the test passes if no exception is raised


    def test_connect_db(self):
        """
        Test that connect_db() successfully connects to the database and returns a connection object.
        """
        with app.app_context():
            from flaskr.flaskr import connect_db
            connection = connect_db()
            assert isinstance(connection, sqlite3.Connection)
            assert connection.row_factory == sqlite3.Row
            connection.close()
            

    def test_init_db(self):
        """
        Test that init_db() correctly initializes the database.

        This test verifies that the init_db function creates the necessary
        tables in the database by executing the SQL script from schema.sql.
        It checks if the 'entries' table is created and if it has the expected
        structure.
        """
        with app.app_context():
            init_db()
            db = get_db()

            # Check if the 'entries' table exists
            result = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entries'").fetchone()
            assert result is not None

            # Check if the 'entries' table has the expected columns
            cursor = db.execute('PRAGMA table_info(entries)')
            columns = [row[1] for row in cursor.fetchall()]
            expected_columns = ['id', 'title', 'text']
            assert set(columns) == set(expected_columns)
            
            # Check if the 'wiki_pages' table exists
            result = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='wiki_pages'").fetchone()
            assert result is not None
            
            # Check if the 'wiki_pages' table has the expected columns
            cursor = db.execute('PRAGMA table_info(wiki_pages)')
            columns = [row[1] for row in cursor.fetchall()]
            expected_columns = ['id', 'title', 'content', 'created', 'updated']
            assert set(columns) == set(expected_columns)

    def test_initdb_command(self):
        """
        Test that the initdb_command initializes the database correctly.

        This test verifies that the 'init_db' command:
        1. Calls the init_db() function
        2. Prints the expected message after initialization
        """
        runner = app.test_cli_runner()
        result = runner.invoke(args=['init_db'])
        assert 'Initialized the database.' in result.output
        assert result.exit_code == 0

    def test_invalid_username(self):
        """
        Test login functionality when an invalid username is provided.

        This test case covers the following path:
        - request.method == 'POST'
        - request.form['username'] != app.config['USERNAME']

        Expected outcome:
        - The login attempt should fail
        - An error message 'Invalid username' should be returned
        - The user should not be redirected
        """
        with app.test_client() as client:
            response = client.post('/login', data={
                'username': 'invalid_user',
                'password': 'default'
            }, follow_redirects=True)

            assert b'Invalid username' in response.data
            assert response.status_code == 200
            assert b'You were logged in' not in response.data

    def test_login_get(self):
        """
        Test login when request method is not POST.

        This test verifies that when the login route is accessed with a GET request,
        it renders the login template without any error message.
        """
        with app.test_client() as client:
            response = client.get('/login')
            assert response.status_code == 200
            assert b'<form action=' in response.data
            assert b'method=post' in response.data
            assert b'Invalid username' not in response.data
            assert b'Invalid password' not in response.data

    def test_login_successful(self):
        """
        Test successful login with correct username and password.
        Verifies that the user is redirected to show_entries page and logged in.
        """
        with app.test_client() as client:
            response = client.post('/login', data={
                'username': app.config['USERNAME'],
                'password': app.config['PASSWORD']
            }, follow_redirects=True)

            assert response.status_code == 200
            assert b'You were logged in' in response.data
            assert b'log out' in response.data

    def test_show_entries(self):
        """
        Test the show_entries function to ensure it correctly renders the template
        with the entries from the database.
        """
        with app.test_client() as client:
            # Make a GET request to the root URL
            response = client.get('/')

            # Check if the response status code is 200 (OK)
            assert response.status_code == 200

            # Check if the response contains the expected content
            assert b'<title>Amazon Q Developer Flask Demo</title>' in response.data
            # Remove the check for <h2>Entries</h2> as it's not in the template
            
            # Note: We're not checking for specific entries here because
            # the database state is not guaranteed. In a real-world scenario,
            # you might want to set up a known database state before running this test.

    def test_delete_entry(self):
        """
        Test the delete_entry function to ensure it correctly removes an entry from the database.
        """
        with app.test_client() as client:
            # Log in
            client.post('/login', data={
                'username': app.config['USERNAME'],
                'password': app.config['PASSWORD']
            })
            
            # Add an entry
            client.post('/add', data={
                'title': 'Test Entry',
                'text': 'This is a test entry to be deleted.'
            })
            
            # Get the entries to find the ID of the one we just added
            with app.app_context():
                db = get_db()
                entry = db.execute('SELECT id FROM entries WHERE title = ?', ['Test Entry']).fetchone()
                entry_id = entry['id']
            
            # Delete the entry
            response = client.post(f'/delete/{entry_id}', follow_redirects=True)
            
            # Check if the deletion was successful
            assert response.status_code == 200
            assert b'Entry was successfully deleted' in response.data
            
            # Verify the entry is no longer in the database
            with app.app_context():
                db = get_db()
                entry = db.execute('SELECT * FROM entries WHERE id = ?', [entry_id]).fetchone()
                assert entry is None

    def test_delete_entry_unauthorized(self):
        """
        Test that unauthorized users cannot delete entries.
        """
        with app.test_client() as client:
            # Try to delete an entry without being logged in
            response = client.post('/delete/1')
            
            # Should get a 401 Unauthorized response
            assert response.status_code == 401
            
    # Wiki tests
    def test_show_wiki_pages(self):
        """
        Test the show_wiki_pages function to ensure it correctly renders the template.
        """
        with app.test_client() as client:
            response = client.get('/wiki')
            
            # Check if the response status code is 200 (OK)
            assert response.status_code == 200
            
            # Check if the response contains the expected content
            assert b'<h2>Wiki Pages</h2>' in response.data
            
    def test_create_wiki_page_unauthorized(self):
        """
        Test that unauthorized users cannot create wiki pages.
        """
        with app.test_client() as client:
            # Try to access the create page without being logged in
            response = client.get('/wiki/create')
            
            # Should get a 401 Unauthorized response
            assert response.status_code == 401
            
    def test_create_wiki_page(self):
        """
        Test creating a new wiki page.
        """
        with app.test_client() as client:
            # Log in
            client.post('/login', data={
                'username': app.config['USERNAME'],
                'password': app.config['PASSWORD']
            })
            
            # Access the create page
            response = client.get('/wiki/create')
            assert response.status_code == 200
            assert b'Create New Wiki Page' in response.data
            
            # Create a new wiki page
            response = client.post('/wiki/create', data={
                'title': 'Test Wiki Page',
                'content': 'This is a test wiki page content.'
            }, follow_redirects=True)
            
            # Check if the creation was successful
            assert response.status_code == 200
            assert b'New wiki page was successfully created' in response.data
            
            # Verify the page is in the database
            with app.app_context():
                db = get_db()
                page = db.execute('SELECT * FROM wiki_pages WHERE title = ?', ['Test Wiki Page']).fetchone()
                assert page is not None
                assert page['content'] == 'This is a test wiki page content.'
                
    def test_view_wiki_page(self):
        """
        Test viewing a wiki page.
        """
        with app.test_client() as client:
            # Log in and create a wiki page
            client.post('/login', data={
                'username': app.config['USERNAME'],
                'password': app.config['PASSWORD']
            })
            
            client.post('/wiki/create', data={
                'title': 'View Test Page',
                'content': 'This is a test wiki page for viewing.'
            })
            
            # Get the page ID
            with app.app_context():
                db = get_db()
                page = db.execute('SELECT id FROM wiki_pages WHERE title = ?', ['View Test Page']).fetchone()
                page_id = page['id']
            
            # View the page
            response = client.get(f'/wiki/{page_id}')
            
            # Check if the view is successful
            assert response.status_code == 200
            assert b'View Test Page' in response.data
            assert b'This is a test wiki page for viewing.' in response.data
            
    def test_edit_wiki_page(self):
        """
        Test editing a wiki page.
        """
        with app.test_client() as client:
            # Log in and create a wiki page
            client.post('/login', data={
                'username': app.config['USERNAME'],
                'password': app.config['PASSWORD']
            })
            
            client.post('/wiki/create', data={
                'title': 'Edit Test Page',
                'content': 'Original content.'
            })
            
            # Get the page ID
            with app.app_context():
                db = get_db()
                page = db.execute('SELECT id FROM wiki_pages WHERE title = ?', ['Edit Test Page']).fetchone()
                page_id = page['id']
            
            # Access the edit page
            response = client.get(f'/wiki/{page_id}/edit')
            assert response.status_code == 200
            assert b'Edit Wiki Page' in response.data
            
            # Edit the page
            response = client.post(f'/wiki/{page_id}/edit', data={
                'title': 'Updated Test Page',
                'content': 'Updated content.'
            }, follow_redirects=True)
            
            # Check if the edit was successful
            assert response.status_code == 200
            assert b'Wiki page was successfully updated' in response.data
            assert b'Updated Test Page' in response.data
            assert b'Updated content.' in response.data
            
            # Verify the changes in the database
            with app.app_context():
                db = get_db()
                page = db.execute('SELECT * FROM wiki_pages WHERE id = ?', [page_id]).fetchone()
                assert page['title'] == 'Updated Test Page'
                assert page['content'] == 'Updated content.'
                
    def test_delete_wiki_page(self):
        """
        Test deleting a wiki page.
        """
        with app.test_client() as client:
            # Log in and create a wiki page
            client.post('/login', data={
                'username': app.config['USERNAME'],
                'password': app.config['PASSWORD']
            })
            
            client.post('/wiki/create', data={
                'title': 'Delete Test Page',
                'content': 'This page will be deleted.'
            })
            
            # Get the page ID
            with app.app_context():
                db = get_db()
                page = db.execute('SELECT id FROM wiki_pages WHERE title = ?', ['Delete Test Page']).fetchone()
                page_id = page['id']
            
            # Delete the page
            response = client.post(f'/wiki/{page_id}/delete', follow_redirects=True)
            
            # Check if the deletion was successful
            assert response.status_code == 200
            assert b'Wiki page was successfully deleted' in response.data
            
            # Verify the page is no longer in the database
            with app.app_context():
                db = get_db()
                page = db.execute('SELECT * FROM wiki_pages WHERE id = ?', [page_id]).fetchone()
                assert page is None


class AuthActions(object):

    def __init__(self, client):
        self._client = client

    def login(self, username='admin', password='default'):
        return self._client.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self._client.get('/logout', follow_redirects=True)