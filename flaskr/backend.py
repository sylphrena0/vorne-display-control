import serial #pyserial
import time
import requests
import traceback
import schedule
from json import loads as loads
from datetime import datetime
from flask import g, request, session, Blueprint, app
from flaskr.db import log, get_db
from threading import Thread

#Manual: https://www.vorne.com/support/product-manuals/m1000.pdf

#############################################
###### [M1000 Communication Functions] ######
############################################# 
def sendmessage(text="CHANGEME",addr=["01"],font=1,line=1,char="",rate=None,blinktype=None,scrollexpiry=None,center=False,debug=False): #defines function to send data to display
    #translate optional arguments to command syntax or null strings if not specifed
    blink, scroll, messagetype = "", "", "static "
    if char != "":
        char = "\x1b%sC" % (char)
        messagetype = "partial "
    if blinktype != None:
        blink = "\x1b%s;+%s" % (rate,blinktype)
        messagetype = "blinking "
    if scrollexpiry != None:
        scroll = "\x1b%s;%sS\x1b20R " % (rate,scrollexpiry)
        messagetype = "scrolling "
    if [char,blink,scroll].count("") < 2: #ensure mutliple commands are not specified
        log("WARN","Conflicting message commands - canceling message!")
        print([char,blink,scroll].count("") < 2,[char,blink,scroll].count(""), [char,blink,scroll])
        return

    centerspcs = ""
    fontlength = [20,15,10,8,15,12,20,20,20]
    if center and len(text) < 19: #this will center the message if enabled
        centerspcs = "\x1b%sR " % int((fontlength[font] - len(text))/2)

    for address in addr: #iterates through all displays
        g.ser.open() #open COM port
        string = "\x1b%sA\x1b%sL%s\x1b-b\x1b-B\x1b%sF%s%s%s%s\r" % (address,line,char,font,blink,scroll,centerspcs,text) #\x1b is eqv to <ESC> in the manual, \r to <CR> (EOL)
        g.ser.write(b'%s' % (string.encode('ascii'))) #encodes as ascii, changes to bytes, and writes to display
        g.ser.close() #close COM 

    if debug: log("DEBUG","Sending %smessage to displays" % (messagetype))
def parsemode(mode,rate=None, scrollexpiry=None, blinktype=None): #turns the mode string used by flask into three backend compabile options
    if mode.endswith("Scrolling"):
        scrollexpiry = 0
    elif mode.endswith("Blinking"):
        blinktype = "B"
    if mode.startswith("Slow"):
        rate = 5 if scrollexpiry != None else 50
    elif mode.startswith("Medium"):
        rate = 10 if scrollexpiry != None  else 100
    elif mode.startswith("Fast"):
        rate = 15 if scrollexpiry != None  else 150
    return rate, scrollexpiry, blinktype
def get_ser():
    settings = {}
    storedsettings = get_db().execute('SELECT * FROM settings')
    for setting in storedsettings:
        settings[setting['setting']] = setting['stored']
    g.ser = serial.Serial()
    g.ser.baudrate = int(settings['BAUD_RATE']) #baud rate, set to number shown on the display
    g.ser.port = settings['COM_PORT'] #COM port of serial display control.
    g.ser.timeout = 2 #timeout. Leave as is
    if(g.ser.isOpen() == True): #checks for improper shutdown
        g.ser.close()
        log("info","Caught unclosed port. Closing now.")
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

        ser = get_ser()
        
        ##########################################
        ############### [Settings] ###############
        ###########################################
        settings = {}
        addresses, shippingaddress = [], []
        storedsettings = get_db().execute('SELECT * FROM settings')
        for setting in storedsettings:
            settings[setting['setting']] = setting['stored']
        fnt = int(settings['FNT'])

        storedaddresses = get_db().execute('SELECT * FROM addresses')
        for address in storedaddresses:
            if address['shipping'] == '1':
                shippingaddress.append(address['stored'])
            else:
                addresses.append(address['stored'])

        #addresses = ["01","02","03","04","05","06","07","18"] #defines the list of addresses of our normal displays. #5-5am
    
        

        ###########################################
        ##### [Update Shipstation Order Data] #####
        ########################################### 
        @schedule.repeat(schedule.every(3).minutes.at(':30')) #decorator schedules the FBM update every three minutes 
        def getfbmOrders():
            msg = get_db().execute('SELECT df FROM msg WHERE id = 1').fetchone()
            ss_api_key = settings['SS_API_KEY']
            ss_api_secret = settings['SS_API_SECRET']
            response = requests.get("https://ssapi.shipstation.com/orders?orderStatus=awaiting_shipment&pageSize=500", auth=(ss_api_key, ss_api_secret))
            dict = loads(response.text) #gets post request response
            storedict = {"thermalbladedealer": 67315,"thermalblade": 89213,"qqship": 91927,"qqshipCA": 61349,"nms": 67134,"manual": 38981,"unbranded": 82894} #defines dictionary of shipstation store IDs
            totalfbm, thermalblade, qqship, manual, nms = 0, 0, 0, 0, 0 #initializes order variable counters
            for order in dict.get("orders"): #grabs the order dictionarys from the set response
                advancedOptions = order.get("advancedOptions") #gets the dictionary that containes the storeID from each order
                totalfbm += 1
                if (advancedOptions.get('storeId') == storedict.get("thermalbladedealer")) or (advancedOptions.get('storeId') == storedict.get("thermalblade")): 
                    thermalblade += 1 
                elif advancedOptions.get('storeId') == storedict.get("qqship") or advancedOptions.get('storeId') == storedict.get("qqshipCA"): 
                    qqship += 1 
                elif advancedOptions.get('storeId') == storedict.get("manual") or advancedOptions.get('storeId') == storedict.get("unbranded"): 
                    manual += 1 
                elif advancedOptions.get('storeId') == storedict.get("nms"): 
                    nms += 1 
            sendmessage("NMS:" + str(nms) + " QQShip:" + str(qqship),addr=shippingaddress,font=fnt,line=1,center=True)
            sendmessage("TMB:" + str(thermalblade) + " Manual:" + str(manual),addr=shippingaddress,font=fnt,line=2,center=True)
            sendmessage(str(time.strftime("%H:%M") + " RO:" + str(totalfbm) + " DF:" + str(msg['df'])),addr=addresses,font=fnt,line=1)

            #update database for other modules
            try:
                db = get_db()
                db.execute("UPDATE msg SET ro = ? WHERE id = 1",(totalfbm,))
                db.commit()
            except Exception as e:
                log("ERROR",e)
            
        ###########################################
        ########## [Initialize Displays] ##########
        ########################################### 
        sendmessage(text=str(time.strftime("%H:%M")),char=0,addr=addresses,font=1,line=1)

        msg = get_db().execute('SELECT * FROM msg WHERE id = 1').fetchone()
        rate, scrollexpiry, blinktype = parsemode(msg['mode']) #parse the human readable mode to commands
        sendmessage(msg['msg'],addr=addresses,font=fnt,line=2,rate=rate,scrollexpiry=scrollexpiry,blinktype=blinktype)
        time.sleep(.5)

        getfbmOrders() #initializes automatic order qtys
        
        #this will schedule display updates only when they are needed
        schedule.every().minute.at(':00').do(sendmessage,text=str(time.strftime("%H:%M")),char=0,addr=addresses,font=1,line=1) #update time everytime the sys clock is xx:xx:00

        while True:
            schedule.run_pending()
            time.sleep(5)     

#function called from __init__.py to start the function above in a sub-process with the application context
def start(app):
    thread = Thread(target=backend, args=(app,))
    thread.daemon = True
    thread.start()