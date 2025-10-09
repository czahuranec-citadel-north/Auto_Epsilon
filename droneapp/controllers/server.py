import asyncio
import logging

from flask import jsonify
from flask import render_template
from flask import request

from droneapp.models.drone_backend import VehicleCommand

import config

from datetime import datetime

logger = logging.getLogger(__name__)
app = config.app
drone = VehicleCommand.get_instance()


def get_drone():
    return drone


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/controller/')
def controller():
    return render_template('controller.html')


@app.route('/api/details/')
def details():
    asyncio.set_event_loop(asyncio.new_event_loop())
    asyncio.run(get_drone().print_all(), debug=True)
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
    """Return telemetry data as JSON for 3D visualization"""
    asyncio.set_event_loop(asyncio.new_event_loop())
    asyncio.run(get_drone().print_all(), debug=True)

    this_drone = get_drone()

    # Extract numeric values from string representations
    def extract_value(text, default=0):
        try:
            # Extract numbers from strings like "Pitch: 12.5"
            parts = text.split(':')
            if len(parts) > 1:
                value_str = parts[1].strip().split()[0].replace('%', '')
                return float(value_str)
            return default
        except:
            return default

    telemetry_data = {
        'altitude': extract_value(this_drone.altitude_str, 0),
        'pitch': extract_value(this_drone.pitch_str, 0),
        'roll': extract_value(this_drone.roll_str, 0),
        'yaw': extract_value(this_drone.yaw_str, 0),
        'battery': extract_value(this_drone.battery_remaining_str, 100),
        'throttle': this_drone.throttle,
        'position': {
            'x': 0,  # Can be extended with GPS data
            'y': extract_value(this_drone.altitude_str, 0),
            'z': 0
        },
        'flight_mode': this_drone.flight_mode_str.replace('Flight Mode: ', ''),
        'in_air': 'Flying' in this_drone.flight_status_str
    }

    return jsonify(telemetry_data)


@app.route('/api/command/', methods=['POST'])
def command():
    asyncio.set_event_loop(asyncio.new_event_loop())
    cmd = request.form.get('command')
    logger.info({'action': 'command', 'cmd': cmd})
    this_drone = get_drone()
    if cmd == 'takeOff':
        asyncio.run(this_drone.takeoff(2), debug=True)
    if cmd == 'land':
        asyncio.run(this_drone.land(), debug=True)
    if cmd == 'speed':
        speed = request.form.get('speed')
        logger.info({'action': 'command', 'cmd': cmd, 'speed': speed})
        if speed:
            this_drone.set_speed(int(speed))
    # if cmd == 'attitude':
    #     yaw = str(request.form.get('yaw'))
    #     throttle = str(request.form.get('throttle'))
    #     roll = str(request.form.get('roll'))
    #     pitch = str(request.form.get('pitch'))
    #     brake = str(request.form.get('brake'))
    #     logger.info({'action': 'command', 'cmd': cmd, 'yaw': yaw, 'throttle': throttle, 'roll': roll, 'pitch': pitch,
    #                  'brake': brake})
    #     asyncio.run(this_drone.attitude(yaw, throttle, roll, pitch, brake), debug=True)
    if cmd == 'up':
        asyncio.run(this_drone.up(), debug=True)
    if cmd == 'down':
        asyncio.run(this_drone.down(), debug=True)
    if cmd == 'forward':
        asyncio.run(this_drone.forward(), debug=True)
    if cmd == 'back':
        asyncio.run(this_drone.back(), debug=True)
    if cmd == 'left':
        asyncio.run(this_drone.left(), debug=True)
    if cmd == 'right':
        asyncio.run(this_drone.right(), debug=True)
    if cmd == 'clockwise':
        asyncio.run(this_drone.clockwise(), debug=True)
    if cmd == 'counterclockwise':
        asyncio.run(this_drone.counterclockwise(), debug=True)
    # if cmd == 'avoid':
    #     asyncio.run(this_drone.subscriber(), debug=True)
    if cmd == 'stop':
        asyncio.run(this_drone.stop(), debug=True)
    if cmd == 'serv_up':
        asyncio.run(this_drone.serv_up(), debug=True)
    if cmd == 'serv_down':
        asyncio.run(this_drone.serv_down(), debug=True)
    # if cmd == 'toggle_avoid':
    #     asyncio.run(this_drone.toggle_avoidance(), debug=True)
    if cmd == 'activate':
        asyncio.run(this_drone.activate_sup(), debug=True)

    return jsonify(status='success'), 200


def run():
    app.run(host=config.WEB_ADDRESS, port=config.WEB_PORT, threaded=True)
