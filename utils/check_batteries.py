#!/usr/bin/env python3

#
# Routine reports when batteries are low
#

import yaml

import app.current_temp as ct
from app.notifications import Notifications

# fetch (local) thermometer details
with open("./app/thermometers.yaml", "r") as file:
    thermometers = yaml.safe_load(file.read())

for key in thermometers.keys():
    if thermometers[key]['type'] != 'parameter':
        values = ct.Current_Temperature().details(key)
        if values['battery'] < 15:
            message = f"Battery is very low on the thermometer in the {thermometers[key]['name']}. Please replace when convenient. "
            Notifications().send(['email','alexa'], 'Low Battery Warning', message, urgent=True)

#### VERY TEMP STUFF TODO

import redis
from datetime import datetime
with redis.Redis(db=15, decode_responses = True) as r:
    battery = r.hget('BLIND:BATTERY', datetime.now().strftime('%Y-%m-%d'))
    if battery and (int(battery) < 50):
        message = f"Battery is less than 50 on the blinds"
        Notifications().send(['email','alexa'], 'Low Battery Warning', message)

