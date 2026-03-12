#!/usr/bin/env python3

##not  used!!!!!

# one-off run to calculate energy_in values between dates
#
import time

from datetime import datetime, timedelta

from app.query_mysql import Heatpump_db

start = datetime(2025, 4, 17)

endd = datetime(2025, 9, 10)

dbh = Heatpump_db()

dat = start
while dat < endd:

    str_dat = dat.strftime('%Y-%m-%d')

    ##x = dbh.energy_out(str_dat)
    x = dbh.performance(str_dat)

    if x is not None:
        energy_out = x

        #cop = round((energy_out / energy_in), 2)
        print(f"For {str_dat} energy out was {energy_out}.  ")

    dat += timedelta(days = 1)
    time.sleep(1)
    print('')
