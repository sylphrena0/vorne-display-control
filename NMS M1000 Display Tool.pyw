#! /usr/bin/python3
import logging
import serial #pyserial
import time
import requests
import PySimpleGUIWeb as sg
import urllib.request
import traceback
import os
import sys
from json import loads as loads
from datetime import datetime
import logging.handlers as handlers #to manage old logs


#!!TO-DO: change message functions to update both lines at once

###### [Setup Configs for Serial] ###### 
ser = serial.Serial()
ser.baudrate = 9600 #baud rate, set to number shown on the display
ser.port = '/dev/ttyS0' #COM port of serial display control.
ser.timeout = 2 #timeout. Leave as is
#---------------------------------------

###### [Setup Logging] ###### 
#if os.path.exists("latest-log"): #rename latest log if program didn't call a reboot on last run
#  os.rename("latest-log",str(datetime.now().strftime('%m/%d/%Y %H:%M:%S')))

logger = logging.getLogger('display-tool')
logger.setLevel(logging.INFO)
logHandler = handlers.TimedRotatingFileHandler('/home/nms/Documents/Display-Tool/logs/latest.log', when='M', interval=86400, backupCount=30)
formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

loghead = "Logging file, starting from " + str(datetime.now().strftime('%m/%d/%Y %H:%M:%S'))
logger.info(loghead) #sends logging header


#-----------------------------

###### [Attempt to Prevent Errors] ###### 
os.system("sudo fuser -k 80/tcp") #terminates any other programs using port 80
logging.info("Terminating other programs using port 80.")

if(ser.isOpen() == True): #checks for improper shutdown
    ser.close()
    logger.info("Caught unclosed port. Closing now.")
#--------------------------------------------


###### [M1000 Communication Functions] ###### 
def sendstatic(text="CHANGEME",addr=["01"],font=5,line=1): #defines function to send data to display
    for address in addr: #iterates through all displays
        ser.open() #open COM port
        string = "\x1b%sA\x1b%sL\x1b-b\x1b-B\x1b%sF%s\r" % (address,line,font,text) #\x1b is eqv to <ESC> in the manual, \r to <CR>
        ser.write(b'%s' % (string.encode('ascii'))) #encodes as ascii, changes to bytes, and writes to display
        ser.close() #close COM port
    logger.debug("Sending static messages")

def sendblinkingmsg(text="CHANGEME",addr=["01"],font=5,line=1,blinkrate=50,blinktype="B"): #defines function to send data to display
    for address in addr: #iterates through all displays
        ser.open() #open COM port
        string = "\x1b%sA\x1b%sL\x1b-b\x1b-B\x1b%sF\x1b%s;+%s%s\r" % (address,line,font,blinkrate,blinktype,text) #\x1b is eqv to <ESC> in the manual, \r to <CR> | \x1b-b\x1b-B disables all active blink commands
        ser.write(b'%s' % (string.encode('ascii'))) #encodes as ascii, changes to bytes, and writes to display
        ser.close() #close COM port
    logger.debug("Sending blinking messages")

def sendscrollingmsg(text="CHANGEME",addr=["01"],font=5,line=1,scrollrate=5,scrollexpiry=0): #defines function to send scrolling data
    for address in addr: #iterates through all displays
        ser.open() #open COM port
        string = "\x1b%sA\x1b%sL\x1b-b\x1b-B\x1b%sF\x1b%s;%sS%s\x1b20R \x04\r" % (address,line,font,scrollrate,scrollexpiry,text) #\x1b is eqv to <ESC> in the manual, \r to <CR>. \x04 markes the end of transmission, enabling us to do static text after scrolled.
        ser.write(b'%s' % (string.encode('ascii'))) #encodes as ascii, changes to bytes, and writes to display
        ser.close() #close COM port
    logger.debug("Sending srolling messages")

