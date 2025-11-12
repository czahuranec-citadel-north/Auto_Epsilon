import logging

from flask import jsonify
from flask import render_template
from flask import request

from droneapp.models.mavsdk_backend import MAVSDKDroneBackend as VehicleCommand
from droneapp.models.camera_stream import CameraStream
from mavsdk_waypoint_navigator import MAVSDKNavigator
from droneapp.models.ai_pilot import AIPilot

import config

from datetime import datetime

logger = logging.getLogger(__name__)
app = config.app
drone = VehicleCommand.get_instance()
camera = CameraStream.get_instance()
navigator = MAVSDKNavigator()
ai_pilot = AIPilot(drone, navigator)


def get_drone():
    return drone


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/controller/')
def controller():
    return render_template('controller.html')


@app.route('/demo/')
def demo():
    return render_template('demo.html')


@app.route('/api/details/')
def details():
    get_drone().print_all()
    current_time = "Current Time: " + datetime.now().strftime("%H:%M:%S")
    response = (f"{current_time}</br>" +
                f"{get_drone().battery_remaining_str}</br>" +
                f"{get_drone().battery_voltage_str}</br>" +
                f"{get_drone().pitch_str}</br>" +
                f"{get_drone().roll_str}</br>" +
                f"{get_drone().yaw_str}</br>" +
                f"Throttle: {get_drone().throttle}</br>" +
                f"{get_drone().altitude_str}</br>" +
                f"{get_drone().flight_mode_str}</br>" +
                f"{get_drone().flight_status_str}"
                )

    return response


@app.route('/api/telemetry/')
def telemetry():
    """Return telemetry data as JSON for visualization"""
    this_drone = get_drone()

    # Get position and status from MAVSDK backend
    position = this_drone.get_position()
    status = this_drone.get_status()

    telemetry_data = {
        'altitude': position['altitude'],
        'pitch': 0,  # Not yet implemented
        'roll': 0,   # Not yet implemented
        'yaw': 0,    # Not yet implemented
        'battery': status['battery'],
        'throttle': 0,
        'position': {
            'north': position['north'],
            'east': position['east'],
            'altitude': position['altitude']
        },
        'flight_mode': status['flight_mode'],
        'in_air': status['in_air'],
        'armed': status['armed'],
        'connected': status['connected']
    }

    return jsonify(telemetry_data)


@app.route('/api/command/', methods=['POST'])
def command():
    cmd = request.form.get('command')
    logger.info({'action': 'command', 'cmd': cmd})

    try:
        this_drone = get_drone()

        # MAVSDK commands
        if cmd == 'arm':
            this_drone.arm()
        elif cmd == 'takeOff' or cmd == 'takeoff':
            this_drone.takeoff(2)
        elif cmd == 'land':
            this_drone.land()
        elif cmd == 'emergency_stop':
            this_drone.emergency_stop()
        # Manual control commands (offboard mode)
        elif cmd == 'up':
            this_drone.up()
        elif cmd == 'down':
            this_drone.down()
        elif cmd == 'forward':
            this_drone.forward()
        elif cmd == 'back':
            this_drone.back()
        elif cmd == 'left':
            this_drone.left()
        elif cmd == 'right':
            this_drone.right()
        elif cmd == 'clockwise':
            this_drone.clockwise()
        elif cmd == 'counterclockwise':
            this_drone.counterclockwise()
        elif cmd == 'stop':
            this_drone.stop()
        # Legacy commands (not implemented)
        elif cmd == 'speed':
            speed = request.form.get('speed')
            logger.info({'action': 'command', 'cmd': cmd, 'speed': speed})
        elif cmd in ['serv_up', 'serv_down', 'activate']:
            logger.info(f"Servo command not implemented: {cmd}")
        else:
            logger.warning(f"Unknown command: {cmd}")

        return jsonify(status='success'), 200

    except ConnectionError as e:
        logger.error(f"Connection error: {e}")
        return jsonify(status='error', message=str(e)), 503
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify(status='error', message=f"Command failed: {str(e)}"), 500


