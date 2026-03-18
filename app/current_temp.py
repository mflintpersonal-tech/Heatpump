from datetime import datetime, timedelta, tzinfo
from dateutil import tz
import os
import subprocess
import yaml
from zoneinfo import ZoneInfo

class Current_Temperature():
  #GOVEE_LINES = 40
  GOVEE_LINES = 20    # changed to 20 on 24/10/25

  thermometers = False

  @classmethod
  # fetch (local) thermometer details
  def load_thermometers(cls):
    dir = os.path.dirname(__file__)
    filename = os.path.join(dir, "thermometers.yaml")

    with open(filename, "r") as file:
      cls.thermometers = yaml.safe_load(file.read())

  def __init__(self):

    if not Current_Temperature.thermometers:
      Current_Temperature.load_thermometers()

  def details(self, id = 'A4C13836B444'):

    if id not in Current_Temperature.thermometers.keys(): raise RuntimeError(f"Unknown thermometer with id {id}")

    if 'adjust' in Current_Temperature.thermometers[id].keys():
      adjust = Current_Temperature.thermometers[id]['adjust']
    else:
      adjust = 0

    dir = os.path.dirname(__file__)

    yymm = datetime.now().strftime('%Y-%0m')
    filename = os.path.join(dir, 'thermometer_values', f"{id}-{yymm}.txt")

    # this to handle change of month when the temp file might not yet exist for 'this' month
    if os.path.isfile(filename):
        pass
    else:
        yymm = (datetime.now() - timedelta(days=1)).strftime('%Y-%0m')
        filename = os.path.join(dir, 'thermometer_values', f"{id}-{yymm}.txt")

    last_lines = subprocess.run(['tail', f'-n {Current_Temperature.GOVEE_LINES}', filename], stdout=subprocess.PIPE).stdout.decode('utf-8')
    last_lines = last_lines.strip()

    tim, humidity, battery = 0, 0, 0
    count = 0
    sum_temps = 0
    for line in last_lines.split("\n"):
        count += 1
        tim, temperature, humidity, battery = line.split("\t")
        ## # this fixes an issue with goveebtlogger
        ## temperature = int(float(temperature) * 1000) / 1000
        sum_temps += float(temperature)

    ave_temp = sum_temps / count

    tim = datetime.strptime(tim, "%Y-%m-%d %H:%M:%S")
    tim = tim.replace(tzinfo=ZoneInfo('UTC'))
    tim = tim.astimezone(tz.tzlocal())

    ##return {'time': tim, 'temperature': int((temperature.truncate(1)) * 10), 'humidity':int((humidity) * 10)}
    return {'time': tim, 'temperature': round(ave_temp * 10)+adjust, 'humidity':round(float(humidity) * 10), 'battery':int(battery)}



if __name__ == "__main__":
    x = Current_Temperature().details()
    print(x)
    x = Current_Temperature().details(id = 'D43535307339')
    print(x)
    x = Current_Temperature().details(id = '343444zzzz')

