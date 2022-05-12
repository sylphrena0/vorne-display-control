import io #used to store frames
import logging #self-explainatory
import json #to get data from js
import socketserver #may be unused?
from flask import Blueprint, flash, g, redirect, render_template, request, url_for, Flask, Response #web framework imports
from werkzeug.exceptions import abort
from flaskr.auth import login_required
from flaskr.db import get_db,close_db #access to database

#sets the blueprint for this code
bp = Blueprint('control', __name__)

'''
def updateSettings():
    db = get_db()
    settings_list = db.execute('SELECT * FROM settings WHERE id = 1') #grab settings data
    #settings['throttle'] settings['nightvision'] settings['buttoncontrol'] settings['keycontrol'] settings['resolution'] 

    #set nightvision mode


updateSettings()
'''

#defines a settings function which is called when /getmsg is accessed
@bp.route('/getmsg')
@login_required
def getmsg():
    db = get_db()
    settings = db.execute( 'SELECT msg, mode, df FROM msg WHERE id = 1' ).fetchone()
    data = []
    data.append(list(settings))
    print(data)
    #updateSettings()
    return Response(json.dumps(data))

#defines the index page and controls buttons. control buttons should be removed!
@bp.route('/', methods=['GET','POST'])
@login_required
def index():
    if request.method == 'POST':
        msg = request.form['msg']
        mode = request.form['mode']
        df = request.form['df']
        error = None

        if not msg:
            error = 'Message is required.'
        elif not df:
            error = 'DF Orders is required.'

        try:
            db = get_db()
            print("UPDATE msg SET (msg, mode, df) = (?, ?, ?) WHERE id = 1",(msg, mode, df,))
            db.execute("UPDATE msg SET (msg, mode, df) = (?, ?, ?) WHERE id = 1",(msg, mode, df,))
            db.commit()
        except error as e:
            flash(e)

        if error is not None:
            flash(error)
    elif request.method == 'GET':
        return render_template('control/index.html', form=request.form)
    return render_template('control/index.html')

#defines the settings page, currently blank. contains depreciated code from tutorial
@bp.route('/settings', methods=('GET', 'POST'))
@login_required
def settings():
    return render_template('control/settings.html')