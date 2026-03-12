#!/usr/bin/env python3
#
# Heat Pump values
#

from . query_mysql import Heatpump_db

def row_factory(cursor, row):
    columns = [t[0] for t in cursor.getdescription()]
    return dict(zip(columns, row))

class Pump:
  MONITOR_STORE = 'HeatPump:Monitor'      # Monitor data starts with this value then :<key>, where key = Time.to_i

  CREATED_KEY = 'HeatPump:Created_Key:'   # Redis keys of the actual created_key value for this minute of the day
  LAST_CREATED = 'HeatPump:Latest'        # Redis key of last created monitor data (just the time part)
  LOCAL_QUEUE = 'HeatPump:ForRemote'      # Queue for transferring data

  COMMAND_QUEUE = 'HeatPump:Commands'     # Queue of commands to execute
  COMMAND_QUEUED = 'HeatPump:Queued'      # List of commands queued
  COMMAND_RESULTS = 'HeatPump:Results'    # Queue of command results

  BOOST_DHW = 'HeatPump:DHW_Boost'        # DHW Boost active: true/false
  BOOST_DHW_START = 'HeatPump:DHW_Boost_Start'  # DHW Boost started time

  NORMAL_FACTOR = 0.1                     # The factor we'll work with in calculations

  parameters = False

  @classmethod
  def load_parameters(cls):
      db = Heatpump_db()
      return db.load_parameters()

  @classmethod
  def parm_to_reg(cls, p):
      #if not Pump.parameters:
      #    Pump.parameters = cls.load_parameters()
      #return Pump.parameters[p]['register']
      return Pump.parm_details(p)['register']

  @classmethod
  def parm_details(cls, p):
      if not Pump.parameters:
          Pump.parameters = cls.load_parameters()
      return Pump.parameters[p]

  def __init__(self, id):
      self.id = id
      self.real_value = None

      if not Pump.parameters:
          Pump.parameters = Pump.load_parameters()

      self.details = Pump.parameters[self.id]
      if self.details is None:
          raise RuntimeError("Unknown parameter!")

  # returns factorised value of 'real-value' (passed or as set for instance)
  def value(self, val = None):
      factor = self.details['factor'] or 1
      if val is None:
        return self.real_value * factor
      #print(f"{self.id}: {factor} {val}")
      return val * factor

  # returns normalised value - e.g. some are held with factor 0.1 / others of 1; return the "0.1" version of the value
  def normalised(self):
      factor = self.details['factor'] or 1
      if factor == self.NORMAL_FACTOR:
          return int(self.real_value)
      return int(self.real_value * (1.0/self.NORMAL_FACTOR))

  # string representation
  def __repr__(self):
      return f"<Pump parameter='{self.id}:{self.details['description']}' real_value={self.real_value} value={self.value()}{self.details['units']}>"  

  def register(self):
      return self.details['register']

  # return the (monitoring) type e.g. 'Y' it's monitored; 'C'ontrol; ...
  def type(self):
      return self.details['monitor']

  def is_control(self):
      return (self.type() == 'C')

  # set value of register (locally)
  def set_value(self, val):
      self.real_value = val
  
  # get real value (given a factored value)
  def get_value(self, val):
      return int((val / self.details['factor']))

"""
d = Pump('21 03')
d.set_value(300)
print(d.value())
print(repr(d))
print(d.normalised())

d = Pump('01 06')
d.set_value(14)
print(d.value())
print(repr(d))
print(d.normalised())
"""
"""
  def __getitem__(self, key):
      return getattr(self, key, None)
  
  def __setitem__(self, key, value):
      return setattr(self, key, value)
"""  
