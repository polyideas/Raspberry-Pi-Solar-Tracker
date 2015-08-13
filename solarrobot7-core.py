#!/usr/bin/python

#Version Notes
#23: 	Fixed Azimuth calculations in tomorrow calculations to match standard calculation
#	Simplified curheading calc into fewer lines
#24:	Attempted to fix tomorrow calc by consolidating if/then statements
#	Removed temp sensor stuff after shorting out the sensor
#25:	Added sensor code back in
#26:	Added lines for actual readings of heading and elevation to the rrdtool graphs
#27:	Cleanup of the angle code to fix horizon issues and addition of the analog chart
#28:	Moved modprobe stuff for temp to rc.local, moved serial from usb to onboard ttyAMA0
#	Tweaked names in the html output
#29:	Clean up html and image generation for the combo graph (used by the twitter script)
#30:	Added digital IO controls for passive mode, removed temp code and put it in its own script
#	Removed digital IO controls
#31:	Added digiital IO control backs and tested with GPIO 16.
#	Added motor limit code so that rotation motor doesn't run longer than 30 seconds
#32:	Added limit code for tilt
#33:	**************************************
#	Moving motor code to new platform, changed motor motion for linear actuator to match the motor
#34:	Added calibration routines
#	Added/fixed manual switches for ovveride (sleep) mode and horizon (setup) modes	
#35:	Cleaned up old code comments
#36:	Added code for backup, which runs the panning motor backwards for 4 seconds at dusk- this
#	keeps the robot from getting stuck near magnetic north, which can confuse the robot
#37:	Moved variables to config file, allowing for web based control
#38:	Cleaned up old comments and motor control code- motors now ramp correctly

from __future__ import print_function
import time, math
import serial, Pysolar, datetime

#digital stuff
import RPi.GPIO as GPIO

#support for storing our values in a config file
import ConfigParser

# for the motor control we need the libraries for this controller:
from SmartDrive import SmartDrive
SmartDrive = SmartDrive()

import os, sys

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

#prep the digital ports
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(16, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) #this pin is for the override mode switch
GPIO.setup(19, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) #this pin is for horizon mode, on=do no motor movement at all

#These are our global motor speed variables- don't touch
global motor1speed
motor1speed = 0
global motor2speed
motor2speed = 0

#Open the serial port for the IMU
serialport = serial.Serial("/dev/ttyAMA0", 57600, timeout=5)

#Make sure the motors aren't doing anything before we start
SmartDrive.SmartDrive_Stop(SmartDrive.SmartDrive_Motor_1, SmartDrive.SmartDrive_Next_Action_Brake)
SmartDrive.SmartDrive_Stop(SmartDrive.SmartDrive_Motor_2, SmartDrive.SmartDrive_Next_Action_Brake)

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
#	print(headresponse)
        words = headresponse.split(",")
	if len(words) > 2:
		try:
		        curheading = (float(words[0])) + 180
			if curheading + Declination > 360: curheading = curheading - 360 + Declination
			else: curheading = curheading + Declination
		except:
			curheading = 999
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
	        motor2speed = motor2speed + 1
#	print(getcurheading())
#	print("Motor speed clockwise")
	SmartDrive.SmartDrive_Run_Unlimited(SmartDrive.SmartDrive_Motor_2, SmartDrive.SmartDrive_Direction_Reverse, motor2speed)
	return

def motor2backup():
	motor2speed = 0
	backupsecs = 4
	backup_start_time = datetime.datetime.utcnow()
	while 	(datetime.datetime.utcnow() < (backup_start_time + datetime.timedelta(seconds=backupsecs))): 
	        while motor2speed < motor2max_speed:
        	        motor2speed = motor2speed + 1
	print(getcurheading())
	print("Backup")
#			SmartDrive.SmartDrive_Run_Unlimited(SmartDrive.SmartDrive_Motor_2, SmartDrive.SmartDrive_Direction_Reverse, motor2speed)
#		SmartDrive.SmartDrive_Stop(SmartDrive.SmartDrive_Motor_2, SmartDrive.SmartDrive_Next_Action_Brake)
	return

def motor2pos():
	global motor2speed
	if (motor2speed < motor2max_speed):
	        motor2speed = motor2speed + 1
		SmartDrive.SmartDrive_Run_Unlimited(SmartDrive.SmartDrive_Motor_2, SmartDrive.SmartDrive_Direction_Forward, motor2speed)
#	print(getcurheading())
#	print(motor2speed)
#	print("Motor speed clockwise")
	return

def motor1raise():
	global motor1speed
	if (motor1speed < motor1max_speed):
	        motor1speed = motor1speed + 1
	#raise the panel from the horizon
	#forward motor speed extends the actuator
        SmartDrive.SmartDrive_Run_Unlimited(SmartDrive.SmartDrive_Motor_1, SmartDrive.SmartDrive_Direction_Forward, motor1speed)
	return

