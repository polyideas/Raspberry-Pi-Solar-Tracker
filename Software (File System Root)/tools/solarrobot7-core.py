#!/usr/bin/python

#Version Notes
#39:    Brought over from solar robot 7, cleanup of OpenElectrons code (going back to a Pololu controller)
#40:    Code optimizations for Raspberry Pi A+
#42:    Code cleanup, added debug toggle

from __future__ import print_function
import time, math
import serial, Pysolar, datetime
from dual_mc33926_rpi import motors, MAX_SPEED

#digital stuff
import RPi.GPIO as GPIO

#support for storing our values in a config file
import ConfigParser

# for the motor control we need the libraries for this controller:

import os, sys
print(((str(sys.argv[1:])[2:])[:-2]))
if (((str(sys.argv[1:])[2:])[:-2]) == "debug"):
    debug = True
else:
    debug = False

#read in all our variables
config = ConfigParser.ConfigParser()
config.read("/tools/inputs/masterinputs.txt")
#our latitude
maplat = float(config.get("myvars", "maplat"))
#our longitude
maplon = float(config.get("myvars", "maplon"))
#time limits to keep the robot from doing crazy things
pan_time_limit = int(config.get("myvars", "pan_time_limit"))
tilt_time_limit = int(config.get("myvars", "tilt_time_limit"))

#the lowest angle the IMU and mechanical hardware will reliably support
lowestangle = int(config.get("myvars", "lowestangle"))

#motor speed settings
motor1max_speed = int(config.get("myvars", "motor1max_speed"))
#motor2 is the panning motor
motor2max_speed = int(config.get("myvars", "motor2max_speed"))

#sleep tolerance is the margin by which difference between dawn target and actual heading
#this keeps the robot from moving during the night as the compass shifts
sleep_tolerance = int(config.get("myvars", "sleep_tolerance"))

#This is my magnetic declination *offset*
#If your declination is 11, your offset is -11
MagneticDeclination = float(config.get("myvars", "MagneticDeclination"))

#Calibration of the IMU
HorizontalCalibration = int(config.get("myvars", "HorizontalCalibration"))
AngleOffset = int(config.get("myvars", "AngleOffset"))

#Since the heading can fluctuate, we give a small margin to the compass
#Smaller numbers mean more accurate heading, but motor must go slower
hmargin = int(config.get("myvars", "hmargin"))

#Pololu Motor Stuff
# Set up sequences of motor speeds.
test_forward_speeds = list(range(0, MAX_SPEED, 1)) + [MAX_SPEED] * 200 + list(range(MAX_SPEED, 0, -1)) + [0]
test_reverse_speeds = list(range(0, -MAX_SPEED, -1)) + [-MAX_SPEED] * 200 + list(range(-MAX_SPEED, 0, 1)) + [0]
motors.enable()
motors.setSpeeds(0, 0)

#prep the digital ports
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(16, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) #this pin is for the override mode switch
GPIO.setup(19, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) #this pin is for horizon mode, on=do no motor movement at all
GPIO.setup(20, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) #unused but wired
GPIO.setup(21, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) #unused but wired

#These are our global motor speed variables- don't touch
global motor1speed
motor1speed = 0
global motor2speed
motor2speed = 0

#Open the serial port for the IMU
serialport = serial.Serial("/dev/ttyAMA0", 57600, timeout=5)

#Make sure the motors aren't doing anything before we start
motors.setSpeeds(0, 0)

#Calibrate the heading
Declination = MagneticDeclination + HorizontalCalibration

#Give the serial port time to open, so wait 2 seconds
time.sleep(1)

#Parse the IMU string to get tilt, which we don't really use
#Besides making sure the robot hasn't turned on its side
def getcurtilt():
        # The escape character for # is \x23 in hex
        serialport.write("\x23o0\x23f")
        response = serialport.readline()
        words = response.split(",")
        if len(words) > 2:
                try:
                        curtilt = float(words[2])
                except:
                        curtilt = 999
        return curtilt

#Get the heading from the IMU
#Translate the IMU from magnetic north to true north since the calcs use true north
def getcurheading():
# The escape character for # is \x23 in hex
        serialport.write("\x23o0 \x23f")
        headresponse = serialport.readline()
