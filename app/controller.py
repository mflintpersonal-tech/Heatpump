#!/usr/bin/python3
#
# class to perform controller actions on the Heat Pump
#

import redis

from app.heating_schedule import Schedule

class Controller:

    DHW_DEMAND = 'Controller:DHW:Demand'
    DHW_PHASE  = 'Controller:DHW:Phase'

    MODE_CH    = 'CH'
    MODE_DHW   = 'DHW'

    SWITCH     = 'SWITCH'               # Redis key of either 'CHSWITCH' or 'DHWSWITCH'
    ON         = 'ON'
    OFF        = 'OFF'

    CHOFF      = 'CH:OFF'
    DHWOFF     = 'DHW:OFF'

    def __init__(self):
        self.redis_db = False
        self.dhw_activity = False
        self.schedule = Schedule()

        self.target = None
        # TODO - sort out Redis connection!!! - below line added 26/1/26 as a shirt-term(?) option (should use class method?)
        self.connect()

    """ hot_water_demand: determines if we're in a DHW period
    """
    def hot_water_demand(self, now):
        hw_target, x = self.schedule.find_target(now, zone = 'W', return_none = True)
        # if DHW circuit is off, then don't do any DHW phase stuff (other than tidying up - see thermistor)
        if self.DHWTurnedOff():
            hw_target = False
        return hw_target

    """ set_mode: sets the operating mode based on passed parameter - either CH or DHW
    """
    def set_mode(self, mode, target=None):
        self.mode = mode
        if target: self.target = target

    # Indicates if DHW activity has happened in this 'period'
    def set_dhw_activity(self):
        self.dhw_activity = True

    def clear_dhw_activity(self):
        self.dhw_activity = False

    # Are we doing Central Heating?
    def central_heating_mode(self):
        return self.mode == self.MODE_CH

    def hot_water_mode(self):
        return self.mode == self.MODE_DHW

    """ turn DHW controls on - i.e. set DHW_DEMAND to 'Y' (any value will do in reality)
    """
    # DONT think this is used any longer
    def startDHW(self):

        self.resetDHW()     # clear down just in case

        self.redis_db.set(Controller.DHW_DEMAND, 'Y')

    """ reset the DHW controls i.e. remove the DHW_PHASE key in redis, and reset the phase to 0
    """
    def resetDHW(self):

        self.connect()

        self.redis_db.delete(Controller.DHW_DEMAND)   ## possibly no longer needed?!
        self.redis_db.set(Controller.DHW_PHASE, '0') 

    """ Turns off either CH or DHW
        This is just the flag in the Redis DB - it doesn't amend the state of any device at all, that's all handled
        by the thermistor module. These are the states of the (virtual) 'controller' object, not phyisical devices.
    """
    def TurnOff(self, mode):

        self.connect()
        if (mode == Controller.MODE_CH):
            self.redis_db.set(Controller.CHOFF, 'True')
        elif (mode == Controller.MODE_DHW):
            self.redis_db.set(Controller.DHWOFF, 'True')
        else:
            raise RuntimeError(f"{mode} is not a valid option")

    """ Turns on either CH or DHW
    """
    def TurnOn(self, mode):

        self.connect()
        if (mode == Controller.MODE_CH):
            self.redis_db.delete(Controller.CHOFF)
        elif (mode == Controller.MODE_DHW):
            self.redis_db.delete(Controller.DHWOFF)
        else:
            raise RuntimeError(f"{mode} is not a valid option")

    """ Returns a 'True' if CH turned off
    """
    def CHTurnedOff(self):

        self.connect()

        return self.redis_db.get(Controller.CHOFF)

    """ Returns a 'True' if DHW turned off
    """
    def DHWTurnedOff(self):

        self.connect()

        return self.redis_db.get(Controller.DHWOFF)

    """ Enable either CH or DHW
    """
    def Enable(self, mode):
        self.connect()
        self._validate(mode)
        self._setSwitch(mode, Controller.ON)

    """ Disable either CH or DHW
    """
    def Disable(self, mode):
        self.connect()
        self._validate(mode)
        self._setSwitch(mode, Controller.OFF)

    """ Returns switch status (ON/OFF)
    """
    def SwitchStatus(self, mode):
        self.connect()
        self._validate(mode)
        return self._getSwitch(mode)

    """ Set the Main Switch value (ON or OFF)
    """
    def _setSwitch(self, mode, status):
        self.redis_db.set(f"{mode}{Controller.SWITCH}", status)

    """ Set the Main Switch value (ON or OFF)
    """
    def _getSwitch(self, mode):
        st = self.redis_db.get(f"{mode}{Controller.SWITCH}")
        st = Controller.OFF if not st else st
        return st

    """ Validate passed mode
    """
    def _validate(self, mode):
        if (mode != Controller.MODE_CH) and (mode != Controller.MODE_DHW):
            raise RuntimeError(f"{mode} is not a valid option")

    # used for (lazy) connection to local Redis database ... not explicitly closed
    def connect(self):
        if not self.redis_db:
            self.redis_db = redis.Redis(decode_responses = True)