def motor1lower():
	global motor1speed
	if (motor1speed < motor1max_speed):
	        motor1speed = motor1speed + 1
	#lower the panel to the horizon
	#reverse motor speed extends the actuator
        SmartDrive.SmartDrive_Run_Unlimited(SmartDrive.SmartDrive_Motor_1, SmartDrive.SmartDrive_Direction_Reverse, motor1speed)
	return

tomorrow_static = tomorrow_heading()
#Here we check to make sure horizon (19) and ovveride (16) digital pins aren't on
print("GPIO 16 (ovveride) is " + str(GPIO.input(16)))
print("GPIO 19 (horizon) is " + str(GPIO.input(19)))
#print(GPIO.input(19))
if (GPIO.input(16) == False) and (GPIO.input(19) == False): #check to see if the passive mode switch is on
# GPIO 16 is for override and GPIO 19 is for horizon mode

#In this section we rotate as needed
	starttime = datetime.datetime.utcnow()

        if (getcurheading() > getsolarheading()) and (getsolarangle() > 2) and getcurheading() <> 999:
		print("Case 1")
		while (getcurheading() > (getsolarheading() + hmargin)) and (starttime + datetime.timedelta(seconds=pan_time_limit) > datetime.datetime.utcnow()):
                	motor2neg()
		SmartDrive.SmartDrive_Stop(SmartDrive.SmartDrive_Motor_2, SmartDrive.SmartDrive_Next_Action_Brake)
	starttime = datetime.datetime.utcnow()

        if (getcurheading() < getsolarheading()) and (getsolarangle() > 2) and (getcurheading() <> 999):
		print("Case 2")
                while (getcurheading() < (getsolarheading() - hmargin)) and (starttime + datetime.timedelta(seconds=pan_time_limit) > datetime.datetime.utcnow()):
			motor2pos()
		SmartDrive.SmartDrive_Stop(SmartDrive.SmartDrive_Motor_2, SmartDrive.SmartDrive_Next_Action_Brake)
	starttime = datetime.datetime.utcnow()

	if (getcurheading() > tomorrow_static) and (getsolarangle()<0) and (getcurheading() <> 999):
		print("Case 3")
		if (getcurheading() - tomorrow_static) > sleep_tolerance:
#			if getcurheading() > 345:
#				motor2backup()
#			if getcurheading() < 0:
#				motor2backup()
               		while (getcurheading() > (tomorrow_static + hmargin)) and (starttime + datetime.timedelta(seconds=pan_time_limit) > datetime.datetime.utcnow()):
                       		motor2neg()
			SmartDrive.SmartDrive_Stop(SmartDrive.SmartDrive_Motor_2, SmartDrive.SmartDrive_Next_Action_Brake)
	starttime = datetime.datetime.utcnow()
        if (getcurheading() < tomorrow_static) and (getsolarangle()<0) and (getcurheading <> 999):
		print("Case 4")
		if (tomorrow_static - getcurheading()) > sleep_tolerance:
			if getcurheading() < 15:
				motor2backup()
               		while (getcurheading() < (tomorrow_static - hmargin)) and (starttime + datetime.timedelta(seconds=pan_time_limit) > datetime.datetime.utcnow()):
				motor2pos()
			SmartDrive.SmartDrive_Stop(SmartDrive.SmartDrive_Motor_2, SmartDrive.SmartDrive_Next_Action_Brake)

#In this section we angle the panels as needed
	starttime = datetime.datetime.utcnow()
        if (getcurangle() < getsolarangle()) and (getsolarangle() > lowestangle):# and (getcurangle() <> 999):
                while (getcurangle() < getsolarangle()) and (starttime + datetime.timedelta(seconds=tilt_time_limit) > datetime.datetime.utcnow()):
			motor1raise()
		SmartDrive.SmartDrive_Stop(SmartDrive.SmartDrive_Motor_1, SmartDrive.SmartDrive_Next_Action_Brake)

        if (getcurangle() > getsolarangle()):# and (getcurangle() <> 999):
                while (getcurangle() > getsolarangle()) and (getsolarangle() > lowestangle) and (starttime + datetime.timedelta(seconds=tilt_time_limit) > datetime.datetime.utcnow()):
			motor1lower()
		SmartDrive.SmartDrive_Stop(SmartDrive.SmartDrive_Motor_1, SmartDrive.SmartDrive_Next_Action_Brake)

#This is horizon mode- if the GPIO switch for pin 19 is flipped
#we lower the panel to 20 degrees. This is good for installing the solar panel,
#since it keeps the robot from moving any more while we're working on it
if (GPIO.input(19) == True) and (GPIO.input(16) == False):
	while (getcurangle() > 20):
        	motor1lower()
	SmartDrive.SmartDrive_Stop(SmartDrive.SmartDrive_Motor_1, SmartDrive.SmartDrive_Next_Action_Brake)

