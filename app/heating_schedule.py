#!/usr/bin/env python3

from datetime import datetime
# import time    <<<< doesn't work if import time is here!!!

from . import query_mysql as db

class Schedule():
    DEFAULT_TEMP = 150

    def __init__(self):
      self.dbh = db.Heatpump_db()

    # Finds target temperature for time passed as a datetime object
    def find_target(self, current_time, zone = '1', return_none = False):
      import time
      #d = time.localtime(int(current_time.timestamp()))
      #print(d)
      # time.struct_time(tm_year=2023, tm_mon=10, tm_mday=29, tm_hour=12, tm_min=4, tm_sec=9, tm_wday=6, tm_yday=302, tm_isdst=0)

      season = 'summer' if (time.localtime(int(current_time.timestamp())).tm_isdst > 0) else 'winter'

      day_mask = ['_'] * 7
      day = current_time.weekday()
      day_mask[day] = '1'
      day_mask = ''.join(day_mask)
      time = current_time.strftime('%H:%M')

      target = self.dbh.find_target(season, day_mask, zone, time)

      # check for holiday

      dat = current_time.strftime('%Y-%m-%d')
      ddat = current_time.date()
      holiday, info = self.dbh.find_holiday(dat)

      if holiday and (zone != 'W'):
          if ( (info['start_date'] == ddat) and (current_time.hour > 12) ) or \
             ( (info['end_date'] == ddat) and (current_time.hour < 12) ) or \
             ( (info['start_date'] < ddat) and (ddat < info['end_date']) ):
              if not target: target = self.DEFAULT_TEMP
              # holiday modification applies to Zone 1 only (cos Zone 2 is kept cold!)
              target = max([ info['minimum'], (target - info['reduction']) ]) if (zone == '1') else target

      if (target is None) and not return_none:
          return self.DEFAULT_TEMP
      return target, holiday


if __name__ == "__main__":
    x = Schedule()
    print( x.find_target( datetime.strptime("2025-05-12 09:00", '%Y-%m-%d %H:%M') ) )


"""
x = Schedule()

print( x.find_target(datetime.now()) )
"""
