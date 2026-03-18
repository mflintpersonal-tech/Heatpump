#!/usr/bin/env python3

#
# This routine determines if the heating should be on, and sets the LWT (Leaving Water Temperature) 
# for the heat pump
#

from datetime import datetime, timedelta, timezone
import json
import redis
import time
import yaml

from app.control_settings import ControlSettings
from app.controller import Controller
from app.current_temp import Current_Temperature
from app.ch_controls import CH_Controls
from app.current_value import CurrentValue
from app.device_control import DeviceControl
from app.dhw_controls import DHW_Controls
from app.heating_schedule import Schedule
from app.notifications import Notifications
from app.pump_value import Pump
from app.query_mysql import Heatpump_db

from . display import MiniDisplay

from app import monitor_log
log = monitor_log.loggr
log.basicConfig(filename='/var/log/thermistor.log', format=monitor_log.FORMAT, force=True)
#log.basicConfig(filename='/var/log/thermistor.log', level=log.DEBUG, format=monitor_log.FORMAT, force=True)
##import sys
##log.basicConfig(stream=sys.stdout, level=log.DEBUG, format=monitor_log.FORMAT, force=True)

log.info("Thermistor starting.")

RUN_EVERY = 1                          # run every 1 minute
DELAY_SECONDS = 45
INTERVAL_TIME = 60 * RUN_EVERY

#USE_MODULATED = False                  # whether LWT will be set to the modulatd, or standard WCC calculated value
USE_MODULATED = True        # set on 1/12/25

COLD_TEMP = 160     # limit for lowest indoor temp - maybe place elsewhere?
HIGH_HUMID = 700    # 70% humidity is too high

def delay_for(interval):
    now = datetime.now()
    mins = (int(now.minute / interval) + 1) * interval       # next multiple of RUN_EVERY
    #delay = (mins - now.minute) + 1                          # plus 1 minute e.g. 10:23 -> run at 10:26; 9:05 -> 9:06
    delay = (mins - now.minute)                              # plus 1 minute e.g. 10:23 -> run at 10:26; 9:05 -> 9:06
    delay = (delay * 60) - now.second
    delay = delay + DELAY_SECONDS                            # shift into the minute a little
    log.info(f"Sleep for {delay} seconds.")
    time.sleep(delay)

# --------------------------------------------------- #
# Start-up : Delay to run on multiple of <n> minutes  #
# --------------------------------------------------- #

delay_for(RUN_EVERY)

# fetch (local) thermometer details - include only Switchbot ones
with open("./app/thermometers.yaml", "r") as file:
    therms = yaml.safe_load(file.read())
thermometers = dict((k, v) for k,v in therms.items() if v['type'] == 'switchbot')   # only Pi4 grabs Switchbot thermometers
indoors = list(v for v in therms.values() if v['location'] == 'inside')
indoors_temps = list(CurrentValue(v['temperature']) for v in indoors)
indoors_humids = list(CurrentValue(v['humidity']) for v in indoors if 'humidity' in v)

# fetch probe details
with open("./app/probes.yaml", "r") as file:
    probs = yaml.safe_load(file.read())
probes = dict((k, v) for k,v in probs.items() if v['monitor'])

hp_lwt = CurrentValue(ControlSettings.PARAMETER_FIXED_LWT)   # the "current value" of Heat Pump LWT fixed value

dbh = Heatpump_db()

# --------------------------------------------------- #
# Step 1 : Collect current heat parameters from Grant #
# --------------------------------------------------- #

# Two zones

zones = ['1','2']
num_zones = len(zones)

schedule = Schedule()
display = MiniDisplay()
controller = Controller()

# --------------------------------------- #
# Step 2 : Determine heating requirements #
# --------------------------------------- #

heating = False
old_heating = heating
last_target = 0

controls = {}                       # Dictionary of CH_Controls, key = zone in zones

# By zone dictionaries...
shown_calc = {}                     # - have we shown the WC calculation yet?
targets = {}                        # - current temperature target for zone
now_lwt = {}                        # - the LWT value to set

for zone in zones:
    shown_calc[zone] = False

# Most things are "per zone" but an LWT can only be "per heat pump" so there's only one (like Highlander)
set_lwt = 0                         # this is the calculated LWT based on WC curve
set_new_lwt = 0                     # this is the modulated LWT taking into account IAT
last_lwt = None

# pre-load the zone details for CH zones
for zone in zones:
    cs = ControlSettings(zone=zone)
    ch_control = CH_Controls(zone, cs, log=log)
    controls[zone] = ch_control

