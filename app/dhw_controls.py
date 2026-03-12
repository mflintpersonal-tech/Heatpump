#!/usr/bin/python3
#
# class to perform controller actions on the DHW logic
#

from datetime import datetime
import redis

from redmail import EmailSender

from app import app
from app.controller import Controller
from app.control_settings import ControlSettings
from app.current_value import CurrentValue
from app.device_control import DeviceControl
from app.notifications import Notifications
from app.pump_value import Pump
from app.query_mysql import Heatpump_db

from app import monitor_log
#log = monitor_log.loggr

class DHW_Controls:
    #FACTOR = 40
    FACTOR = 20     # Changed to 2 degrees on 25/10/25

    MIN_BOOST = 10  # minimum time between boost presses
    MAX_BOOST = 60  # maximum boost time
    BOOST_TRUE = 1
    BOOST_FALSE = 0

    def __init__(self, control_values, controller, log=monitor_log.loggr, redis_db=None):
        self.start_hour = datetime.now()

        self.hp_controls = control_values
        self.controller = controller
        self.log = log

        self.redis_db = redis_db
        if not self.redis_db:
            self.connect()

        self.hw_value = CurrentValue(ControlSettings.PARAMETER_DHW_TEMP) # DHW temperature parameter
        self.hw_target = CurrentValue(ControlSettings.PARAMETER_DHW_TARGET)
        # Below value is used in thermistor when setting fixed LWT during DHW cycle
        self.hw_set_lwt, x = CurrentValue(ControlSettings.PARAMETER_DHW_SET_LWT).fetch()
        #self.hw_set_lwt = 550     # TEMP FIXME
        self.hw_hysterisis, x = CurrentValue(ControlSettings.PARAMETER_DHW_HYSTERISIS).fetch()

        self.dhw_ch_lwt = True

        self.phase = self.redis_db.get(Controller.DHW_PHASE)
        self.phase = 0 if self.phase == None else int(self.phase)

        self.device = DeviceControl('DHW')

        self.notifications = Notifications()

    """ actions whatever is required for each phase of hot_water_demand:
            0 : Initial state / OFF
           10 : Pre-heat LWT
           20 : Turn DHW circuit on
           30 : Run DHW on period
           80 : DHW target hit
           85 : Use DHW heat to power CH (if required)
           90 : DHW over/target hit ... return to Phase 0
    """
    def phase_action(self):
        self.log.debug(f"On entry, phase = {self.phase}")

        if 1 == 1:   # match self.phase:
            #case 0|None:
            if self.phase == 0:  #case 0|None:
                self.start_hour = datetime.now()
                # See if there's any need to heat water
                if self.current_HW_temp() < self.HW_target():
                    self.set_phase(10)
                else:
                    self.set_phase(90)      # changed from 99 on 30/1/25


            elif self.phase == 10:    # case 10:
                # pre-heat LWT
                # TODO
                # a) raise TargetLWT to maximum
                # b) await CurrentLWT > current HW temp
                #    - when true, turn DHW circuit on (i.e. DHWPhase := 20)
                #      (else leave phase as 10)
                # [[this phase can go straight to 20 if there's no preheat set-up]]
                self.set_phase(20)

            elif self.phase == 20:    # case 20:
                # turn DHW on
                if self.set_dhw('on'):
                    self.set_phase(30)

            elif self.phase == 30:     # case 30:
                # stop heating when target hit
                if self.current_HW_temp() >= self.HW_target():
                    self.set_phase(80)

            elif self.phase == 80:    # case 80:
                # finish up
                if self.set_dhw('off'):
                    # FIXME - repeats code below! sort out.
                    lwt_value, y = CurrentValue('01 09').fetch()  # Actual LWT value
                    self.dhw_ch_lwt = lwt_value - self.FACTOR
                    self.set_phase(85)
                # HANDLE what to do if can't turn DHW off!
                # TODO

                #self.set_phase(90)

            elif self.phase == 85:   # case 85:
                # On 'cool down' find actual LWT and suggest that as Target LWT (minus "factor") to CH thermistor

                if self.dhw_ch_lwt == False:
                    self.set_phase(90)
                else:
                    # FIXME 
                    lwt_value, y = CurrentValue('01 09').fetch()  # Actual LWT value
                    self.dhw_ch_lwt = lwt_value - self.FACTOR

                # This logic is contained in utils/thermistor which sets dhw_ch_lwt to False when the condition below is true
                # if TargetLWT <= genuine target LWT (based on CH zone requirements), set TargetLWT to genuine LWT
                #    and set DHWPhase to 90

            elif self.phase == 90:   # case 90:
                # all done
                self.set_phase(0)

        self.log.debug(f"On exit, phase = {self.phase} ")

    # return current HW temperature
    def current_HW_temp(self):
        x, y = self.hw_value.fetch()
        self.log.info(f"current HW temp = {x}")
        self.log.debug(f"Value obtained at time = {y}")

        # see if we need to apply hysterisis - see if target has been met first...
        if Heatpump_db().limit_reached(ControlSettings.PARAMETER_DHW_TARGET, self.start_hour.strftime('%Y-%d-%m %H:00:00'), x):
            if (self.phase < 30) or (self.phase > 80):
                x = x + self.hw_hysterisis
                self.log.info(f"HW hysterisis appied. Current HW temp is {x}")

        return x

    # return DHW target temperature
    def HW_target(self):
        x, y = self.hw_target.fetch()
        self.log.debug(f"target hw temp = {x}")
        return x

    # set DHW target from controller target value
    def set_target(self):
        self.hw_target.set(self.controller.target)

    # set DHW circuit on or off
    def set_dhw(self, status, msg=None):

        # Do nothing if the main switch is OFF
        if self.controller.SwitchStatus(Controller.MODE_DHW) == 'OFF':
            self.log.info(f"Not amending DHW circuit as Main Switch is set to OFF")
            return False

        text = msg if msg else f"Setting DHW circuit = {status}"
        self.log.info(text)

        if status == 'on':
            res = self.device.turn_on()
        else:
            res = self.device.turn_off()

        if not res:
            self.notifications.send(['email','alexa'], 'DHW Control Failed', f"Failed to set DHW {status}.")
        else:
            msg = f"Hot water turned {status}."
            if res == status:
                msg += f" By the way, it was already {status}, which seems odd to me."
            self.notifications.send(['alexa'], 'DHW Control', msg)

        return res

    # set phase number to passed value (locally, and store in Redis)
    def set_phase(self, phase_number):
        self.phase = phase_number
        self.redis_db.set(Controller.DHW_PHASE, phase_number)

    # handle DHW boost
    def set_boost(self):
        active = self.BOOST_FALSE
        with redis.Redis(decode_responses = True) as r:
            active = r.get(Pump.BOOST_DHW)
            last_time = r.get(Pump.BOOST_DHW_START)
        last_time = int(last_time) if last_time else 0
        active = int(active) if active else self.BOOST_FALSE

        now = int(datetime.now().timestamp())
        if (now - last_time) < (self.MIN_BOOST * 60):
            self.log.info("Ignoring press as too soon since last active.")
        else:
            if active:
                self.log.info(f"Cancelling Hot Water boost")
                self.set_dhw('off')
            else:
                msg = "Starting Hot Water boost. Will end in 1 hour or if cancelled manually."
                self.set_dhw('on', msg=msg)
                self.notifications.send(['alexa'], 'DHW Boost', msg)

            with redis.Redis(decode_responses = True) as r:
                active = self.BOOST_TRUE - active
                r.set(Pump.BOOST_DHW, str(active))
                r.set(Pump.BOOST_DHW_START, str(now))

    # check DHW boost
    def check_boost(self):
        complete = False
        active = self.BOOST_FALSE
        with redis.Redis(decode_responses = True) as r:
            active = r.get(Pump.BOOST_DHW)
            last_time = r.get(Pump.BOOST_DHW_START)
        last_time = int(last_time) if last_time else 0
        active = int(active) if active else self.BOOST_FALSE

        now = int(datetime.now().timestamp())
        if active and (now - last_time) > (self.MAX_BOOST * 60):
            self.log.info("Boost complete. Switching off.")
            self.set_dhw('off')
            with redis.Redis(decode_responses = True) as r:
                r.set(Pump.BOOST_DHW, self.BOOST_FALSE)
            complete = True

        return [active, complete]

    # connection to local Redis database ... not explicitly closed (apparently the Python module handles it!)
    def connect(self):
        self.redis_db = redis.Redis(decode_responses = True)


if __name__ == "__main__":

    import time
    x = DHW_Controls('', '')
    #x.set_boost()
    act, comp = x.check_boost()
    print(f"Boost active?", act)
    print(f"Boost complete?", comp)
