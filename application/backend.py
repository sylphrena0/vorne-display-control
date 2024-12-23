import serial #pyserial
import time
import datetime
import requests
import schedule
import traceback
from json import loads as loads
from datetime import datetime
from flask import g, request, session, Blueprint, app
from application.db import log, get_db
from threading import Thread

#Manual: https://www.vorne.com/support/product-manuals/m1000.pdf

#############################################
###### [M1000 Communication Functions] ######
############################################# 
def send_message(text="CHANGEME",addr=["01"],font=1,line=1,char="",rate=None,blink_type=None,scroll_expiry=None,center=False,debug=False): #defines function to send data to display
    #translate optional arguments to command syntax or null strings if not specified
    blink, scroll, message_type = "", "", "static "
    if char != "":
        char = "\x1b%sC" % (char)
        message_type = "partial "
    if blink_type != None:
        blink = "\x1b%s;+%s" % (rate,blink_type)
        message_type = "blinking "
    if scroll_expiry != None:
        scroll = "\x1b%s;%sS\x1b20R " % (rate,scroll_expiry)
        message_type = "scrolling "
    if [char,blink,scroll].count("") < 2: #ensure multiple commands are not specified
        message_type = "partial "
    if blink_type != None:
        blink = "\x1b%s;+%s" % (rate,blink_type)
        message_type = "blinking "
    if scroll_expiry != None:
        scroll = "\x1b%s;%sS\x1b20R " % (rate,scroll_expiry)
        message_type = "scrolling "
    if [char,blink,scroll].count("") < 2: #ensure multiple commands are not specified
        log("WARN","Conflicting message commands - canceling message!")
        print([char,blink,scroll].count("") < 2,[char,blink,scroll].count(""), [char,blink,scroll])
        return

    centerspcs = ""
    fontlength = [20,15,10,8,15,12,20,20,20]
    if center and len(text) < 19: #this will center the message if enabled
        centerspcs = "\x1b%sR " % int((fontlength[font] - len(text))/2)

    log("DEBUG","Sending message: " + text + " to " + str(addr))
    for address in addr: #iterates through all displays
        g.ser.open() #open COM port
        string = "\x1b%sA\x1b%sL%s\x1b-b\x1b-B\x1b%sF%s%s%s%s\r" % (address,line,char,font,blink,scroll,centerspcs,text) #\x1b is eqv to <ESC> in the manual, \r to <CR> (EOL)
        g.ser.write(b'%s' % (string.encode('ascii'))) #encodes as ascii, changes to bytes, and writes to display
        g.ser.close() #close COM 

    if debug: log("DEBUG","Sending %smessage to displays" % (message_type))

def parse_mode(mode,rate=None, scroll_expiry=None, blink_type=None): #turns the mode string used by flask into three backend compabile options
    if mode.endswith("Scrolling"):
        scroll_expiry = 0
    elif mode.endswith("Blinking"):
        blink_type = "B"
    if mode.startswith("Slow"):
        rate = 5 if scroll_expiry != None else 50
    elif mode.startswith("Medium"):
        rate = 10 if scroll_expiry != None  else 100
    elif mode.startswith("Fast"):
        rate = 15 if scroll_expiry != None  else 150
    return rate, scroll_expiry, blink_type

def get_ser():
    try:
        settings = {}
        stored_settings = get_db().execute('SELECT * FROM settings')
        for setting in stored_settings:
            settings[setting['setting']] = setting['stored']
        g.ser = serial.Serial()
        g.ser.baudrate = int(settings['BAUD_RATE']) #baud rate, set to number shown on the display
        g.ser.port = settings['COM_PORT'] #COM port of serial display control.
        g.ser.timeout = 2 #timeout. Leave as is
        if(g.ser.isOpen() == True): #checks for improper shutdown
            g.ser.close()
            log("info","Caught unclosed port. Closing now.")
    except Exception:
        log("CRIT",traceback.format_exc())
    return g.ser

#Information on setting the font for the next message
#1 -  8x6 pixels  2 lines of 20 characters.  
#2 -  8x8 pixels  2 lines of 15 characters.  
#3 -  16x12 pixels 1 lines of 10 characters.  
#4 -  16x15 pixels  1 lines of 8 characters.  
#5 -  16x8 pixels  1 lines of 15 characters.  
#6 -  16x10 pixels  1 lines of 12 characters.  
#7 -  8x6 pixels  2 lines of 20 characters.  * JIS8 / Katakana
#8 -  8x6 pixels  2 lines of 20 characters.  * Slavic
#9 -  8x6 pixels  2 lines of 20 characters.  * Cyrillic 
#Horizontal Tab 09h <HT> Move the cursor to the next tab stop. Stops are set at character columns 8 and 16. 

