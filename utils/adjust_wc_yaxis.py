#!/usr/bin/env python3

#
# Adjust WC curve/line y-axis values i.e. '21 02' and '21 03'
#                                            A           C
#

from datetime import datetime
import json

from app.commands import Commands
from app.control_settings import ControlSettings
from app.current_value import CurrentValue
from app.pump_value import Pump
from app.query_mysql import Heatpump_db

import argparse
parser = argparse.ArgumentParser(__file__)
parser.add_argument("offset", help="Amount to offset WC values by.", type=int)
args = parser.parse_args()

MAX_ADJUST = 6

if abs(args.offset) > MAX_ADJUST:
    raise RuntimeError(f"Don't try to shift things by more than {MAX_ADJUST} either way.")

current_a = CurrentValue(ControlSettings.PARAMETER_WC_SLOPE_A)
current_c = CurrentValue(ControlSettings.PARAMETER_WC_SLOPE_C)

# Ensure we start from the 'long-term' control values, not the latest ones
current_a.reset()
current_c.reset()

# Get current values
value_a, x = current_a.fetch()
value_c, x = current_c.fetch()

# Apply offset
new_a = value_a + (args.offset * 10)
new_c = value_c + (args.offset * 10)

# Set values locally (but do not send to pump)
current_a.set(new_a, defer=True)
current_c.set(new_c, defer=True)

# Send to pump, as a pair
commands = Commands()
commands.add_command([f"{current_a.id},{new_a}", f"{current_c.id},{new_c}"])
commands.load_commands()
