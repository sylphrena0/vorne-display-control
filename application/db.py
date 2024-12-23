import sqlite3
import click
import traceback
from datetime import datetime
from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

def get_db():
    try:
        if 'db' not in g:
            g.db = sqlite3.connect(
                current_app.config['DATABASE'],
                detect_types=sqlite3.PARSE_DECLTYPES
            )
            g.db.row_factory = sqlite3.Row
    except Exception:
        log("CRIT",traceback.format_exc())
    return g.db

#custom logging function that prints and sends to database. also deletes old messages
def log(level,message):
    timestamp = datetime.now().strftime("%m/%d/%Y: %H:%M:%S")
    int_level = ["DEBUG","INFO","WARN","ERROR","CRIT"].index(level.upper())
    try:
        db = get_db()
        db.execute("DELETE FROM logging WHERE id NOT IN (SELECT id FROM logging ORDER BY id DESC LIMIT 100000)")
        db.commit()
        db.execute("INSERT INTO logging (datetime, lvl, msg) VALUES (?, ?, ?)", (timestamp, int_level, message), )
        print(timestamp,"-",message)
        db.commit()
    except Exception:
        print("Critical Error: Could not log to database!")
        print(traceback.format_exc())

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))
    try:
        with current_app.open_resource('ss-api-insert.sql') as f:
            db.executescript(f.read().decode('utf8'))
    except:
        pass

    #make default user
    db.execute("INSERT INTO user (username, admin, password) VALUES (?, ?, ?)",    ('Admin', 1, generate_password_hash('administrator')),)
    db.commit()

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

def init_app(app):
    #app.teardown_appcontext(close_db) #this will make db commands not work elsewhere, do not do this
    app.cli.add_command(init_db_command)