#update the databases
os.system('/usr/bin/rrdtool update /tools/sensors/corrected_azimuth_db.rrd --template corr_az N:' + str(getsolarheading()))
os.system('/usr/bin/rrdtool update /tools/sensors/elevation_db.rrd --template elev N:' + str(getsolarangle()))
os.system('/usr/bin/rrdtool update /tools/sensors/actual_elevation_db.rrd --template elev N:' + str(getcurangle()))
os.system('/usr/bin/rrdtool update /tools/sensors/actual_heading_db.rrd --template corr_az N:' + str(getcurheading()))

#update the azimuth graph
os.system('/usr/bin/rrdtool graph /var/www/azimuth_graph.png \
-w 785 -h 120 -a PNG \
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
-w 785 -h 120 -a PNG \
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

#Update the log files for power monitoring
logwatts = open('/tools/inputs/wattvalue.txt','w')
writeline=("[myvars]\n")
logwatts.write(writeline)
try:
	batt_volts = str(round((SmartDrive.GetBattVoltage()/1000),2))
except ValueError:
	#no battery reading is evil!
	batt_volts = 6.66
writeline=("batt_volts: " + batt_volts + "\n")
logwatts.write(writeline)
logwatts.close()

#Update the solar file for reporting
logwatts = open('/tools/inputs/solarvalues.txt','w')
writeline=("[myvars]\n")
logwatts.write(writeline)
writeline=("heading: " + str(round((float(getsolarheading())),1)) + "\n")
logwatts.write(writeline)
writeline=("elevation: " + str(round((float(getsolarangle())),1))+ "\n")
logwatts.write(writeline)
logwatts.close()


#Create the stats.html page
loghtml = open('/var/www/stats.html','w')
writeline=("<font size=\x222\x22 face=\x22verdana\x22>\n")
loghtml.write(writeline)
writeline=("<head><meta http-equiv=\x22refresh\x22 content=\x2260\x22></head> \n")
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
writeline =("<a href=\x22/config/inputs.html\x22>Change Settings</a><br></br> \n")
loghtml.write(writeline)
writeline =("<a href=\x22/debug-solar.csv\x22>Debug Log CSV</a><br></br> \n")
loghtml.write(writeline)
writeline =("<table style=\x22undefined;table-layout: fixed; width: 387px\x22> \n<colgroup> \n<col style=\x22width: 160px\x22> \n<col style=\x22width: 240px\x22> \n </colgroup> \n")
loghtml.write(writeline)
writeline =("<tr> \n <td>Date Time</td> \n    <td>" + str(datetime.datetime.now()) + "</td> \n  </tr> \n")
loghtml.write(writeline)
writeline =("<tr> \n    <td>Raw Azimuth</td> \n    <td>" + str(getrawazimuth()) + "</td> \n  </tr> \n  <tr> \n    <td>Calculated Heading</td> \n    <td>" + str(getsolarheading()) + "</td> \n")
loghtml.write(writeline)
writeline =("  </tr> \n  <tr> \n    <td>Actual Heading</td> \n    <td>" + str(getcurheading()) + "</td> \n  </tr> \n")
loghtml.write(writeline)
writeline = ("  <tr> \n    <td>Calculated Angle</td> \n    <td>" + str(getsolarangle()) + "</td> \n  </tr> \n")
loghtml.write(writeline)
writeline = ("  <tr> \n    <td>Battery Voltage</td> \n    <td>" + batt_volts + "</td> \n  </tr> \n</table>")
loghtml.write(writeline)
writeline =("<br></br> \n")
loghtml.write(writeline)
# we add the temp graph to the html but generate the image in the other script
writeline =("<img src=\x22combo_temp_graph.png\x22 alt=\x22[combo_temp_graph]\x22><br></br> \n")
loghtml.write(writeline)
writeline =("<img src=\x22azimuth_graph.png\x22 alt=\x22[elevation_graph]\x22><br></br> \n")
loghtml.write(writeline)
writeline =("<img src=\x22elevation_graph.png\x22 alt=\x22[elevation_graph]\x22><br></br></font> \n")
loghtml.write(writeline)
writeline =("<img src=\x22battery.png\x22 alt=\x22[battery_graph]\x22><br></br></font> \n")
loghtml.write(writeline)
writeline =("<img src=\x22analog7_graph.png\x22 alt=\x22[analog7_graph]\x22><br></br></font> \n")
loghtml.write(writeline)
loghtml.close()
print (datetime.datetime.now(), ",", getrawazimuth(), ",", getsolarheading(), ",", getcurheading(), ",", getsolarangle(),",0,", getcurangle(), ",", str(SmartDrive.GetBattVoltage()/1000),",",tomorrow_static)
serialport.close()
