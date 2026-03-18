#!/usr/bin/env python3

import json
import math
import operator
import pickle
import random
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app import app
from app.db_connection import DBConnection
#from . import pump_value as pv

# apsw cursor method to convert timestamp columns to datetime structs
def sqlite_to_datetime(v: str):
    return v             # for mysql dont do shit
#    return datetime.strptime(v, "%Y-%m-%d %H:%M:%S")

class Heatpump_db:

    PARAMETER_DEFROST = '01 05'
    PARAMETER_OAT = '01 06'
    PARAMETER_ENERGY = '01 03'
    PARAMETER_POWER = '01 03'
    PARAMETER_TEMP_RET = '01 00'
    PARAMETER_TEMP_OUT = '01 09'
    PARAMETER_TEMP_RET_ALT = '11 00'
    PARAMETER_TEMP_OUT_ALT = '11 09'
    PARAMETER_THERM_1 = '99 01'
    SPECIFIC_HEAT_CAPACITY = 4.2

    DEFROST_LLH_ENERGY = 250    # Watts

    DEFAULT_FLOW = 24    # default flow rate in litres/min

    parameters = None
    DATETIME_FMT = "%Y-%m-%d %H:%M:%S"

    MAX_THREADS = 3
    threads = []

    calculations = {}

    def __init__(self):

        ###if len(Heatpump_db.threads) >= self.MAX_THREADS:
        ###    self.db = Heatpump_db.threads[random.randrange(0,self.MAX_THREADS)]
        ###else:
        self.db = DBConnection(
                db_type="mysql",
                database='heatpump',
                #db_type="sqlite",
                #database='heatpump.db',
                host="localhost",
                user="heatpump",
                password="HSpassword26!"
                ##database=app.config['DATABASE']
                )
        ###    Heatpump_db.threads.append(self.db)

        # TYPES ##### (see below)
        #self.registrar = apsw.ext.TypesConverterCursorFactory()

        self.tz_local = ZoneInfo('Europe/London')

    def close(self):
        self.db.close()
        ###Heatpump_db.threads.remove(self.db)


    # ========== #
    # PARAMETERS #
    # ========== #

    # load the set of parameter
    def load_parameters(self):
        res = {}

        sql = "select id, description, register, type, factor, units, colour, monitor from parameters order by id"

        ### if changing connection row tracer on connection is required :
        ###    x = self.db.rowtrace
        ###    self.db.setrowtrace(new_trace)       <----- new row tracer
        ###     :    :     :                        <----- some DB access
        ###    self.db.setrowtrace(x)               <----- restore original/default (as set above on init

        for r in list(self.db.execute(sql)):
            res[r['id']] = r

        return res

    def update_parameter(self, id, description, colour):
        sql = "update parameters set description = ?, colour = ? where id = ? "
        self.db.execute(sql, [description, colour, id])


    # ======= #
    # MONITOR #
    # ======= #

    #USE_MONITOR_DATA = False
    USE_MONITOR_DATA = True
    # Fetch rows of monitoring data
    def get_monitor(self, range1, range2, time1, time2, parms):

        if Heatpump_db.parameters is None:
            print('Loading HeatPump Parameters')
            Heatpump_db.parameters = self.load_parameters()

        # TYPES - this doesn't work; seems to override row_factory on connection either/or choice
        # created column : timestamp string -> datetime
        ##self.db.cursor_factory = self.registrar
        ##self.registrar.register_converter("timestamp", sqlite_to_datetime)
        g1 = datetime.now()

        res = []

        if not self.USE_MONITOR_DATA:

            sql = f"select created, parameter, value from monitor where created >= '{range1}' and created <= '{range2}' "

            if time1 != 'X':
              sql += f" and time(created) >= '{time1}' and time(created) <= '{time2}' "

            sql += f"""and parameter in ("{'","'.join(parms)}") order by parameter, created """

            #for r in list(self.db.execute(sql)):
            rr = list(self.db.execute(sql))
            g2 = datetime.now()
            for r in rr:
                r['created'] = sqlite_to_datetime(r['created'])
                res.append(r)
            g3 = datetime.now()

        else:
            # this method is about 8 times faster than the individual items
            d = range1
            t = '00:00:00' if time1 == 'X' else f"{time1}:00"
            dt = datetime.strptime(f"{datetime.strftime(d,'%Y-%m-%d')} {t}", "%Y-%m-%d %H:%M:%S")
            r1 = int(dt.timestamp())
            #r1 = int(time.mktime(dt.timetuple()))
            #print(dt, r1)
            d = range2
            t = '23:59:59' if time1 == 'X' else f"{time2}:59"
            dt = datetime.strptime(f"{datetime.strftime(d,'%Y-%m-%d')} {t}", "%Y-%m-%d %H:%M:%S")
            r2 = int(dt.timestamp())
            #print(dt, r2)

            sql = f"select created_date, data from monitor_data where created_key >= '{r1}' and created_key <= '{r2}' order by created_key ASC "
            #print(sql)


            #for r in list(self.db.execute(sql)):
            rr = list(self.db.execute(sql))
            g2 = datetime.now()
            for r in rr:
                data = json.loads(r['data'])
                #created = datetime.fromtimestamp(r['created_key'], tz=self.tz_local)
                #created = self._utc_to_local(r['created_date'])
                created = r['created_date']

                data = list( a for a in data if a[0] in parms )

                for a in data:
                    res.append({'created': created, 'parameter': a[0], 'value': a[1]})
            g3 = datetime.now()

        # clear registrar
        ##self.db.cursor_factory = apsw.Cursor
        print(f"GET_MONITOR database  = {g2-g1}")
        print(f"GET_MONITOR format    = {g3-g2}")

        return res

    # Returns the latest value for an ID from what's in the database
    def monitor_value(self, id):

        val = None; created = None

        sql = f"select value, created from monitor where parameter = '{id}' order by `created` desc limit 0,1 "

        for r in list(self.db.execute(sql)):
            val = r['value']
            created = r['created']

        return [val, created]

    # Returns Boolean if value is greater than or equal to limit passed for parameter
    def limit_reached(self, id, dat, limit):

        res = False

        sql = f"select value from monitor where parameter = '{id}' and created >  '{dat}' and value >= {limit} limit 0,1 "

        for r in list(self.db.execute(sql)):
            res = True

        return res

    def insert_monitor_data(self, key, data, converted='N', force=False):
        # Added 12/1/26 : don't overwrite 'Z' data(!)
        sql = f"select converted from monitor_data where created_key = {key} "
        conv = False
        for r in list(self.db.execute(sql)):
            conv = (r['converted'] == 'Z')

        # To partition the table we needed unique keys to include partition column (converted) which meant primary key
        # became created_date+converted rather than created_date.
        # This means we can get duplicates on created_date with different 'converted' values.
        # To avoid, always delete all, before inserting.
        if force or (not conv):
            sql = f"delete from monitor_data where created_key = {key}; "
            self.db.execute(sql)
            sql = "insert into monitor_data (created_key, created_date, converted, data) values (?, ?, ?, ?) "
            self.db.execute(sql, [key, datetime.fromtimestamp(int(key), tz=timezone.utc), converted, data])

    # passed a date as Y-m-d, remove all entries from monitor_data before then
    def delete_monitor_data(self, from_date):

        dat = datetime.strptime(from_date, "%Y-%m-%d")
        dat = dat.timestamp()

        sql = "delete from monitor_data where created_key < ? "
        changes = self.db.execute(sql, [dat])

        return changes

    # passed a date as Y-m-d, remove all entries from monitor before then
    def delete_monitor(self, from_date):

        dat = f"{from_date} 23:59:59"

        sql = "delete from monitor where created < ? "
        changes = self.db.execute(sql, [dat])

        return changes

    # re-create the monitor_data entry from monitor data (this leads to improved retrieval performance)
    def rebuild_monitor_data(self, created, force=False):

        sql = f"select parameter, value from monitor where created = '{created.strftime(self.DATETIME_FMT)}' "

        res = []
        for r in list(self.db.execute(sql)):
            res.append([ r['parameter'], r['value'] ])

        data = json.dumps(res)

        #dt = int(time.mktime(created.timetuple()))
        dt = created.timestamp()

        #with open("/var/www/heatpump/update.log", "a") as f:
        #    f.write(created.strftime('%Y-%m-%d %H:%M:%S')+"\n")
        #    f.write(str(dt)+"\n")
        #    f.write(data+"\n")

        self.insert_monitor_data(dt, data, converted='Z', force=force)

        return True

    # re-create the monitor_data for an entire day
    def rebuild_monitor_data_day(self, dat, force=False):

        # find all the datetime values for the day in question
        ## using 'ORDER' makes sqlit choose a poor index (just on parameter); and in this case, order doesn't matter
        #sql = self._sqldatetime(f"select created as cr from monitor where parameter = '{self.PARAMETER_TEMP_RET}' and DATE(created) = dat order by created ASC ", dat)
        sql = self._sqldatetime(f"select created as cr from monitor where parameter = '{self.PARAMETER_TEMP_RET}' and DATE(created) = dat  ", dat)
        #print(sql)

        for r in list(self.db.execute(sql)):
            #print(r['cr'])
            self.rebuild_monitor_data( sqlite_to_datetime(r['cr']), force=force )

        return True

    # re-create the monitor records from monitor_data : dat passed as string yyyy-mm-dd
    def rebuild_monitor_day(self, dat):

        sql = f"select created_key, created_date, data from monitor_data where created_date between ? and ? "

        res = []
        for row in self.db.execute(sql, [dat+' 00:00:00', dat+' 23:59:59' ]):
            recs = json.loads(row['data'])
            for r in recs:
                res.append([row['created_date'], r[0], r[1]])

        print(len(res))
        sql = "insert into monitor (created, parameter, value) values (?, ?, ?) "
        self.db.executemany(sql, res)

        return True

    # re-create probe and temperature data for an entire day (for when things go wrong)
    def rebuild_thermistor_data(self, dat):

        # find all the datetime values for the day in question
        sql = self._sqldatetime(f"select created from monitor where parameter = '{self.PARAMETER_TEMP_RET}' and DATE(created) = dat ", dat)
        #print(sql)

        updates = []
        for r in list(self.db.execute(sql)):

            sql = f"select parameter, value from monitor where created = '{r['created']}' "
            sql += f" and parameter in ('01 00', '01 09', '01 06') "

            for s in list(self.db.execute(sql)):
                updates.append([ r['created'], s['parameter'], s['value'] ])

        #print(updates)

        replaced = {'01 00': '11 00', '01 09': '11 09', '01 06': '01 32'}
        for u in updates:

            sql = f"select value from monitor where created = '{u[0]}' and parameter = '{replaced[u[1]]}' "

            found = False
            for r in list(self.db.execute(sql)):
                found = True
            if not found:
                print(f"replacing for {replaced[u[1]]} {u}")
                sql2 = "replace into monitor (created, parameter, value) values (?, ?, ?) "
                self.db.execute(sql2, [ u[0], replaced[u[1]], int(u[2])*10 ])

        return True

    # add a new entry to the monitor table
    def insert_monitor(self, parm, time, value):

        #value = -1 if value > 32756    # Hack for some reason

        sql = "replace into monitor (created, parameter, value) values (?, ?, ?) "
        self.db.execute(sql, [time, parm, value])
    """
    NOT USED
    # add the created date field to monitor table where missing
    def insert_created_date(self, dat):

        # find all the datetime values for the day in question
        sql = self._sqldatetime(f"select created as cr from monitor where parameter = '{self.PARAMETER_TEMP_RET}' and DATE(created) = dat ", dat)
        #print(sql)

        dat2 = self._compressdate(dat)

        for r in list(self.db.execute(sql)):
            sql2 = "update monitor set created_date = ? where created = ? "
            self.db.execute(sql2, [dat2, r['cr']])

        return True
    """

    # set the monitor data flag to 'Y'
    def update_monitor_data(self, key, value):
        sql = "update monitor_data set converted = ? where created_key = ? "
        self.db.execute(sql, [value, key])

    # return any unconverted monitor_data rows
    def fetch_unconverted(self):

        res = []

        sql = "select created_key, data from monitor_data where converted = 'N' order by created_key ASC "

        for r in list(self.db.execute(sql)):
            res.append(r)

        return res

    # add a new entry to the monitor pending_values table
    def insert_pending(self, time, parm, value):

        ##sql = "insert into pending_values (created, parameter, value) values (?, ?, ?) "
        # TODO s/be temp as we have duplicate parameter IDs in app/thermoeters currently!   9/25
        sql = "replace into pending_values (created, parameter, value) values (?, ?, ?) "
        self.db.execute(sql, [time, parm, value])

    def delete_pending(self, hhmm, parm):
        self.db.execute(f"delete from pending_values where created = {hhmm} and parameter = '{parm}' ")

    # return all rows of pending_values
    def fetch_pending(self):

        res = []

        sql = "select created, parameter, value from pending_values "

        for r in list(self.db.execute(sql)):
            res.append(r)

        return res

    # repair pending
    # fixes any leftover pending values by looking in monitor_data to match up the time, and then applying the values to monitor_data (and monitor)
    def repair_pending(self):

        # first bring back pending values

        pending = self.fetch_pending()

        # match them up against monitor_data created_date times

        rebuild_monitor_dates = set()

        for pend in pending:
            print(f"Pending data: {pend}")
            t = pend['created']
            t = f"{t[0:4]}-{t[4:6]}-{t[6:8]} {t[8:10]}:{t[10:12]}"       # yymmddhhmm --> yyyy-mm-dd hh:mm
            sql = f"select created_key, created_date from monitor_data where created_date between '{t}:03' and '{t}:44' limit 0,1"
            r = self.db.execute(sql)
            if len(r) > 0:
                print(f"- found matching date of {r[0]['created_date']}")
                self.insert_monitor(pend['parameter'], r[0]['created_date'], pend['value'])
                self.delete_pending(pend['created'], pend['parameter'])
                rebuild_monitor_dates.add(r[0]['created_date'])
            else:
                sql = f"update pending_values set repair_fails = repair_fails + 1 where created = ? and parameter = ? "
                self.db.execute(sql, [ pend['created'], pend['parameter'] ])

        # new monitor data, so rebuild the monitor_data
        for created in rebuild_monitor_dates:
            print(f"Rebuilding monitor_data for {created}")
            self.rebuild_monitor_data(created, force=True)

        # finally, remove anything from pending_values where we've failed to repair it more than 5 times
        pending_limit = 5
        if len(pending) > 0:
            sql = f"delete from pending_values where repair_fails > ? "
            self.db.execute(sql, [ pending_limit ])

    def load_power(self, dat1, dat2, limit = 0):

        minutes = self.monitor_step(dat1)

        res = []

        ## sql = f"" "select created, value from monitor where parameter = '{self.PARAMETER_POWER}' and DATE(created) >= '{dat1}'
        ##                                               and DATE(created) <= '{dat2}' and value > {limit} order by created;"" "
        sql = f"""select created, value from monitor where parameter = '{self.PARAMETER_POWER}' and created >= '{self._local_to_utc(dat1+' 00:00:00')}'
                                                       and created <= '{self._local_to_utc(dat2+' 23:59:59')}' and value > {limit} order by created;"""
        for r in list(self.db.execute(sql)):
            r['created'] = sqlite_to_datetime(r['created'])
            r['value'] = r['value'] / (600/minutes)
            res.append(r)

        return res

    # TODO: Explain why we do this!!!!   ZZZZZZZ
    def _sqldatetime(self, str, d):
        #return str.replace(' DATE(created) = dat ', f" created between datetime('{d+' 00:00:00'}') and datetime('{d+' 23:59:59'}') ") 
        #return str.replace(' DATE(created) = dat ', f" created_date = '{self._compressdate(d)}' ")
        return str.replace(' DATE(created) = dat ', f" created between '{self._local_to_utc(d+' 00:00:00')}' and '{self._local_to_utc(d+' 23:59:59')}' ")

    # passed local time string, return datetime string in UTC
    def _local_to_utc(self, d):
        dt_local = datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
        dt_local = dt_local.replace(tzinfo=self.tz_local)
        dt_utc = dt_local.astimezone(timezone.utc)
        return dt_utc.strftime("%Y-%m-%d %H:%M:%S")

    # passed UTC datetime, return local datetime
    def _utc_to_local(self, d):
        dt_local = d.replace(tzinfo=self.tz_local)
        return dt_local.astimezone(timezone.utc)

    def _compressdate(self, d):
        return d[0:10].replace('-','')

    # return time period being used for monitoring on this date (either 1 or 5 minutes)
    def monitor_step(self, dat):

        sql = f"select created_date from monitor_data where created_date between '{dat} 00:01:00' and '{dat} 20:59:59' limit 0,2 "
        two = list(self.db.execute(sql))
        if len(two) == 0: return 5         # make a default if not known

        sdiff = sqlite_to_datetime(two[1]['created_date']) - sqlite_to_datetime(two[0]['created_date'])
        sdiff = sdiff.total_seconds()

        return 1 if sdiff < 90 else 5


    # ====== #
    # ENERGY #
    # ====== #

    # calculate energy into heat pump for specific date; date is passed as string "YYYY-MM-DD"
    def energy_in(self, dat):
        ee0 = datetime.now()

        e = None

        sql = f"select sum(value) as total from monitor where parameter = '{self.PARAMETER_POWER}' and DATE(created) = dat "
        sql = self._sqldatetime(sql, dat)

        for r in list(self.db.execute(sql)):
            if r['total'] is not None: e = int(r['total'])
        ee1 = datetime.now()

        if e is None: return None

        minutes = self.monitor_step(dat)

        ee2 = datetime.now()

        # The power consumption is recorded every 5 minutes, and is in units of 100 Watts
        # To convert to 'energy used (KWh)' take the total value for the date, and divide by 12 (which is 60 / 5) gives Watts/hr
        # then account for 100W units and convert to KW from W
        # In short, divide by 120.

        e = e / (600 / minutes)

        #sql = "insert into energy (date, type, kwh) values (?, ?, ?) "
        #self.db.execute(sql, [dat, 'I', e])

        # add on 250W for each defrost cycle (see p14 of "Grant Combined Volumiser/Low Loss Header Installation Instructions"

        extra = (self.DEFROST_LLH_ENERGY * self.defrost_count(dat)) / 12000    # assumes 5 minute runs for each defrost (I think)
        print("ENERGY IN:")
        print(e)
        print(f"Defrost energy addition: {extra}")
        e += extra
        ee3 = datetime.now()

        print(f"GET DATA = {ee1-ee0}")
        print(f"GET STEP = {ee2-ee1}")
        print(f"DEFROST  = {ee3-ee2}")
        print(f"GET DATA = {ee1-ee0}")

        return e

    # Return set of performance figures from database, and fill in any gaps; range is in days
    def performance_set(self, start, day_range):

        st = start.strftime('%Y-%m-%d')

        sql = f"select date, type, kwh from energy where date between date_sub('{st}', interval {day_range} day) and '{st}' "

        res = []
        found_dates = set()
        row = {}
        # build array of dictionaries; one row per date with all energy values for that data in there

        # For historical/compatability purposes, the values need to be in this order...
        # 'DATE','IN','OUT','COP','AOOT','OAT','STD','IAT']
        #  date   I    O           U      T     V     W
        for r in self.db.execute(sql):
            if r['type'] == 'F': continue        # 'F' used to indicate Flow-rate ... maybe have a better mechanism?
            row[r['type']] = r['kwh']
            if len(row) == 6:
                cop = round((row['O'] / row['I']), 2) if row['I'] > 0 else 'N/A'
                rsorted = {'date': r['date'], 'I': row['I'], 'O': row['O'], 'COP': cop,
                           'U': row['U'], 'T': row['T'], 'V': row['V'], 'W': row['W']
                          }
                res.append(rsorted)
                row = {}
                found_dates.add(r['date'])

        # check for missing days

        all_dates = set(start.date() - timedelta(days=i) for i in range(day_range))
        missing = all_dates - found_dates

        if len(missing) > 0:
            for dat in missing:
                details = self.performance(dat.strftime('%Y-%m-%d'))
                details['date'] = dat
                res.append(details)

        return sorted(res, key=operator.itemgetter('date'), reverse=True)

    # Find scop values based on a starting date and range (in months)
    # NOTE: ratio of sums DOES NOT equal average of ratios!  i.e. summing energy out over energy in is not the average COP!
    def find_scop(self, start, month_range=None):

        st = start.strftime('%Y-%m-%d')

        r = ''
        if month_range:
            r = f"e1.date between date_sub('{st}', interval {month_range} month) and '{st}' and "

        #sql = f"select type, sum(kwh) as total from energy where {r} type ='I' union select type, sum(kwh) as total from energy where {r} type ='O';"

        sql=f"select avg(e1.kwh/e2.kwh) as cop from energy e1 inner join energy e2 on e1.date=e2.date where {r} e1.type = 'O' and e2.type='I';"

        cop = 'N/A'
        for r in self.db.execute(sql):
            cop = r['cop']

        return cop

    def aggregate(self, vals):

        # average each value over 'rrange' adjacent values - set to 2 either side i.e. 5 values in total

        rrange = 5    # how wide we'll look at values around current one (this means 2 either side)

        start_ave = sum(vals[0:rrange]) / rrange   # filler values either side based on simple average
        end_ave = sum(vals[-rrange:]) / rrange

        v2 = [start_ave] * (rrange - 1)
        v2.extend(vals)                         # build a slightly larger array so the calculation is simple
        v2.extend([end_ave] * (rrange - 1))

        scope = (rrange - 1) * 2 + 1
        v3 = []
        for i in range(0, len(v2)-scope+1):
            v = v2[i:i+scope]
            v3.append( sum(v) / scope )

        return v3

    # calculate energy out of the heat pump for specific date; date is passed as string "YYYY-MM-DD"
    def energy_out(self, dat, use_alt=False):

        e = None

        # Page 48 of Installation manual:
        # Flow rate = Heat output (kW) ÷ Temperature differential (K) ÷ Specific heat capacity of water (4.2kJ/kgK) * 60
        #
        # i.e. Flow = (60 * Heat output) / (Temperature differential * Specific heat capacity) )

        # Therefore, Heat output (kW) = ( Flow * Temperature differential * Specific heat capacity ) / 60

        # The 'energy' table is used to store Flow on the start date for when that flow was recorded, as it's not available
        # via the interface, so this is a crude approximation currently.

        """ 
        # Find times in day when power was on; use those times to find temp differential.
        # Get flow rate, and do the necessary.

        sql = f"select created, value from monitor where parameter = '{self.PARAMETER_ENERGY}' and DATE(created) = dat and value > 0 "
        sql = self._sqldatetime(sql, dat)

        # (there are times when only 100W is being used, and nothing is being pumped. Not sure what this is, but list the real times also)
        ## times = []
        ## ###times_not100 = []
        ## for r in list(self.db.execute(sql)):
        ##     times.append(r['created'])
        ##     ###if r['value'] > 1: times_not100.append(r['created'])

        times = list( r['created'] for r in list(self.db.execute(sql)) )

        #times = ['2023-10-24 09:20:04','2023-10-24 09:25:04','2023-10-24 09:30:05','2023-10-24 09:35:05','2023-10-24 09:40:04','2023-10-24 09:45:04','2023-10-24 09:50:04','2023-10-24 09:55:04','2023-10-24 10:00:05']

        if len(times) == 0: return None

        # HERE'S A METHOD FOR ALL TIMES!
        sql = f" ""select created, parameter, value from monitor
                  where (parameter = '{self.PARAMETER_TEMP_OUT}' or parameter = '{self.PARAMETER_TEMP_RET}')
                         and DATE(created) = '{dat}' ;

        # Create two dictionaries keyed on time for out/ret temps
        temp_out = {}
        temp_ret = {}

        results = list(self.db.execute(sql))

        for r in results:
            if r['parameter'] == self.PARAMETER_TEMP_OUT:
                temp_out[r['created']] = r['value']
            elif r['parameter'] == self.PARAMETER_TEMP_RET:
                temp_ret[r['created']] = r['value']

        # Create two dictionaries keyed on time for out/ret temps

        """

        """
        # Alternative to the above!
        use_parm = self.PARAMETER_TEMP_OUT_ALT if use_alt else self.PARAMETER_TEMP_OUT
        sql = f""select created, parameter, value from monitor
                  where parameter = '{use_parm}'
                       and DATE(created) = dat ;
              ""
        sql = self._sqldatetime(sql, dat)
        results = list(self.db.execute(sql))
        temp_out = dict((r['created'], r['value']) for r in results)

        use_parm = self.PARAMETER_TEMP_RET_ALT if use_alt else self.PARAMETER_TEMP_RET
        sql = f""select created, parameter, value from monitor
                  where parameter = '{use_parm}'
                        and DATE(created) = dat ;
              ""
        sql = self._sqldatetime(sql, dat)
        """

        # ANOTHER alternative!
        out_parm = self.PARAMETER_TEMP_OUT_ALT if use_alt else self.PARAMETER_TEMP_OUT
        ret_parm = self.PARAMETER_TEMP_RET_ALT if use_alt else self.PARAMETER_TEMP_RET

        sql = f"""select created, parameter, value from monitor  where parameter in ('{out_parm}','{ret_parm}') and created in
                  (select created from monitor where parameter = '{self.PARAMETER_ENERGY}' and DATE(created) = dat and value > 0)
                  order by created ;
               """
        sql = self._sqldatetime(sql, dat)

        results = self.db.execute(sql)
        temp_out = dict((r['created'], r['value']) for r in results if r['parameter'] == out_parm)
        temp_ret = dict((r['created'], r['value']) for r in results if r['parameter'] == ret_parm)

        # For times where energy used, find temp difference

        diff = 0
        for t in temp_out.keys():
            if (t in temp_ret.keys()):
                xx = (temp_out[t] - temp_ret[t])
                if xx > 0:
                    diff += xx
        print(f'Non aggregated Diff = {diff}')
        ndiff = diff

        if use_alt:              # no need to aggregate if using ALT parameters as they are fine grade
            diff = diff / 10     # but must account for values being 10* (ought to be done better!)  #FIXME
            ndiff = diff

        else:
            ### THis probably no longer works!!!!   MF 9/2/26
            # ADDED on 5/2/24
            new_vals = self.aggregate(list(temp_out.values()))
            i = 0
            for k in temp_out.keys():
                temp_out[k] = new_vals[i]
                i += 1

            new_vals = self.aggregate(list(temp_ret.values()))
            i = 0
            for k in temp_ret.keys():
                temp_ret[k] = new_vals[i]
                i += 1

            # For times where energy used, find temp difference

            diff = 0
            # PATCH (see above)
            #for t in times:
            #    if (t in temp_out.keys()) and (t in temp_ret.keys()):
            for t in temp_out.keys():
                if (t in temp_ret.keys()):
                    xx = (temp_out[t] - temp_ret[t])
                    if xx > 0:
                        diff += xx
                        #diff += (temp_out[t] - temp_ret[t])

            print(f'Aggregated Diff = {diff}')

        diff = max(diff, ndiff)
        print(f'Max is = {diff}')

        ###diff_not100 = 0
        ###for t in times_not100:
        ###    if (t in temp_out.keys()) and (t in temp_ret.keys()):
        ###        diff_not100 += (temp_out[t] - temp_ret[t])
        #print('overall difference in K:')
        #print(diff)

        #temp_out = {}
        #temp_ret = {}
        #for r in list(self.db.execute(sql)):
        #    if r['parameter'] == self.PARAMETER_TEMP_OUT:
        #        temp_out[r['created']] = r['value']
        #    elif r['parameter'] == self.PARAMETER_TEMP_RET:
        #        temp_ret[r['created']] = r['value']
        ###diff_all = 0
        ###for a in temp_out.keys():
        ###    xx = (temp_out[a] - temp_ret[a])
        ###    if xx > 0: diff_all += xx
        ###################################

        # see what measurements were in operation on the day
        minutes = self.monitor_step(dat)
        #print(f"Working on {minutes} recordings")

        # Therefore, Heat output (kW) = ( Flow * Temperature differential * Specific heat capacity ) / 60

        # Find flow rate for the date

        flow = self.flow_rate(dat)
        print(f"For date of {dat} have selected flow of {flow}.")

        e = (flow * diff * self.SPECIFIC_HEAT_CAPACITY) / 60
        e = e / (60/minutes)       # account for measurements taken every 5 minutes (12th of an hour)

        ###e_not100 = (flow * diff_not100 * self.SPECIFIC_HEAT_CAPACITY) / 60
        ###e_not100 = e_not100 / (60/minutes)       # account for measurements taken every 5 minutes (12th of an hour)

        ###e_all = (flow * diff_all * self.SPECIFIC_HEAT_CAPACITY) / 60
        ###e_all = e_all / (60/minutes)             # account for measurements taken every 5 minutes (12th of an hour)

        ###print(f"Energy out {e} or compare with excluding 100W times of {e_not100}; or all times is {e_all}")

        # add on 250W for each defrost cycle (see p14 of "Grant Combined Volumiser/Low Loss Header Installation Instructions"

        extra = (self.DEFROST_LLH_ENERGY * self.defrost_count(dat)) / 12000    # assumes 5 minute runs for each defrost (I think)
        print("ENERGY OUT:")
        print(e)
        print(f"Defrost energy addition: {extra}")
        e += extra

        return e

    # Return flow rate for a specific date (integer)
    def flow_rate(self, dat):
        flow = self.DEFAULT_FLOW     # DEFAULT

        sql = f"select kwh from energy where type = 'F' and date <= '{dat}' order by date desc limit 0,1 "

        for r in list(self.db.execute(sql)):
            flow = float(r['kwh'])

        return flow

    # find average Indoor Air Temperature
    def average_iat(self, dat):
        sql = f"select avg(value) as iat from monitor where parameter = '{self.PARAMETER_THERM_1}' and DATE(created) = dat "
        sql = self._sqldatetime(sql, dat)

        temp = 0.0
        for r in list(self.db.execute(sql)):
            temp = r['iat']/10 if r['iat'] else 0.0

        return round(temp,2)

    # find average Outdoor Air Temperature
    def average_oat(self, dat):
        sql = f"select avg(value) as oat from monitor where parameter = '{self.PARAMETER_OAT}' and DATE(created) = dat "
        sql = self._sqldatetime(sql, dat)

        temp = 0.0
        for r in list(self.db.execute(sql)):
            temp = r['oat']

        return round(temp,2)

    # finds standard deviation of OAT (cheaply - as square root of variance)
    def stddev_var(self, dat):
        sql = f"select AVG(value*value) - AVG(value)*AVG(value) as var from monitor where parameter = '{self.PARAMETER_OAT}' and DATE(created) = dat "
        sql = self._sqldatetime(sql, dat)

        std = None
        for r in list(self.db.execute(sql)):
            if r['var']: std = math.sqrt(r['var'])

        return round(std,2)

    # finds average Outdoor Operating Air Temperature (ave temp during times HP was operating)
    def average_aoot(self, dat):

        """
        # find times HP was active
        sql = f"select created from monitor where parameter = '{self.PARAMETER_ENERGY}' and DATE(created) = dat and value > 0 "
        sql = self._sqldatetime(sql, dat)

        times = []
        for r in list(self.db.execute(sql)):
            times.append(r['created'].strftime(self.DATETIME_FMT))

        if len(times) == 0: return None
        #sql = f""select AVG(value) as aoot from monitor
        #          where (parameter = '{self.PARAMETER_OAT}')
        #                 and created in ('{"','".join(times)}') ;
        #     ""
        """
        sql = f"""select AVG(value) as aoot from monitor where parameter = '{self.PARAMETER_OAT}' and created in
                  (select created from monitor where parameter = '{self.PARAMETER_ENERGY}' and DATE(created) = dat  and value > 0);
               """
        sql = self._sqldatetime(sql, dat)
        aoot = None
        for r in self.db.execute(sql):
            aoot = round(r['aoot'],2)

        return aoot

    # retrieve performance stats for date, or generate if missing
    def performance(self, dat):
        updates = {}

        d1 = datetime.now()

        sql = f"select type, kwh from energy where type in ('I', 'O', 'T', 'U', 'V', 'W') and date = '{dat}' "

        res = {}
        for r in list(self.db.execute(sql)):
            res[r['type']] = r['kwh']

        d2 = datetime.now()

        # ENERGY IN
        if not ('I' in res):
            res['I'] = self.energy_in(dat)
            updates['I'] = res['I']
        d3 = datetime.now()

        # ENERGY OUT
        if not ('O' in res):
            # Changed 11/11/25 : Calculate using probes as well and HP values, and use maximum
            # Eventually I think we'll just use the 'alt' versions
            # Changed 19/11/25 : Only calculate 'normal' values at end of day when we store in database
            alt = self.energy_out(dat, use_alt=True)
            res['O'] = alt
            updates['O'] = res['O']

            if (dat < datetime.now().strftime('%Y-%m-%d')):
                normal = self.energy_out(dat)
                # AS ABOVE, RECORD uplift for use_alt method, daily
                sql = "insert into uplift (date, normal, alt, uplift) values (?, ?, ?, ?) "
                self.db.execute(sql, [dat, normal, alt, round( (((alt - normal) * 100) / normal), 2 )])

        d4 = datetime.now()

        # AVERAGE OUTDOOR AIR TEMP
        if not ('T' in res):
            res['T'] = self.average_oat(dat)
            updates['T'] = res['T']
        d5 = datetime.now()

        # AVERAGE OPERATING OUTDOOR AIR TEMPERATURE
        if not ('U' in res):
            res['U'] = self.average_aoot(dat)
            updates['U'] = res['U']
        d6 = datetime.now()

        # STD DEVIATION OF AOT
        if not ('V' in res):
            res['V'] = self.stddev_var(dat)
            updates['V'] = res['V']
        d7 = datetime.now()

        # INDOOR AIR TEMPERATURE
        if not ('W' in res):
            res['W'] = self.average_iat(dat)
            updates['W'] = res['W']
        d8 = datetime.now()

        if (len(updates) > 0) and (dat < datetime.now().strftime('%Y-%m-%d')):
            for u in updates.keys():
                sql = "insert into energy (date, type, kwh) values (?, ?, ?) "
                self.db.execute(sql, [dat, u, updates[u]])

        print(f"{d1} START PERFORMANCE")
        print(f"{d2} Fetch from DB = {d2 - d1}")
        print(f"{d3} Energy IN     = {d3 - d2}")
        print(f"{d4} Energy OUT    = {d4 - d3}")
        print(f"{d5} Averagge OAT  = {d5 - d4}")
        print(f"{d6} Averarge AOOT = {d6 - d5}")
        print(f"{d7} STDDEV +VAR   = {d7 - d6}")
        print(f"{d8} Averege IAT   = {d8 - d7}")
        print(f"{d8} Time in PERF  = {d8 - d1}")

        return res

    #- Aggregate table -#

    # Aggregate energy used per hour in a month (passed Year, Month, and Hour)
    def find_aggregate(self, year, month, hour):
        sql = f"select sum(value) as total from monitor where parameter = '{self.PARAMETER_POWER}' and DATE_FORMAT(created, '%Y%m%H') = '{year}{month}{hour:02d}'; "
        #sql = f"select sum(value) as total from monitor where parameter = '{self.PARAMETER_POWER}' and substring(created,1,7) == '{year}-{month}' and substring(created,12,2) = '{hour:02d}' "
        for r in list(self.db.execute(sql)):
            val = r['total']

        return val

    # as above, but MySQL can do the work for a month at once
    def find_aggregate_month(self, year, month):
        res = []

        sql = f"""select HOUR(created) as hr, sum(value) as total from monitor where parameter = '{self.PARAMETER_POWER}' 
                  and DATE(created) between '{year}-{month}-01' and LAST_DAY('{year}-{month}-01') group by HOUR(created) """

        for r in list(self.db.execute(sql)):
            res.append(r)

        return res

    # set the aggregate energy for month/hour
    def insert_aggregate(self, year, month, hour, kwh100):
        sql = "insert into aggregate_energy (year, month, hour, total) values (?, ?, ?, ?) "
        self.db.execute(sql, [year, month, hour, kwh100])
        return True

    # retrieve the aggregate energy for year/month/hour
    def get_aggregate(self, year, month, hour):
        val = 0

        now = datetime.now()

        if (year == now.year) and (int(month) == now.month):
            minutes = self.monitor_step(now.strftime('%Y-%m-%d'))

            energy = self.find_aggregate(now.year, f"{month:02d}", hour)

            kwh = float(energy) / (600 / minutes)
            kwh_int = round(kwh * 100)

            val = kwh_int

        else:
            sql = f"select total from aggregate_energy where year = {year} and month = {month} and hour = {hour} "

            for r in list(self.db.execute(sql)):
                val = r['total']

        return val

    # return defrost cycle count for date
    #
    #   A defrost cycle can be identified if:
    #
    #   - min(outdoor temp) < 50 i.e. 5C
    #   - defrost temp at time t0 < 0C AND defrost within next 8 minutes 20C greater than that (i.e. t0 + 5mins)
    #   - and each t0 is 30 mins from the next one (NOT IMPLEMENTED)
    def defrost_count(self, dat):
        count = 0

        calc_key = datetime.now().strftime('%Y%m%d%H%M%S')
        if calc_key in Heatpump_db.calculations:
            return Heatpump_db.calculations[calc_key]
        else:
            if len(Heatpump_db.calculations) > 50:
                Heatpump_db.calculations.clear()

        dd0 = datetime.now()

        # We use parameter 01 06, which is the HP external air temp, as this is most likely to influence defrost cycles
        sql = f"select min(value) as oat from monitor where parameter = '{self.PARAMETER_OAT}' and DATE(created) = dat "
        sql = self._sqldatetime(sql, dat)

        temp = 0.0
        for r in list(self.db.execute(sql)):
            temp = r['oat']

        # Wasn't that cold a day
        if temp >= 5: return count

        # ---------------------------------------------------
        # 19/11/25 :: ALTERNATIVE method is ...
        # If it is a cold day (and it is by here) then get all defrost temps > 10
        # Collate ones within 30 mins of each other, and count those

        # select all times where defrost parameter 01 05 > 14C

        sql = f"select created from monitor where parameter = '{self.PARAMETER_DEFROST}' and DATE(created) = dat and value > 14 "
        sql = self._sqldatetime(sql, dat)

        times = []
        for r in list(self.db.execute(sql)):
            times.append(sqlite_to_datetime(r['created']))

        if len(times) == 0: return count                 # no candidate defrost times

        times.append(times[-1]+timedelta(minutes=45))    # add on an ending value
        quick_count = 0
        current = times[0]
        for tim in times[1:]:
            if (tim - current).seconds > (30 * 60):
                #print('found')
                #print(current)
                quick_count += 1
                current = tim

        print(f"Quick time = {datetime.now()-dd0}")
        print(f"Quick count = {quick_count}")
        # ----------------------------------------------

        if quick_count > 1:      # can be fooled on some short days, in which case do long computation
            return quick_count

        # select all times where defrost parameter 01 05 is less than -2C

        sql = f"select created, value from monitor where parameter = '{self.PARAMETER_DEFROST}' and DATE(created) = dat and value < -2 "
        sql = self._sqldatetime(sql, dat)

        times = self.db.execute(sql)
        print(f"Load from DB = {datetime.now()-dd0}")
        dd1 = datetime.now()

        # Look for any times 8 minutes later, where the defrost temp was 20C more than the sub-zero temperature

        for t in times:
            # look at all times in the next 8 minutes for value of 20 above this one
            sql = f"""select created, value from monitor where parameter = '{self.PARAMETER_DEFROST}'
                                                and created between '{t['created']}' and '{t['created'] + timedelta(minutes=8)}'
                                                and value >= {t['value'] + 20} limit 1
                   """
            rr = self.db.execute(sql)
            print(f"{t['created']}: time spent is {datetime.now()-dd1}")
            if len(rr) > 0:
                print('found one')
                print(rr[0]['created'])
                count += 1

        """
        # is this pointless??
        times = []
        for r in list(self.db.execute(sql)):
            times.append([ sqlite_to_datetime(r['created']), r['value'] ])
        times = self.db.execute(sql, as_dict=False)
        print(f"Load from DB = {datetime.now()-dd0}")
        dd1 = datetime.now()

        # if temp < 0, look for any times 8 minutes later, where the defrost temp was 20C more than the sub-zero temperature

        i = 0
        while i < len(times):
            #print(f"i is now {i}, day time is {times[i][0]}; temp is {times[i][1]} and time spent is {datetime.now()-dd1}")
            if times[i][1] > -2:           # it's warm
                i += 1
                continue
            cold_time = times[i][0]
            cold_val = times[i][1]
            # look at all times in the next 8 minutes for value of 20 above this one
            end_time = cold_time + timedelta(minutes = 8)

            sql = f""select created, value from monitor where parameter = '{self.PARAMETER_DEFROST}'
                                                and created between '{cold_time}' and '{cold_time + timedelta(minutes=8)}'
                                                and value >= {cold_val + 20} limit 1
                   ""
            rr = self.db.execute(sql)
            print(f"i is {i}: time spent is {datetime.now()-dd1}")
            if len(rr) > 0:
                print('found one')
                print(rr[0]['created'])
                count += 1
                i = i + 29     # can advance by about 30 mins now as minimum defrost period is 40 minutes

            "
            for j in range(i+1, len(times)):
                print(f"j is {j}: time spent is {datetime.now()-dd1}")
                if times[j][0] <= end_time:
                    #sql = f""
                    #    select value from monitor where parameter = '{self.PARAMETER_DEFROST}' and created = '{times[j][0].strftime(self.DATETIME_FMT)}' and value >= {cold_val+20}
                    #    union
                    #    select value from monitor where parameter = '{self.PARAMETER_DEFROST}' and created = '{(times[j][0]+timedelta(seconds=1)).strftime(self.DATETIME_FMT)}' and value >= {cold_val + 20}
                    #    union
                    #    select value from monitor where parameter = '{self.PARAMETER_DEFROST}' and created = '{(times[j][0]-timedelta(seconds=1)).strftime(self.DATETIME_FMT)}' and value >= {cold_val + 20}
                    #    union
                    #    select value from monitor where parameter = '{self.PARAMETER_DEFROST}' and created = '{(times[j][0]+timedelta(seconds=2)).strftime(self.DATETIME_FMT)}' and value >= {cold_val + 20}
                    #    limit 1;
                    #    ""
                    sql = f""
                        select value from monitor where parameter = '{self.PARAMETER_DEFROST}' and created between '{times[j][0] - timedelta(seconds=3)}'
                                                                                                               and '{times[j][0] + timedelta(seconds=5)}' and value >= {cold_val + 20} limit 1
                        ""
                    if len(self.db.execute(sql)) > 0:
                        print('found one')
                        print(times[j])
                        count += 1
                        #i = j + 1
                        i = j + 29     # can advance by about 30 mins now as minimum defrost period is 40 minutes
                        break
                else:
                    i = j + 1      # this might be wrong?!!
                    break
            i = i + 1
            """
        print(f"Do calculations = {datetime.now()-dd1}")

        print(f"Find defrosts = {datetime.now()-dd0}")

        Heatpump_db.calculations[calc_key] = count

        return count


    # ======== #
    # CONTROLS #
    # ======== #

    # load the control values (latest 'limit' values)
    def load_controls(self, limit = 5):

        # get latest time (last time control values were checked - and possibly updated
        latest = None
        sql = "select `time` from control_values where parameter = '99999' "

        for r in list(self.db.execute(sql)):
            latest = r['time'].strftime(self.DATETIME_FMT)

        # find the last 'n' updates

        times = []

        sql = f"select distinct `time` from control_values order by `time` desc limit 0, {limit + 1} "

        for r in list(self.db.execute(sql)):
            times.append(r['time'].strftime(self.DATETIME_FMT))
        #times.reverse()

        results = {}
        for tim in times:
            res = {}
            sql = f"select parameter, value from control_values where `time` = '{tim}' "

            for r in list(self.db.execute(sql)):
                res[r['parameter']] = r['value']

            # the data can be ignored if it's just the 'latest' update time
            if (len(res) == 1) and (tim == latest):
                pass
            else:
                results[tim] = res

        return (latest, results)

    # Returns the latest control value for an ID from what's in the database
    def control_value(self, id, with_time=False):

        val = None; tim = None

        #sql = f"select value from control_values where time = (select max(time) from control_values where parameter = '{id}');"
        sql = f"select value from control_values where parameter = '{id}' order by `time` desc limit 0,1 "
        if with_time: sql = sql.replace('select value', 'select `time`, value', 1)

        for r in list(self.db.execute(sql)):
            val = r['value']
            if with_time: tim = r['time']

        return [val, tim] if with_time else val

    # Returns the latest control value for an ID from the 'current_value' table
    def current_value(self, id, with_time=False):

        val = None; tim = None

        sql = f"select value from current_values where parameter = '{id}' "
        if with_time: sql = sql.replace('select value', 'select `time`, value', 1)

        for r in list(self.db.execute(sql)):
            val = r['value']
            if with_time: tim = r['time']

        return [val, tim] if with_time else val

    # Set the 'current value' of a parameter (local DB only)
    def current_value_update(self, id, value):

        sql = "replace into current_values (parameter, `time`, value) values (?, ?, ?) "
        self.db.execute(sql, [id, datetime.now().strftime(self.DATETIME_FMT), int(value)])

    def current_value_delete(self, id):

        sql = f"delete from current_values where parameter = '{id}' "
        self.db.execute(sql)

    """
      # fetch latest value for this Control parameter
      def control_value(parm)
        res = nil

        sql = "select value from control_values where parameter = '#{parm}' order by `time` desc limit 0,1 "

        self.myquery(sql).each{|a| res = a[:value]}

        res
      end
    """

    # set the latest Control parameter value
    def insert_control(self, parm, time, value):
        sql = "replace into control_values (parameter, `time`, value) values (?, ?, ?) "
        self.db.execute(sql, [parm, time.strftime(self.DATETIME_FMT), int(value)])

    # update a control parm time value (primary use is to update the CONTROL_PARM row)
    def update_control(self, parm, value, time):
        sql = "update control_values set time = ? where parameter = ? and value = ?  "
        self.db.execute(sql, [time.strftime(self.DATETIME_FMT), parm, int(value)])


    # ======== #
    # SCHEDULE #
    # ======== #

    def find_target(self, season, day_mask, zone, time):

        ### TODO : include 'holiday' periods which override the stuff below
        ###        e.g. select target from schedule where season = 'holiday' time between start and end
        ###        do that first and if anything, return that first;; maybe use UNION and limit 0.1 ?

        sql = f"""SELECT target FROM schedule
                   where season = '{season}' and rpad(days,7,' ') like '{day_mask}' and zone = '{zone}'
                     and ( ('{time}' between start and end)
                            !!1!!
                         ) """

        sql = sql.replace('!!1!!', '') if zone == 'W' else sql.replace('!!1!!', f"or ((start > end) and (end >= '{time}' or start <= '{time}'))")

        target = None

        for r in list(self.db.execute(sql)):
            target = r['target']

        return target

    def mysql_hhmm(self,v):
        return datetime.strftime(datetime.strptime(str(v), "%H:%M:%S"), "%H:%M")

    def load_schedule(self, season, zone):

        sql = f"""SELECT days, start, end, target FROM schedule
                  where season = '{season}' and zone = '{zone}' order by days, period, start """
        res = []

        for r in list(self.db.execute(sql)):
            # start/end come back as timedelta objects, but we want just 'hh:mm' format...
            if self.db.db_type == 'mysql':
                r['days']  = r['days'].ljust(7)
                r['start'] = self.mysql_hhmm(r['start'])
                r['end']   = self.mysql_hhmm(r['end'])
            res.append(r)

        return res

    def update_schedule(self, season, zone, days, slot, tim, target):

        # hacks for fixed days
        sdays = '11111  ' if days == 'MF' else '     11'
        itarget = float(target) * 10

        sql = "update schedule set start = ?, target = ? where season = ? and zone = ? and days = ? and period = ?  "
        self.db.execute(sql, [tim, int(itarget), season, zone, sdays, int(slot)])

        # amend 'end' of previous period to be start of this one

        prev_slot = int(slot) - 1 if slot != '1' else 5
        sql = "update schedule set end = ? where season = ? and zone = ? and days = ? and period = ?  "
        self.db.execute(sql, [tim, season, zone, sdays, prev_slot])

        return True


    # ======= #
    # TARIFFS #
    # ======= #

    # load the tariffs
    def load_tariffs(self):
        res = {}

        sql = f"""select id, current, standing_charge, description, exit_fee from tariffs
                  order by id asc """

        for r in list(self.db.execute(sql)):
            res[r['id']] = r

        return res

    def get_tariff_band(self, tariff, hr):

        sql = f"select price from tariff_bands where tariff_id = {tariff} and from_hour <= {hr} order by from_hour desc limit 0,1 "

        for r in list(self.db.execute(sql)):
            val = r['price']

        return val


    # ======== #
    # HOLIDAYS #
    # ======== #

    # load the holidays (last 3)
    def load_holidays(self, limit = 3):
        res = []

        sql = f"""select start_date, end_date, reduction, minimum from holidays
                  order by start_date asc limit 0, {limit} """

        for r in list(self.db.execute(sql)):
            r['reduction'] = r['reduction'] / 10
            r['minimum'] = r['minimum'] / 10
            res.append(r)

        return res

    # is the date passed a holiday (and it it start or end)
    def find_holiday(self, date):
        res = False
        data = False
        sql = f"""SELECT start_date, end_date, reduction, minimum FROM holidays
                   where start_date <= '{date}' and end_date >= '{date}' """

        for r in list(self.db.execute(sql)):
            res = True
            data = r

        return (res, data)

    # replaces the three dates with what's passed
    def update_holidays(self, start_dates, end_dates, reductions, minimums):
        print(start_dates)

        sql = "delete from holidays; "
        self.db.execute(sql)

        sql = "insert into holidays (start_date, end_date, reduction, minimum) values (?, ?, ?, ?) "

        for i in range(len(start_dates)):
            self.db.execute(sql, [start_dates[i], end_dates[i], int(float(reductions[i]) * 10), int(float(minimums[i]) * 10)])


    # ======== #
    # COMMANDS #
    # ======== #

    # load the latest commands (latest 'limit' values)
    def load_commands(self, limit = 50):
        res = []

        sql = f"""select id, created, command, not_before, not_after, retry, status, executed, result, `values` from commands
                  order by created desc limit 0, {limit} """

        for r in list(self.db.execute(sql)):
            r['parameter'], r['value'] = r['values'].split(';')[0].split(',')
            res.append(r)

        #res.reverse()
        return res

    # fetch un-executed commands
    def fetch_commands(self):
        res = []

        sql = "select id, created, command, not_before, not_after, retry, `values` from commands where status = -1 order by created asc "

        for r in list(self.db.execute(sql)):
            r['created'] = r['created'].strftime(self.DATETIME_FMT)
            r['parameter'], r['value'] = r['values'].split(';')[0].split(',')
            res.append(r)

        return res

    # insert control commands : values is a list of items like "21 01,450" meaning set '21 01' to 450
    def insert_commands(self, values, not_before=None, not_after=None, retry='N'):
        # sql = "insert into commands (created, command, parameter, value, status) values (?, ?, ?, ?, ?) "
        # self.db.execute(sql, [datetime.now().strftime(self.DATETIME_FMT), 'UPDATE', parameter, int(value), -1])
        sql = "insert into commands (created, command, not_before, not_after, retry, status, `values`) values (?, ?, ?, ?, ?, ?, ?) "
        self.db.execute(sql, [datetime.now().strftime(self.DATETIME_FMT), 'UPDATE', not_before, not_after, retry, -1, ';'.join(values)])

    # amend a control command entry
    def update_commands(self, id, status, time, result):
        sql = "update commands set status = ?, executed = ?, result = ? where id = ?  "
        self.db.execute(sql, [int(status), time.strftime(self.DATETIME_FMT), result, int(id)])

    # set status of a command to 'Queued', if it was 'Added'; return 1/True if it was updated, else 0/False
    def update_command_queued(self, id):
        sql = "update commands set status = ? where id = ? and status = -1 "
        changes = self.db.execute(sql, [-2, id])
        return changes


    # =========== #
    # COLLECTIONS #
    # =========== #

    # load the set of collections
    def load_collections(self):
        res = []

        sql = "select id, description, parameters from collections order by id"

        for r in list(self.db.execute(sql)):
            r['parameters'] = r['parameters'].split(',')
            res.append(r)

        return res

    # ==== #
    # USER #
    # ==== #

    INVALID_LIMIT = 3

    def usersettings(self, user):
        resp = None
        sql = f"select * from users where user = '{user}' "

        for r in list(self.db.execute(sql)):
            resp = r

        return resp

    # return user secure hash
    def usershash(self, user):
        resp = None
        sql = f"select shash from users where user = '{user}' and invalid_pwd < {self.INVALID_LIMIT}"

        for r in list(self.db.execute(sql)):
            resp = r['shash']

        return resp

    def userinvalidpwdinc(self, user):
        sql = f"update users set invalid_pwd = invalid_pwd +1 where user = '{user}'"
        self.db.execute(sql)

        sql = f"select invalid_pwd from users where user = '{user}'"

        count = 0
        for r in list(self.db.execute(sql)):
            count = r['invalid_pwd']

        return count

    # update user stored hash
    def updateusershash(self, user, hash):
        sql = "update users set shash = ? where user = ?"
        self.db.execute(sql, [hash, user])

    def resetinvalidpwd(self, user):
        sql = "update users set invalid_pwd = 0 where user = ?"
        self.db.execute(sql, [user])

    # add new user stored hash
    def adduser(self, user, hash):
        sql = "insert into users values (?, 0, '', ?)"
        self.db.execute(sql, [user, hash])


    # ======= #
    # SESSION #
    # ======= #

    def insertsession(self, user, session, message):
        data = {}
        sql = "replace into sessions values (?, ?, ?, '2023-01-01 09:00:00', ?)"
        self.db.execute(sql, [user, session, message, pickle.dumps(data)])

    def updatesession(self, user, session, message):
        sql = f"update sessions set message_id = '{message}' where user = '{user}' and session_id = '{session}'"
        self.db.execute(sql)

    def checksession(self, user, session, message):
        sql = f"select message_id from sessions where user = '{user}' and session_id = '{session}'"

        msg = 'z'
        for r in list(self.db.execute(sql)):
            msg = r['message_id']

        print('in check session')
        print(f"message_id in db is {msg}")
        print(f"message_id in session is {message}")

        return (msg == message)

    def readsessiondata(self, user, session):
        sql = f"select data from sessions where user = '{user}' and session_id = '{session}'"

        msg = ''
        for r in list(self.db.execute(sql)):
            msg = r['data']

        data = pickle.loads(msg) if msg != '' else {}
        return data

    # update session data
    def updatesessiondata(self, user, session, hash):
        sql = "update sessions set data = ? where user = ? and session_id = ? "
        self.db.execute(sql, [pickle.dumps(hash), user, session])


