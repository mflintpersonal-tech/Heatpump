import os
from datetime import timedelta

class Config(object):
    dir = os.path.dirname(__file__)
    DATABASE = os.path.join(dir, '..', 'heatpump.db')
    APP_LOG = '/var/log/pump_monitor.log'
    SECRET_KEY = b'<database secret>'
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    MAIL = {'host':     '<mail host>',                 # e.g. example.com
            'port':     '587',                         # port
            'username': '<user>',                      # username
            'password': '<password>'                   # password
           }

    DEVICES = {  'DHW': {'ip': '192.168.1.nnn', 'name': "shellyplus1-xxxxxxx",
                         'switch_on': '/rpc/Switch.Set?id=0&on=true',
                         'switch_off': '/rpc/Switch.Set?id=0&on=false',
                        },
               'ZONE1': {'ip': '192.168.1.ooo', 'name': "shellyplus2pm-xxxxxxxx",
                         'switch_on': '/rpc/Switch.Set?id=0&on=true',
                         'switch_off': '/rpc/Switch.Set?id=0&on=false',
                         'disabled': False
                        },
               'ZONE2': {'ip': '192.168.1.ppp', 'name': "shellyplus2pm-xxxxxxxxx",
                         'switch_on': '/rpc/Switch.Set?id=1&on=true',
                         'switch_off': '/rpc/Switch.Set?id=1&on=false',
                         'disabled': False
                        },
               # Temperature probes attached to ShellyPlus1
               'PROBE1': {'ip': '192.168.1.qqq', 'name': "shellyplus1-xxxxxxxx",
                         'get_status': '/rpc/Temperature.GetStatus?id=100'
                        },
               # Temperature probes attached to ShellyPlus1
               'PROBE2': {'ip': '192.168.1.rrr', 'name': "shellyplus1-xxxxxxxxxxx",
                         'get_status': '/rpc/Temperature.GetStatus?id=101'
                        }
              }

