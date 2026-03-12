#!/usr/bin/env python3

import json
import redis

from app.query_mysql import Heatpump_db
from app.pump_value import Pump
from app.commands import Commands

dbh = Heatpump_db()

#parameters = dbh.load_parameters()

print('\nCurrent outstanding commands:')
print(dbh.fetch_commands())

commands = Commands()
commands.load_commands()

print('Commands now queued for execution.')