"""
  # remove sessions
  def deletesessions(from)
    sql = "delete from sessions where last_message < '#{from}'"
    @dbh.query(sql)
  end

  # tidy sessions
  def clean(from)
    @dbh.connect
    @dbh.deletesessions(from)
  end
"""

if __name__ == "__main__":

    x = Heatpump_db()
    """
    d = input("Enter date to find performance:")
    z = x.performance(d)
    print(z)
    """
    d = input("Enter date for monitor step:")
    z = x.monitor_step(d)
    print(z)
    #d = input("Enter date to get defrost count:")
    #s = x.defrost_count(d)
    #print(s)
    """
    d = input("Enter date to get monitor data:")
    d = datetime.strptime(d, '%Y-%m-%d')
    dd = x.get_monitor(d, d, 'X', 'X', ['01 00', '01 03', '11 00', '11 09', '01 06'])
    print(len(dd))
    """
    """
    d = input("Enter date and range for scop:")
    d = datetime.strptime(d, "%Y-%m-%d")
    #print(x.performance_set(d, day_range=30))
    print(x.find_scop(d, month_range=1))
    print(x.find_scop(d, month_range=3))
    print(x.find_scop(d, month_range=6))
    print(x.find_scop(d))
    """
    d = input("Enter date to rebuild thermistor data:")
    x.rebuild_thermistor_data(d)
    #d = input("Enter date to rebuild monitor data:")
    #x.rebuild_monitor_day(d)
    d = input("Enter date to rebuild monitor_data for day:")
    x.rebuild_monitor_data_day(d)
    #x.rebuild_monitor_data("2023-06-04 21:40:05")  <<<< now needs to be a datetime!

    #y = x.get_monitor("2026-01-06 00:00", "2026-01-06 23:59", 'X', '17:00', ['01 06', '01 09'] )
    #print(y[0:2])
    #print(y[-2:])
    #print(len(y))

