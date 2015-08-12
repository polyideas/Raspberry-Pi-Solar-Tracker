#!/usr/bin/python
# Modified version of tweetpic.py
# by Alex Eames http://raspi.tv/?p=5918
# Modified to post rrdtool graphs and tweet the uptime of the Raspberry Pi
# Modified by Jay Doscher http://polyideas.com

import tweepy
from subprocess import call
from datetime import datetime
from uptime import uptime
import os, sys, glob
import ConfigParser

base_dir = '/sys/bus/w1/devices/'
device1_folder = glob.glob(base_dir + '28-0000065e925b')[0]
device2_folder = glob.glob(base_dir + '28-0000068d9fc0')[0]
device1_file = device1_folder + '/w1_slave'
device2_file = device2_folder + '/w1_slave'

def read_temp1_raw():
    f = open(device1_file, 'r')
    lines = f.readlines()
    f.close()
    return lines

def read_temp2_raw():
    f = open(device2_file, 'r')
    lines = f.readlines()
    f.close()
    return lines

def read_temp1():
    lines = read_temp1_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp1_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        return temp_f

def read_temp2():
    lines = read_temp2_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp2_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        return temp_f

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

# Consumer keys and access tokens, used for OAuth
consumer_key = 'your-consumer-key-here'
consumer_secret = 'your-consumer-secret-here'
access_token = 'your-access-token-here'
access_token_secret = 'your-access-token-secret-here'

# OAuth process, using the keys and tokens
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)

# Creation of the actual interface, using authentication
api = tweepy.API(auth)


config0 = ConfigParser.ConfigParser()
config0.read("/tools/inputs/tweetschedule.txt")
schedule_int = float(config0.get("myvars", "schedule_int"))

#Power Graph Tweet
if (schedule_int==1):
        print("1")
        #read in battery values
        config1 = ConfigParser.ConfigParser()
        config1.read("/tools/inputs/auxvalues.txt")
        batt_amps = float(config1.get("myvars", "batt_amps"))
        batt_watts = float(config1.get("myvars", "batt_watts"))
        config2 = ConfigParser.ConfigParser()
        config2.read("/tools/inputs/wattvalue.txt")
        batt_volts = float(config2.get("myvars", "batt_volts"))
        # Send the tweet with photo
        photo1_path = '/var/www/battery.png'
        status1 = 'Up ' +  uptimestr + ', battery:' + str(batt_volts) + 'V, system drawing ' + str(batt_watts) + 'W. Current power graph: \x23solar \x23robot \x23IoT'
        api.update_with_media(photo1_path, status=status1)
        schedule = open('/tools/inputs/tweetschedule.txt','w')
        writeline=("[myvars]\n")
        schedule.write(writeline)
        writeline=("schedule_int: 2\n")
        schedule.write(writeline)
        schedule.close()
        exit(0)
# Temperature Graph Tweet
if (schedule_int==2):
        print("2")
        #read in battery values
        config3 = ConfigParser.ConfigParser()
        config3.read("/tools/inputs/tempvalues.txt")
        temp_int = float(config3.get("myvars", "temp_int"))
        temp_ext = float(config3.get("myvars", "temp_ext"))
        # Send the tweet with photo
        photo1_path = '/var/www/combo_temp_graph.png'
        status1 = 'Up ' +  uptimestr + ', compute chassis temp ' + str(temp_int) + u'\u00b0' +', battery box ' + str(temp_ext) + u'\u00b0' + '. Current temperature graph: \x23solar \x23robot \x23IoT'
        api.update_with_media(photo1_path, status=status1)
        schedule = open('/tools/inputs/tweetschedule.txt','w')
        writeline=("[myvars]\n")
        schedule.write(writeline)
        writeline=("schedule_int: 3\n")
        schedule.write(writeline)
        schedule.close()
        exit(0)

# Solar Heading Tweet
if (schedule_int==3):
        print("3")
        #read in heading values
        config4 = ConfigParser.ConfigParser()
        config4.read("/tools/inputs/solarvalues.txt")
        heading = float(config4.get("myvars", "actual_heading"))
        elevation = float(config4.get("myvars", "actual_elevation"))
        # Send the tweet with photo
        photo1_path = '/var/www/azimuth_graph.png'
        status1 = 'Up ' +  uptimestr + ', current solar heading is  ' + str(heading) + u'\u00b0'  + '. Current heading graph: \x23solar \x23robot \x23IoT'
        api.update_with_media(photo1_path, status=status1)
        schedule = open('/tools/inputs/tweetschedule.txt','w')
        writeline=("[myvars]\n")
        schedule.write(writeline)
        writeline=("schedule_int: 4\n")
        schedule.write(writeline)
        schedule.close()
        exit(0)
# Solar Elevation Tweet
if (schedule_int==4):
        print("4")
        #read in elevation values
        config4 = ConfigParser.ConfigParser()
        config4.read("/tools/inputs/solarvalues.txt")
        heading = float(config4.get("myvars", "actual_heading"))
        elevation = float(config4.get("myvars", "actual_elevation"))
        # Send the tweet with photo
        photo1_path = '/var/www/elevation_graph.png'
        status1 = 'Up ' +  uptimestr + ', current solar elevation is  ' + str(elevation) + u'\u00b0'  + '. Current elevation graph: \x23solar \x23robot \x23IoT'
        api.update_with_media(photo1_path, status=status1)
        schedule = open('/tools/inputs/tweetschedule.txt','w')
        writeline=("[myvars]\n")
        schedule.write(writeline)
        writeline=("schedule_int: 1\n")
        schedule.write(writeline)
        schedule.close()
        exit(0)