#!/usr/bin/env python3

# each month, add new aggregate energy usage values to table for previous month
#

from datetime import datetime, timedelta

##from app.query_mysql import Heatpump_db
from app.query_mysql import Heatpump_db

# need to go into "last month"
dat = datetime.now() - timedelta(days = 5)
#dat = datetime.now() - timedelta(days = 15)

dbh = Heatpump_db()

total = 0

str_dat = dat.strftime('%Y-%m-%d')
minutes = dbh.monitor_step(str_dat)    # <---- how many minutes each monitor record relates to (either 1 or 5)

energy = dbh.find_aggregate_month(dat.year, dat.month)

for e in energy:

    kwh = float(e['total']) / (600 / minutes)
    kwh_int = round(kwh * 100)

    #print(kwh_int, e['hr'])
    dbh.insert_aggregate(dat.year, dat.month, e['hr'], kwh_int)

    total += kwh_int

print(total)
