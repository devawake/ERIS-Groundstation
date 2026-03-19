#!/bin/bash
# Move into the correct directory relative to the script
cd "$(dirname "$0")"

echo "Waiting up to 30 seconds for Wi-Fi connection..."
for i in {1..30}; do
    if ping -q -c 1 -W 1 8.8.8.8 >/dev/null 2>&1; then
        echo "Network is up. Pulling latest code..."
        git pull origin main
        break
    fi
    sleep 1
done

if [ "$i" -eq 30 ]; then
    echo "No network connection detected within 30 seconds. Skipping git pull."
fi

echo "Starting ERIS Ground Station Server..."
source venv/bin/activate
# Using direct path to the venv python executable is safest for background services
venv/bin/python3 server.py &
SERVER_PID=$!

echo "Waiting 5 seconds for server to start..."
sleep 5

echo "Setting up Wayland environment..."
if [ -z "$XDG_RUNTIME_DIR" ]; then
    export XDG_RUNTIME_DIR=/run/user/$(id -u)
    if [ ! -d "$XDG_RUNTIME_DIR" ]; then
        export XDG_RUNTIME_DIR=/tmp/$(id -u)-wayland
        mkdir -p "$XDG_RUNTIME_DIR"
        chmod 0700 "$XDG_RUNTIME_DIR"
    fi
fi

echo "Starting Chromium Browser in Kiosk Mode on HDMI screen..."
# Use cage, a lightweight Wayland compositor, to launch Chromium on the Pi without a desktop
# It outputs directly to the HDMI screen
cage -d -- chromium --kiosk --noerrdialogs --disable-infobars --no-first-run --ozone-platform-hint=auto --enable-features=OverlayScrollbar http://localhost:5000 &
BROWSER_PID=$!

# Wait for the server process forever
wait $SERVER_PID
