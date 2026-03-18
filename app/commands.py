#
# interface to commands to heat pump
#

import json
import redis

from app.pump_value import Pump
from app.query_mysql import Heatpump_db

class Commands:
    sent = []

    def __init__(self):
        self.dbh = Heatpump_db()

    # adds a command (or commands) to the database
    def add_command(self, commands):
        # currently, 'commands' is just an array of strings "parm, value"
        self.dbh.insert_commands(commands)

    # loads any un-executed commands to the command queue for execution
    def load_commands(self):

        all = self.dbh.fetch_commands()

        r = redis.Redis()

        # This is duplicated code from utils/convert, which needs looking at for obvious reasons!
        msg = True
        while msg:
            msg = r.lpop(Pump.COMMAND_QUEUED)
            if msg:
                id = msg
                Commands.sent.append(id)

        for c in all:
            # additional rudimentary attempt to stop duplicate commands being sent(!)
            if not (c['id'] in Commands.sent):
                msg = json.dumps(c)
                r.rpush(Pump.COMMAND_QUEUE, msg)
                Commands.sent.append(c['id'])

if __name__ == "__main__":
    x = Commands()
    x.load_commands()




