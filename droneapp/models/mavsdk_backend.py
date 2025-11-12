#!/usr/bin/env python3
"""
MAVSDK Backend for Flask
-------------------------
Bridges synchronous Flask with asynchronous MAVSDK
"""

import asyncio
import threading
import time
from typing import Optional
from mavsdk import System
from mavsdk.offboard import OffboardError, PositionNedYaw


class MAVSDKDroneBackend:
    """Singleton MAVSDK drone backend for Flask"""

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.drone = System()
        self.loop = None
        self.thread = None
        self.connected = False
        self.armed = False
        self.in_air = False
        self.offboard_active = False

        # Telemetry data
        self.position_north = 0.0
        self.position_east = 0.0
        self.altitude = 0.0
        self.battery = 100.0
        self.flight_mode = "IDLE"

        # Start background thread
        self._start_background_loop()

        # Connect to drone
        self._run_async(self._connect())

    def _start_background_loop(self):
        """Start asyncio event loop in background thread"""
        def run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=run_loop, args=(self.loop,), daemon=True)
        self.thread.start()

    def _run_async(self, coro):
        """Run async coroutine in background loop"""
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future

    async def _connect(self):
        """Connect to PX4 and start telemetry"""
        try:
            await self.drone.connect(system_address="udp://:14540")

            # Wait for connection
            async for state in self.drone.core.connection_state():
                if state.is_connected:
                    self.connected = True
                    print("✅ MAVSDK Backend connected to PX4")
                    break

            # Start telemetry monitoring
            asyncio.ensure_future(self._monitor_telemetry(), loop=self.loop)

        except Exception as e:
            print(f"✗ Connection failed: {e}")

    async def _monitor_telemetry(self):
        """Monitor telemetry data continuously"""
        try:
            # Monitor position
            async def monitor_position():
                async for pos_ned in self.drone.telemetry.position_velocity_ned():
                    self.position_north = pos_ned.position.north_m
                    self.position_east = pos_ned.position.east_m
                    self.altitude = abs(pos_ned.position.down_m)

            # Monitor armed status
            async def monitor_armed():
                async for armed in self.drone.telemetry.armed():
                    self.armed = armed

            # Monitor in_air status
            async def monitor_in_air():
                async for in_air in self.drone.telemetry.in_air():
                    self.in_air = in_air

            # Monitor flight mode
            async def monitor_flight_mode():
                async for flight_mode in self.drone.telemetry.flight_mode():
                    flight_mode_str = str(flight_mode).replace("FlightMode.", "")
                    self.flight_mode = flight_mode_str

                    # Update offboard_active flag based on actual flight mode
                    if "OFFBOARD" in flight_mode_str:
                        self.offboard_active = True
                    else:
                        # If flight mode changed away from OFFBOARD, update flag
                        if self.offboard_active and "OFFBOARD" not in flight_mode_str:
                            self.offboard_active = False
                            print(f"⚠️ Offboard mode deactivated (flight mode changed to {flight_mode_str})")

            # Monitor battery
            async def monitor_battery():
                async for battery in self.drone.telemetry.battery():
                    self.battery = battery.remaining_percent * 100

            # Run all monitors concurrently
            await asyncio.gather(
                monitor_position(),
                monitor_armed(),
                monitor_in_air(),
                monitor_flight_mode(),
                monitor_battery()
            )

        except Exception as e:
            print(f"Telemetry monitoring error: {e}")

    # Synchronous command methods for Flask

    def arm(self):
        """Arm the drone"""
        async def _arm():
            try:
                await self.drone.action.arm()
                print("✅ Armed")
            except Exception as e:
                print(f"✗ Arm failed: {e}")

        self._run_async(_arm())

    def takeoff(self, altitude=2.0):
        """Takeoff to specified altitude"""
        async def _takeoff():
            try:
                # Stop offboard mode if active (prevents conflict with takeoff mode)
                if self.offboard_active:
                    await self.drone.offboard.stop()
                    self.offboard_active = False
                    print("⚠️ Stopping offboard mode before takeoff")
                    await asyncio.sleep(0.5)

                # Arm if not armed
                if not self.armed:
                    await self.drone.action.arm()
                    await asyncio.sleep(1)

                # Set takeoff altitude and takeoff
                await self.drone.action.set_takeoff_altitude(altitude)
                await self.drone.action.takeoff()
                print(f"✅ Taking off to {altitude}m")
            except Exception as e:
                print(f"✗ Takeoff failed: {e}")

        self._run_async(_takeoff())

    def land(self):
        """Land the drone"""
        async def _land():
            try:
                # Stop offboard if active
                if self.offboard_active:
                    await self.drone.offboard.stop()
                    self.offboard_active = False

                await self.drone.action.land()
                print("✅ Landing")
            except Exception as e:
                print(f"✗ Land failed: {e}")

        self._run_async(_land())

    def goto_position(self, north, east, altitude):
        """Navigate to position using offboard mode"""
        async def _goto():
            try:
                # Engage offboard if not active
                if not self.offboard_active:
                    # Get current position
                    pos_ned = await self.drone.telemetry.position_velocity_ned().__anext__()
                    current_north = pos_ned.position.north_m
                    current_east = pos_ned.position.east_m
                    current_down = pos_ned.position.down_m

                    # Send setpoints before starting offboard
                    for _ in range(10):
                        await self.drone.offboard.set_position_ned(
                            PositionNedYaw(current_north, current_east, current_down, 0)
                        )
                        await asyncio.sleep(0.2)

                    # Start offboard
                    await self.drone.offboard.start()
                    self.offboard_active = True
                    print("✅ Offboard mode active")

                # Send position command
                target_down = -abs(altitude)
                await self.drone.offboard.set_position_ned(
                    PositionNedYaw(north, east, target_down, 0)
                )
                print(f"✅ Navigating to N={north}, E={east}, Alt={altitude}m")

            except Exception as e:
                print(f"✗ Goto position failed: {e}")

        self._run_async(_goto())

    def emergency_stop(self):
        """Emergency stop - kill motors"""
        async def _emergency():
            try:
                await self.drone.action.kill()
                print("⚠️ EMERGENCY STOP")
            except Exception as e:
                print(f"✗ Emergency stop failed: {e}")

        self._run_async(_emergency())

    def move_relative(self, north=0.0, east=0.0, down=0.0, yaw=0.0):
        """Move relative to current position"""
        async def _move():
            try:
                # Engage offboard if not active
                if not self.offboard_active:
                    # Get current position
                    pos_ned = await self.drone.telemetry.position_velocity_ned().__anext__()
                    current_north = pos_ned.position.north_m
                    current_east = pos_ned.position.east_m
                    current_down = pos_ned.position.down_m

                    # Send setpoints before starting offboard
                    for _ in range(10):
                        await self.drone.offboard.set_position_ned(
                            PositionNedYaw(current_north, current_east, current_down, 0)
                        )
                        await asyncio.sleep(0.2)

                    # Start offboard
                    await self.drone.offboard.start()
                    self.offboard_active = True
                    print("✅ Offboard mode active for manual control")

                # Calculate new position relative to current
                new_north = self.position_north + north
                new_east = self.position_east + east
                new_down = -(self.altitude + down)  # down is negative in NED

                # Send position command
                await self.drone.offboard.set_position_ned(
                    PositionNedYaw(new_north, new_east, new_down, yaw)
                )
                print(f"Moving: N+{north}, E+{east}, D+{down}, Yaw={yaw}")

            except Exception as e:
                print(f"✗ Move relative failed: {e}")

        self._run_async(_move())

    # Manual control commands for controller sidebar
    def up(self):
        """Throttle up (increase altitude by 0.5m)"""
        self.move_relative(down=-0.5)  # Negative down = up

    def down(self):
        """Throttle down (decrease altitude by 0.5m)"""
        self.move_relative(down=0.5)  # Positive down = down

    def forward(self):
        """Pitch forward (move 0.5m north)"""
        self.move_relative(north=0.5)

    def back(self):
        """Pitch back (move 0.5m south)"""
        self.move_relative(north=-0.5)

    def left(self):
        """Roll left (move 0.5m west)"""
        self.move_relative(east=-0.5)

    def right(self):
        """Roll right (move 0.5m east)"""
        self.move_relative(east=0.5)

    def clockwise(self):
        """Yaw clockwise (rotate 15 degrees)"""
        self.move_relative(yaw=15)

    def counterclockwise(self):
        """Yaw counterclockwise (rotate -15 degrees)"""
        self.move_relative(yaw=-15)

    def stop(self):
        """Stop movement (hold current position)"""
        async def _stop():
            try:
                if self.offboard_active:
                    # Set current position as target to stop movement
                    await self.drone.offboard.set_position_ned(
                        PositionNedYaw(
                            self.position_north,
                            self.position_east,
                            -self.altitude,
                            0
                        )
                    )
                    print("✅ Holding position")
            except Exception as e:
                print(f"✗ Stop failed: {e}")

        self._run_async(_stop())

    # Telemetry getters

    def get_position(self):
        """Get current position"""
        return {
            'north': self.position_north,
            'east': self.position_east,
            'altitude': self.altitude
        }

    def get_status(self):
        """Get drone status"""
        return {
            'connected': self.connected,
            'armed': self.armed,
            'in_air': self.in_air,
            'offboard_active': self.offboard_active,
            'flight_mode': self.flight_mode,
            'battery': self.battery
        }

    # Legacy compatibility methods (for old backend API)

    @property
    def altitude_str(self):
        return f"Altitude: {self.altitude:.2f} m"

    @property
    def battery_remaining_str(self):
        return f"Battery: {self.battery:.1f}%"

    @property
    def battery_voltage_str(self):
        return f"Battery Voltage: N/A"

    @property
    def pitch_str(self):
        return "Pitch: 0.0"

    @property
    def roll_str(self):
        return "Roll: 0.0"

    @property
    def yaw_str(self):
        return "Yaw: 0.0"

    @property
    def throttle(self):
        return 0

    @property
    def flight_mode_str(self):
        return f"Flight Mode: {self.flight_mode}"

    @property
    def flight_status_str(self):
        if self.in_air:
            return "Flight Status: Flying"
        elif self.armed:
            return "Flight Status: Armed (On Ground)"
        else:
            return "Flight Status: Disarmed"

    def print_all(self):
        """Print all telemetry"""
        pass  # No-op for compatibility


# Alias for compatibility
VehicleCommand = MAVSDKDroneBackend
