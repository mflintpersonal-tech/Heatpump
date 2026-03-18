#!/usr/bin/env python3

from app.current_value import CurrentValue
from app.query_mysql import Heatpump_db

dbh = Heatpump_db()
parameters = dbh.load_parameters()

parm = input("Enter parameter number: ")

if parm not in parameters.keys():
    raise RuntimeError("unknown parameter!")

c = CurrentValue(parm)
v, tim = c.fetch()
print(f"Current value was set at {tim} and is:")
print(c.pump_value)
print(f"Value retrieved from {c.source}")
print('----------------------------','')

val = input("Enter value (real-value) i.e. a temperature will probably by 10 times the actual temp: ")
val = int(val)

print('')

print(f"Set this value to new value, via commands?")

doit = input("continue? (Y/N) ")

if 'y' in doit:
    c.set(val)
    print('inserted in database, and command queued to run (possibly)')
else:
    print('nothing done')