############################################
############ [Backend Function] ############
############################################
def backend(app):
    with app.app_context(): #activates application context
        log("INFO","Backend active")
        ser = get_ser()
        
        ##########################################
        ############### [Settings] ###############
        ###########################################
        settings = {}
        addresses, shipping_address = [], []
        stored_settings = get_db().execute('SELECT * FROM settings')
        for setting in stored_settings:
            settings[setting['setting']] = setting['stored']
        fnt = int(settings['FNT'])

        stored_addresses = get_db().execute('SELECT * FROM addresses')
        for address in stored_addresses:
            if address['shipping'] == 1:
                shipping_address.append(address['stored'])
            else:
                addresses.append(address['stored'])

        ###########################################
        ##### [Update Shipstation Order Data] #####
        ########################################### 
        def update_fbm():
            try:
                log("DEBUG","Updating FBM orders")
                msg = get_db().execute('SELECT df FROM msg WHERE id = 1').fetchone()
                ss_api_key = settings['SS_API_KEY']
                ss_api_secret = settings['SS_API_SECRET']
                response = requests.get("https://ssapi.shipstation.com/orders?orderStatus=awaiting_shipment&pageSize=500", auth=(ss_api_key, ss_api_secret))
                if response.status_code == 204:
                    raise RuntimeWarning("Shipstation API returned 204: Success, No Content")
                _dict = loads(response.text) #gets post request response
                store_dict = {"thermalbladedealer": 67315,"thermalblade": 89213,"qqship": 91927,"qqshipCA": 61349,"nms": 67134,"manual": 38981,"unbranded": 82894} #defines dictionary of shipstation store IDs
                total_fbm, thermalblade, qqship, manual, nms = 0, 0, 0, 0, 0 #initializes order variable counters
                for order in _dict.get("orders"): #grabs the order dictionaries from the set response
                    advanced_options = order.get("advancedOptions") #gets the dictionary that contains the storeID from each order
                    total_fbm += 1
                    if (advanced_options.get('storeId') == store_dict.get("thermalbladedealer")) or (advanced_options.get('storeId') == store_dict.get("thermalblade")): 
                        thermalblade += 1 
                    elif advanced_options.get('storeId') == store_dict.get("qqship") or advanced_options.get('storeId') == store_dict.get("qqshipCA"): 
                        qqship += 1 
                    elif advanced_options.get('storeId') == store_dict.get("manual") or advanced_options.get('storeId') == store_dict.get("unbranded"): 
                        manual += 1 
                    elif advanced_options.get('storeId') == store_dict.get("nms"): 
                        nms += 1 
                send_message("NMS:" + str(nms) + " QQShip:" + str(qqship),char=0,addr=shippingaddress,font=fnt,line=1,center=True)
                send_message("TMB:" + str(thermalblade) + " Manual:" + str(manual),char=0,addr=shippingaddress,font=fnt,line=2,center=True)
                send_message(str("RO:" + str(totalfbm) + " DF:" + str(msg['df']) + "    "),char=7,addr=addresses,font=fnt,line=1)
                
                #update database for other modules
                db = get_db()
                db.execute("UPDATE msg SET ro = ? WHERE id = 1",(total_fbm,))
                db.commit()
            except Exception:
                log("ERROR", "Error in ShipStation API call!")
                log("ERROR",traceback.format_exc())

        ###########################################
        ##### [Update Shipstation Order Data] #####
        ########################################### 
        def update_time():
            now = datetime.now()
            send_message(text=str(now.strftime("%H:%M ")),char=0,addr=addresses,font=1,line=1)

        ###########################################
        ########## [Initialize Displays] ##########
        ########################################### 
        def initialize_displays():
            #initializes time and automatic order qtys
            update_time()
            time.sleep(.5)
            update_fbm()

            #adds message from previous instance
            msg = get_db().execute('SELECT * FROM msg WHERE id = 1').fetchone()
            rate, scrollexpiry, blinktype = parsemode(msg['mode']) #parse the human readable mode to commands
            send_message(msg['msg'],addr=addresses,font=fnt,line=2,rate=rate,scroll_expiry=scrollexpiry,blink_type=blinktype)

            #schedules message functions
            schedule.every(int(settings['FBM_DELAY'])).minutes.at(':30').do(update_fbm).tag('send-msg')
            schedule.every().minute.at(':00').do(update_time).tag('send-msg')

        ###########################################
        ############ [Timeout Handler] ############
        ###########################################
        #handles scheduling and turns off displays at night
        
        @schedule.repeat(schedule.every(5).minutes.at(':10'))
        def timeout_handler():
            try:
                active = get_db().execute('SELECT * FROM settings WHERE setting = "ACTIVE"').fetchone()['stored']
                end_hour, end_min = get_db().execute('SELECT * FROM settings WHERE setting = "END_TIME"').fetchone()['stored'].split(":")
                start_hour, start_min = get_db().execute('SELECT * FROM settings WHERE setting = "START_TIME"').fetchone()['stored'].split(":")
                end = int(end_hour)*60 + int(end_min)
                start = int(start_hour)*60 + int(start_min)
                now_min = datetime.now().hour*60 + datetime.now().minute

                log("DEBUG","Timeout handler called")
                if now_min >= start and now_min <= end and active == '0': #if time is beyond start hour and the displays are off, schedule message updates
                    db = get_db()
                    db.execute('UPDATE settings SET stored = "1" WHERE setting = "ACTIVE"')
                    db.commit()
                    log("INFO","Startup time reached. Activating displays.")
                    initialize_displays() #will add initial messages and schedule update tasks
                if now_min >= end and active == '1': # if time is beyond end hour and the displays are on
                    log("INFO","Shutdown time reached. Deactivating displays.")
                    db = get_db()
                    db.execute('UPDATE settings SET stored = "0" WHERE setting = "ACTIVE"')
                    db.commit()
                    schedule.clear('send-msg') #clears tasks with 'send-msg' tag
                    send_message(text="\x1b20R ",addr=addresses + shippingaddress,font=1,line=1) #clears display by filling with empty space
                    send_message(text="\x1b20R ",addr=addresses + shippingaddress,font=1,line=2) #clears display by filling with empty space
            except Exception:
                log("ERROR",traceback.format_exc())

        initialize_displays()
        time.sleep(0.5)
        timeout_handler()
        while True:
            schedule.run_pending()
            time.sleep(5)     

#function called from __init__.py to start the function above in a sub-process with the application context
def start(app):
    thread = Thread(target=backend, args=(app,))
    thread.daemon = True
    thread.start()