def sendmsg(msg,mode,addresses,fnt,line):
    if mode == "Static":
        sendstatic(msg,addr=addresses,font=fnt,line=line)
    elif mode == "Scrolling - Slow":
        sendscrollingmsg(msg,addr=addresses,font=fnt,line=line,scrollrate=5)
    elif mode == "Scrolling - Med":
        sendscrollingmsg(msg,addr=addresses,font=fnt,line=line,scrollrate=10)
    elif mode == "Scrolling - Fast":
        sendscrollingmsg(msg,addr=addresses,font=fnt,line=line,scrollrate=15)
    elif mode == "Blinking - Slow":
        sendblinkingmsg(msg,addr=addresses,font=fnt,line=line,blinkrate=50)
    elif mode == "Blinking - Med":
        sendblinkingmsg(msg,addr=addresses,font=fnt,line=line,blinkrate=100)
    elif mode == "Blinking - Fast":
        sendblinkingmsg(msg,addr=addresses,font=fnt,line=line,blinkrate=150)
#--------------------------------------------

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


###### [Grab Shipstation Order Data] ###### 
def getfbmOrders():
    ss_api_key = 'API_KEY_HERE'
    ss_api_secret = 'API_SECRET_HERE'
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
#----------------------------------

###### [Gui Configuration] ###### 
sg.theme('DarkBrown4')
sg.theme_text_color(('white'))
sg.theme_input_text_color(('white'))
sg.theme_input_background_color(('#111111'))

