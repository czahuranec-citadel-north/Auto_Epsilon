#!/usr/bin/env python

import time

from dronekit import connect, VehicleMode
from pymavlink import mavutil

vehicle = connect('/dev/ttyAMA0', wait_ready=True,baud=57600)

pivot_value = 1500
rail = 8

while True:
    val = raw_input('Enter a for activation - or w or d to pivot:')
    if val == 'w' or val == 'd':
        if val == 'd':
            pivot_value -= 100
        elif val == 'w':
            pivot_value += 100
        print(pivot_value)

        msg = vehicle.message_factory.command_long_encode(
                0,
                0,
                mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                0,
                rail,
                pivot_value,
                0,
                0,
                0,
                0,
                0)
        vehicle.send_mavlink(msg)

    elif val == 'a':

        msg = vehicle.message_factory.command_long_encode(
                0,
                0,
                mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                0,
                7,
                20000,
                0,
                0,
                0,
                0,
                0)
        vehicle.send_mavlink(msg)
        print('active!')
        time.sleep(3)

        msg = vehicle.message_factory.command_long_encode(
                0,
                0,
                mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                0,
                7,
                0,
                0,
                0,
                0,
                0,
                0)
        vehicle.send_mavlink(msg)
        print('deactivated!')
