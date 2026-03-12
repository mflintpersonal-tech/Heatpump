#!/usr/bin/env python3

#
# Obtain latest control settings from the stored records in Redis
#

import json
import redis
from datetime import datetime, timedelta

from . import current_temp as ct
from . import current_value as cv
from . import pump_value as pv
from . import query_mysql as db
from . import temperature as tp

class ControlSettings():
    PARAMETER_DHW_TEMP = '01 31'                   # Parameter for DHW current temperature
    PARAMETER_DHW_TARGET = '31 11'                 # Parameter for DHW Target temperature
    PARAMETER_DHW_SET_LWT = '41 30'                # Parameter for DHW set LWT (set by Service menu only - not updatable?)
    PARAMETER_DHW_HYSTERISIS = '31 13'             # Parameter for DHW comfort hysterisis
    
    #PARAMETER_EXTERNAL_AIR_TEMPERATURE = '01 06'   # Parameter ID in the RS485 interface for external temperature
    PARAMETER_WC_ENABLED = '21 00'                 # Parameter for setting WC on/off
    PARAMETER_FIXED_LWT  = '21 01'                 # Parameter for setting a 'fixed' LWT
    #                                                (in reality we calcualte the LWT based on parameters A -> D and then set the 
    #                                                'fixed' value to that, so it is the WC values, just manually set.
    PARAMETER_WC_SLOPE_A = '21 02'                 # Parameter for wc, value 'a' (see 'find_wc')
    PARAMETER_WC_SLOPE_B = '21 04'                 #                   value 'b'
    PARAMETER_WC_SLOPE_C = '21 03'                 #                   value 'c'
    PARAMETER_WC_SLOPE_D = '21 05'                 #                   value 'd'
    PARAMETER_ZONE2 = '1'                          # How to get to the Zone 2 parameter values: '21 02' -> '21 12', etc.
    TEMP_INTERVAL = timedelta(seconds=120)         # How often we refresh the current temperature value
    TEMP_HYSTERISIS = 2       # (this is 0.2C)
    #                         # larger negative => less of a descrease of default LWT (must be at most -1.0 though)
    # MAGIC_NUMBER = -1.73      # This is too low on LWT: changed to below on 1/12/25
    MAGIC_NUMBER = -1.85      # larger negative => less of a descrease of default LWT (must be at most -1.0 though)
    # -0.75 is quite a harsh impact; -2.0 if much less aggressive
    MODULATE_THRESHOLD = 20

    RANGE_OFFSET = 40         # When deriving a wcc how far above/below the top external temperatures to give

    def __init__(self, zone=1, fine=False):
        self.zone = zone

        self.fine = fine    # whether LWTs returned are "nearest 0.5" or actual number

        self.get_monitor_values()

        self.find_wc(self.zone)

        self.temperature = tp.Temperature('inside', zone=self.zone)

    def hysterisis(self):
        return self.TEMP_HYSTERISIS

    # return current temperature (for this zone)
    def current_temperature(self):
        ###if self.temperature and ( (ControlSettings.last_temperature + self.TEMP_INTERVAL) > datetime.now() ):
        ###    return self.temperature

        ###ControlSettings.last_temperature = datetime.now()

        return self.temperature.value()

    # returns the external air temperature
    def external_temperature(self):
        return tp.Temperature('outside').value()
        #return int(self.values[self.PARAMETER_EXTERNAL_AIR_TEMPERATURE] * 10)

    # returns the LWT based on the WC settings of the Grant
    def find_lwt(self, ext=None):
        if ext == None: ext = self.external_temperature()
        if ext > self.maximum_ext_temp:
            ext = self.maximum_ext_temp
            #return 0

        lwt = int((ext * self.gradient) + self.konstant)
        return min([self.nearest_5(lwt), self.maximum_lwt])

    # Returns a modulated LWT based on proximity to target temperature
    # ----------------------------------------------------------------
    # If difference > THRESHOLD; LWT is unmodulated
    # Else LWT is modulated based on the distance from THRESHOLD to target
    def modulated_lwt(self, target):
        # Amended 17/10/25 - ensure there's never a -ve difference : shouldn't really happen as we're above 'target', but...
        difference = abs(target - self.current_temperature())

        if (difference > self.MODULATE_THRESHOLD):
            modulate = 1
        elif (difference == 0):
            modulate = 0.99
        else:
            modulate = 1 - (difference ** self.MAGIC_NUMBER)

        basic_lwt = self.find_lwt()
        new_lwt = basic_lwt * modulate

        # amended 1/12/25 : modify the modulated, based on outside temps (i.e. less impact when it's colder)
        mod_factor = 1
        ext = self.external_temperature() / 10   # FIXME - shouldn't just divide by 10 - use object
        if ext < 0: ext = 0
        lwt_factor = 3 - (ext // 5)
        if lwt_factor < 0: lwt_factor = 0
        new_lwt = ( (new_lwt * mod_factor) + (basic_lwt * lwt_factor) ) / (mod_factor + lwt_factor)

        new_lwt = max([self.nearest_5(new_lwt), self.minimum_lwt])

        return int(new_lwt)

    # Temperature settings for ASHP need to be in multiples of 0.5C
    def nearest_5(self, number):
        return number if self.fine else int(int(number / 5) * 5)

    def get_monitor_values(self):

        with redis.Redis(decode_responses = True) as r:

            last_monitor = r.get(pv.Pump.LAST_CREATED)
            key = f"{pv.Pump.MONITOR_STORE}:{last_monitor}"
            self.values = dict( (a[0], a[1]) for a in json.loads(r.get(key)) )

    # returns an array of [external_temp, lwt] for range of 4 below B to 4 above D (see 'find_wc')
    def wcc_range(self, zone):

        wcc = {}
        #for ext in range(self.parm_b - self.RANGE_OFFSET, self.parm_d + self.RANGE_OFFSET + 5, 5):
        for ext in range(self.parm_b - self.RANGE_OFFSET, self.parm_d + 5, 5):
            wcc[ext/10] = self.find_lwt(ext)/10
        #wcc[(self.parm_d + 0)/10] = 0
        return wcc

    def find_wc(self, this_zone):
        """
        Calculate formula for WC on Grant based on parameters:

        21 02 = Maximum LWT (at minimum external temp of '21 04')
        21 03 = LWT at maximum external temp of '21 04' (above '21 04' no heating takes place)


        LWT    |
               | Maximum LWT is A; external temps below B still produce LWT of A
       '21 02' +----- A.
               |          .
               |              .
               |                  .
               |                      .
               |                          .
               |                              .
       '21 03' +                                  .C --no heating here--
               |                                     --no heating here--
               |                                     --no heating here--
               +------B----------------------------D-----------------------
                   '21 04'                      '21 05'       External Temp

        Formula is LWT = ((A - C) / (B - D) * External Temp) + Konstant <------ required as line does not cross (0,0)
        """

        # the key values for the wc slope are grabbed from the database (they are updated regularly from the Pi W controls)

        dbh = db.Heatpump_db()

        parameter_a = self.PARAMETER_WC_SLOPE_A
        parameter_b = self.PARAMETER_WC_SLOPE_B
        parameter_c = self.PARAMETER_WC_SLOPE_C
        parameter_d = self.PARAMETER_WC_SLOPE_D

        if this_zone == '2':
            parameter_a = parameter_a[:3] + self.PARAMETER_ZONE2 + parameter_a[4:]    # python can be crappy
            parameter_b = parameter_b[:3] + self.PARAMETER_ZONE2 + parameter_b[4:]
            parameter_c = parameter_c[:3] + self.PARAMETER_ZONE2 + parameter_c[4:]
            parameter_d = parameter_d[:3] + self.PARAMETER_ZONE2 + parameter_d[4:]

        #self.values[parameter_a] = dbh.control_value(parameter_a)
        #self.values[parameter_b] = dbh.control_value(parameter_b)
        #self.values[parameter_c] = dbh.control_value(parameter_c)
        #self.values[parameter_d] = dbh.control_value(parameter_d)
        self.values[parameter_a] = cv.CurrentValue(parameter_a).fetch()[0]
        self.values[parameter_b] = cv.CurrentValue(parameter_b).fetch()[0]
        self.values[parameter_c] = cv.CurrentValue(parameter_c).fetch()[0]
        self.values[parameter_d] = cv.CurrentValue(parameter_d).fetch()[0]

        a = self.values[parameter_a]
        b = self.values[parameter_b]
        c = self.values[parameter_c]
        d = self.values[parameter_d]
        # FIXME
        self.parm_b = b
        self.parm_d = d

        self.gradient = (a - c) / (b - d)

        # Find Konstant, K, using the known point of (D, C)

        self.konstant = c - (self.gradient * d)

        self.minimum_lwt = c
        self.maximum_lwt = a
        self.maximum_ext_temp = d



if __name__ == "__main__":
    x = ControlSettings(fine=True)
    #y = x.find_lwt()
    #print(y)
    #print('................................')
    z = x.modulated_lwt(205)
    print(z)
    z = x.modulated_lwt(240)
    print(z)
    #a = x.wcc_range('1')
    #print(a)
