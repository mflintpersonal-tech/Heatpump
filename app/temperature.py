import os
import yaml

from app.current_temp import Current_Temperature
from app.current_value import CurrentValue

class Temperature():

  thermometers = False

  @classmethod
  # fetch (local) thermometer details
  def load_thermometers(cls):
    dir = os.path.dirname(__file__)
    filename = os.path.join(dir, "thermometers.yaml")

    with open(filename, "r") as file:
      cls.thermometers = yaml.safe_load(file.read())

  def __init__(self, type, zone=False):
    self.type = type

    if not Temperature.thermometers:
      Temperature.load_thermometers()

    if zone:
      self.type_thermometers = dict((k, v) for k,v in Temperature.thermometers.items() if Temperature.thermometers[k].get('zone') == int(zone))
    else:
      self.type_thermometers = dict((k, v) for k,v in Temperature.thermometers.items() if v['location'] == self.type)

    if len(self.type_thermometers) == 0: raise RuntimeError(f"No thermometers of type {type}/{zone} found!")

    # only 1 thermometer, it's weight is 1
    if len(self.type_thermometers) == 1: self.type_thermometers[ list(self.type_thermometers)[0] ]['weight'] = 1

  # Returns the value of this temperature, taken as a weighted average of thermometers of this type
  def value(self):
    no_weight = 0
    sum = 0
    weight = {}
    for therm, vals in self.type_thermometers.items():
      if 'weight' in vals.keys():
        weight[therm] = vals['weight']
        sum += vals['weight']
      else:
        weight[therm] = 0
        no_weight += 1
    #print(weight)

    if (sum >= 1) or (no_weight == 0):
      pass
    else:
      for therm, w in weight.items():
        if w == 0:
          w = (1 - sum) / no_weight
          weight[therm] = w
      #print(weight)

    # find the weighted value across all thermometers of this type

    temp = 0
    for therm, vals in self.type_thermometers.items():
      if vals['type'] == 'parameter':
        v, tim = CurrentValue(vals['temperature']).fetch()
      else:
        v = Current_Temperature().details(therm)['temperature']
      temp = temp + (v * weight[therm])

    return round(temp)


if __name__ == "__main__":
    x = Temperature('inside')
    print('inside')
    print(x.value())
    x = Temperature('inside', zone=1)
    print('inside/zone1')
    print(x.value())
    x = Temperature('inside', zone=2)
    print('inside/zone2')
    print(x.value())
    x = Temperature('outside')
    print('Outside')
    print(x.value())


