#!/usr/bin/env python3

# look at temperature variations across probes for a date
#
import math

from datetime import datetime, timedelta

from app.query_mysql import Heatpump_db

class myHeatpump_db(Heatpump_db):

    def gather(self, parameter, date, multiply = 1):
        res = []

        sql = f"select value from monitor where parameter = '{parameter}' and substring(created,1,10) = '{date}' order by created "
        #print(sql)

        for r in list(self.db.execute(sql)):
            res << = int(r['value'] * multiply)

        return res

analyse = datetime(2025, 10, 25)

dbh = myHeatpump_db()

#       base temp    probe1   probe2
sensors = ['99 01', '11 00', '11 09']
data = {}
totals = {}
for s in sensors:
    mult = 10 if (s == '99 01') else 1
    data[s] = dbh.gather(s, analyse, mult)
    totals[s] = sum(data[s])

order = sorted(totals.items(), key=lambda x: x[1])

for k in order.keys():
    diff = data[


    for hr in range(24):

        energy = dbh.agg(str_dat[0:4], str_dat[5:7], hr)

        kwh = energy / (600 / minutes)

        #print(f"For {str_dat[0:7]} hour {hr} aggregated energy in was {kwh} kWh")

        #kwh_int = math.ceil(kwh * 100)
        kwh_int = round(kwh * 100)
        dbh.insert_aggregate(int(str_dat[0:4]), int(str_dat[5:7]), hr, kwh_int)

        total += kwh_int

    print(f"Monthly total = {total}")
    #exit(44)

    dat += timedelta(days=32)
    if dat.day > 20: dat -= timedelta(days=15)
    print(dat)
