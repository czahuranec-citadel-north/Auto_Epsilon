#!/usr/bin/env python3
"""
MAVSDK Waypoint Navigator
-------------------------
Purpose: Class-based waypoint navigation interface using MAVSDK

Features:
- Clean async/await API
- Automatic connection and health monitoring
- Waypoint navigation with position accuracy checking
- Offboard mode management
- Error handling and recovery

Architecture:
  AI/Controller → MAVSDKNavigator → MAVSDK → MAVLink → PX4
"""

import asyncio
from typing import Tuple, Optional
from mavsdk import System
from mavsdk.offboard import (OffboardError, PositionNedYaw)


class MAVSDKNavigator:
    """Waypoint navigation interface using MAVSDK"""

    def __init__(self, system_address: str = "udp://:14540"):
        """
        Initialize navigator

        Args:
            system_address: MAVLink connection string (default: udp://:14540)
        """
        self.system_address = system_address
        self.drone = System()
        self.connected = False
        self.armed = False
        self.offboard_active = False

        # Current position (NED coordinates)
        self.current_north = 0.0
        self.current_east = 0.0
        self.current_down = 0.0  # Negative altitude
        self.current_yaw = 0.0

        # Navigation parameters
        self.waypoint_threshold = 0.5  # meters - how close to consider "reached"
        self.position_update_rate = 0.2  # seconds - 5Hz setpoint rate

    async def connect(self, timeout_sec: float = 10.0) -> bool:
        """
        Connect to PX4 and wait for ready

        Args:
            timeout_sec: Connection timeout

        Returns:
            True if connected successfully
        """
        print(f"Connecting to PX4 at {self.system_address}...")
        await self.drone.connect(system_address=self.system_address)

        # Wait for connection with timeout
        try:
            async def wait_connection():
                async for state in self.drone.core.connection_state():
                    if state.is_connected:
                        self.connected = True
                        return True

            await asyncio.wait_for(wait_connection(), timeout=timeout_sec)
            print("✅ Connected to PX4!")
            return True

        except asyncio.TimeoutError:
            print(f"✗ Connection timeout after {timeout_sec}s")
            return False

    async def wait_for_armable(self, timeout_sec: float = 30.0) -> bool:
        """
        Wait until drone is armable (all sensors calibrated)

        Args:
            timeout_sec: How long to wait

        Returns:
            True if armable within timeout
        """
        print("Waiting for armable status...")
        start_time = asyncio.get_event_loop().time()

        check_count = 0
        while (asyncio.get_event_loop().time() - start_time) < timeout_sec:
            check_count += 1

            async for health in self.drone.telemetry.health():
                if health.is_armable:
                    print(f"✅ Drone is armable (check #{check_count})")
                    return True
                else:
                    print(f"⏳ Not armable yet (check #{check_count}):")
                    print(f"   Accel: {health.is_accelerometer_calibration_ok}, "
                          f"Mag: {health.is_magnetometer_calibration_ok}, "
                          f"Gyro: {health.is_gyrometer_calibration_ok}")
                    print(f"   Local pos: {health.is_local_position_ok}, "
                          f"Global pos: {health.is_global_position_ok}, "
                          f"Home: {health.is_home_position_ok}")
                break

            await asyncio.sleep(3)

        print(f"✗ Timeout waiting for armable status")
        return False

    async def arm(self) -> bool:
        """
        Arm the drone

        Returns:
            True if armed successfully
        """
        print("Arming...")
        await self.drone.action.arm()

        # Wait for armed confirmation
        async for armed in self.drone.telemetry.armed():
            if armed:
                self.armed = True
                print("✅ Armed!")
                return True

        return False

    async def takeoff(self, altitude_m: float = 2.0) -> bool:
        """
        Takeoff to specified altitude

        Args:
            altitude_m: Target altitude in meters (positive up)

        Returns:
            True if reached target altitude
        """
        print(f"Taking off to {altitude_m}m...")
        await self.drone.action.set_takeoff_altitude(altitude_m)
        await self.drone.action.takeoff()

        # Monitor altitude with timeout
        start_time = asyncio.get_event_loop().time()
        stable_count = 0
        last_alt = 0.0

        async for position in self.drone.telemetry.position():
            current_alt = abs(position.relative_altitude_m)
            elapsed = asyncio.get_event_loop().time() - start_time

            print(f"  Altitude: {current_alt:.2f}m (target: {altitude_m}m)", end="\r")

            # Check if we're within 30cm of target
            if current_alt >= altitude_m - 0.3:
                print(f"\n✅ Reached altitude: {current_alt:.2f}m")
                # Update current position
                self.current_down = -abs(position.relative_altitude_m)  # NED down
                return True

            # Check if altitude has stabilized (even if below target)
            if abs(current_alt - last_alt) < 0.05:  # Less than 5cm change
                stable_count += 1
                if stable_count >= 20 and current_alt >= altitude_m * 0.8:  # 80% of target and stable
                    print(f"\n✅ Altitude stabilized at: {current_alt:.2f}m (close enough to {altitude_m}m)")
                    self.current_down = -abs(position.relative_altitude_m)
                    return True
            else:
                stable_count = 0

            last_alt = current_alt

            # Timeout after 60 seconds
            if elapsed > 60:
                print(f"\n⚠️ Takeoff timeout at {current_alt:.2f}m")
                return False

            await asyncio.sleep(0.1)

        return False

    async def engage_offboard_mode(self) -> bool:
        """
        Engage offboard mode (required before goto_position)

        CRITICAL: Must send setpoints for 2 seconds before engaging

        Returns:
            True if offboard mode activated
        """
        print("Engaging offboard mode...")

        # Get current position from telemetry (NED coordinates)
        try:
            pos_ned = await self.drone.telemetry.position_velocity_ned().__anext__()
            self.current_north = pos_ned.position.north_m
            self.current_east = pos_ned.position.east_m
            self.current_down = pos_ned.position.down_m
        except:
            # Fallback to basic position
            current_pos = await self.drone.telemetry.position().__anext__()
            self.current_north = 0.0
            self.current_east = 0.0
            self.current_down = -abs(current_pos.relative_altitude_m)

        print(f"  Current position: N={self.current_north:.2f}, "
              f"E={self.current_east:.2f}, "
              f"Alt={abs(self.current_down):.2f}m")

        # CRITICAL: Send setpoints BEFORE starting offboard
        print("  Sending position setpoints (required by PX4)...")
        for i in range(10):  # 2 seconds at 5Hz
            await self.drone.offboard.set_position_ned(
                PositionNedYaw(
                    self.current_north,
                    self.current_east,
                    self.current_down,
                    self.current_yaw
                )
            )
            await asyncio.sleep(self.position_update_rate)

        # Start offboard mode
        try:
            await self.drone.offboard.start()
            self.offboard_active = True
            print("✅ Offboard mode active!")
            return True

        except OffboardError as error:
            print(f"✗ Failed to start offboard mode: {error._result.result}")
            return False

    async def goto_position(
        self,
        north: float,
        east: float,
        altitude: float,
        yaw: float = 0.0,
        timeout_sec: float = 30.0
    ) -> bool:
        """
        Navigate to target position

        Args:
            north: North position in meters (positive north)
            east: East position in meters (positive east)
            altitude: Altitude in meters (positive up)
            yaw: Heading in degrees (0 = north)
            timeout_sec: Navigation timeout

        Returns:
            True if reached target position
        """
        # Convert altitude to NED down coordinate
        target_down = -abs(altitude)

        print(f"Navigating to: N={north:.2f}, E={east:.2f}, Alt={altitude:.2f}m")

        # Send position command
        await self.drone.offboard.set_position_ned(
            PositionNedYaw(north, east, target_down, yaw)
        )

        # Wait until reached target
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout_sec:
            # Get current position from telemetry (NED local position)
            try:
                pos_ned = await self.drone.telemetry.position_velocity_ned().__anext__()
                current_north = pos_ned.position.north_m
                current_east = pos_ned.position.east_m
                current_down = pos_ned.position.down_m

                # Calculate horizontal distance to target
                distance = ((north - current_north)**2 + (east - current_east)**2)**0.5
                current_alt = abs(current_down)  # Convert NED down to altitude

                print(f"  Pos: N={current_north:.2f}, E={current_east:.2f}, "
                      f"Dist: {distance:.2f}m, Alt: {current_alt:.2f}m", end="\r")

                if distance < self.waypoint_threshold:
                    # Update stored position
                    self.current_north = current_north
                    self.current_east = current_east
                    self.current_down = current_down
                    print(f"\n✅ Reached target position!")
                    return True

            except Exception as e:
                # Fallback to basic position if NED not available
                print(f"\n⚠️ Position telemetry error: {e}")
                pass

            # Continue sending setpoints
            await self.drone.offboard.set_position_ned(
                PositionNedYaw(north, east, target_down, yaw)
            )

            await asyncio.sleep(self.position_update_rate)

        print(f"\n⚠️ Timeout reaching target position")
        return False

    async def land(self) -> bool:
        """
        Land the drone

        Returns:
            True if landed successfully
        """
        print("Landing...")

        # Stop offboard mode if active
        if self.offboard_active:
            try:
                await self.drone.offboard.stop()
                self.offboard_active = False
            except:
                pass

        # Land
        await self.drone.action.land()

        # Wait for landed confirmation
        async for in_air in self.drone.telemetry.in_air():
            if not in_air:
                self.armed = False
                print("✅ Landed!")
                return True

        return False

    async def get_position(self) -> Tuple[float, float, float]:
        """
        Get current position

        Returns:
            (north, east, altitude) in meters
        """
        try:
            pos_ned = await self.drone.telemetry.position_velocity_ned().__anext__()
            return (
                pos_ned.position.north_m,
                pos_ned.position.east_m,
                abs(pos_ned.position.down_m)  # Altitude (positive up)
            )
        except:
            # Fallback to basic position
            pos = await self.drone.telemetry.position().__anext__()
            return (
                0.0,  # Relative north from start
                0.0,  # Relative east from start
                abs(pos.relative_altitude_m)  # Altitude (positive up)
            )

    async def emergency_stop(self):
        """Emergency stop - kills motors immediately"""
        print("⚠️ EMERGENCY STOP!")
        await self.drone.action.kill()


# Example usage
async def example_flight():
    """Example flight demonstrating the API"""

    nav = MAVSDKNavigator()

    try:
        # Connect
        if not await nav.connect():
            return

        # Wait for armable
        if not await nav.wait_for_armable():
            return

        # Arm
        if not await nav.arm():
            return

        # Takeoff
        if not await nav.takeoff(altitude_m=2.0):
            return

        # Engage offboard mode
        if not await nav.engage_offboard_mode():
            await nav.land()
            return

        # Navigate waypoints
        waypoints = [
            (3.0, 0.0, 2.0, "Point 1: 3m North"),
            (3.0, 3.0, 2.0, "Point 2: 3m East"),
            (0.0, 3.0, 2.0, "Point 3: 3m South"),
            (0.0, 0.0, 2.0, "Point 4: Home"),
        ]

        for north, east, alt, name in waypoints:
            print(f"\n→ {name}")
            if not await nav.goto_position(north, east, alt):
                print("Navigation failed!")
                break
            await asyncio.sleep(2)  # Pause at waypoint

        # Land
        await nav.land()

        print("\n✅ Flight complete!")

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        await nav.land()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        await nav.land()


if __name__ == "__main__":
    asyncio.run(example_flight())
