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
python3 server.py &
SERVER_PID=$!

echo "Waiting 5 seconds for server to start..."
sleep 5

echo "Starting Chromium Browser in Kiosk Mode on HDMI screen..."
# Use cage, a lightweight Wayland compositor, to launch Chromium on the Pi without a desktop
# It outputs directly to the HDMI screen
cage -d chromium --kiosk --noerrdialogs --disable-infobars --no-first-run --ozone-platform-hint=auto --enable-features=OverlayScrollbar http://localhost:5000 &
BROWSER_PID=$!

# Wait for the server process forever
wait $SERVER_PID
