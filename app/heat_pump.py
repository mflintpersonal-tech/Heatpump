#!/usr/bin/python3
#
# class to access Heat Pump over RS485 interface using modbus protocol
#

import itertools
import minimalmodbus
import serial

#from . import pump_value
import pump_value as pv

def to_ranges(iterable):
    iterable = sorted(set(iterable))
    for key, group in itertools.groupby(enumerate(iterable),
                                        lambda t: t[1] - t[0]):
        group = list(group)
        yield group[0][1], group[-1][1]

class HeatPump:

    DEFAULT_DEVICE = '/dev/ttyUSB0'

    # From Modbus RS485 settings (Parameters 52 01 to 52 04)
    BAUD = 19200
    DATABITS = serial.EIGHTBITS
    STOPBITS = serial.STOPBITS_TWO
    PARITY = 0
  
    UID = 1  # ?????
  
    # convert register type to number used in modbus interface (see https://minimalmodbus.readthedocs.io/en/stable/modbusdetails.html)
    READ_TYPES = {
        'coil':     (1, 'bits'),
        'holding':  (3, 'registers'),
        'input':    (4, 'registers')
    }
    WRITE_TYPES = {
        'coil':     (15, 'bits'),
        'holding':  (16, 'registers')
        #'input':    4   Cannot write to an Input register
    }

    SIGN_BIT = 1 << 15

    def __init__(self, device = False):

        self.device = device or self.DEFAULT_DEVICE
    
        self.instrument = minimalmodbus.Instrument(self.device, self.UID)  # port name, slave address (in decimal)
        self.instrument.serial.stopbits = serial.STOPBITS_TWO

    def read_registers(self, register, number, type_value):
        values = self.instrument.read_registers(register, number, type_value)   # read registers starting at n
        return values

    def write_register(self, register, value, type_value):
        sign = True if value < 0 else False
        self.instrument.write_register(register, value, 0, type_value, sign)    # write a register
        return True

    def read_bit_registers(self, register, number, type_value):
        values = self.instrument.read_bits(register, number, type_value)        # read registers starting at n
        return values

    def write_bit_register(self, register, value, type_value):
        self.instrument.write_bit(register, value, type_value)                  # write bit register
        return True

    # access register values
    def read(self, register, number, type):
        type_value, kind = self.READ_TYPES[type]
    
        if kind == 'registers':
            data = self.read_registers(register, number, type_value)
            data = [ (d & (self.SIGN_BIT - 1)) - (d & self.SIGN_BIT) for d in data ]
        elif kind == 'bits':
            data = self.read_bit_registers(register, number, type_value)
            data = [ int(d) for d in data]
        else:
            raise RuntimeError(f"Unknown register type {type}")
        return data

    # read an array of values; passed array of parameters; can be of any type
    def read_values(self, parameters):
        value = {}

        for parm in parameters:
            pump_value = pv.Pump(parm)
            pump_value.set_value(self.read(pump_value.register(), 1, pump_value.type())[0])
            value[parm] = pump_value

        return value

    # read an array of (input) registers : list is an array of input/holding_register parameters e.g. ["01 00", "31 02"]
    #     ------------ ALL PARAMETERS MUST BE OF SAME TYPE -------------- e.g. all holding registers
    # returns - hash of Pump::Value items with current register value set
    def read_range(self, parm_list, type = 'input'):
        reg_list = [pv.Pump.parm_to_reg(l) for l in parm_list]
        ranges = list(to_ranges(reg_list))                    # shrink to ranges

        data = []
        for range in ranges:
            data += self.read(range[0], (range[1] - range[0] + 1), type)

        value = {}
        for parm in parm_list:
          pump_value = pv.Pump(parm)
          pump_value.set_value(data[len(value)])
          value[parm] = pump_value

        return value

    # read an explicit register value (not really used - testing mainly)
    def read_register(self, type, register):
        x = self.read(register, 1, type)
        return x[0] if x is not None else None
        
    # write (a list) of register values, passed a list of parameters and values
    def write_values(self, plist):
    
        for parm, value in plist:
            print(parm)
            print(value)
            details = pv.Pump.parm_details(parm)
            print(repr(details))
            type_value, kind = self.WRITE_TYPES[details['type']]
    
            if kind == 'registers':
                self.write_register(details['register'], value, type_value)
            elif kind == 'bits':
                self.write_bit_register(details['register'], value, type_value)
            else:
                raise RuntimeError(f"Unwritable register type {details['type']}")


"""
interface = HeatPump()
#print(interface)

pvalue = interface.read(1, 7, 'input')
print(repr(pvalue))
pvalue = interface.read(4, 1, 'holding')
print(repr(pvalue))
print('COIL!')
pvalue = interface.read(2, 1, 'coil')
print(repr(pvalue))
print(repr(interface.read_register('input', 1)))
print("above value should match first value on first output")

l = ['01 01', '01 02', '01 03']
x = interface.read_range(l)
print(repr(x))

l = ['21 01', '21 02', '21 03', '21 04']
x = interface.read_range(l, type = 'holding')
print(repr(x))
"""
