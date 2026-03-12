#!/usr/bin/env python
#
# What it says on the tin - skewed towards Shelly devices, cos...

from app import app

import sys
import traceback
import urllib3

class DeviceControl:

    def __init__(self, id):
        self.id = id
        self.http = urllib3.PoolManager(retries=2, timeout=5.0)

        if id in app.config['DEVICES']:
            self.config = app.config['DEVICES'][id]
        else:
            raise RuntimeError(f"{id} is not a known device - check app/config/DEVICES")

        self.fake_reply = FakeResponse()

    # Returns: False is something went wrong, else 'on'/'off' as the previous atate of the switch
    def turn_on(self):
        self.fake_reply.value = False     # fake it to off
        r = self.__call_device__(f"http://{self.config['ip']}{self.config['switch_on']}")
        #print(r)
        #print(r.data)
        if r:
            return 'on' if r.json()['was_on'] else 'off'
        else:
            return r

    # Returns: False is something went wrong, else 'on'/'off' as the previous atate of the switch
    def turn_off(self):
        self.fake_reply.value = True       # fake it to on
        r = self.__call_device__(f"http://{self.config['ip']}{self.config['switch_off']}")
        if r:
            return 'on' if r.json()['was_on'] else 'off'
        else:
            return r

    # Returns: Status values as a dictionary
    def get_status(self, id=100):
        r = self.__call_device__(f"http://{self.config['ip']}{self.config['get_status']}")
        if r:
            return r.json()
        else:
            return r

    # Get/Set KVS (on a Shelly device)
    def kvs(self, type, key, value=0):
        resp = value
        if type == 'get':
            r = self.__call_device__(f"http://{self.config['ip']}/rpc/KVS.Get?key={key}")
            if r: resp = r.json()['value']
        elif type == 'set':
            r = self.__call_device__(f"http://{self.config['ip']}/rpc/KVS.Set?key={key}&value={value}")
        else:
            raise ProgramRuntimeError("Bad thing")

        return resp if r else r

    def start_script(self, script_number):
        r = self.__call_device__(f"http://{self.config['ip']}/rpc/Script.Start?id={script_number}")
        if r:
            return 'running' if r.json()['was_running'] else 'not_running'
        else:
            return r

    def stop_script(self, script_number):
        r = self.__call_device__(f"http://{self.config['ip']}/rpc/Script.Stop?id={script_number}")
        if r:
            return 'running' if r.json()['was_running'] else 'not_running'
        else:
            return r

    def __call_device__(self, parms, method='GET'):
        if ('disabled' in self.config) and self.config['disabled']:
            return self.fake_reply
        try:
            res = self.http.request(method, parms)
            if res and (res.status == 200): return res
            print(res.status, file=sys.stderr)
            print(res.data, file=sys.stderr)
            return False
        except urllib3.exceptions.HTTPError as ex:
            print(ex, file=sys.stderr)
            traceback.print_exc()
            return False

class FakeResponse:
    def __init__(self):
        self.value = ''
    def json(self):
        return {'was_on': self.value}

if __name__ == "__main__":

    #x = DeviceControl('ZONE1')
    #b = x.kvs('get', 'pulse_temp')
    #print(b)
    #exit()

    import argparse
    parser = argparse.ArgumentParser(__file__)
    parser.add_argument("device", help="Name of device to control e.g. DHW.", type=str)
    parser.add_argument("state", help="What to do with it e.g/ turn ON/OFF.", type=str)
    args = parser.parse_args()

    x = DeviceControl(args.device)
    if (args.state) == 'ON':
        res = x.turn_on()
        print(res)
        print('turned on')
    elif (args.state) == 'OFF':
        res = x.turn_off()
        print(res)
        print(type(res))
        print('turned off')

    #time.sleep(3)
    #y = DeviceControl('XYZ123')