#       print(headresponse)
        words = headresponse.split(",")
        if len(words) > 2:
                try:
                        curheading = (float(words[0])) + 180
                        if curheading + Declination > 360: curheading = curheading - 360 + Declination
                        else: curheading = curheading + Declination
                except:
                        curheading = 999
#       print(curheading)
        return curheading

#Read the IMU to get the angle of incline (forwards/backwards)
#This is what we use for the solar panels, so we have to switch
#from 0 degrees on the normal axis to 0 degrees on the horizon
def getcurangle():
        # The escape character for # is \x23 in hex
        serialport.write("\x23o0 \x23f")
        response = serialport.readline()
        words = response.split(",")
        if len(words) > 2:
                try:
                        if ((float(words[1]) -90) * -1) < 89:
                                curangle = ((float(words[1]) -90) * -1)
                        else:
                                curangle = 0
                except:
                        curangle = 999
        return curangle + AngleOffset

#For troubleshooting, we use raw Azimuth from the calc
#Since this is in Azimuth:
# and we need true heading:
# and Azimuth actually is the direction of the shadow, not the sun
def getrawazimuth():
        Azimuth = Pysolar.GetAzimuth(maplat, maplon, datetime.datetime.utcnow())
        return Azimuth

#Convert Azimuth (the direction of the shadow, degrees from south)
# to heading, we have to deal with a few cases
def getsolarheading():
        Azimuth = Pysolar.GetAzimuth(maplat, maplon, datetime.datetime.utcnow())
        if Azimuth < 0:
                if (Azimuth >= -180):
                        solarheading = ((Azimuth * -1) + 180)
                if (Azimuth < -180):
                        solarheading = ((Azimuth * -1) - 180)
        if Azimuth >= 0:
                solarheading = Azimuth
        return solarheading


def tomorrow_heading():
        increment_min = 1
        incrementeddatetime = 0
        tomorrow_corrected = 90
        if Pysolar.GetAltitude(maplat, maplon, datetime.datetime.utcnow()) < 0:
                while Pysolar.GetAltitude(maplat, maplon, (datetime.datetime.utcnow() + datetime.timedelta(minutes=incrementeddatetime))) < 0:
                        incrementeddatetime = incrementeddatetime + increment_min
                sunrise_time=(datetime.datetime.utcnow() + datetime.timedelta(minutes=incrementeddatetime))
                tomorrow_heading = Pysolar.GetAzimuth(maplat, maplon, sunrise_time)
                if tomorrow_heading < 0:
                        if (tomorrow_heading >= -180):
                                tomorrow_corrected = ((tomorrow_heading * -1) + 180)
                        if (tomorrow_heading < -180):
                                tomorrow_corrected = ((tomorrow_heading * -1) - 180)
                if tomorrow_heading >= 0:
                        tomorrow_corrected = tomorrow_heading
        return tomorrow_corrected

def getsolarangle():
        solarangle = Pysolar.GetAltitude(maplat, maplon, datetime.datetime.utcnow())
        return solarangle

def motor2neg():
    global motor2speed
    if (motor2speed < motor2max_speed):
        motor2speed = motor2speed + 5
    motors.motor2.setSpeed((motor2speed*-1))
    return

def motor2backup():
        motor2speed = 0
        backupsecs = 4
        backup_start_time = datetime.datetime.utcnow()
        while   (datetime.datetime.utcnow() < (backup_start_time + datetime.timedelta(seconds=backupsecs))):
                while motor2speed < motor2max_speed:
                        motor2speed = motor2speed + 1
#Backup
#Doesn't do anything right now
        return

def motor2pos():
    global motor2speed
    if (motor2speed < motor2max_speed):
        motor2speed = motor2speed + 5
    motors.motor2.setSpeed(motor2speed)
    return

def motor1raise():
    global motor1speed
    if (motor1speed < motor1max_speed):
        motor1speed = motor1speed + 5
        #raise the panel from the horizon
        #reverse motor speed extends the actuator
    motors.motor1.setSpeed((motor1speed*-1))
    return

def motor1lower():
    global motor1speed
    if (motor1speed < motor1max_speed):
        motor1speed = motor1speed + 5
        #lower the panel to the horizon
        #forward motor speed contracts the actuator
    motors.motor1.setSpeed(motor1speed)
    return

