#!/bin/bash
cd "$(dirname "$0")")
source venv/bin/activate
echo "Starting ERIS Ground Station Server..."
python3 server.py