controller.set_mode(Controller.MODE_DHW) # mode: either 'CH' or 'DHW'; only 1 can happen at a time
hw_control = DHW_Controls(controls[zones[0]].hp_controls, controller, log=log)     # passes in controls for Zone 1 (or first zone)
while True:
    now = datetime.now()
    now_utc = datetime.now(tz=timezone.utc)

    hw_control.check_boost()        # Handle any DHW boost that's running
    # TODO what about DHW boost during daily DHW phase?

    required = ''                   # Which zones require heat? e.g. "12" => both zones; "1" => only zone 1

    # DHW has precedence over CH

    controller.set_mode(Controller.MODE_DHW)

    if hw_target := controller.hot_water_demand(now):           # the return value is the target DHW temp
        controller.set_mode(Controller.MODE_DHW, target=hw_target)
        hw_control.set_target()
        log.info(f"DHW phase = {hw_control.phase}")
        hw_control.phase_action()
        #if hw_control.phase == 99:
        #changed on 29/1/25
        if (hw_control.phase == 0) or (hw_control.phase > 80):
            controller.set_mode(Controller.MODE_CH)     # HW done with - let CH happen
            if hw_control.phase >= 90:
                controller.clear_dhw_activity()
        else:
            # IF statement added 30/1/25
            if (hw_control.phase > 20) and (hw_control.phase < 85):
                controller.set_dhw_activity()
    else:
        if controller.dhw_activity:
            # tidy-up and shutdown any DHW heating that's going on
            if (hw_control.phase > 0):
                if hw_control.phase < 80:
                    hw_control.set_phase(80)
                hw_control.phase_action()
                # changed 28/1/25 to add line below!
                controller.set_mode(Controller.MODE_CH)
            elif (hw_control.phase == 0) or (hw_control.phase > 80):
                controller.set_mode(Controller.MODE_CH)
        else:
            controller.set_mode(Controller.MODE_CH)

    log.info(f"Mode = {controller.mode}.")

    if controller.central_heating_mode():
        controller.resetDHW()

    #
    # Central Heating (we do the calculations even if DHW is 'active')
    #

    for zone in zones:
        target, holiday = schedule.find_target(now, zone=zone)

        ch_control = controls[zone]      # for convenience!

        #### lots of this ought to be in the Controller class which doesn't seem to be doing a great deal!!!!

        # re-fetch control settings 4 times an hour
        if (now.minute % 15) == 0:
            ch_control.set_control(ControlSettings(zone=zone))
            shown_calc[zone] = False

        ch_control.set_target(target)

        ch_control.target_changed()

        ### maybe could use current_values class ??????
        log.info(f"Zone {zone}: Target temperature is {ch_control.target}; current control temperature is {ch_control.hp_controls.current_temperature()}")

        if not shown_calc[zone]: log.info(f"Zone {zone}: LWT is calculated as External Temp * {ch_control.hp_controls.gradient} + {ch_control.hp_controls.konstant}")
        shown_calc[zone] = True

        # TODO incorporate boost option ... should that just set a high target? Yes.

        temp = ch_control.hp_controls.current_temperature()

        if temp >= ch_control.target:
            log.info(f"Zone {zone}: Target reached.")
            ch_control.target_reached = True

        # add hysterisis value if the target has not been reached before (i.e. we're in a rising temperature situation)
        if not heating and ch_control.target_reached: temp += (ch_control.hp_controls.hysterisis() - 1)
        #                                                                      it's -1 as we trigger at hysterisis, not below(!)
        log.debug(f"ZONE{zone} target_reached = {ch_control.target_reached}")

        # Calculate these LWT values always, even if not needed to record in monitor data
        ch_control.lwt = ch_control.hp_controls.find_lwt()
        ch_control.new_lwt = ch_control.hp_controls.modulated_lwt(ch_control.target)

        # now_lwt is the LWT to set, either the default or modulated one
        now_lwt[zone] = ch_control.new_lwt if USE_MODULATED else ch_control.lwt
        log.debug(f"ZONE{zone} now_lwt = {now_lwt[zone]}  ch_control.new_lwt = {ch_control.new_lwt} lwt = {ch_control.lwt} ")

        # TODO - maybe move this into the 'required' if below????
        # amend the LWT targets if we're cooling down from an DHW period
        log.debug(f"**** hw.control_phase = {hw_control.phase} ")
        if hw_control.phase == 85:
            log.debug(f"**** hw.control_phase = {hw_control.phase} :: hw_control.dhw_ch_lwt = {hw_control.dhw_ch_lwt}; lwt = {now_lwt[zone]}")
            if hw_control.dhw_ch_lwt < now_lwt[zone]:
                # cool enough - end the DHW phase entirely now
                hw_control.dhw_ch_lwt = False
            else:
                ch_control.lwt = hw_control.dhw_ch_lwt
                ch_control.new_lwt = hw_control.dhw_ch_lwt
                now_lwt[zone] = ch_control.new_lwt if USE_MODULATED else ch_control.lwt
                log.info(f"Target LWT adjusted to {ch_control.lwt} to utilise energy from DHW phase.")
                # last_lwt must be different to what we want it to be; setting it 0.5C below ensures it gets set correctly to desired LWT
                last_lwt = ch_control.lwt - 5
                log.debug(f"Last LWT is {last_lwt} in DHW phase 85.")

        if temp < ch_control.target:
            ch_control.target_reached = False

            log.info(f"Zone {zone}: Heating is required")
            log.info(f"Zone {zone}: Target:{ch_control.target}. Temp right now = {ch_control.hp_controls.current_temperature()}. LWT is {ch_control.lwt}.")
            log.info(f"Zone {zone}: modulated LWT is {ch_control.new_lwt}")
            log.debug(f"ZONE{zone} now_lwt = {now_lwt[zone]}  ch_control.new_lwt = {ch_control.new_lwt} lwt = {ch_control.lwt} ")

            required = required + zone

        targets[zone] = ch_control.target

    # Zone calculations complete - see what needs doing

    if (required != '') and controller.central_heating_mode():
        log.debug(f"**** required = {required} ")
        log.debug(f"Zone1LWT = {now_lwt['1']}. Zone2LWT = {now_lwt['2']}. last_lwt = {last_lwt} ")
        heating = True
        if heating is not old_heating: log.info("Turning heating on")

        # if only Zone 2, use zone 2 figures; else use zone 1

        zone = '2' if (required == '2') else '1'

        # switch on appropriate circuits
        off_zones = list(zones)
        for z in required:
            controls[z].set_ch('on')
            off_zones.remove(z)
        # (and turn off the others)
        for z in off_zones:
            controls[z].set_ch('off')

        set_lwt = controls[zone].lwt
        set_new_lwt = controls[zone].new_lwt
        log.debug(f"**** >>>>>>>>>>>>>>>> 2 values s/be the same! ZONE {zone} :: lwt = {controls[zone].lwt} now_lwt = {now_lwt[zone]} ")

        # s/be no longer needed as we get the real last value in hp_lwt in Stage 0.
        #if not last_lwt: last_lwt = now_lwt - 5     # if this is 1st time thru, set a last lwt to 0.5C below this one

        # The setting of 21 01 parameter only has effect if '21 00' = 0 (i.e. disable WCC)
        # So if WCC is ENABLED, these commands have no effect, but are done anyway.
        # The setting of WCC (21 00) is done outside of this module, as it's not a "now and then" decision
        # 21 00 = 1 to enable wc; = 0 for fixed

        if not last_lwt:
            # NOTE: we can't just retrieve it every time, as a command to update the LWT might take several minutes to execute so
            #       we'd end up sending duplicate commands for no good reason.
            last_lwt, last_time = hp_lwt.fetch()        # last LWT on the HP
            log.info(f"Retrieved last LWT from HP as first run. LWT = {last_lwt} at {last_time}.")

        if last_lwt == now_lwt[zone]:
            log.info(f"LWT (21 01) is currently set to {now_lwt[zone]} - no change required")
            log.debug(f"Last LWT is {last_lwt} after 'they are the same' code")
        else:
            # rather than going directly to the new LWT, move toward it, maximum of 2.0 degree at a time
            delta = min([abs(last_lwt - now_lwt[zone]), 20])
            log.debug(f"**** last_lwt = {last_lwt} delta = {delta} ")
            now_lwt[zone] = (last_lwt + delta) if now_lwt[zone] > last_lwt else (last_lwt - delta)
            log.info(f"Setting LWT (21 01) to {now_lwt[zone]}")
            hp_lwt.set(now_lwt[zone], by_command=True)
            last_lwt = now_lwt[zone]
            log.debug(f"Last LWT is {last_lwt} after set LWT command")

        # This line moved to the above else clause on 7/11/25 .... suspicion we might be holding a very out of date one - see 7/11/25 data!
        #last_lwt = now_lwt[zone]

    elif controller.hot_water_mode() and not ( (hw_control.phase == 0) or (hw_control.phase > 80) ):
                                                            # 'and' added 1/2/25  --- FIXME Should be a method of dhw_control
        set_lwt = hw_control.hw_set_lwt                     # in DHW mode, there's a fixed LWT to note
        set_new_lwt = hw_control.hw_set_lwt

    else:
        heating = False
        if heating is not old_heating:
          log.info("Turning heating off")
        for z in zones:
            controls[z].set_ch('off')
        set_lwt = controls['1'].lwt      # this is TEMP as the actual controls might be wanting heating
        set_new_lwt = controls['1'].new_lwt

    # test here if any indoor thermometer drops below COLD_TEMP

    i = 0
    for therm in indoors_temps:
        if therm.fetch()[0] < COLD_TEMP:
            message = f"Indoor temperature in the {indoors[i]['name']} has dropped below {int(COLD_TEMP/10)} degrees - please investigate."
            log.warning(message)
            Notifications().send(['alexa'], 'Indoor Temperature Alert', message, rate=60*60, urgent=True)
        i += 1

    i = 0
    for indoor_therm in indoors:
        if 'humidity' in indoor_therm.keys():
            if indoors_humids[i].fetch()[0] > HIGH_HUMID:
                message = f"Indoor humidity exceeds {int(HIGH_HUMID/10)} percent in the {indoor_therm['name']} - please investigate."
                log.warning(message)
                Notifications().send(['alexa'], 'Indoor Humidity Alert', message, urgent=True, rate=15*60)
            i += 1

    # Add new parameter values (e.g. thermometer or LWT) go to 'pending_values': key = YYYYMMDDHHMM + parm;

    # 01 11 = Target temp (zone 1)
    # 01 12 = Target temp (zone 2)
    # 99 08 = LWT calculated
    # 99 09 = LWT modulated
    # ...plus any thermometers only grabbed by Pi4

    hhmm = now_utc.strftime('%Y%m%d%H%M')
    dbh.insert_pending(hhmm, '01 11', targets['1'])
    dbh.insert_pending(hhmm, '01 12', targets['2'])
    dbh.insert_pending(hhmm, '99 08', set_lwt)
    dbh.insert_pending(hhmm, '99 09', set_new_lwt)
    for k, v in thermometers.items():
        h = Current_Temperature().details(k)
        dbh.insert_pending(hhmm, v['temperature'], h['temperature'])
        if 'humidity' in v: dbh.insert_pending(hhmm, v['humidity'], h['humidity'])

    # Now, include the temperature probes attached to Shelly1Plus

    for probe, vals in probes.items():
        probe = DeviceControl(probe)
        if tc := probe.get_status():                    # if we got it, use it
            v = float(tc['tC']) * 10
            v += 0      ## hack to draw value up to room thermometer      +6 for PROBE1
        else:           ## could use 'adjust' value at this point?        +4 for PROBE2?
            v = CurrentValue(vals['temperature']).fetch()[0]        # else, use the last good value
        dbh.insert_pending(hhmm, vals['temperature'], int(v))

    with redis.Redis(decode_responses = True) as r:

        # TEMP:  FIXME
        r.set('Schedule:Heating', 'on') if heating else r.set('Schedule:Heating', 'off')
        r.set('Schedule:Zones', required)
        r.set('Schedule:Target', targets['1'])
        r.set('Schedule:Target:1', targets['1'])
        r.set('Schedule:Target:2', targets['2'])
        r.set('Schedule:Holiday', str(holiday))

        # Now, read all the data in the 'pending_values' table table, and use date key part to read redis HeatPump:Created_Key
        # to obtain the "real" created_key value, then write the value to the 'monitor' table using that "real" created_key
        # If there's no hit in redis leave on 'pending_values'; if hit, delete from 'pending_values'

        finished_keys = set()           # set of created_keys
        for row in dbh.fetch_pending():
            # created, parameter, value
            if real_key := r.get(Pump.CREATED_KEY + row['created']):
                # found genuine key; add to real monitor table
                real_time = datetime.fromtimestamp(int(real_key))
                dbh.insert_monitor(row['parameter'], str(real_time), row['value'])
                # and delete row from table
                dbh.delete_pending(row['created'], row['parameter'])
                #log.debug(f"Inserted value of {row['value']} for {row['parameter']} for key {real_key}")
                finished_keys.add(real_time)

        if len(finished_keys) > 0:
            log.info(f"Going to re-build monitor_data for keys {finished_keys}.")
            for key in finished_keys:
                dbh.rebuild_monitor_data(key)

    if heating is not old_heating:
        # Don't display anything for now - waste of energy!
        # display.message('Heating On') if heating else display.clear_screen()
        display.clear_screen()

    old_heating = heating

    wait_for = (INTERVAL_TIME - datetime.now().second + DELAY_SECONDS) % INTERVAL_TIME
    if wait_for == 0: wait_for = INTERVAL_TIME
    time.sleep(wait_for)
