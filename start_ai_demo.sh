#!/bin/bash
# AI-Powered Drone Demo Startup Script
# This script sets up the environment and starts the Flask server with AI integration

# Check if ANTHROPIC_API_KEY is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY environment variable is not set"
    echo ""
    echo "To set your API key, run:"
    echo "  export ANTHROPIC_API_KEY='your-api-key-here'"
    echo ""
    echo "Get your API key from: https://console.anthropic.com/"
    echo ""
    exit 1
fi

echo "=========================================="
echo "AI-Powered Drone Control System"
echo "=========================================="
echo ""
echo "✓ ANTHROPIC_API_KEY is set"
echo "✓ Starting Flask server on http://localhost:5000"
echo ""
echo "DEMO INTERFACE:"
echo "  http://localhost:5000/demo/"
echo ""
echo "TRY THESE COMMANDS:"
echo "  - Take off to 2 meters"
echo "  - Fly to coordinates 5 north, 3 east"
echo "  - Search the north wing for survivors"
echo "  - Return to home and land"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================================="
echo ""

# Start Flask server
cd /home/chris-zahuranec/Desktop/Auto_Epsilon/Auto_Epsilon
python3 -m droneapp.main
