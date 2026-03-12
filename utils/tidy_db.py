#!/usr/bin/env python3
#
# Tidy database:
#  - remove monitor_data rows older than 6 months
#

#DAYS_BACK = 30 * 6   # 180 days
DAYS_BACK = 30 * 12   # 360 days

from datetime import datetime, timedelta

from app.query_mysql import Heatpump_db

dbh = Heatpump_db()

date = datetime.now() - timedelta(days = DAYS_BACK)
date = date.strftime("%Y-%m-%d")
#date = "2024-06-01"

#dels = dbh.delete_monitor_data(date)
#print(f"Have removed {dels} rows from monitor_data - rows older than {date}")

dels = dbh.delete_monitor(date)
print(f"Have removed {dels} rows from monitor - rows older than {date}")
