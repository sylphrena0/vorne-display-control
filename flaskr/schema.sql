DROP TABLE IF EXISTS user;
DROP TABLE IF EXISTS msg;
DROP TABLE IF EXISTS logging;
DROP TABLE IF EXISTS settings;
DROP TABLE IF EXISTS addresses;

CREATE TABLE user ( --create user table
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username  CHARACTER(20) UNIQUE NOT NULL,
  admin BOOLEAN NOT NULL,
  password TEXT NOT NULL
);

CREATE TABLE msg ( --create settings table
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  msg TEXT NOT NULL,
  mode TEXT NOT NULL,
  ro INT NOT NULL,
  df INT NOT NULL
);

CREATE TABLE logging ( --create logging table
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  datetime TEXT NOT NULL,
  lvl INT NOT NULL,
  msg TEXT NOT NULL
);

CREATE TABLE settings ( --create logging table
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  setting CHARACTER(20) NOT NULL,
  stored CHARACTER(20) NOT NULL
);

CREATE TABLE addresses ( --create logging table
  stored TEXT NOT NULL PRIMARY KEY,
  shipping BOOLEAN NOT NULL
);

INSERT INTO msg VALUES( --insert default values
  1, --id
  "Welcome to North Mountain Supply", --msg
  "Medium Scrolling", --mode
  0, --ro
  0 --df
);

INSERT INTO addresses(stored, shipping) VALUES --insert default values
  ("11", 0), 
  ("08", 1);

INSERT INTO settings(setting, stored) VALUES --insert default values
  ("COM_PORT", "/dev/ttyS0"),
  ("BAUD_RATE", "9600"),
  ("FNT","1"),
  ("FBM_DELAY","3"),
  ("START_TIME","04:00"),
  ("END_TIME","17:00");