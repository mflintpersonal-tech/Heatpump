#!/usr/bin/env python3
#
# Class for Tempest Weatherflow messages
#

from datetime import datetime

class TempestMessage:

  MESSAGE_DETAILS = {     # Rain Start Event
                     'evt_precip': ['evt', ['time']],
                          # Lightning Strike Event
                     'evt_strike': ['evt', ['time','distance','energy']],
                          # Rapid Wind Event
                     'rapid_wind': ['ob',  ['time','wind_speed','wind_direction']],
                          # Observation Air
                     'obs_air':    ['obs', ['time','station_pressure','air_temperature','humidity',
                                            'lightning_strike_count','lightning_strike_ave_distance','battery','report_interval']],
                          # Observation Sky
                     'obs_sky':    ['obs', ['time','illuminance','uv','rain_amount_previous_minute','wind_lull','wind_avg','wind_gust',
                                            'wind_direction','battery','report_interval','solar_radiation','rain_accumulation',
                                            'rain_type','wind_sample_interval']],
                          # Observation
                     'obs_st':     ['obs', ['time','wind_lull','wind_avg','wind_gust','wind_direction','wind_sample_interval',
                                            'station_pressure','air_temperature','humidity','illuminance','uv','solar_radiation',
                                            'rain_amount_previous_minute','rain_type','lightning_strike_ave_distance','lightning_strike_count','battery','report_interval']],
                          # Hub Status
                     'hub_status':    ['radio_stats', ['version,','reboot_count','i2c_error_count','radio_stats','radio_network_id']],
                          # Device Status
                     'device_status': [False, [False]]
                    }

  def __init__(self, msg_data):
      self.type = None
      self.message = {}
      self.msg = msg_data

  def parse(self):
      self.header()

      if self.type in self.MESSAGE_DETAILS.keys():
          root, values = self.MESSAGE_DETAILS[self.type]

          if root:
              details = self.__flatten__(self.msg[root])
              del self.message[root]
              i = 0
              for v in values:
                  self.message[v] = details[i]
                  i += 1

          # TODO - bit hacky
          if not ('time' in self.message): self.message['time'] = self.message['timestamp']

          self.message['message_time'] = datetime.fromtimestamp(self.message['time'])

      else:
          raise RuntimeError(f"Unknown message type of {self.message['type']} encountered")

  def header(self):
      for k in self.msg.keys():
          self.message[k] = self.msg[k]
      self.type = self.message['type']

  def __flatten__(self, a):
      if isinstance(a[0], list):
          return [item for sublist in a for item in sublist]
      else:
          return a


"""
d = {"serial_number": "SK-00008453",
     "type":"evt_precip",
     "hub_sn": "HB-00000001",
     "evt":[1493322445]
    }

d = {
 "serial_number": "AR-00004049",
 "type":"evt_strike",
 "hub_sn": "HB-00000001",
 "evt":[1493322445,27,3848]
}

d = {
 "serial_number": "SK-00008453",
 "type":"rapid_wind",
 "hub_sn": "HB-00000001",
 "ob":[1493322445,2.3,128]
}

d = {
 "serial_number": "AR-00004049",
 "type":"obs_air",
 "hub_sn": "HB-00000001",
 "obs":[[1493164835,835.0,10.0,45,0,0,3.46,1]],
 "firmware_revision": 17
}


d = { "serial_number": "SK-00008453",
 "type":"obs_sky",
 "hub_sn": "HB-00000001",
 "obs":[[1493321340,9000,10,0.0,2.6,4.6,7.4,187,3.12,1,130,'null',0,3]],
 "firmware_revision": 29
}

d = {
 "serial_number": "ST-00000512",
 "type": "obs_st",
 "hub_sn": "HB-00013030",
 "obs": [
  [1588948614,0.18,0.22,0.27,144,6,1017.57,22.37,50.26,328,0.03,3,0.000000,0,0,0,2.410,1]
  ],
 "firmware_revision": 129
}

x = TempestMessage(d)
x.parse()
print(x.type)
print(x.message)
"""
