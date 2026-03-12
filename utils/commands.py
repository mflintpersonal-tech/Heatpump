#!/usr/bin/env python3
#
# Periodic job to execute commands placed on the remote Redis queue
#

from datetime import datetime
import json
import redis
import sys
import traceback

import heat_pump
import pump_value as pv
from monitor_log import log

parameters = pv.Pump.load_parameters()

log.info("Looking for new commands.")

redis_remote = redis.Redis(host = "192.168.1.150", decode_responses = True)

updates = {}

msg = True
while msg:
    msg = redis_remote.lpop(pv.Pump.COMMAND_QUEUE)

    if msg:
        try:
            cmd = json.loads(msg)
            id = int(cmd['id'])
            log.info(f"Received command {cmd['id']} to set parameter {cmd['parameter']} to {cmd['value']}.")
            now = int(datetime.now().timestamp())
            updates[id] = [cmd['parameter'], int(cmd['value'])]
            redis_remote.lpush(pv.Pump.COMMAND_QUEUED, cmd['id'])
        except Exception as ex:
            print("Remote redis command fetch failed", file=sys.stderr)
            print(ex, file=sys.stderr)
            traceback.print_exc()
            redis_remote.rpush(pv.Pump.COMMAND_QUEUE, msg)
            msg = False

### some form of tidyup needed if falure - the gathered command need re-adding to remote queue if possible

if len(updates) > 0:

    # Set these parameter values
    interface = heat_pump.HeatPump()

    changes = list((a[0], a[1]) for a in updates.values())
    print(changes)
    interface.write_values(changes)
    now = int(datetime.now().timestamp())
    
    for a in updates.values():
        log.info(f"- set parameter {a[0]} to {a[1]}")

    for id in updates.keys():
        # how can it fail????
        msg = ':'.join([id, str(now), 'true'])
        redis_remote.rpush(pv.Pump.COMMAND_RESULTS, msg)

redis_remote.close()
        
#log.info("Updates completed.")
