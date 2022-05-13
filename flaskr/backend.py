import serial #pyserial
import time
import datetime
import requests
import urllib.request
import traceback
import os
import sys
from json import loads as loads
from datetime import datetime
from flask import g, request, session, Blueprint
from flaskr.db import log, get_db
from threading import Thread

#https://www.vorne.com/support/product-manuals/m1000.pdf


def start(app):
    with app.app_context(): #activates application context
        ###########################################
        ###### [Grab Shipstation Order Data] ######
        ########################################### 
        def getfbmOrders():
            ss_api_key = '2d434e9321574d708dbdc966c30bbd36'
            ss_api_secret = '2611068a8a7c4a1d905b33e074b972e2'
            response = requests.get("https://ssapi.shipstation.com/orders?orderStatus=awaiting_shipment&pageSize=500", auth=(ss_api_key, ss_api_secret))
            dict = loads(response.text) #gets post request response
            storedict = {"thermalbladedealer": 67315,"thermalblade": 89213,"qqship": 91927,"qqshipCA": 61349,"nms": 67134,"manual": 38981,"unbranded": 82894} #defines dictionary of shipstation store IDs
            total, thermalblade, qqship, manual, nms = 0, 0, 0, 0, 0 #initializes order variable counters
            for order in dict.get("orders"): #grabs the order dictionarys from the set response
                advancedOptions = order.get("advancedOptions") #gets the dictionary that containes the storeID from each order
                total += 1
                if (advancedOptions.get('storeId') == storedict.get("thermalbladedealer")) or (advancedOptions.get('storeId') == storedict.get("thermalblade")): 
                    thermalblade += 1 
                elif advancedOptions.get('storeId') == storedict.get("qqship") or advancedOptions.get('storeId') == storedict.get("qqshipCA"): 
                    qqship += 1 
                elif advancedOptions.get('storeId') == storedict.get("manual") or advancedOptions.get('storeId') == storedict.get("unbranded"): 
                    manual += 1 
                elif advancedOptions.get('storeId') == storedict.get("nms"): 
                    nms += 1 
            return [total, thermalblade, qqship, manual, nms] #returns list of data results

        ############################################
        ######## [Setup Configs for Serial] ########
        ############################################
        ser = serial.Serial()
        ser.baudrate = 9600 #baud rate, set to number shown on the display
        ser.port = 'COM2' #COM port of serial display control.
        ser.timeout = 2 #timeout. Leave as is

        #############################################
        ###### [M1000 Communication Functions] ######
        ############################################# 
        def sendmessage(text="CHANGEME",addr=["01"],font=5,line=1,char="",blinkrate=None,blinktype=None,scrollrate=None,scrollexpiry=None,debug=False): #defines function to send data to display
            #translate optional arguments to command syntax or null strings if not specifed
            blink, scroll, messagetype = "", "", "static "
            if char != "":
                char = "\x1b%sC" % (char)
                messagetype = "partial "
            if blinkrate != None and blinktype != None:
                blink = "\x1b%s;+%s" % (blinkrate,blinktype)
                messagetype = "blinking "
            if scrollrate != None and scrollexpiry != None:
                scroll = "\x1b%s;%sS" % (scrollrate,scrollexpiry)
                messagetype = "scrolling "
            if [char,blink,scroll].count("") < 2: #ensure mutliple commands are not specified
                log("WARN","Conflicting message commands - canceling message!")
                print([char,blink,scroll].count("") < 2,[char,blink,scroll].count(""), [char,blink,scroll])
                return

            for address in addr: #iterates through all displays
                ser.open() #open COM port
                string = "\x1b%sA\x1b%sL%s\x1b-b\x1b-B\x1b%sF%s%s%s\r" % (address,line,char,font,blink,scroll,text) #\x1b is eqv to <ESC> in the manual, \r to <CR> (EOL)
                ser.write(b'%s' % (string.encode('ascii'))) #encodes as ascii, changes to bytes, and writes to display
                ser.close() #close COM 

            if debug: log("DEBUG","Sending %smessage to displays" % (messagetype))
        
        #---------------------------------------
        print("\nBackend Started\n")
        log("INFO","Backend Started")
        #---------------------------------------

        if(ser.isOpen() == True): #checks for improper shutdown
            ser.close()
            log("INFO", "Caught unclosed port. Closing now.")

        addresses = ["11"]
        lastfbm = 0
        while True:
            sendmessage(str(time.strftime("%H:%M")),char=0,addr=addresses,font=1,line=1) #updates time every ten seconds. We use the char command to set start point without clearing display.
            time.sleep(10)
            lastfbm += 10
            
            if lastfbm >= 180:
                pass

#function called from __init__.py to start the function above in a sub-process with the application context
def backend(app):
    thread = Thread(target=start, args=(app,))
    thread.daemon = True
    thread.start()