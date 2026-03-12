#!/usr/bin/env python3

# checks the rate of decay of the DHW temperature, as an adbherent rate implies possible dripping tap!

from datetime import datetime, timedelta
from statistics import mean

from app.control_settings import ControlSettings
from app.notifications import Notifications
from app.query_mysql import Heatpump_db

# average deltas above this will trigger warning.
trigger_notification = 1.0

now = datetime.now()
##now = datetime.strptime('2024-12-09', '%Y-%m-%d')

# range of hours to check is 21-23 at night, and 0-7 in the morning
rr = range(21,24) if now.hour > 20 else range(0,8)

start_date = now - timedelta(days = 4)
end_date = now - timedelta(days = 0)

warnings = set()

dbh = Heatpump_db()

averages = {}

dat = start_date
while dat <= end_date:
    temps = []

    for hr in rr:
        start_time = dat.replace(hour=hr, minute=0, second=0)

        vals = dbh.get_monitor(start_time, start_time + timedelta(seconds = 30), 'X', 'X', [ControlSettings.PARAMETER_DHW_TEMP])

        temps.append(vals[0]['value']/10)

    print(dat)
    print(temps)

    diffs = []
    last = temps.pop(0)

    for tmp in temps:
        diffs.append(last - tmp)
        last = tmp
    print(diffs)
    averages[dat.strftime('%Y-%m-%d')] = mean(diffs)

    # note any date where an hourly drop is more than twice the smallest (non-zero) drop
    non_zero_diffs = list(a for a in diffs if a != 0)
    non_zero_diffs.sort()
    if len(non_zero_diffs) > 1:
        max = non_zero_diffs.pop(0) * 2
        print(max)
        big_drops = list(a for a in non_zero_diffs if a > max)
        print(big_drops)
        if len(big_drops) > 0:
            warnings.add(dat.strftime('%Y-%m-%d'))

    dat += timedelta(days = 1)

print(averages)

# record all those dates where average is above notification value
warnings.update( list(k for k,v in averages.items() if v > trigger_notification) )

if len(warnings) > 0:
    print(warnings)
    message = "Possible water leak detected for " + "\n\n".join(warnings)
    Notifications().send(['email','alexa'], 'Water Temperature Alert', message, urgent=True)
