drop table if exists entries;
create table entries (
  id integer primary key autoincrement,
  title text not null,
  'text' text not null
);

drop table if exists wiki_pages;
create table wiki_pages (
  id integer primary key autoincrement,
  title text not null,
  content text not null,
  created timestamp not null default current_timestamp,
  updated timestamp not null default current_timestamp
);
