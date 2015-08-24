#!/usr/bin/python

# Simple example of sending and receiving values from Adafruit IO with the REST
# API client.
# Original Author: Tony DiCola
# Updated for some additional capability- read values from files to prevent race conditions on I2C and serial port value readings

# Import Adafruit IO REST client.
from Adafruit_IO import Client
from uptime import uptime
import os, sys
import ConfigParser

#Calculate the server uptime
uptimehrs = round((uptime()*0.000277778), 2)
if uptimehrs > 24:
        uptimemod = uptimehrs%24
        uptimedays = int(uptimehrs / 24)
        if uptimedays > 1:
                daystr = ' days, '
        else:
                daystr = ' day, '
        uptimestr = str(uptimedays) + daystr +str(uptimemod) + ' hours'
if uptimehrs <= 24:
        uptimestr = str(uptimehrs) + ' hours'

#read in all our variables
config2 = ConfigParser.ConfigParser()
config2.read("/tools/inputs/tempvalues.txt")
temp_int = float(config2.get("myvars", "temp_int"))

config3 = ConfigParser.ConfigParser()
config3.read("/tools/inputs/solarvalues.txt")
solar_heading = float(config3.get("myvars", "solar_heading"))
solar_elevation = float(config3.get("myvars", "solar_elevation"))
actual_heading = float(config3.get("myvars", "actual_heading"))
actual_elevation = float(config3.get("myvars", "actual_elevation"))


# Set to your Adafruit IO key.
ADAFRUIT_IO_KEY = 'your_adafruit_io_key_here'

# Create an instance of the REST client.
aio = Client(ADAFRUIT_IO_KEY)

# Send a value to the feed 'Test'.  This will create the feed if it doesn't
# exist already.
aio.send('your-robot-heading', actual_heading)
aio.send('your-robot-elevation', actual_elevation)
aio.send('your-robot-solar-heading', solar_heading)
aio.send('your-robot-solar-elevation', solar_elevation)
aio.send('your-robot-temp_int', temp_int)
aio.send('your-robot-uptimehrs', uptimehrs)


