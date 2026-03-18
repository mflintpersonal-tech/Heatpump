#!/usr/bin/env python3

#
# Take the latest set of monitor data and convert it to individual items
# If a monitored item doesn't change value, stop monitoriing it!
#

from datetime import datetime, timezone
import json
import redis
import sys
import time
import traceback

#import config
from app.pump_value import Pump
from app.query_mysql import Heatpump_db

from app import monitor_log
log = monitor_log.loggr

CONTROL_LATEST = '99999'

# First thing to do is record the results of any commands that have executed - can happen right away

log.info("Checking for any completed commands.")

results = {}

with redis.Redis(decode_responses = True) as r:

    dbh = Heatpump_db()

    msg = True
    while msg:
        msg = r.lpop(Pump.COMMAND_RESULTS)

        if msg:
            try:
                id, tim, res, err = msg.split(':', 3)
                res = int(res)
                dtime = datetime.fromtimestamp(int(tim))

                message = f"Received result for command {id}, executed at {dtime}. Result = {res}/{err}."
                log.info(message)

                # update the database command table with result
                dbh.update_commands(id, res, dtime, err)

                # report on any errors
                if int(res) >= 10:
                    Notifications().send(['email'], 'Command Execution Failure', message, urgent=True)

            except Exception as ex:
                print("Command result update failed", file=sys.stderr)
                print(ex, file=sys.stderr)
                traceback.print_exc()
                r.rpush(Pump.COMMAND_RESULTS, msg)
                msg = False

    msg = True
    while msg:
        msg = r.lpop(Pump.COMMAND_QUEUED)

        if msg:
            log.info(f"Pulled id {msg} from Queued queue")
            id = msg
            # check to see status is currently just 'added' and if it is, then set to 'queued'
            # (it might already have a result, in which case, queued status is skipped
            #if dbh.update_command_queued(id): log.info(f"Command {id}, is now queued for execution.")
            xy = dbh.update_command_queued(id)
            log.info(f"Result of update for command {id} is {xy}")
            if xy: log.info(f"Command {id}, is now queued for execution.")

# Runs every 5 minutes, but give delay to get latest data here
time.sleep(15)

log.info("Converting monitor data to monitor elements")

# Take list of latest monitor logs and add into the database proper

dbh = Heatpump_db()

# Grab all the new data we've received

to_delete = []
with redis.Redis(decode_responses = True) as r:
    # TODO Latest must not be deleted as needed in thermistor - check why!!
    latest = r.get(Pump.LAST_CREATED)

    for item in r.scan_iter(match = 'HeatPump:Monitor' + ':*'):

        data = r.get(item)
        key = item.split(':')[-1]

        # record the data in database

        log.info(f"Adding data with key {key} into database")
        dbh.insert_monitor_data(int(key), data)

        if key != latest: to_delete.append(item)
        #to_delete.append(item)

    # remove the keys we've uploaded
    if len(to_delete) > 0: r.delete(*to_delete)

# All new data now in database. Proceed to conversion

# Grab all un-converted monitor_data records

parameters = Pump.load_parameters()      # load up all parameter details

new_data = dbh.fetch_unconverted()       # fetch unconverted rows

monitored_parms = []
control_parms = []
r = redis.Redis()
for item in new_data:

    #time = datetime.fromtimestamp(item['created_key'])
    time = datetime.fromtimestamp(item['created_key'], tz=timezone.utc)

    # record the actual created_key against the 'time' (down to HHMM) to match up with later database updates of local monitor values
    r.set(Pump.CREATED_KEY + time.strftime('%Y%m%d%H%M'), item['created_key'], ex = 4*60*60)

    parms = json.loads(item['data'])

    # Hack really just to isolate the Control parameter values (which only come through a few times a day)

    if parameters[parms[0][0]]['monitor'] == 'C':  # if the first parameter is a Control one, they all will be
        control_parms.append(item)                 # store it for now
        continue                                   # and skip this record

    for parameter, value in parms:
        #dbh.insert_monitor(parameter, str(time), value)
        dbh.insert_monitor(parameter, time, value)

    dbh.update_monitor_data(item['created_key'], 'Y')      # now converted
    log.info(f"Added converted monitor data for {time} to database")

# For control parameters, don't record an un-changed value; just amend the 'latest' time

if len(control_parms) > 0:
    log.info("Recording Control parameters")
    print(control_parms)

    latest = datetime(2000,1,1,tzinfo=timezone.utc)
    for item in control_parms:

        #time = datetime.fromtimestamp(item['created_key'])
        time = datetime.fromtimestamp(item['created_key'], tz=timezone.utc)

        parms = json.loads(item['data'])

        for parameter, value in parms:
            last_value = dbh.control_value(parameter)
            if last_value is None:
                dbh.insert_control(parameter, time, value)
            elif last_value != value:
                log.info(f"- value for parameter {parameter} has changed from {last_value} to {value}.")
                dbh.insert_control(parameter, time, value)

        latest = max([latest, time])

        dbh.update_monitor_data(item['created_key'], 'Y')    # now converted

    dbh.update_control(CONTROL_LATEST, 9999, time)

log.info("Conversion complete.")