tomorrow_static = tomorrow_heading()
#Here we check to make sure horizon (19) and ovveride (16) digital pins aren't on
#print("GPIO 16 (ovveride) is " + str(GPIO.input(16)))
#print("GPIO 19 (horizon) is " + str(GPIO.input(19)))
#print(GPIO.input(19))
if (GPIO.input(16) == False) and (GPIO.input(19) == False): #check to see if the passive mode switch is on
# GPIO 16 is for override and GPIO 19 is for horizon mode

#In this section we rotate as needed
    starttime = datetime.datetime.utcnow()
    if (getcurheading() > getsolarheading()) and (getsolarangle() > 2) and (getcurheading() <> 999):
        while (getcurheading() > (getsolarheading() + hmargin)) and (starttime + datetime.timedelta(seconds=pan_time_limit) > datetime.datetime.utcnow()):
            if debug == True:
                print("1: Moving " + str(getcurheading()) + " to " + str(getsolarheading()))
            motor2neg()
        motors.setSpeeds(0, 0)

    starttime = datetime.datetime.utcnow()
    if (getcurheading() < getsolarheading()) and (getsolarangle() > 2) and (getcurheading() <> 999):
        while (getcurheading() < (getsolarheading() - hmargin)) and (starttime + datetime.timedelta(seconds=pan_time_limit) > datetime.datetime.utcnow()):
            if debug == True:
                print("2: Moving " + str(getcurheading()) + " to " + str(getsolarheading()))
            motor2pos()
        motors.setSpeeds(0, 0)

    starttime = datetime.datetime.utcnow()
    if (getcurheading() > tomorrow_static) and (getsolarangle()<0) and (getcurheading() <> 999):
        if (getcurheading() - tomorrow_static) > sleep_tolerance:
            while (getcurheading() > (tomorrow_static + hmargin)) and (starttime + datetime.timedelta(seconds=pan_time_limit) > datetime.datetime.utcnow()):
                if debug == True:
                    print("3: Moving " + str(getcurheading()) + " to " + str(tomorrow_static + hmargin))
                motor2neg()
            motors.setSpeeds(0, 0)

    starttime = datetime.datetime.utcnow()
    if (getcurheading() < tomorrow_static) and (getsolarangle()<0) and (getcurheading <> 999):
        if (tomorrow_static - getcurheading()) > sleep_tolerance:
            while (getcurheading() < (tomorrow_static - hmargin)) and (starttime + datetime.timedelta(seconds=pan_time_limit) > datetime.datetime.utcnow()):
                if debug == True:
                    print("4: Moving " + str(getcurheading()) + " to " + str(tomorrow_static + hmargin))
                motor2pos()
            motors.setSpeeds(0, 0)

#In this section we angle the panels as needed
    starttime = datetime.datetime.utcnow()
    if (getcurangle() < getsolarangle()) and (getsolarangle() > lowestangle):
        print("Case 5")
        while (getcurangle() < getsolarangle()) and (starttime + datetime.timedelta(seconds=tilt_time_limit) > datetime.datetime.utcnow()):
            if debug == True:
                print("5: Moving " + str(getcurangle()) + " to " + str(getsolarangle()))
            motor1raise()
        motors.setSpeeds(0, 0)

    if (getcurangle() > getsolarangle()):
        while (getcurangle() > getsolarangle()) and (getsolarangle() > lowestangle) and (starttime + datetime.timedelta(seconds=tilt_time_limit) > datetime.datetime.utcnow()):
            if debug == True:
                print("6: Moving " + str(getcurangle()) + " to " + str(getsolarangle()))
            motor1lower()
        motors.setSpeeds(0, 0)

#This is horizon mode- if the GPIO switch for pin 19 is flipped
#we lower the panel to 20 degrees. This is good for installing the solar panel,
#since it keeps the robot from moving any more while we're working on it
if (GPIO.input(19) == True) and (GPIO.input(16) == False):
    while (getcurangle() > 20):
        motor1lower()
    motors.setSpeeds(0, 0)

