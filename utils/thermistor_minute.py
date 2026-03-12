#!/usr/bin/env python3

#
# This routine determines if the heating should be on, and sets the LWT (Leaving Water Temperature) 
# for the heat pump
#

from datetime import datetime, timedelta
import json
import redis
import time

from app.control_settings import ControlSettings
from app.heating_schedule import Schedule
from app.pump_value import Pump

from . display import MiniDisplay

from app import monitor_log
log = monitor_log.loggr
log.basicConfig(filename='/var/log/thermistor.log', format=monitor_log.FORMAT, force=True)
###import sys
###log.basicConfig(stream=sys.stdout, format=monitor_log.FORMAT, force=True)

log.info("Thermistor starting.")

RUN_EVERY = 1                          # run every 1 minute
DELAY_SECONDS = 45
INTERVAL_TIME = 60 * RUN_EVERY

def delay_for(interval):
    now = datetime.now()
    mins = (int(now.minute / interval) + 1) * interval       # next multiple of RUN_EVERY
    delay = (mins - now.minute) + 1                          # plus 1 minute e.g. 10:23 -> run at 10:26; 9:05 -> 9:06
    delay = (delay * 60) - now.second
    delay = delay + DELAY_SECONDS                            # shift into the minute a little
    log.info(f"Sleep for {delay} seconds.")
    time.sleep(delay)

# ---------------------------------------------------- #
# Start-up : Delay to run on multiple of 5 minutes + 1 #
# ---------------------------------------------------- #

delay_for(RUN_EVERY)

# --------------------------------------------------- #
# Step 1 : Collect current heat parameters from Grant #
# --------------------------------------------------- #

# Two zones

zones = ['1','2']
num_zones = len(zones)

schedule = Schedule()
display = MiniDisplay()

# --------------------------------------- #
# Step 2 : Determine heating requirements #
# --------------------------------------- #

heating = False
old_heating = heating
last_target = 0

controls = {}

shown_calc = {}
target_reached = {}
last_target = {}
targets = {}
for zone in zones:
    controls[zone] = ControlSettings(zone=zone)
    shown_calc[zone] = False
    target_reached[zone] = False
    last_target[zone] = 0

set_lwt = 0
set_new_lwt = 0
while True:
    starttime = time.monotonic()

    lwt = {}
    new_lwt = {}
    required = ''

    for zone in zones:
        now = datetime.now()
        target = schedule.find_target(now, zone=zone)

        if target != last_target[zone]:
            target_reached[zone] = False
            last_target[zone] = target

        ### controls.current_temperature is some amalgamted function; gathered at most every NN seconds - cache in class
        log.info(f"Zone {zone}: Target temperature is {target}; current control temperature is {controls[zone].current_temperature()}")
        #log.info "Target had been reached at #{controls.target_reached_time}" if controls.target_reached?

        if not shown_calc[zone]: log.info(f"Zone {zone}: LWT is calculated as External Temp * {controls[zone].gradient} + {controls[zone].konstant}")
        shown_calc[zone] = True

        # TODO incorporate boost option ... should that just set a high target? Yes.

        tt = controls[zone].current_temperature()

        if tt >= target:
            log.info(f"Zone {zone}: Target reached.")
            target_reached[zone] = True

        if not heating and target_reached: tt += controls[zone].hysterisis()

        # Calculate these values always, even if not needed
        lwt[zone] = controls[zone].find_lwt()
        new_lwt[zone] = controls[zone].modulated_lwt(target)

        if tt < target:
            target_reached[zone] = False

            log.info(f"Zone {zone}: Heating is required")
            log.info(f"Zone {zone}: Target:{target}. Temp right now = {controls[zone].current_temperature()}. LWT is {lwt[zone]}.")
            log.info(f"Zone {zone}: modulated LWT is {new_lwt[zone]}")

            required = required + zone

    if required != '':
        heating = True
        if heating is not old_heating: log.info("Turning heating on")
        if required == '2':
            set_lwt = lwt['2'] 
            set_new_lwt = new_lwt['2']
        else:
            set_lwt = lwt['1'] 
            set_new_lwt = new_lwt['1']

        ### ... at this point do smooth takeover of heating controls ###
        ### turn heating on if heating != old_heating
        log.info(f"Setting LWT (21 01) to {set_new_lwt}")
        # 21 00 = 1 to enable wc; = 0 for fixed

    else:
        heating = False
        if heating is not old_heating: log.info("Turning heating off")
        set_lwt = lwt['1']
        set_new_lwt = new_lwt['1']

    targets[zone] = target

    ## TEMP :: record entries on Redis within 'last key' :
    ##         01 11 = Target temp
    ##         99 08 = LWT calculated
    ##         99 09 = LWT modulated

    with redis.Redis(decode_responses = True) as r:
        last_monitor = r.get(Pump.LAST_CREATED)
        key = f"{Pump.MONITOR_STORE}:{last_monitor}"
        values = json.loads(r.get(key))
        values.append(['01 11', target['1']])  ### should this be append?  Modify Parameters to make a 'Control' maybe????
        values.append(['01 12', target['2']])    ### should this be append?  Modify Parameters to make a 'Control' maybe????
        values.append(['99 08', set_lwt])
        values.append(['99 09', set_new_lwt])
        r.set(key, json.dumps(values))
        r.set(Pump.PREVIOUS_STORE, json.dumps(values))

        # TEMP:  FIXME
        r.set('Schedule:Heating', 'on') if heating else r.set('Schedule:Heating', 'off')
        r.set('Schedule:Zones', required)
        r.set('Schedule:Target', target['1'])
        r.set('Schedule:Target:1', target['1'])
        r.set('Schedule:Target:2', target['2'])

    if heating is not old_heating:
        display.message('Heating On') if heating else display.clear_screen()

    old_heating = heating

    time.sleep(INTERVAL_TIME - ((time.monotonic() - starttime) % INTERVAL_TIME))
