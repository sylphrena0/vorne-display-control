from dis import dis
import json #to get data from js
import traceback
import os
from flask import Blueprint, flash, g, redirect, render_template, request, url_for, Flask, Response #web framework imports
from flaskr.auth import login_required, admin_required
from flaskr.db import log, get_db,close_db #access to database
from flaskr.backend import parsemode, sendmessage, get_ser

#sets the blueprint for this code
bp = Blueprint('control', __name__)

############################################
############# [Control Routes] #############
############################################ 
#defines a function which is called when /getmsg is accessed
@bp.route('/getmsg')
@login_required
def getmsg():
    db = get_db()
    settings = db.execute( 'SELECT msg, mode, df FROM msg WHERE id = 1' ).fetchone()
    data = []
    data.append(list(settings))
    print(data)
    return Response(json.dumps(data))

#defines the index page and controls buttons. control buttons should be removed!
@bp.route('/', methods=['GET','POST'])
@login_required
def index():
    if request.method == 'POST': #if the user hits the submit button
        msg = request.form['msg']
        mode = request.form['mode']
        df = request.form['df'] + "    "
        error = None #initializes error message

        if not msg: #check for incomplete form, though it should not be allowed by html
            error = 'Message is required.'
        elif not df:
            error = 'DF Orders is required.'

        try: #send new message to database and log any errors
            db = get_db()
            db.execute("UPDATE msg SET (msg, mode, df) = (?, ?, ?) WHERE id = 1",(msg, mode, df,))
            db.commit()
        except Exception:
            log("CRIT",traceback.format_exc())
    
        rate, scrollexpiry, blinktype = parsemode(mode) #parse the human readable mode to commands
        
        get_ser() #gets serial config from backend.py to enable serial control from here

        #grab addresses from settings in db
        settings = {}
        addresses, shipping = [], []
        storedsettings = get_db().execute('SELECT * FROM settings')
        for setting in storedsettings:
            settings[setting['setting']] = setting['stored']
        fnt = int(settings['FNT'])

        storedaddresses = get_db().execute('SELECT * FROM addresses')
        for address in storedaddresses:
            if address['shipping'] == 1:
                shipping.append(address['stored'])
            else:
                addresses.append(address['stored'])

        #get FBM numbers and update messages
        totalfbm = get_db().execute('SELECT ro FROM msg').fetchone()[0]
        sendmessage(msg,addr=addresses,font=fnt,line=2,rate=rate,scrollexpiry=scrollexpiry,blinktype=blinktype)
        sendmessage("RO:" + str(totalfbm) + " DF:" + str(df) + "        ",char=7,addr=addresses,font=fnt,line=1)

        if error is not None:
            flash(error)
    elif request.method == 'GET':
        return render_template('control/index.html', form=request.form)
    return render_template('control/index.html')

