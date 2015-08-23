#!/usr/bin/env python

import cgi
import cgitb

cgitb.enable()

f = open( '/tools/inputs/masterinputs.txt', 'w' )
f.write('[myvars]\n' )

print "Content-type: text/html\n\n"

form=cgi.FieldStorage()

if "maplat" not in form:
        f.write('maplat: 33.123135\n' )
        print "<h1>No value entered, going with 33.000001</h1>"
else:
        text=form["maplat"].value
        print "<h1>Robot latitude is:</h1>"
        print text
        f.write('maplat: ' +text + '\n' )

if "maplon" not in form:
        f.write('maplon: -117.224479\n' )
        print "<h1>No value entered, going with -117.000001</h1>"
else:
        text=form["maplon"].value
        print "<h1>Robot longitude is:</h1>"
        print text
        f.write('maplon: ' +text + '\n' )

if "pan_time_limit" not in form:
        f.write('pan_time_limit: 15\n' )
        print "<h1>No value entered, going with 15</h1>"
else:
        text=form["pan_time_limit"].value
        print "<h1>Max pan time (seconds) is:</h1>"
        print text
        f.write('pan_time_limit: ' +text + '\n' )

if "tilt_time_limit" not in form:
        f.write('tilt_time_limit: 30\n' )
        print "<h1>No value entered, going with 30</h1>"
else:
        text=form["tilt_time_limit"].value
        print "<h1>Tilt time limit is:</h1>"
        print text
        f.write('tilt_time_limit: ' +text + '\n' )

if "lowestangle" not in form:
        f.write('lowestangle: 15\n' )
        print "<h1>No value entered, going with 15</h1>"
else:
        text=form["lowestangle"].value
        print "<h1>Lowest tilt angle from horizon is:</h1>"
        print text
        f.write('lowestangle: ' +text + '\n' )

if "motor1max_speed" not in form:
        f.write('motor1max_speed: 20\n' )
        print "<h1>No value entered, going with 20</h1>"
else:
        text=form["motor1max_speed"].value
        print "<h1>Max motor 1 speed is:</h1>"
        print text
        f.write('motor1max_speed: ' +text + '\n' )

if "motor2max_speed" not in form:
        f.write('motor2max_speed: 20\n' )
        print "<h1>No value entered, going with 20</h1>"
else:
        text=form["motor2max_speed"].value
        print "<h1>Max motor 2 speed is:</h1>"
        print text
        f.write('motor2max_speed: ' +text + '\n' )

if "sleep_tolerance" not in form:
        f.write('sleep_tolerance: 5\n' )
        print "<h1>No value entered, going with 12</h1>"
else:
        text=form["sleep_tolerance"].value
        print "<h1>Sleep tolerance is:</h1>"
        print text
        f.write('sleep_tolerance: ' +text + '\n' )

if "AngleOffset" not in form:
        f.write('AngleOffset: 9\n' )
        print "<h1>No value entered, going with 9</h1>"
else:
        text=form["AngleOffset"].value
        print "<h1>Angle calibration offset is:</h1>"
        print text
        f.write('AngleOffset: ' +text + '\n' )

if "MagneticDeclination" not in form:
        f.write('MagneticDeclination: -11.8333\n' )
        print "<h1>No value entered, going with -11.8333</h1>"
else:
        text=form["MagneticDeclination"].value
        print "<h1>Magnetic declination is:</h1>"
        print text
        f.write('MagneticDeclination: ' +text + '\n' )

if "HorizontalCalibration" not in form:
        f.write('HorizontalCalibration: 9\n' )
        print "<h1>No value entered, going with 9</h1>"
else:
        text=form["HorizontalCalibration"].value
        print "<h1>Horizontal calibration is:</h1>"
        print text
        f.write('HorizontalCalibration: ' +text + '\n' )

if "hmargin" not in form:
        f.write('hmargin: 9\n' )
        print "<h1>No value entered, going with 9</h1>"
else:
        text=form["hmargin"].value
        print "<h1>Horizontal margin is:</h1>"
        print text
        f.write('hmargin: ' +text + '\n' )

        f.close()