#update the databases
os.system('/usr/bin/rrdtool update /tools/sensors/corrected_azimuth_db.rrd --template corr_az N:' + str(getsolarheading()))
os.system('/usr/bin/rrdtool update /tools/sensors/elevation_db.rrd --template elev N:' + str(getsolarangle()))
os.system('/usr/bin/rrdtool update /tools/sensors/actual_elevation_db.rrd --template elev N:' + str(getcurangle()))
os.system('/usr/bin/rrdtool update /tools/sensors/actual_heading_db.rrd --template corr_az N:' + str(getcurheading()))

#update the azimuth graph
os.system('/usr/bin/rrdtool graph /var/www/azimuth_graph.png \
-w 600 -h 120 -a PNG \
--slope-mode \
--start -86400 --end now \
--font DEFAULT:7: \
--title \x22heading in degrees\x22 \
--watermark \x22`date`\x22 \
--vertical-label \x22degrees\x22 \
--right-axis-label \x22 \x22 \
--lower-limit 0 \
--right-axis 1:0 \
--x-grid MINUTE:10:HOUR:1:MINUTE:120:0:%R \
--alt-y-grid --rigid \
DEF:azimuth=/tools/sensors/corrected_azimuth_db.rrd:corr_az:MAX \
DEF:heading=/tools/sensors/actual_heading_db.rrd:corr_az:MAX \
LINE1:azimuth\x23707070:\x22Calculated\x22:dashes \
LINE1:heading\x230000FF:\x22Actual\x22 \
GPRINT:azimuth:LAST:\x22Cur Calc\: %5.2lf\x22 \
GPRINT:heading:LAST:\x22Cur Actual\: %5.2lf\x22 \
GPRINT:azimuth:AVERAGE:\x22Avg\: %5.2lf\x22 \
GPRINT:azimuth:MAX:\x22Max\: %5.2lf\x22 \
GPRINT:azimuth:MIN:\x22Min\: %5.2lf\t\t\t\x22 >/dev/null')

#update the elevation graph
os.system('/usr/bin/rrdtool graph /var/www/elevation_graph.png \
-w 600 -h 120 -a PNG \
--slope-mode \
--start -86400 --end now \
--font DEFAULT:7: \
--title \x22angle in degrees\x22 \
--watermark \x22`date`\x22 \
--vertical-label \x22degrees\x22 \
--right-axis-label \x22 \x22 \
--lower-limit -50 \
--right-axis 1:0 \
--x-grid MINUTE:10:HOUR:1:MINUTE:120:0:%R \
--alt-y-grid --rigid \
DEF:calculated=/tools/sensors/elevation_db.rrd:elev:MAX \
DEF:actual=/tools/sensors/actual_elevation_db.rrd:elev:MAX \
LINE1:calculated\x23707070:\x22Calculated\x22:dashes \
LINE1:actual\x230000FF:\x22Actual\x22 \
GPRINT:calculated:LAST:\x22Cur Calc\: %5.2lf\x22 \
GPRINT:actual:LAST:\x22Cur Actual\: %5.2lf\x22 \
GPRINT:calculated:AVERAGE:\x22Avg\: %5.2lf\x22 \
GPRINT:calculated:MAX:\x22Max\: %5.2lf\x22 \
GPRINT:calculated:MIN:\x22Min\: %5.2lf\t\t\t\x22 >/dev/null')

#Update the solar file for reporting
logsolar = open('/tools/inputs/solarvalues.txt','w')
writeline=("[myvars]\n")
logsolar.write(writeline)
writeline=("solar_heading: " + str(round((float(getsolarheading())),1)) + "\n")
logsolar.write(writeline)
writeline=("solar_elevation: " + str(round((float(getsolarangle())),1))+ "\n")
logsolar.write(writeline)
writeline=("actual_elevation: " + str(round((float(getcurangle())),1))+ "\n")
logsolar.write(writeline)
writeline=("actual_heading: " + str(round((float(getcurheading())),1))+ "\n")
logsolar.write(writeline)
logsolar.close()


