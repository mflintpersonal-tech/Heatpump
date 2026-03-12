#!/usr/bin/env python3
#
# Backup controller for CH if there's a communication issue.
#
# During Holiday periods, every hour we send the current timestamp to the Shelly CH controller.
# If connection is lost, then the value does not get to the Shelly device, and it has two scripts
# which gather current temperature, and sets the heating on, if the timestamp it holds is out of date
# (implying that communication is not possible, so it's in charge).
# The WC curve is also enabled to ensure we don't run on whatever fixed value was last set by the
# thermistor. It's turned off again outside of 'holiday'.
#
# This process runs hourly, and sends the timestamp, and starts the scripts on the Shelly during holidays.
# There's a gap on the morning where this might fail, and the scripts are not started. That's life.

from datetime import datetime
import json
import redis

from app import app
from app.control_settings import ControlSettings
from app.current_value import CurrentValue
from app.device_control import DeviceControl
from app.notifications import Notifications

# sets WC on or off i.e. parameter 21 00 to 1 or 0
def set_wcc(onoff):
    set_to = 1 if (onoff == 'on') else 0
    wc = CurrentValue(ControlSettings.PARAMETER_WC_ENABLED)
    v, tim = wc.fetch()
    if int(v) == set_to:
        log.info(f"WC curve is already {onoff} so not doing anything to it.")
    else:
        wc.set(set_to, by_command=True)     # force the update now
        log.info(f"WC curve turned {onoff}.")

# checks config for any disabled device and warns if they are
def check_devices():
    for device in app.config['DEVICES'].values():
        if ('disabled' in device) and device['disabled']:
            msg = "Warning - some devices are disabled. This is probably wrong during a holiday period."
            log.info(msg)
            Notifications().send(['email','alexa'], 'Devices disabled', rate = 60 * 60)

from app import monitor_log
log = monitor_log.loggr

# See if we're on holiday
hols = False
active = False
with redis.Redis(decode_responses = True) as r:
    hols = r.get("Schedule:Holiday")
    active = r.get("Backup:Running")

hols = not (hols == 'False')
active = not (active == 'False')

device = DeviceControl('ZONE1')

##hols = True

if not hols:
    if active:
        # Stop the scripts on the device
        device.stop_script('1')
        device.stop_script('2')
        with redis.Redis(decode_responses = True) as r:
            r.set("Backup:Running", 'False')
        log.info("Backup CH Controller scripts stopped")
        set_wcc('off')
    raise SystemExit()

now = datetime.now().timestamp()

# Set the current time on the Shelly device
device.kvs('set', 'pulse_time', value=str(int(now)))
log.info(f"Sent timestamp of {int(now)} to Backup CH Controller.")

if not active:
    # Enable the scripts on the device
    device.start_script('1')
    device.start_script('2')
    log.info("Backup CH Controller scripts started")
    set_wcc('on')
    with redis.Redis(decode_responses = True) as r:
        r.set("Backup:Running", 'True')
    Notifications().send(['email','alexa'], 'Backup Controller Activated', f"Backup Central Heating Controller scripts started.")
    check_devices()

    # Also, kill the upstairs Pi4 nicely.
    import os
    os.system('ssh mike@192.168.1.151 "/var/www/sleep/build_killme.sh"')
