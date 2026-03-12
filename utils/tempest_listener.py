#!/usr/bin/env python3

import json
import redis
import socket
from datetime import date, datetime

from app.notifications import Notifications
import app.tempest_log
import app.tempest_message as tm

# ip/port to listen to
BROADCAST_IP = '192.168.1.54'
BROADCAST_PORT = 50222

MPSTOMPH = 2.2369363      # metres/sec to MPH
MILESTOKM =  0.6214       # miles to km

# Tempest events we're interested in
EVENTS = ['evt_precip', 'evt_strike', 'rapid_wind', 'obs_sky', 'obs_st']
# Redis database 1 Wind_Threshold holds a dynamic value: this is a fallback default
WIND_THRESHOLD = 10

today = date.today()

r = redis.Redis(db = 1, decode_responses = True)
key = f"Tempest:Wind_Gust:{today.strftime('%Y%m%d')}"
highest_today = r.get(key) or 0
highest_today = float(highest_today)

wind_threshold = r.get("Wind_Threshold") or WIND_THRESHOLD
wind_threshold = float(wind_threshold)

log = app.tempest_log.loggr
##import sys
##log.basicConfig(stream=sys.stdout, level=log.DEBUG, format=tempest_log.FORMAT, force=True)

# create broadcast listener socket
def create_broadcast_listener_socket(broadcast_ip, broadcast_port):

    # from: https://github.com/ninedraft/python-udp/blob/master/client.py

    b_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)  # UDP

    # Enable port reusage so we will be able to run multiple clients and servers on single (host, port).
    # Do not use socket.SO_REUSEADDR except you using linux(kernel<3.9): goto https://stackoverflow.com/questions/14388706/how-do-so-reuseaddr-and-so-reuseport-differ for more information.
    # For linux hosts all sockets that want to share the same address and port combination must belong to processes that share the same effective user ID!
    # So, on linux(kernel>=3.9) you have to run multiple servers and clients under one user to share the same (host, port).
    # Thanks to @stevenreddie
    b_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

    # Enable broadcasting mode
    b_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    ## NOTE: Bind against all interfaces
    b_sock.bind(('', broadcast_port))

    return b_sock

# record highest wind gust of the day so far
def highest_wind(gust, time):
    gust = round( (gust * MPSTOMPH), 2 )
    result = False
    global highest_today
    global today
    global wind_threshold

    # report on anything over threshold
    if gust > wind_threshold:
        notify_key = f"WindGust:{int(gust // 3)}"
        result = {'time': time, 'event': 'WIND', 'notify_key': notify_key,
                  'description': f"wind gust of {gust} miles per hour recorded"}

    # record highest today
    if gust > highest_today:
        highest_today = gust
        # store highest for 'today'
        with redis.Redis(db = 1) as r:
            key = f"Tempest:Wind_Gust:{today.strftime('%Y%m%d')}"
            r.set(key, highest_today)
        log.info(f"New daily wind gust high of {gust} MPH recorded.")

    return result


# create the listener socket
b_listener = create_broadcast_listener_socket(BROADCAST_IP, BROADCAST_PORT)

while True:

    data, addr = b_listener.recvfrom(4096)

    if addr[0] != BROADCAST_IP:
        continue

    # convert data from json
    data_dict = json.loads(data)

    tempest = tm.TempestMessage(data_dict)
    tempest.parse()

    log.debug(tempest.message)

    if (n := date.today()) != today:
        today = n
        highest_today = 0

    if tempest.type in EVENTS:

        if tempest.type == 'evt_precip':
            details = {'time': tempest.message['message_time'], 'event': 'RAIN',
                       'description': "it's started raining"}

        elif tempest.type == 'evt_strike':
            miles = int( int(tempest.message['distance']) * MILESTOKM )
            details = {'time': tempest.message['message_time'], 'event': 'LIGHTNING',
                       'description': f"lightning strike detected approximately {miles} miles away"}

        elif tempest.type == 'rapid_wind':
            details = highest_wind(tempest.message['wind_speed'], tempest.message['message_time'])

        elif tempest.type == 'obs_st':
            details = {'time': tempest.message['message_time'], 'event': 'STATUS',
                       'temperature': tempest.message['air_temperature'], 'humidity': tempest.message['humidity'],
                       'battery': tempest.message['battery']}

            windy = highest_wind(tempest.message['wind_gust'], tempest.message['message_time'])
            if windy:
                log.info(windy)
                Notifications().send(['alexa'], 'Heading', windy['description'])

        elif tempest.type == 'obs_sky':
            details = highest_wind(tempest.message['wind_gust'], tempest.message['message_time'])


        if details:
            log.info(details)
            if 'description' in details:
                notify_key = details['notify_key'] if ('notify_key' in details) else False
                Notifications().send(['alexa'], 'Heading', details['description'], key=notify_key)