@app.route('/api/chat/', methods=['POST'])
def chat():
    """Handle natural language chat commands with Claude AI"""
    data = request.get_json()
    message = data.get('message', '')
    logger.info({'action': 'chat', 'message': message})

    try:
        # Use AI pilot to process message
        result = ai_pilot.process_message(message)

        # Execute any commands the AI requested
        for command in result['commands']:
            success, msg = ai_pilot.execute_command(command)
            logger.info(f"AI command executed: {command.get('command')} - {msg}")

        return jsonify(response=result['response'], status='success'), 200

    except Exception as e:
        logger.error(f"Chat error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(response="Error processing command. Please check that ANTHROPIC_API_KEY is set.", status='error'), 500


@app.route('/api/camera/feed')
def camera_feed():
    """Return latest camera frame as JPEG"""
    try:
        from flask import Response
        frame = camera.get_frame()
        return Response(frame, mimetype='image/jpeg')
    except Exception as e:
        logger.error(f"Camera feed error: {e}")
        return jsonify(status='error', message=str(e)), 500


@app.route('/api/camera/stream')
def camera_stream():
    """Return camera feed as base64 JSON for AJAX polling"""
    try:
        frame_base64 = camera.get_frame_base64()
        return jsonify(frame=frame_base64, status='success')
    except Exception as e:
        logger.error(f"Camera stream error: {e}")
        return jsonify(status='error', message=str(e)), 500


@app.route('/api/run_waypoint_test/', methods=['POST'])
def run_waypoint_test():
    """Run the waypoint navigation test (3m square pattern)"""
    import asyncio
    import threading

    def test_thread():
        """Run test in background thread"""
        try:
            from mavsdk_waypoint_navigator import MAVSDKNavigator

            async def run_test():
                nav = MAVSDKNavigator()

                try:
                    # Connect
                    logger.info("TEST: Connecting to PX4...")
                    if not await nav.connect():
                        logger.error("TEST FAILED: Could not connect")
                        return

                    # Wait for armable
                    logger.info("TEST: Waiting for armable status...")
                    if not await nav.wait_for_armable():
                        logger.error("TEST FAILED: Drone not armable")
                        return

                    # Arm
                    logger.info("TEST: Arming...")
                    if not await nav.arm():
                        logger.error("TEST FAILED: Could not arm")
                        return

                    # Takeoff
                    logger.info("TEST: Taking off to 2m...")
                    if not await nav.takeoff(altitude_m=2.0):
                        logger.error("TEST FAILED: Takeoff failed")
                        return

                    # Wait for stabilization
                    logger.info("TEST: Waiting 3 seconds for stabilization...")
                    await asyncio.sleep(3)

                    # Engage offboard mode
                    logger.info("TEST: Engaging offboard mode...")
                    if not await nav.engage_offboard_mode():
                        logger.error("TEST FAILED: Could not engage offboard mode")
                        await nav.land()
                        return

                    # Define waypoints (3m square)
                    waypoints = [
                        (3.0, 0.0, 2.0, "Point 1: 3m North"),
                        (3.0, 3.0, 2.0, "Point 2: 3m East"),
                        (0.0, 3.0, 2.0, "Point 3: 3m South"),
                        (0.0, 0.0, 2.0, "Point 4: Home"),
                    ]

                    # Navigate waypoints
                    logger.info(f"TEST: Navigating {len(waypoints)} waypoints...")
                    for i, (north, east, alt, name) in enumerate(waypoints, 1):
                        logger.info(f"TEST: Waypoint {i}/{len(waypoints)}: {name}")
                        success = await nav.goto_position(north, east, alt, timeout_sec=30.0)

                        if not success:
                            logger.error(f"TEST FAILED: Could not reach {name}")
                            await nav.land()
                            return
                        else:
                            logger.info(f"TEST: Reached {name}")

                        # Pause at waypoint
                        await asyncio.sleep(2)

                    # Land
                    logger.info("TEST: Landing...")
                    await nav.land()

                    logger.info("TEST PASSED: All waypoints reached successfully!")

                except Exception as e:
                    logger.error(f"TEST FAILED: {e}")
                    import traceback
                    traceback.print_exc()
                    try:
                        await nav.land()
                    except:
                        pass

            # Run the async test
            asyncio.run(run_test())

        except Exception as e:
            logger.error(f"Waypoint test error: {e}")

    # Start test in background thread
    thread = threading.Thread(target=test_thread, daemon=True)
    thread.start()

    return jsonify(status='success', message='Waypoint test started. Watch the Gazebo window and check logs for progress.'), 200


def run():
    app.run(host=config.WEB_ADDRESS, port=config.WEB_PORT, threaded=True)
