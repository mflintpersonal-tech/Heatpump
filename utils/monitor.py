#!/usr/bin/ruby
#
# Periodic job to query pump's parameters as set in monitor.yaml
#

from datetime import datetime
import json
import redis
import sys
import traceback
import yaml

import current_temp
import heat_pump
import pump_value as pv
from monitor_log import log

parameters = pv.Pump.load_parameters()

log.info("Monitor starting.")

interface = heat_pump.HeatPump()
now = int(datetime.now().timestamp())

values = {}
for type in ['input', 'holding', 'coil']:

    parms = [id for id, vals in parameters.items() if (vals['type'] == type) and (vals['monitor'] == 'Y')]

    # reading a range is more efficient than 1 by 1
    if len(parms) > 0:
        values.update(interface.read_range(parms, type))

log.info(f"Monitor has gathered data with key {now}.")

# add in zero values for the 'extra' parameters

parms = [id for id, vals in parameters.items() if (vals['type'] == 'extra')]

for prm in parms:
    pump_value = pv.Pump(prm)
    pump_value.set_value(0)
    values[prm] = pump_value

# override some parameters (just locally) to include values from indoor temperature sensors

with open("thermometers.yaml", "r") as file:
    thermometers = yaml.safe_load(file.read())

for key, v in thermometers.items():
    h = current_temp.govee_details(key)

    if (datetime.now().astimezone() - h['time']).seconds > 240:
        raise RuntimeWarning("Temperature values are too old")
    
    values[v['temperature']].set_value(h['temperature'])
    if 'humidity' in v:
        values[v['humidity']].set_value(h['humidity'])

# Write parameter and real value to Redis with key of current time

with redis.Redis() as r:
    key = f"{pv.Pump.MONITOR_STORE}:{now}"
    vals = list([k, v.real_value] for k,v in values.items())
    r.set(key, json.dumps(vals))

    # log the key of latest created set of data
    r.set(pv.Pump.LAST_CREATED, now)

    #### Possibly TEMP ... mirror to other database
    r.rpush('REMOTE:QUEUE', '***'.join([key, json.dumps(vals)]))
    r.rpush('REMOTE:QUEUE', '***'.join([pv.Pump.LAST_CREATED, str(now)]))

redis_remote = redis.Redis(host = "192.168.1.150")
redis_local =  redis.Redis(decode_responses = True)

msg = True
while msg:
    msg = redis_local.lpop('REMOTE:QUEUE')

    if msg:
        try:
            k, v = msg.split('***', 2)
            redis_remote.set(k, v)
            log.info(f"Placed data for {k} on remote Redis server.")
        except Exception as ex:
            print("Remote redis data SET failed", file=sys.stderr)
            print(ex, file=sys.stderr)
            traceback.print_exc()
            redis_local.rpush('REMOTE:QUEUE', msg)
            msg = False

redis_remote.close()
redis_local.close()