#Create the index.html page
loghtml = open('/var/www/index.html','w')
writeline=("<font size=\x222\x22 face=\x22verdana\x22>\n")
loghtml.write(writeline)
writeline=("<head><meta http-equiv=\x22refresh\x22 content=\x2260\x22></head> \n")
loghtml.write(writeline)
writeline=("<link rel=\x22shortcut icon\x22 href=\x22/favicon.ico\x22/> \n")
loghtml.write(writeline)
writeline=("<link rel=\x22apple-touch-icon\x22 href=\x22apple-icon.png\x22/> \n \
<link rel=\x22apple-touch-icon\x22 sizes=\x2272x72\x22 href=\x22apple-icon-72x72.png\x22/> \n \
<link rel=\x22apple-touch-icon\x22 sizes=\x22114x114\x22 href=\x22apple-icon-114x114.png\x22/> \n \
<link rel=\x22apple-touch-icon\x22 sizes=\x22120x120\x22 href=\x22apple-icon-120x120.png\x22/> \n \
<link rel=\x22apple-touch-icon\x22 sizes=\x22144x144\x22 href=\x22apple-icon-144x144.png\x22/> \n \
<link rel=\x22apple-touch-icon\x22 sizes=\x22152x152\x22 href=\x22apple-icon-152x152.png\x22/> \n \
<link rel=\x22apple-touch-icon\x22 sizes=\x22180x180\x22 href=\x22apple-icon-180x180.png\x22/> \n")
loghtml.write(writeline)
writeline=("<link rel=\x22shortcut icon\x22 type=\x22image/x-icon\x22 href=\x22/favicon.ico\x22/> \n")
loghtml.write(writeline)
writeline=("<title>Solar Robot</title> \n")
loghtml.write(writeline)
writeline =("<font face=\x22helvetica\x22> \n")
loghtml.write(writeline)
writeline =("<link rel=\x22apple-touch-icon\x22 href=/icon_114.png\x22 /> \n")
loghtml.write(writeline)
writeline =("<table style=\x22undefined;table-layout: fixed; width: 387px\x22> \n<colgroup> \n<col style=\x22width: 160px\x22> \n<col style=\x22width: 240px\x22> \n </colgroup> \n")
loghtml.write(writeline)
writeline =("<tr> \n <td><a href=\x22/config/inputs.html\x22>Change Settings</a></td> \n    <td><a href=\x22/debug-solar.csv\x22>Debug Log CSV</a></td> \n  </tr> \n")
loghtml.write(writeline)
writeline =("<tr> \n <td>Date Time</td> \n    <td>" + str(datetime.datetime.now()) + "</td> \n  </tr> \n")
loghtml.write(writeline)
writeline =("<tr> \n    <td>Raw Azimuth</td> \n    <td>" + str(getrawazimuth()) + "</td> \n  </tr> \n  <tr> \n    <td>Calculated Heading</td> \n    <td>" + str(getsolarheading()) + "</td> \n")
loghtml.write(writeline)
writeline =("  </tr> \n  <tr> \n    <td>Actual Heading</td> \n    <td>" + str(getcurheading()) + "</td> \n  </tr> \n")
loghtml.write(writeline)
writeline = ("  <tr> \n    <td>Calculated Angle</td> \n    <td>" + str(getsolarangle()) + "</td> \n  </tr> \n")
loghtml.write(writeline)
writeline = ("  <tr> \n    <td>Current Angle</td> \n    <td>" + str(getcurangle()) + "</td> \n  </tr> \n</table>")
loghtml.write(writeline)
writeline =("<br></br> \n")
loghtml.write(writeline)
# we add the temp graph to the html but generate the image in the other script
writeline =("<img src=\x22internal_temp_graph.png\x22 alt=\x22[internal_temp_graph]\x22><br></br> \n")
loghtml.write(writeline)
writeline =("<img src=\x22azimuth_graph.png\x22 alt=\x22[elevation_graph]\x22><br></br> \n")
loghtml.write(writeline)
writeline =("<img src=\x22elevation_graph.png\x22 alt=\x22[elevation_graph]\x22><br></br></font> \n")
loghtml.write(writeline)
loghtml.close()
#print (datetime.datetime.now(), ",", getrawazimuth(), ",", getsolarheading(), ",", getcurheading(), ",", getsolarangle(),",", getcurangle(),",",tomorrow_static)
print (datetime.datetime.now(), ",", getrawazimuth(), ",", getsolarheading(), ",", getcurheading(), ",", getsolarangle(),",", getcurangle())

motors.setSpeeds(0, 0)
motors.disable()
serialport.close()
