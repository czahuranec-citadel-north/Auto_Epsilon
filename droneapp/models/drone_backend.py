#!/usr/bin/env python

import logging

import asyncio
import threading

#from datetime import datetime

from mavsdk import System
from mavsdk.offboard import VelocityNedYaw

#from mavsdk.offboard import Attitude, VelocityNedYaw
#from mavsdk.telemetry import FlightMode

from droneapp.models.base import Singleton

logger = logging.getLogger(__name__)

DEFAULT_VELOCITY = 10

#sudo mavproxy.py --master=/dev/serial0 --baudrate=921600 --out=tcpin:0.0.0.0:5762
#.\mavsdk_server_win32.exe -p 50051 tcp://192.168.7.114:5762

class VehicleCommand:
    __metaclass__ = Singleton
    __instance = None

    @staticmethod
    def get_instance():
        """ Static access method. """
        if VehicleCommand.__instance is None:
            VehicleCommand()
        return VehicleCommand.__instance

    def __init__(self):
        """ Virtually private constructor. """
        if VehicleCommand.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            VehicleCommand.__instance = self
            #self.vehicle = System(mavsdk_server_address='192.168.1.70', port=50051)
            self.vehicle = System(mavsdk_server_address='192.168.56.101', port=50051)
            self.connected = False
            # self.vehicle.parameters['PLND_ENABLED'] = 1
            # self.vehicle.parameters['PLND_TYPE'] = 1
            # self.vehicle.parameters['PLND_EST_TYPE'] = 0
            # self.vehicle.parameters['LAND_SPEED'] = 30

            self.velocity = -.5  # m/s
            self.takeoff_height = 2  # m
            self.default_speed = DEFAULT_VELOCITY

            self.move_coefficient = {'PITCH_K': 0, 'ROLL_K': 0, 'YAW_K': 0, 'THROTTLE_K': 0}
            self.distance_threshold = 1.5  # m
            self.time_last = 0
            self.avoidance_active = False
            self.servo_pwm_start = 1500
            self.servo_num = 13

            self.pitch = 0
            self.roll = 0
            self.yaw = 0
            self.throttle = 0.5
            self.brake = 0

            self.battery_remaining_str = "Battery Remaining: Unknown"
            self.battery_voltage_str = "Battery Voltage: Unknown"
            self.pitch_str = "Pitch: Unknown"
            self.yaw_str = "Yaw: Unknown"
            self.roll_str = "Roll: Unknown"
            self.altitude_str = f"Altitude: Unknown"
            self.flight_mode_str = f"Flight Mode: Unknown"
            self.flight_status_str = "Flight Status: Unknown"

            self.details_enabled = False
            self.attitude_task = None

    async def get_connection(self):
        #if not self.connected:
        #await self.vehicle.connect('serial:///dev/serial0:115200')
        #await self.vehicle.connect('192.168.1.222:50051')
        await self.vehicle.connect('192.168.56.101:50051')

        print("Waiting for drone to connect...")
        async for state in self.vehicle.core.connection_state():
            if state.is_connected:
                print(f"-- Connected to drone!")
                self.connected = True
                self.details_enabled = True
                break
        return self

    async def arm_and_takeoff(self, target_height=2.0):
        # real drone IP = 'tcp:10.0.0.131:5762' '127.0.0.1:14550 for SITL'
        # .\mavsdk_server_win32.exe -p 50051 tcp://192.168.7.114:5762
        await self.get_connection()

        # async for health in self.vehicle.telemetry.health():
        #     if health.is_global_position_ok and health.is_home_position_ok:
        #         print("-- Global position state is good enough for flying.")
        #         break

        # Execute the maneuvers
        print("-- Arming")
        await self.vehicle.action.hold()
        await self.vehicle.action.arm()

        print("-- Taking off")
        #await self.vehicle.offboard.set_velocity_ned(VelocityNedYaw(0, 0, 0, 0))
        #await self.vehicle.offboard.start()
        #self.vehicle.calibration.calibrate_accelerometer()
        #offboard_is_active = await self.vehicle.offboard.is_active()
        #print("-- Is Offboard active?", offboard_is_active)
        #await self.attitude(0, 1, 0, 0, 0)

        await self.vehicle.action.set_takeoff_altitude(target_height)
        await self.vehicle.action.takeoff()

        await asyncio.sleep(5)
        self.attitude_task = asyncio.ensure_future(self.set_rc_channel())

        return self

    async def print_all(self):
        if self.details_enabled:
            try:
                await self.print_battery()
                await self.print_attitude()
                await self.print_altitude()
                await self.print_flight_mode()
                await self.print_is_in_air()
            except Exception as ex:
                print(f"Exception encountered: {ex}")
        return self

    async def print_battery(self):
        """ Prints the battery """

        await self.get_connection()

        async for battery in self.vehicle.telemetry.battery():
            remaining = battery.remaining_percent
            voltage = battery.voltage_v
            self.battery_remaining_str = f"Battery Remaining: {remaining}%"
            self.battery_voltage_str = f"Battery Voltage: {voltage}"
            print(self.battery_remaining_str)
            print(self.battery_voltage_str)
            break

        return self

    async def print_attitude(self):
        """ Prints the attitude """

        await self.get_connection()

        async for attitude in self.vehicle.telemetry.attitude_euler():
            pitch = attitude.pitch_deg
            yaw = attitude.yaw_deg
            roll = attitude.roll_deg
            self.pitch_str = f"Pitch: {pitch}"
            self.yaw_str = f"Yaw: {yaw}"
            self.roll_str = f"Roll: {roll}"
            print(self.pitch_str)
            print(self.yaw_str)
            print(self.roll_str)
            break

        return self

    async def print_altitude(self):
        """ Prints the altitude when it changes """

        await self.get_connection()

        async for position in self.vehicle.telemetry.position():
            altitude = round(position.relative_altitude_m)
            self.altitude_str = f"Altitude: {altitude}"
            print(self.altitude_str)
            break

        return self

    async def print_flight_mode(self):
        """ Prints the flight mode when it changes """

        await self.get_connection()

        async for flight_mode in self.vehicle.telemetry.flight_mode():
            self.flight_mode_str = f"Flight Mode: {flight_mode}"
            print(self.flight_mode_str)
            break

        return self

    async def print_is_in_air(self):
        """ Monitors whether the drone is flying or not and
        returns after landing """

        async for is_in_air in self.vehicle.telemetry.in_air():
            if is_in_air:
                self.flight_status_str = "Flight Status: Flying"
            else:
                self.flight_status_str = "Flight Status: Landed"
            break
        return self

    async def observe_is_in_air(self, running_tasks):
        """ Monitors whether the drone is flying or not and
        returns after landing """

        was_in_air = False

        async for is_in_air in self.vehicle.telemetry.in_air():
            if is_in_air:
                was_in_air = is_in_air

            if was_in_air and not is_in_air:
                for task in running_tasks:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                await asyncio.get_event_loop().shutdown_asyncgens()
                return

    async def takeoff(self, target_height):
        await self.arm_and_takeoff(target_height)
        return self

    async def land(self):
        await self.get_connection()
        print_altitude_task = asyncio.ensure_future(self.print_altitude())
        print_flight_mode_task = asyncio.ensure_future(self.print_flight_mode())

        running_tasks = [print_altitude_task, print_flight_mode_task, self.attitude_task]
        asyncio.ensure_future(self.observe_is_in_air(running_tasks))

        print('Landing...')
        await self.vehicle.action.land()

        print('Landed!')

        return self

    async def set_rc_channel(self):
        await self.get_connection()

        await self.vehicle.manual_control.set_manual_control_input(float(0), float(0), float(self.throttle), float(0))
        await self.vehicle.manual_control.start_altitude_control()
        while True:
            print(f"pitch = {self.pitch}, roll = {self.roll}, throttle = {self.throttle}, yaw = {self.yaw}")
            await self.vehicle.manual_control.set_manual_control_input(float(self.pitch), float(self.roll), float(self.throttle), float(self.yaw))
            await asyncio.sleep(0.1)

    async def up(self):
        self.throttle += .02
        return self

    async def down(self):
        self.throttle -= .02
        return self

    async def left(self):
        self.roll -= .02
        return self

    async def right(self):
        self.roll += .02
        return self

    async def forward(self):
        self.pitch -= .02
        return self

    async def back(self):
        self.pitch += .02
        return self

    async def clockwise(self):
        self.yaw += .02
        return self

    async def counterclockwise(self):
        self.yaw -= .02
        return self

    async def stop(self):
        self.pitch = 0
        self.yaw = 0
        self.roll = 0
        self.throttle = .5
        return self

    async def serv_down(self):
        self.servo_pwm_start += .02
        await self.vehicle.action.set_actuator(self.servo_num, self.servo_pwm_start)
        return self

    async def serv_up(self):
        self.servo_pwm_start -= .02
        await self.vehicle.action.set_actuator(self.servo_num, self.servo_pwm_start)
        return self

    async def activate_sup(self):
        pwm_signal = 20000
        await self.vehicle.action.set_actuator(14, pwm_signal)
        return self

    def set_speed(self, speed):
        self.default_speed = speed
        return self
