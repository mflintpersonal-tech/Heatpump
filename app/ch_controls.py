#!/usr/bin/python3
#
# class to perform controller actions on the CH logic; one object for each zone
#

#from app.controller import Controller
from app.control_settings import ControlSettings
from app.controller import Controller
from app.current_value import CurrentValue
from app.device_control import DeviceControl
from app.notifications import Notifications

from app import monitor_log
log = monitor_log.loggr

class CH_Controls:

    def __init__(self, zone, control_values, log=False):

        self.zone = zone
        self.hp_controls = control_values
        self.log = log

        self.device = DeviceControl(f'ZONE{zone}')
        self.current_status = 'off'  ######### <<<< should set by checking status of device!  TODO 

        self.notifications = Notifications()

        self.last_target = 0
        self.target_reached = False

        self.lwt = False
        self.new_lwt = False

    def set_target(self, target):
        self.target = target

    """ target_changed : if the heating target has changed, then reset 'target_reached'
    """
    def target_changed(self):
        if self.last_target == self.target:
            return True
        else:
            self.target_reached = False
            self.last_target = self.target

    """ set_control : update the ControlSettings for this zone
    """
    def set_control(self, controls):
        self.hp_controls = controls

    # set CH circuit on or off
    def set_ch(self, status, force=False):
        log.debug(f"Zone{self.zone} current status: {self.current_status}; changing to {status}")
        if (status == self.current_status) and not force:
          return True

        # Do nothing if the main switch is OFF
        if Controller().SwitchStatus(Controller.MODE_CH) == 'OFF':
            log.info(f"Not amending CH circuit as Main Switch is set to OFF")
            return False

        log.info(f"Setting CH Zone{self.zone} {status}")

        if status == 'on':
            res = self.device.turn_on()
        else:
            res = self.device.turn_off()

        if not res:
            self.notifications.send(['email','alexa'], 'CH Control Failed', f"Failed to set CH Zone{self.zone} {status}.")
        else:
            self.current_status = status
            msg = f"Central Heating Zone{self.zone} turned {status}."
            if res == status:
                msg += f" Ohhh - it was already {status} ... silly me!"
                self.notifications.send(['alexa'], 'CH Control', msg)
            #self.notifications.send(['alexa'], 'CH Control', msg)

        return res

if __name__ == "__main__":

    z = 1
    c = ControlSettings(zone=z)
    x = CH_Controls(z, c)
    x.current_status = 'on'
    x.set_ch('off')
