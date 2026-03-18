#!/usr/bin/env python3

no longer used!!!!! - see 'set_value' instead

##import config
##from app.pump_value import Pump
from app.query_mysql import Heatpump_db
from app.commands import Commands

dbh = Heatpump_db()

parameters = dbh.load_parameters()

parm = input("Enter parameter number: ")

if parm not in parameters.keys():
    raise RuntimeError("unknown parameter!")

val = input("Enter value (real-value) i.e. a temperature will probably by 10 times the actual temp: ")
val = int(val)

print('')

print(parameters[parm]['id'])
print(parameters[parm]['description'])
print(f"Adding a command to update parameter {parm} to {val}")

doit = input("continue? (Y/N) ")

if 'y' in doit:
    Commands().add_command([f"{parm},{val}"])
    print('inserted')
else:
    print('nothing added')

print('\nCurrent outstanding commands:')
print(dbh.fetch_commands())

print('\nRun "load_commands" now if you want these added to the queue sent to the PiW! (they will run in due course anyway)')

