DROP TABLE IF EXISTS user;
DROP TABLE IF EXISTS msg;
DROP TABLE IF EXISTS logging;

CREATE TABLE user ( --create user table
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  admin BOOLEAN NOT NULL,
  password TEXT NOT NULL
);

CREATE TABLE msg ( --create settings table
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  msg TEXT NOT NULL,
  mode TEXT NOT NULL,
  df INT NOT NULL
);

CREATE TABLE logging ( --create logging table
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  datetime TEXT NOT NULL,
  lvl TEXT NOT NULL,
  msg TEXT NOT NULL
);

INSERT INTO msg VALUES( --insert default values
  1, --id
  "Welcome to North Mountain Supply", --msg
  "Medium Scrolling", --mode
  0 --df
);