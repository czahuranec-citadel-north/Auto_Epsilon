#!/usr/bin/env python3
"""
AI Pilot - Claude-powered natural language drone control
"""

import os
import json
import asyncio
import threading
from anthropic import Anthropic


class AIPilot:
    """AI-powered drone pilot using Claude API"""

    def __init__(self, drone_backend, navigator):
        self.drone = drone_backend
        self.navigator = navigator
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.conversation_history = []

        # System prompt defining drone capabilities
        self.system_prompt = """You are an AI pilot controlling a disaster response drone in a warehouse. Your mission is to search for survivors and assess injuries.

WAREHOUSE LAYOUT:
- 30m x 30m building
- Origin (0,0) is at the center
- Coordinates: North (+Y), East (+X), Altitude (+Z up)
- Contains storage boxes and interior walls creating rooms

AVAILABLE COMMANDS:
1. arm() - Arm the drone motors
2. takeoff(altitude_m) - Take off to specified altitude
3. land() - Land the drone
4. goto_position(north, east, altitude) - Fly to NED coordinates
5. emergency_stop() - Immediate motor cutoff

CURRENT STATUS:
- Connected to PX4 autopilot via MAVSDK
- Positioned at warehouse center
- Ready for autonomous flight

YOUR ROLE:
- Respond naturally and professionally
- Plan efficient search patterns
- Provide clear status updates
- Execute commands autonomously when requested
- Prioritize safety

When you want to execute a command, include it in your response using this JSON format on its own line:
EXECUTE: {"command": "command_name", "params": {...}}

Example responses:
User: "Take off and search the north wing"
You: "Roger. I'll begin by taking off to 2 meters, then conduct a systematic search of the northern section.
EXECUTE: {"command": "takeoff", "params": {"altitude": 2.0}}
Once airborne, I'll navigate to the north wing and scan for any signs of survivors."

User: "Fly to coordinates 5 north, 3 east"
You: "Understood. Navigating to position 5 meters north, 3 meters east.
EXECUTE: {"command": "goto_position", "params": {"north": 5.0, "east": 3.0, "altitude": 2.0}}
Maintaining 2 meter altitude for obstacle clearance."

Keep responses concise but professional. You are a capable AI assistant helping in a disaster scenario."""

    def process_message(self, user_message):
        """
        Process user message and return AI response with optional commands

        Returns: {
            'response': str,  # AI's text response
            'commands': []    # List of commands to execute
        }
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        try:
            # Call Claude API
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",  # Fast model
                max_tokens=1024,
                system=self.system_prompt,
                messages=self.conversation_history
            )

            # Extract response text
            assistant_message = response.content[0].text

            # Add to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })

            # Parse commands from response
            commands = self._parse_commands(assistant_message)

            # Remove command JSON from display text
            display_text = self._strip_commands(assistant_message)

            return {
                'response': display_text,
                'commands': commands
            }

        except Exception as e:
            print(f"AI Pilot error: {e}")
            return {
                'response': f"Error processing command: {str(e)}",
                'commands': []
            }

    def _parse_commands(self, text):
        """Extract EXECUTE commands from AI response"""
        commands = []
        for line in text.split('\n'):
            if line.strip().startswith('EXECUTE:'):
                try:
                    json_str = line.strip()[8:].strip()  # Remove 'EXECUTE:'
                    cmd = json.loads(json_str)
                    commands.append(cmd)
                except json.JSONDecodeError as e:
                    print(f"Failed to parse command: {line} - {e}")
        return commands

    def _strip_commands(self, text):
        """Remove EXECUTE lines from text for clean display"""
        lines = []
        for line in text.split('\n'):
            if not line.strip().startswith('EXECUTE:'):
                lines.append(line)
        return '\n'.join(lines).strip()

    def execute_command(self, command):
        """
        Execute a parsed command

        Returns: success (bool), message (str)
        """
        cmd_name = command.get('command')
        params = command.get('params', {})

        try:
            if cmd_name == 'arm':
                self.drone.arm()
                return True, "Drone armed"

            elif cmd_name == 'takeoff':
                altitude = params.get('altitude', 2.0)
                self.drone.takeoff(altitude)
                return True, f"Taking off to {altitude}m"

            elif cmd_name == 'land':
                self.drone.land()
                return True, "Landing"

            elif cmd_name == 'goto_position':
                # This requires MAVSDK navigator - run in background
                north = params.get('north', 0.0)
                east = params.get('east', 0.0)
                altitude = params.get('altitude', 2.0)

                # Start navigation in background thread
                def nav_thread():
                    asyncio.run(self._async_goto(north, east, altitude))

                thread = threading.Thread(target=nav_thread, daemon=True)
                thread.start()

                return True, f"Navigating to N={north}m, E={east}m"

            elif cmd_name == 'emergency_stop':
                self.drone.emergency_stop()
                return True, "EMERGENCY STOP ACTIVATED"

            else:
                return False, f"Unknown command: {cmd_name}"

        except Exception as e:
            return False, f"Command execution failed: {str(e)}"

    async def _async_goto(self, north, east, altitude):
        """Run goto_position asynchronously"""
        try:
            # Connect to navigator
            await self.navigator.connect()
            await self.navigator.wait_for_armable()

            # Check if we need to arm and takeoff first
            status = self.drone.get_status()
            if not status['armed']:
                await self.navigator.arm()
                await self.navigator.takeoff(altitude_m=altitude)
                await asyncio.sleep(3)  # Stabilize

            # Engage offboard if not already
            if not self.navigator.offboard_active:
                await self.navigator.engage_offboard_mode()

            # Navigate to position
            success = await self.navigator.goto_position(north, east, altitude)

            if success:
                print(f"AI Pilot: Reached position N={north}, E={east}")
            else:
                print(f"AI Pilot: Failed to reach position")

        except Exception as e:
            print(f"AI Pilot navigation error: {e}")

    def reset_conversation(self):
        """Clear conversation history"""
        self.conversation_history = []
