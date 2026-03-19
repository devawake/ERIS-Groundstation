#!/bin/bash
# Move into the correct directory relative to the script
cd "$(dirname "$0")"
CURRENT_DIR=$(pwd)
USER_NAME=$(whoami)

echo "Installing necessary packages for Kiosk mode (Cage and Chromium)..."
sudo apt-get update
sudo apt-get install -y cage chromium git systemd

echo "Generating SystemD service file for autostart..."
cat <<EOF | sudo tee /etc/systemd/system/eris-kiosk.service
[Unit]
Description=ERIS Ground Station Kiosk Mode Autostart
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/autostart.sh
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
# Supplementary groups for KMS drawing directly to HDMI
SupplementaryGroups=video render input tty

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd and enabling the service..."
sudo systemctl daemon-reload
sudo systemctl enable eris-kiosk.service

echo "Making scripts executable..."
chmod +x autostart.sh || true
chmod +x start.sh || true

echo "--------------------------------------------------------"
echo "Setup Complete!"
echo "The Pi will now:"
echo " 1. Wait for Wi-Fi on boot"
echo " 2. Run 'git pull' to update"
echo " 3. Start the Flask server"
echo " 4. Display the Web UI directly on your connected HDMI screen"
echo ""
echo "You can test it now by running:  sudo systemctl start eris-kiosk.service"
echo "Or just reboot the Pi."
echo "--------------------------------------------------------"