############################################
############# [Setting Routes] #############
############################################ 
#defines the settings page
@bp.route('/settings', methods=('GET', 'POST'))
@login_required
@admin_required
def settings():
    if request.method == 'POST':
        error = None
        com_port = request.form['COM']
        baud_rate = ''.join(filter(str.isdigit, request.form['baudrate'])) #these contain text in the html, we just need the number
        font = ''.join(filter(str.isdigit, request.form['font'])) #same as above
        ss_api_key = request.form['SS_API_KEY']
        ss_api_secret = request.form['SS_API_SECRET']
        addresses = request.form['displays'].replace(" ","").split(",")
        shipping_addresses = request.form['shipping_displays'].replace(" ","").split(",")
        FBM_delay = request.form['FBM_delay']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        
        try:
            db = get_db()
            db.execute("DELETE FROM addresses")
            db.commit()
            log("INFO","Updating addresses: " + str(addresses) + ", shipping addresses: " + str(shipping_addresses))
            for display in addresses:
                if int(display) >= 0 and int(display) <= 100:
                    db = get_db()
                    db.execute("INSERT INTO addresses VALUES (?, 0)", (display,))
                    db.commit()
                else:
                    error = "Invalid Addresses!"
            for display in shipping_addresses:
                if int(display) >= 0 and int(display) <= 100:
                    if int(display) >= 0 and int(display) <= 9 and len(display) < 2:
                        display = "0" + str(display)
                    db = get_db()
                    db.execute("INSERT INTO addresses(stored, shipping) VALUES (?, 1)", (display,))
                    db.commit()
                else:
                    error = "Invalid Addresses!"
            
            if ss_api_key != "" and ss_api_secret != "":
                log("INFO","Updating Shipstation API Keys")
                db = get_db()
                db.execute("UPDATE settings SET (stored) =  (?) WHERE setting = 'SS_API_KEY'", (ss_api_key,))
                db.execute("UPDATE settings SET (stored) =  (?) WHERE setting = 'SS_API_SECRET'", (ss_api_secret,))
                db.commit()

            log("INFO","Updating settings -" + " com_port: " + com_port + ", baud_rate: " + baud_rate + ", font: " + font + ", FBM_delay: " + FBM_delay + ", start_time: " + start_time + ", end_time: " + end_time)
            db = get_db()
            db.execute("UPDATE settings SET (stored) =  (?) WHERE setting = 'COM_PORT'", (com_port,))
            db.execute("UPDATE settings SET (stored) =  (?) WHERE setting = 'BAUD_RATE'", (baud_rate,))
            db.execute("UPDATE settings SET (stored) =  (?) WHERE setting = 'FNT'", (font,))
            db.execute("UPDATE settings SET (stored) =  (?) WHERE setting = 'FBM_DELAY'", (FBM_delay,))
            db.execute("UPDATE settings SET (stored) =  (?) WHERE setting = 'START_TIME'", (start_time,))
            db.execute("UPDATE settings SET (stored) =  (?) WHERE setting = 'END_TIME'", (end_time,))
            db.commit()
        except Exception:
            log("ERROR",traceback.format_exc())
        if error is not None:
            flash(error)
    elif request.method == 'GET':
        return render_template('control/settings.html', form=request.form)
    return render_template('control/settings.html')

#defines a settings function which is called when /getsettings is accessed
@bp.route('/getsettings')
@login_required
@admin_required
def getsettings():
    db = get_db()

    settings = {}
    for setting in get_db().execute('SELECT * FROM settings WHERE NOT (setting = "SS_API_KEY") AND NOT (setting = "SS_API_SECRET")'):
        settings[setting['setting']] = setting['stored']

    addresses, shipping = "", ""
    for row in get_db().execute('SELECT * FROM addresses'):
        if row['shipping'] == 1:
            if shipping == "":
                shipping += row['stored']
            else:
                shipping += ", " + row['stored']
        else:
            if addresses == "":
                addresses += row['stored']
            else:
                addresses += ", " + row['stored']
    settings['ADDRESSES'] = addresses
    settings['SHIPPING_ADDRESSES'] = shipping

    return Response(json.dumps(settings))

############################################
############ [Debugging Routes] ############
############################################ 
#defines the debugging page
@bp.route('/debugging', methods=('GET', 'POST'))
@login_required
@admin_required
def debugging():
    if request.method == 'POST':
        db = get_db()
        db.execute("DELETE FROM logging")
        db.commit()
        log("INFO","Logs cleared!")
    return render_template('control/debugging.html')

@bp.route('/getlogs')
@login_required
@admin_required
def getlogs():
    lvl = request.args.get("lvl")
    logging = []
    for log in get_db().execute('SELECT * FROM logging WHERE lvl >= {} ORDER BY id DESC'.format(lvl)):
        logging.append(log['datetime'] + " - " + ["DEBUG","INFO","WARN","ERROR","CRIT"][log['lvl']] + ": " + log['msg'])
    if len(logging) < 1:
        logging = ["No entries found"]
    return Response(json.dumps(logging))

@bp.route('/restart')
@login_required
@admin_required
def restart():
    log("INFO","Restarting Service")
    os.system("sudo reboot")
    return