from app import app

from datetime import datetime, timedelta
from ipaddress import ip_address
import csv
import json
import redis
import time
import yaml

from flask import abort, redirect, render_template, request, send_file, url_for
from flask import Flask
from flask import g
from flask import session
from markupsafe import Markup

from . import controller as co
from . import control_settings as cs
from . import current_temp as ct
from . import pump_value as pv
from . import query_mysql as db
from . import session as mysession
from . import temperature as tp
from . import user as u

#app = Flask(__name__)
#app.secret_key = b'hsheatpumphs'

## FIXME!  Where should this be defined?
ENERGY_PARAMETER = '01 03'
SPECIFIC_HEAT_CAPACITY = 4.2
USE_ALT = True                  # Whether we use the built-in LWT/RWT values or the thermal probes in loft
PARAMETER_LWT = '01 09'
PARAMETER_LWT_ALT = '11 09'
PARAMETER_RWT = '01 00'
PARAMETER_RWT_ALT = '11 00'
PARAMETER_EOUT = '99 10'
#               energy    RWT      LWT    energy_out
SMOOTH_PARMS = ['01 03', '01 00', '01 09', '99 10']
#SMOOTH_PARMS = []
#
COMMAND_STATUS = {
    4  : 'Suppressed',
    0  : 'Success',
    -1 : 'Added',
    -2 : 'Queued',
    -3 : 'Not due yet',
    -4 : 'Time passed',
    -10:'Failed:10',
    -11:'Failed:11'
}