def gui(): #this is the function that creates the first window (main menu). Anytime gui() is called, this function will run and return to this window. For documentation on GUI options, dig in here: https://pysimplegui.readthedocs.io/en/latest/call%20reference/
    addresses = ["01","02","03","04","05","06","07","18"] #defines the list of addresses of our normal displays.
    shippingaddress = ["08"]
    print("Starting NMS M1000 Web Control")
    logger.info("Starting NMS M1000 Web Control on addresses:", str(addresses))
    fnt = 1 #sets our global font. Needs to be two lines
    vendororders = str("###") #initializes value for clock update
    FBM = getfbmOrders() #runs FBM order fetch module 
    totalfbm, thermalblade, qqship, manual, nms = str(FBM[0]),str(FBM[1]),str(FBM[2]),str(FBM[3]),str(FBM[4]) #initializes value for clock update
    shipping1 = str("NMS:" + nms + " QQShip:" + qqship) #sets the first line of the initial shipping message
    shipping2 = str("TMB:" + thermalblade + " Manual:" + manual) #sets the second line of the initial shipping message
    sendstatic(shipping1,addr=shippingaddress,font=fnt,line=1) #send initial shipping message to displays
    sendstatic(shipping2,addr=shippingaddress,font=fnt,line=2) #send initial shipping message to displays

    lastFBMupdate = datetime.now() #sets last run time for FBM update
    sendstatic("\x1b20R ",addr=addresses,font=fnt,line=2)

    sg.SetOptions(element_padding=(10, 10)) #sets default element padding. Must be defined for each window, or results will be unpredictable
    layout = [ #this defines the layout as a list of lists
                [sg.Image('/home/nms/Documents/Display-Tool/nms-white.png',pad=(15, 35))], #adds the APS logo
                [sg.Text("Welcome to the NMS M1000 Display Control Tool!\n")], #adds text
                [sg.Text("Direct Fufillment Orders:"),sg.Input("XXX", key='vendor',size=(10,1),justification='c')],
                [sg.Text("Message Mode:"),sg.Combo(values=["Static","Scrolling - Slow","Scrolling - Med","Scrolling - Fast","Blinking - Slow","Blinking - Med","Blinking - Fast"],default_value="Static",readonly=True,key="mode")],
                [sg.Input("Custom Message", key='msg',size=(60,3))],
                [sg.Button("Update Display",pad=(15, 30))] #adds buttons #,sg.Button("Exit",pad=(15, 30))
              ]

    #defines and opens window using defined layout. First element is window title. Finalize is used pretty much everywhere as it allows us to edit the window after defination (we use this for max size, changing text, and a bunch of other things). Size is W x H:
    window = sg.Window("NMS M1000 Display Control", layout, element_justification='c', finalize=True, resizable=True, size=(500,520),web_port=80,web_ip='0.0.0.0') 
    #window.set_min_size((350,390)) #sets minimum window size. Prevents cutoff of important elements

    #create an event loop to control window events like button clicks or an exit:
    while True: #end program if user closes window or presses the Cancel button
        event, values = window.read(timeout=20000) #timeout will run this loop again if nothing happens in a given amount of miliseconds
        #if event == "Exit" or event == sg.WIN_CLOSED: #handles window close and activates our cancel button
        #    sendscrollingmsg("NMS display software disconnected. Please start up the software on the host device.",font=fnt,line=2)
        #    window.close()
        #    break
        if event == "Update Display": #activates our import button, which calls the function which will open the import module, then closes the main menu
            mode = values["mode"]
            msg = values["msg"]
            vendororders = str(values["vendor"])
            sendstatic(str(time.strftime("%H:%M") + " RO:" + totalfbm + " DF:" + vendororders),addr=addresses,font=fnt,line=1)
            logger.info(str("Sent message to displays: " + time.strftime("%H:%M") + " RO:" + totalfbm + " DF:" + vendororders))
            if msg != "Custom Message":
                sendmsg(msg,mode,addresses,fnt,line=2)
                try: #should fix "UnboundLocalError: local variable 'debug' referenced before assignment"
                    if debug:
                        debug = True
                        logger.setLevel(logging.INFO)
                        logHandler.setLevel(logging.INFO)
                        logger.info("Debug mode deactivated") 
                except:
                    pass
            if msg == "DEBUG":
                debug = True
                logger.setLevel(logging.INFO)
                logHandler.setLevel(logging.INFO)
                logger.info("Debug mode activated")
                for address in addresses:
                    debugmsg = "Debug: Address = " + address
                    sendmsg(debugmsg,mode,[address],fnt,line=2)
            if os.path.exists(".rebooted"): #if this event is called, the program is likely not caught in a reboot loop and we can reset this flag
              os.remove(".rebooted")
              logger.info("Removing rebooted flag, program is stable")
        sendstatic(str(time.strftime("%H:%M") + " RO:" + totalfbm + " DF:" + vendororders),addr=addresses,font=fnt,line=1) #updates at least every 20 seconds
        if (datetime.now() - lastFBMupdate).total_seconds() > 180: #proceeds with FBM update if it has been at least three minutes since last update
            FBM = getfbmOrders() #runs FBM order fetch module 
            totalfbm, thermalblade, qqship, manual, nms = str(FBM[0]),str(FBM[1]),str(FBM[2]),str(FBM[3]),str(FBM[4]) #sets actual values using the set we just grabbed
            shipping1 = str("NMS:" + nms + " QQShip:" + qqship) #sets the first line of the initial shipping message
            shipping2 = str("TMB:" + thermalblade + " Manual:" + manual) #sets the second line of the initial shipping message
            lastFBMupdate = datetime.now() #updates last run timestamp
            sendstatic(shipping1,addr=shippingaddress,font=fnt,line=1)
            sendstatic(shipping2,addr=shippingaddress,font=fnt,line=2)
        if (datetime.now() - lastFBMupdate).total_seconds() > 600: #updates the display message every 600 seconds
            sendmsg(msg,mode,addresses,fnt,line=2)
#--------------------------------

###### [Program Execution/Error Handling] ###### 
try:
    gui() #executes program
except Exception as error: #captures issues and logs to file
    traceback.print_exc()
    logger.error(traceback.format_exc())
    logger.error(sys.exc_info()[2])
    pass
finally:
    logger.critical("Fatal Error Occured, closing COM port :/")
    if not(os.path.exists('.rebooted')): #loop that will restart system if this is the first time the script has failed out
        logger.info("System restarting once to attempt to resolve fatal errors")
        open('.rebooted', 'w').close() #creates a dummy hidden file that will signal that a restart was attempted
        os.system('reboot')
#-----------------------------------------------
    

logger.info("Closing NMS M1000 Web Control")
print("Closing NMS M1000 Web Control")
