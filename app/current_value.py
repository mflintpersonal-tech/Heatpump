#!/usr/bin/env python3
#
# Heat Pump values
#

from datetime import datetime

import json
import redis

from . commands import Commands
from . pump_value import Pump
from . query_mysql import Heatpump_db

class CurrentValue:

    def __init__(self, id):
        self.id = id
        self.real_value = None

        self.pump_value = Pump(id)

    # returns the latest value, and what time it relates to (as datetime object)
    def fetch(self):

        with redis.Redis(decode_responses = True) as r:
            last_monitor = r.get(Pump.LAST_CREATED)
            key = f"{Pump.MONITOR_STORE}:{last_monitor}"
            ## values = dict(json.loads(r.get(key)))
            ## above line occasionally fails; not sure why so...
            values = r.get(key)
            if not values:
                print(f"{datetime.now()} key = {key} - no values returned.")
            else:
                values = dict(json.loads(r.get(key)))

            if self.id in values:
                self.pump_value.set_value(values[self.id])
                self.set_at = datetime.fromtimestamp(int(last_monitor))
                self.source = 'redis'
            else:
                dbh = Heatpump_db()
                val, tim = dbh.current_value(self.id, with_time=True)
                if val or (val == 0):
                    self.pump_value.set_value(val)
                    #self.set_at = datetime.strptime(tim, '%Y-%m-%d %H:%M:%S')
                    self.set_at = tim
                    self.source = 'db_cur'
                elif self.pump_value.is_control():
                    val, tim = dbh.control_value(self.id, with_time=True)
                    self.pump_value.set_value(val)
                    #self.set_at = datetime.strptime(tim, '%Y-%m-%d %H:%M:%S')
                    self.set_at = tim
                    self.source = 'db_ctrl'
                else:
                    val, tim = dbh.monitor_value(self.id)
                    self.pump_value.set_value(val)
                    #self.set_at = datetime.strptime(tim, '%Y-%m-%d %H:%M:%S')
                    self.set_at = tim
                    self.source = 'db_mon'

        return [self.pump_value.normalised(), self.set_at]

    # sets the current value (locally, in current_value database, and remotely via a command, if necessary)
    def set(self, value, defer=False, by_command=False):
        self.pump_value.set_value(value)
        val = self.pump_value.normalised()

        if self.pump_value.is_control() or by_command:   # only needed (I think) for control values

            # check the current (last) value we have for this parameter

            last_value, when = self.fetch()

            if (val != last_value) or (self.source != 'db_cur'):      # (or possibly if it's "old"?)

                dbh = Heatpump_db()
                dbh.current_value_update(self.id, val)

                if not defer:
                    commands = Commands()
                    commands.add_command([f"{self.id},{value}"])
                    commands.load_commands()

    # reset (delete value in local database
    def reset(self):
        dbh = Heatpump_db()
        dbh.current_value_delete(self.id)




if __name__ == "__main__":

    id = input("Enter parameter:")

    d = CurrentValue(id)
    print(d.id)
    print(d.fetch())
    print(d.source)
    print(d.pump_value)

