#!/usr/bin/env python3

#
# Set the '46 nn' parameters for a supplemtary heater.
# See - https://renewableheatinghub.co.uk/forums/renewable-heating-air-source-heap-pumps-ashps/is-the-grant-controller-a-thermostat/paged/15
#

from app.commands import Commands

def parse_it(str, col):
    res = []
    parts = str.strip().split('\n')
    for p in parts:
        q = p.split(':')
        parm = q[0]
        r = q[1].split(',')
        val = r[col].replace(' ','')
        res.append(f"{parm},{val}")
    return res

# 46 00 - Backup heater type of function 0=disable:                    0
# 46 01 - manual water set point:                                    500
# 46 02 - Manual water temp hysteris:                                 50
# 46 03 - Delay time of the heater OFF that avoid flow switch alarm:  10
# 46 04 - Heater Activation delay time:                                5
# 46 05 - Integration time for backup heater:                        600
# 46 11 - Outdoor air temperature to enable Backup heaters and disable compressor:            -50
# 46 12 - Outdoor air temperature hysteresis to disable Backup heaters and enable compressor:  50
# 46 13 - Outdoor air temperature to enable Backup heaters (Supplementary mode):               50
# 46 14 - Outdoor air temperature hysteresis to disable Backup heaters (Supplementary mode):   50
# 46 20 - Freeze protection functions:                                 0
# 46 21 - Outgoing water temperature set point during Start-up:       80
# 46 22 - Hysteresis water temperature set point during Start-up:     50

# 46 23 - Temperature at which heater kicks in, maybe?
# 51 46 - Enable terminal 46 to be used as / signal  backup heater (rather than DHW heater)

# string is "parameter id": <current/default value>,<new value>

# >>>>>>>>>>>>>>  We EXCLUDE any values that don't appear to need changing  <<<<<<<<<<<<<

# This set are fairly harmless without any other changes
parm_values_1 = """
46 01: 500,440
46 04: 5,1
46 05: 600,60
46 11: -50,-200
46 13: 50,-50
46 14: 50,20
"""

# This set is what turns it on/off so handle with care
parm_values_2 = """
46 00: 0,3
46 20: 0,3
"""

# These can't be set remotely so need doing manually at the controller!
parm_values_3 = "46 23:240,380\n51 46:0,1"

reset = input("Do we want to set or reset the values? ")
column = 0 if reset == 'reset' else 1

stage = input("Which parameter list to set? (1, 2 - important ones, or both with '12') ")

do_it = input("Really do it or dry run?(YES => do it) ")
print('')

command_string_1 = parse_it(parm_values_1, column)
command_string_2 = parse_it(parm_values_2, column)

if do_it == 'YES':
    # Send to pump
    if '1' in stage:
        commands = Commands()
        commands.add_command(command_string_1)
        commands.load_commands()
        print("Sent commands to amend list 1 parameters - not important ones")
        print('')

    if '2' in stage:
        commands = Commands()
        commands.add_command(command_string_2)
        commands.load_commands()
        print("Sent commands to amend list 2 values - the important ones")
        print('')

else:
    print('Would execute the following, but am not!')
    if '1' in stage: print(command_string_1)
    if '2' in stage: print(command_string_2)

print(f"You also must manually change {parse_it(parm_values_3,column)}")
print('')
print("- by, pressing the Menu -sun symbol- (top left) and + and - buttons for 3 seconds until flashing inst/0000 appears")
print("then the +/- signs move between the two groups of 2-digits, so get to first two then use the")
print("up/down arrows to change the value, and when it says 46 23, press the tick button (by the +/-) to show the value")
print("Now use up/down to amend the value, and tick again once set as required.")
print("Use 'back' (on left of +/-) to go back to where you were, and the 3 buttons again to exit menu.   Easy, eh?")

