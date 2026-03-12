#!/usr/bin/env python3

no longer used!!!!!

import sys

from app.query_mysql import Heatpump_db

if len(sys.argv) < 2:
    raise RuntimeError("Supply date as command-line argument")

dat = sys.argv[1]

dbh = Heatpump_db()

vals = dbh.performance(dat)

print(f"For {dat} energy in was {vals['I']}, energy out was {vals['O']}, and OAT was {vals['T']}")