# aggregate values over n days
def aggregate(vals, days, parm, smooth):
    if days < 2:

        if (not smooth) or (not parm in SMOOTH_PARMS):
            return vals

        # average each value over 'rrange' adjacent values - set to 2 either side i.e. 5 values in total

        rrange = 5    # how wide we'll look at values around current one (this means 2 either side)

        start_ave = sum(vals[0:rrange]) / rrange   # filler values either side based on simple average
        end_ave = sum(vals[-rrange:]) / rrange

        v2 = [start_ave] * (rrange - 1)
        v2.extend(vals)                         # build a slightly larder array so the calculation is simple
        v2.extend([end_ave] * (rrange - 1))

        scope = (rrange - 1) * 2 + 1
        v3 = []
        for i in range(0, len(v2)-scope+1):
            v = v2[i:i+scope]
            v3.append( sum(v) / scope )

        return v3

    else:
        values = []
        periods = (len(vals) // days) * days
        for i in range(0, periods, days):
            ssum = 0
            for j in range(i, i+days):
                ssum += vals[j]
            values.append(ssum / days)

        return values

# Check date is no greater than 'now'; if it is, set it to now
def verify_date(dat, now):
    return now if dat > now else dat

# Convert ' ' to a non-breaking space
@app.template_filter()
def space_nbsp(value):
    return Markup(value.replace(' ', '&nbsp;').replace(',', '&rArr;'))

# A None value returns 'N/A' else format as 00000.00
@app.template_filter()
def perf_figure(value):
    if value is None:
        return 'N/A'
    else:
        return "%05.02f" % value

# Parameter type display
@app.template_filter()
def parm_show(value, type):
    if type == 'type':
        return value.capitalize()
    elif type == 'monitor':
        return {'Y':'Yes', 'N':'No', 'C':'Control'}[value]
    else:
        return value

# COP display
@app.template_filter()
def cop_show(input, output):
    if not input:
        return 'N/A'
    return "%3.02f" % (output / input )

# Command status - convert number status to word
@app.template_filter()
def status_show(status):
    return COMMAND_STATUS[status]

@app.before_request
def before_anything():
    g.dbh = db.Heatpump_db()

    """
    print(request.path)
    all = {}
    x = request.values
    if x: all.update(dict([k, x[k]] for k in x))
    if x := request.headers.get('Content-Type', '') == 'application/json':
        all.update(request.json)
    print(all)
    """

    ## TEMP (hopefully!) if (request.path != '/logon') and (request.path[0:8] != '/static/'):
    if (request.path[0:6] != '/logon') and (request.path[0:8] != '/static/') and (request.path[0:5] != '/ws/t'):
        if '_tudcS' in session:
            g.username = session['user']
            g.session = mysession.Session(user = g.username, session = session['_tudcS'], dbh = g.dbh)
            if not g.session.valid(session['_tudcM']):
                abort(401)
            # retrieve secure session data
            g.ssession = g.session.data()
        else:
            return redirect(url_for('logon_get'))

@app.after_request
def after_everything(resp):
    if 'session' in g:
        if 'ssession' not in g: g.ssession = g.session.data()   # hopefully fixes comment two below!
        #print(g.ssession)
        #g.ssession = g.session.data()         #  <<<<< why is this needed? first time on a new site???
        #print(g.session.data())
        g.session.trail()
        session['_tudcM'] = g.session.message_id
        g.session.update(g.ssession)

    ##if 'dbh' in g: g.dbh.close()

    return resp


@app.get("/")
def main():
    return redirect("/monitor")

@app.get("/monitor")
def monitor():
    page = 'monitor'

    g.parameters = pv.Pump.load_parameters()
    collections = g.dbh.load_collections()
    #params = request.values
    g.params = request.form.to_dict(flat=False)

    if 'performance_date' in request.values:
        g.params['range1'] = request.values['performance_date']
        g.params['range2'] = request.values['performance_date']
        g.params['parms'] = g.ssession['parms']
    else:
        for k in ['parms', 'range1', 'range2']:
            if k in g.ssession:
                g.params[k] = g.ssession[k]

    if 'range1' not in g.params:
        g.params['range1'] = datetime.now().strftime('%Y-%m-%d')
        g.params['range2'] = datetime.now().strftime('%Y-%m-%d')
        g.params['parms'] = ['01 00']

    return render_template('monitor.html', title='Monitor', page=page, collections=collections)

@app.get("/control%20values")
def control():
    page = 'control values'

    g.parameters = pv.Pump.load_parameters()
    controls = [vals for id, vals in g.parameters.items() if (vals['monitor'] == 'C')]

    latest, values = g.dbh.load_controls(limit=10)

    ctrls = cs.ControlSettings(fine=True)
    wc_vals = ctrls.wcc_range('1')

    return render_template('control.html', title='Control Values', page=page, latest=latest, controls=controls,
                                           values=values, exts=wc_vals.keys(), lwts=wc_vals.values())

@app.get("/wcc")
def wcc():
    #### NOT USED !!!!!
    page = 'wcc'

    x = cs.ControlSettings(fine=True)
    zz = x.wcc_range('1')

    return render_template('wcc.html', exts=zz.keys(), lwts=zz.values(), title='Weather Compensation Curve', page=page)

@app.get("/parameters")
def parameters():
    page = 'parameters'

    g.parameters = list(pv.Pump.load_parameters().values())
    return render_template('parameters.html', title='Parameters', page=page)


@app.get("/performance")
def performance():
    DEFAULT_PERIOD = 180
    page = 'performance'

    endd = datetime.now()
    endd = endd.replace(hour=0, minute=0)
    dat = endd - timedelta(days = 1)   # 'start' at yesterday

    # 'Download', downloads all of the data
    if 'download' in request.values:

        start = datetime(2023, 6, 4)   # first date

        data = g.dbh.performance_set(dat, (dat-start).days)

        with open('app/tmp/performance.csv', 'w') as f:

            csv_file = csv.writer(f)
            csv_file.writerow(['DATE','IN','OUT','COP','AOOT','OAT','STD','IAT'])
            csv_file.writerows([a.values() for a in data])

        return send_file('tmp/performance.csv', download_name=f"performance_{datetime.now().strftime('%Y%m%d')}.csv")

        ## as_attachment (bool) – Indicate to a browser that it should offer to save the file instead of displaying it.

    p0 = datetime.now()

    start_date = endd.strftime('%Y-%m-%d')

    scop = [g.dbh.find_scop(dat, month_range=1),
            g.dbh.find_scop(dat, month_range=3),
            g.dbh.find_scop(dat, month_range=6),
            g.dbh.find_scop(dat)]

    scop_str = []
    for s in scop:
        scop_str.append( str( round(s,2) ) )
    scop_str = '/'.join(scop_str)

    p1 = datetime.now()
    print(f"Gather all data = {p1 - p0}")

    data = [{'date': start_date, 'I': 1, 'O': 1}]

    return render_template('performance.html', title='Performance', data=data, page=page, scop = scop_str, default_period = DEFAULT_PERIOD, today=start_date)

@app.get("/ws/performance")
# 'start', '2025-02-28'), ('period', '30'), ('direction', 'back')])
def ws_performance():
    page = 'performance'

    first_date = datetime(2023, 6, 4)

    period = int(request.values['period'])

    endd = datetime.strptime(request.values['start'], "%Y%m%d")

    if request.values['direction'] == 'back':
        endd = endd - timedelta(days=1)
        if endd < first_date: endd = first_date
    elif request.values['direction'] == 'forward':
        endd = endd + timedelta(days=(period+1))
        if endd > datetime.now(): endd = datetime.now()

    start = endd - timedelta(days=period)
    if start < first_date: start = first_date

    print(f"start = {start}")
    print(f"endd  = {endd}")
    print(f"perid = {period}")
    data = g.dbh.performance_set(endd, (endd-start).days)

    ##return render_template('performance_table.html', title='Performance', page=page, data=data, today=datetime.now().strftime('%Y-%m-%d'))
    return render_template('performance_table.html', title='Performance', page=page, data=data, today=datetime.now().date())

## all this stuff should be elsewhere!! FIXME
import itertools
def to_ranges(iterable):
    for key, group in itertools.groupby(enumerate(iterable),
                                        lambda t: t[1] - t[0]):
        group = list(group)
        yield group[0][1], group[-1][1]+1

@app.get("/performance/cost")
def performance_cost():
    from calendar import monthrange

    page = 'performance'
    sub_page = 'cost'

    tariffs = g.dbh.load_tariffs()
    tariff = list(a['id'] for a in tariffs.values() if a['current'] == 'Y')[0]
    tariffs[tariff]['description'] += "  (current tariff)"

    if 'tariff' in request.values:
        tariff = int(request.values['tariff'])
        year   = int(request.values['year'])
    else:
        year = datetime.now().year - 1

    standing = tariffs[tariff]['standing_charge']
    description = tariffs[tariff]['description']

    start = datetime(year, 1, 1)
    endd = datetime(year, 12, 31)

    costs = []
    groups = {}

    total_cost = 0
    for hr in range(24):

        cost = g.dbh.get_tariff_band(tariff, hr)
        total_cost += cost
        costs.append(cost)

        if cost in groups.keys():
            groups[cost].append(hr)
        else:
            groups[cost] = [hr]

    cost_avg = total_cost / 24

    tou = min(costs) != max(costs)

    if tou:
        grouped = dict( (k, list(to_ranges(v))) for k,v in groups.items() )
        output = []
        for rate, hours in grouped.items():
            part = []
            for h in hours:
                part.append(f"{h[0]}-{h[1]}")
            output.append(f"<b>{rate/10000}p</b> ({','.join(part)})")

        output = "Unit costs: " + '; '.join(output)
    else:
        output = f"Unit cost: {costs[0]/10000}p."

    overall_energy = 0
    overall_cost = 0
    overall_st = 0
    overall_total = 0

    figures = []

    dat = start
    while dat < endd:
        total = 0
        kwh_total = 0

        str_dat = dat.strftime('%Y-%m-%d')
        print(str_dat)

        now = datetime.now()
        if (dat.year == now.year) and (dat.month == now.month):
            minutes = g.dbh.monitor_step(str_dat)

            all_hours = g.dbh.find_aggregate_month(now.year, dat.month)
            print(all_hours)
            print(minutes)

            for r in all_hours:
                cost = costs[r['hr']]
                kwh = float(r['total']) / (600 / minutes)
                kwh_int = round(kwh * 100)
                price = cost * kwh_int
                total += price
                kwh_total += kwh_int

        else:
            for hr in range(24):
                cost = costs[hr]
                kwh = g.dbh.get_aggregate(year, dat.month, hr)
                price = cost * kwh
                total += price
                kwh_total += kwh

        st_charge = (standing * monthrange(year, dat.month)[1])
        figures.append({'month':dat.strftime('%B'), 'energy': kwh_total, 'cost': total / 1000000,
                        'standing': st_charge / 10000, 'total': (total / 1000000)+(st_charge / 10000)})

        overall_energy += kwh_total
        overall_cost += total
        overall_st += st_charge
        overall_total += total + (st_charge * 100)

        dat += timedelta(days=32)
        dat = dat.replace(day=1)

    figures.append({'month': 'Heat Pump Total', 'energy': overall_energy, 'cost': overall_cost / 1000000,
                    'standing': overall_st / 10000, 'total': overall_total / 1000000})

    # Add on a (fixed) non Heat Pump cost
    non_hp_kwh = 220000
    non_hp_cost = (non_hp_kwh * cost_avg) / 1000000

    figures.append({'month': 'Non Heat Pump', 'energy': non_hp_kwh, 'cost': non_hp_cost,
                    'standing': 0, 'total': non_hp_cost})

    figures.append({'month': 'TOTAL', 'energy': (overall_energy + non_hp_kwh), 'cost': (non_hp_cost + (overall_cost / 1000000)),
                    'standing': overall_st / 10000, 'total': (non_hp_cost + (overall_total / 1000000)) })

    return render_template('performance_cost.html', output=output, tariffs=tariffs, costs=figures, tariff=tariff, year=year, nextyear=datetime.now().year + 1,
                           title='Cost', page=page)

@app.get("/controller")
def schedule():
    page = 'controller'

    with open("./app/thermometers.yaml", "r") as file:
        therms = yaml.safe_load(file.read())

    thermometers = []

    for key, v in therms.items():

        if v['show'] == 'no': continue

        h = ct.Current_Temperature().details(key)

        h.update({'id': key, 'name': v['name']})

        #if v['name'] =='Main Control':
        #    master = h
        #elif v['show'] == 'yes':
        #    thermometers.append(h)
        thermometers.append(h)

    master = tp.Temperature('inside', zone=1).value()/10        # inside zone 1 temperature

    if 'selected_season' in request.values:
        season = request.values['selected_season']
    else:
        season = 'summer' if (time.localtime(int(datetime.now().timestamp())).tm_isdst > 0) else 'winter'

    hw = g.dbh.load_schedule(season, 'W')
    hw_legionella = list(a for a in hw if len(a['days'].strip()) == 1)[0]
    hw_normal     = list(a for a in hw if len(a['days'].strip()) != 1)[0]

    holidays = g.dbh.load_holidays()

    jan_1 = datetime(datetime.now().year, 1, 1).strftime('%Y-%m-%d')
    for x in range(3 - len(holidays)):
        holidays.append( {'start_date': jan_1,'end_date': jan_1,'reduction': 2,'minimum': 16} )

    switches = {}
    for mode in [co.Controller.MODE_CH, co.Controller.MODE_DHW]:
        switches[mode] = co.Controller().SwitchStatus(mode)

    return render_template('schedule.html', title='Central Heating Schedule', page=page, master=master, season=season, switches=switches,
                           holidays=holidays, thermometers=thermometers, hw_legionella=hw_legionella, hw_normal=hw_normal)

@app.get("/commands")
def commands():
    page = 'commands'

    commands = g.dbh.load_commands(limit=75)
    return render_template('commands.html', title='Commands', page=page, commands=commands)

@app.get("/blinds")
def blinds():
    page = 'blinds'

    with redis.Redis(db=15, decode_responses = True) as r:
        state = r.get('BLIND:STATE')

    import subprocess
    proc = subprocess.Popen(['tail', '-50', '/var/log/switchbot.log'], stdout=subprocess.PIPE, text=True)
    log = ''.join(proc.stdout.readlines())

    return render_template('blinds.html', title='Blinds', page=page, state=state, log=log)


@app.get("/ws_monitor")
def ws_monitor():
    p1 = datetime.now()

    """ Returns a dictionary of:
                  Dates:    date range to display
                  Datasets: the data to show
                  Ticks:    how many x-axis ticks there should be
                  Energy:   summary of energy consumption (only if power usage in requested list of parameters)
                  Performance: energy_out, in, cop
    """
    g.parameters = pv.Pump.load_parameters()

    p1a = datetime.now()

    # store the input parameters in the session data
    g.ssession['parms'] = request.args.getlist('parms[]')
    g.ssession['range1'] = request.values['range1']
    g.ssession['range2'] = request.values['range2']
    g.ssession['time1'] = request.values['time1']
    g.ssession['time2'] = request.values['time2']

    time1 = request.values['time1']
    time2 = request.values['time2']

    now = datetime.now().strftime('%Y-%m-%d')
    range1 = verify_date(request.values['range1'], now)
    range2 = verify_date(request.values['range2'], now)

    range1 = datetime.strptime(range1 + ' 00:00:00', "%Y-%m-%d %H:%M:%S")
    range2 = datetime.strptime(range2 + ' 23:59:59', "%Y-%m-%d %H:%M:%S")

    smoothing = (request.values['smoothing'] == 'Y')

    p1d = datetime.now()

    # identify the granularity of monitoring records
    monitor_minutes = g.dbh.monitor_step(request.values['range1'])

    p1e = datetime.now()

    # Removed on 12/1/26 and it takes us to the next day - now?!
    # if there's a time range, make sure they don't have 'gaps' by shifting the start a bit
    #if time1 != 'X':
    #    range2 += timedelta(minutes=monitor_minutes)
    #else:
    #    range1 += timedelta(minutes=1)

    if range1 > range2:
      range1, range2 = range2, range1

    prms = request.args.getlist('parms[]')

    datasets = []

    # if 'energy' asked for, include LWT and RWT if not already in the list

    parameter_lwt = PARAMETER_LWT_ALT if USE_ALT else PARAMETER_LWT
    parameter_rwt = PARAMETER_RWT_ALT if USE_ALT else PARAMETER_RWT
    factor = 0.1 if USE_ALT else 1    # FIXME

    db_prms = prms.copy()
    #if (request.values['energyflag'] == 'Y') and (ENERGY_PARAMETER in prms):
    if (PARAMETER_EOUT in prms):
        for eprm in [parameter_lwt, parameter_rwt]:
            if eprm not in prms: db_prms.append(eprm)

    p2 = datetime.now()

    if prms is not None:
      data = g.dbh.get_monitor(range1, range2, time1, time2, db_prms)
      #print('data returned =')
      #print(len(data))
    else:
      data = []
      # params['parms'] = ['01 00']
    #print('data:')
    #print(data[0:4])

    p3 = datetime.now()

    # add to the data a value for 'energy out' if it was requested

    if (PARAMETER_EOUT in prms):
        # find konstant to convert deltaT to energy for this date (assumes same flow throughout range)
        k = (g.dbh.flow_rate(request.values['range1']) * SPECIFIC_HEAT_CAPACITY) / 6
        ##k = 1000 * (k / (60/monitor_minutes))
        print(f"k = {k}")

        lwt_vals = list(r['value'] * factor for r in data if r['parameter'] == parameter_lwt)
        rwt_vals = list(r['value'] * factor for r in data if r['parameter'] == parameter_rwt)
        ein_vals = list(r['value'] for r in data if r['parameter'] == ENERGY_PARAMETER)
        ### if the line below is barfing it's cos 01 03 must be shown as well if Power Out.  ::: TODO FIX? See Above!
        e_out = list( round(((lwt_vals[i] - rwt_vals[i]) * k), 2) if ((ein_vals[i] > 0) and (lwt_vals[i] > rwt_vals[i])) else 0 for i in range(0,len(lwt_vals)) )
        ####e_out = list( round(((lwt_vals[i] - rwt_vals[i]) * k), 2) for i in range(0,len(lwt_vals)) )
        parm = PARAMETER_EOUT
        values = aggregate(e_out, (range2 - range1).days, parm, smoothing)
        result = {'Id': parm, 'Parameter': g.parameters[parm]['description'], 'Colour': g.parameters[parm]['colour'],'Values': values}
        datasets.append(result)
        prms.remove(PARAMETER_EOUT)

        # Added 27/2/26: If power_out, also add COP
        cop_out = list( round((e_out[i] / ein_vals[i]), 2) if (ein_vals[i] > 0) else 0 for i in range(0,len(e_out)) )
        temps = [a for a in cop_out if a != 0]
        avg_cop = sum(temps)/len(temps)
        print(f"Alternative COP is {avg_cop}")
        #parm = PARAMETER_EOUT
        #values = aggregate(e_out, (range2 - range1).days, parm, smoothing)
        result = {'Id': 'COP', 'Parameter': 'Moment COP', 'Colour': 'black', 'Values': cop_out}
        datasets.append(result)

    day_range = ( (range2+timedelta(minutes=monitor_minutes)) - range1 ).days
    #print(f"Day_range = {day_range}")
    #print(f"Day_range2 = {(range2 - range1).days}")

    results = {}

    # collate by parameter, the list of dates and values

    p4 = datetime.now()

    max_dates = 0
    dates = None
    for parm in prms:
        pump = pv.Pump(parm)
        values = list(pump.value(r['value']) for r in data if r['parameter'] == parm )
        # FIX applied 2/2/26 - use day_range
        ##values = aggregate(values, (range2 - range1).days, parm, smoothing)
        values = aggregate(values, day_range, parm, smoothing)
        ##max_dates = max( [max_dates, len(dates)] )
        result = {'Id': parm, 'Parameter': g.parameters[parm]['description'], 'Colour': g.parameters[parm]['colour'],'Values': values}
        datasets.append(result)

        # gets the dates from the first parameter, whichever this is...
        if dates is None:
            dates = list(r['created'] for r in data if r['parameter'] == parm )
            if day_range > 1:
                a_dates = []
                for i in range(0, len(dates), day_range):
                    a_dates.append(dates[i])
            else:
                a_dates = dates

            dates = list(r.strftime('%a %d %b %H:%M') for r in a_dates)

            results['Dates'] = dates

    p5 = datetime.now()

    # This was to pad for missing data : ignored for now as that doesn't really happen any longer
    ##for res in datasets:
    ##    diff = max_dates - len(res['Values'])
    ##    if diff > 0:
    ##        res['Values'] = ([0] * diff) + res['Values']

    results['Datasets'] = datasets

    # TODO ;;; and better!!!
    #params['parms'].each do |key|
    #  if split[key].nil? then
    #    split[key] = [{:created => @range1, :parameter => key, :value => 0}]
    #  end
    #end

    # Find days range, and set number of ticks to 24 or 36 based on that

    ticks = 24 if (day_range % 2) else 36
    ticks = 24 if (day_range == 0) else ticks
    if monitor_minutes == 5: ticks += 1

    results['Ticks'] = ticks

    # If the output includes the energy consumption, add some summary figures to show

    p6 = datetime.now()

    if (day_range == 1) and (ENERGY_PARAMETER in prms):

        #energy = g.dbh.load_power(range1.strftime('%Y-%m-%d'), range2.strftime('%Y-%m-%d'))
        # Changed 25/11/24, to exclude the 'pump only' periods of 100W which runs as Frost protection
        #energy = g.dbh.load_power(g.ssession['range1'], g.ssession['range2'])
        energy = g.dbh.load_power(g.ssession['range1'], g.ssession['range2'], limit = 1)

        areas = []

        range_start = None
        i = 0
        j = 0
        while i < (len(energy) - 1):

            if range_start is None: range_start = i

            if range_start is not None:
                #print(f"starting to total period from {energy[range_start]}")
                total = energy[i]['value']
                for j in range(i + 1, len(energy)):
                    #print(f"considering {energy[j]}")
                    if (energy[j]['created'] - energy[i]['created']) < timedelta( minutes = (day_range * 5) + 1 ):
                        total += energy[j]['value']
                        i += 1
                    else:
                        size = j - range_start
                        ## # select a date 'halfway' through this area, but also must exist in 'dates'
                        ## proportion = (range_start + size/2) / len(energy)
                        ## midpoint_date = dates[int( proportion * len(dates) )]
                        ## areas.append([size, midpoint_date, total])
                        areas.append([size, energy[range_start + size//2]['created'].strftime('%a %d %b %H:%M'), total])
                        range_start = None
                        i += 1
                        break

        if range_start is not None:
            size = j - range_start
            areas.append([size, energy[range_start + size//2]['created'].strftime('%a %d %b %H:%M'), total])

        results['Energy'] = areas

    p7 = datetime.now()

    # performance

    perf = {'out': 'N/A', 'in': 'N/A', 'cop': 'N/A'}

    totals = {'I': 0, 'O': 0}; count = 0
    dat = range1
    while day_range > 0:    ## FIXME !
    ##while dat < range2:

        values = g.dbh.performance(dat.strftime('%Y-%m-%d'))

        if (values['I'] is not None) and (values['O'] is not None):
            totals['I'] += values['I']; totals['O'] += values['O']; count += 1

        dat += timedelta(days = 1)
        day_range -= 1

    p8 = datetime.now()

    if count > 0:
        perf = {'out': "%05.02f" % totals['O'], 'in': "%05.02f" % totals['I']}
        perf['cop'] = round((totals['O'] / totals['I']), 2)

    results['Performance'] = perf

    p9 = datetime.now()

    print(f"{p1} START TIME")
    print(f"{p1a} - setup #1")
    print(f"{p1d} - setup prior to call database for monitor step")
    print(f"{p1e} - setup #2")
    print(f"{p2} To initially set up parameters = {p2 - p1}")
    print(f"{p3} To retrieve from database      = {p3 - p2}")
    print(f"{p4} To start of collate/aggregate  = {p4 - p3}")
    print(f"{p5} Time for collate/aggregate     = {p5 - p4}")
    print(f"{p7} Calculating energy usage       = {p7 - p6}")
    print(f"{p8} Calculating performance        = {p8 - p7}")
    print(f"{p9} Total time on server           = {p9 - p1}")

    return results

@app.get("/ws_updates")
def ws_updates():
    """ Returns a dictionary of:
                  Temperatures:    temperature by thermometer id
                  Schedule:        schedule being followed
                  Heating:         true/false
    """

    results = {}

    # temperatures
    with open("./app/thermometers.yaml", "r") as file:
        therms = yaml.safe_load(file.read())

    thermometers = []

    ####  FIXME - duplicated code (see above)

    for key, v in therms.items():

        if v['show'] == 'no': continue

        h = ct.Current_Temperature().details(key)

        #if v['name'] == 'Main Control':
        #    results['Schedule'] = h
        #elif v['show'] == 'yes':
        #    h['id'] = key
        #    thermometers.append(h)
        h['id'] = key
        thermometers.append(h)

    results['Temperatures'] = thermometers

    results['Master'] = tp.Temperature('inside', zone=1).value()/10

    # schedule

    season = request.values['selected_season'].lower()

    results['Schedule'] = {}
    results['Schedule']['zones'] = []
    for zone in ['1','2']:
        schedule = g.dbh.load_schedule(season, zone)

        monfri = list([a['start'][0:5], a['target']] for a in schedule if a['days'] == '11111  ')
        satsun = list([a['start'][0:5], a['target']] for a in schedule if a['days'] == '     11')

        results['Schedule']['zones'].append({'times_weekday': monfri, 'times_weekend': satsun})

    # heating

    with redis.Redis(decode_responses = True) as r:
        results['Heating'] = r.get('Schedule:Heating')
        results['Schedule']['target1'] = r.get('Schedule:Target:1')
        results['Schedule']['target2'] = r.get('Schedule:Target:2')
        results['Schedule']['zones_active'] = r.get('Schedule:Zones')
        results['Schedule']['holiday'] = r.get('Schedule:Holiday')

        #last_monitor = r.get(pv.Pump.LAST_CREATED)
        #key = f"{pv.Pump.MONITOR_STORE}:{last_monitor}"
        #values = dict(json.loads(r.get(key)))
        #results['Schedule']['oat'] = values['01 06']
        results['Schedule']['oat'] = tp.Temperature('outside').value() / 10    # FIXME - should use someinthg to divide by 10

    return results

@app.post("/ws_switch_updates")
def ws_switch_updates():
    # type: ch/dhw  result: true/false  ---- in this instance 'true' means "disable" i.e. it reflects the truth of the disabled state
    c = co.Controller()
    mode = request.values['type'].upper()
    if request.values['result'] == 'false':
        c.Enable(mode)
    elif request.values['result'] == 'true':
        if mode == 'DHW':                    # actually turn the circuit off
          from . import dhw_controls as dh
          dh.DHW_Controls(cs.ControlSettings(), c).set_dhw('off')
        elif mode == 'CH':
          from . import ch_controls as ch
          ch.CH_Controls('1', cs.ControlSettings()).set_ch('off',force=True)
        c.Disable(mode)                      # This has to happen second, as it will disable any attempts to change the circuits!

    res = c.SwitchStatus(mode)
    res = 'false' if res == co.Controller.ON else 'true'
    return {'type': request.values['type'], 'result': res}

@app.post("/ws_update_parms")
def ws_update_parms():
    # {'id': '01&nbsp;03', 'colour': 'brown', 'description': 'Current consumption value'}
    # update parameter with values (crudely)
    g.dbh.update_parameter(request.values['id'], request.values['description'], request.values['colour'])
    return redirect("/parameters")

@app.post("/ws_update_schedule")
def ws_update_schedule():
    # update parameter with values (crudely)
    g.dbh.update_schedule(request.values['season'],request.values['zone'],request.values['days'],request.values['slot'],request.values['time'], request.values['target'])
    return redirect(f"/controller?selected_season={request.values['season']}")

@app.post("/ws_update_holidays")
def ws_update_holidays():
    # update holidays with list of values passed (always updates just 3 holidays)
    # startdate[]: ; enddate[]: ; reduction[]; minimum[]:
    x = request.form.to_dict(flat=False)
    start_dates = x['startdate[]']
    end_dates = x['enddate[]']
    reductions = x['reduction[]']
    minimums = x['minimum[]']
    g.dbh.update_holidays(start_dates, end_dates, reductions, minimums)
    return redirect("/controller")

@app.get("/ws/t/dhw_boost")
def dhw_boost():
    # triggered by long-press on button
    # - if active, deactivate; if inactive, activate, if last time more than 30 minutes ago
    print(f"{datetime.now()} DHW boost pressed.")

    c = co.Controller()
    from . import dhw_controls as dh
    dh.DHW_Controls(cs.ControlSettings(), c).set_boost()

    return 'OK'

# Change blind position - maybe # TODO All temp I think
@app.get("/ws_blind")
def ws_blind():
    import subprocess
    x = request.values['state']
    response = subprocess.run(['/var/www/heatpump/.venv312/bin/python', './switchbot/blind_control.py', x], stdout=subprocess.PIPE).stdout.decode('utf-8')
    print(response)
    return 'OK'

# return lists of thermometers
@app.get("/ws/thermometers")
def ws_thermometers():
    with open("./app/thermometers.yaml", "r") as file:
        thermometers = yaml.safe_load(file.read())
    return thermometers

# return local thermometer values as a JSON string
@app.get("/ws/temperature/<key>")
def ws_temperature_local(key):
    h = ct.Current_Temperature().details(key)

    # we need to stop Flask from returning the datetime object as an ISO 8601 time, so....
    h['time'] = h['time'].strftime('%Y-%m-%d %H:%M:%S')
    return h

# POSTed data from a Shelly device, being used to capture BLE from remote(r) swithbot thermomters.
# - this is a hack of code from ble_async.py FIXME  
@app.post("/ws/t/ble/<key>")
def ble_broadcast(key):
    #print(request.remote_addr)
    #print('---------------')

    if not ip_address(request.remote_addr).is_private: abort(400)

    import base64

    if 'govee' in request.json:
        base64_string = request.json['govee']
        base64_bytes = base64_string.encode("ascii")
        value = base64.b64decode(base64_bytes)        # passed a JSON string base64 encode of manufacturer data, key EC88

        packet = int(value[1:4].hex(), 16)
        temp = float(int(packet / 1000) / 10)
        packet &= 0x7FFFFF
        humi = float((packet % 1000) / 10)
        bat = int(value[4])

    else:

        base64_string = request.json['manufacturer']
        base64_bytes = base64_string.encode("ascii")
        value = base64.b64decode(base64_bytes)        # passed a JSON string base64 encode of manufacturer data, key 0969

        byte8 = int(value[8:9].hex(),16)              # get humidity and temperature
        byte9 = int(value[9:10].hex(),16)
        byte10 = int(value[10:11].hex(),16)
        temp = ((byte8 & 0x0F) * 0.1 + (byte9 & 0x7F)) * (1 if ((byte9 & 0x80) > 0) else -1)
        humi = byte10 & 0x7F

        bat = 80     # not available it seems, so set to 80(!)

    import os
    dir = os.path.dirname(__file__)
    base_directory = os.path.join(dir, 'thermometer_values', 'DDDDDDDDDDDD-YYYY-MM.txt')

    now = datetime.utcnow()
    nam = key.upper().replace(':','')
    file = base_directory.replace('YYYY-MM', now.strftime('%Y-%m'), 1)
    file = file.replace('DDDDDDDDDDDD', nam)
    with open(file, "a") as fh:
      fh.write("\t".join([datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), str(temp), str(humi), str(bat)])+"\n")

    return 'ok'

# This point receives Temperature values from the thermal probes. As above, need to validate MAC and use to set correct
# 'parameter' values - use app/current_value TESTING!!!!!
#
# This results in 'gaps' when minutes are missed ...
# e.g. 08:00:57 Action runs
#      08:00:59 Call from device to Pi4 server
#      08:01:00 Fetch time of 08:01, and thus miss 08:00 slot.
#
# A workaround could be to check 'seconds' and <30 store for previous minute.
#
# We now fetch the value from thermistor
#
"""
@app.get("/ws/t/probe/<key>")
def probe_receive(key):
    print(request.remote_addr)
    print(key)
    print(request.values)

    hhmm = datetime.now().strftime('%Y%m%d%H%M')
    g.dbh.insert_pending(hhmm, '02 00', int(float(request.values['temperature']) * 10))
    #g.dbh.insert_pending(hhmm, '02 00', int(float(request.values['temperature']) * 10))

    return 'ok'
"""

@app.get('/logon')
def logon_get():
    return render_template('logon.html', title='Login', error=None)

@app.post('/logon')
def logon_post():
    g.params = request.values

    error = None
    user = u.User(name=g.params['user'])
    if user.valid_password(g.params['password']):
        g.session = mysession.Session(user = user.name, dbh = g.dbh)
        g.session.new_session()
        session.permanent = True
        session['_tudcS'] = g.session.session_id
        session['_tudcM'] = g.session.message_id
        session['user'] = user.name
    else:
        error = "User or password not known"

    if error:
        return render_template('logon.html', title='Login', error=error), 403
    else:
        return redirect("/monitor")
