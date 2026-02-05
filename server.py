#!/usr/bin/env python3
import time
import threading
import json
import random
import logging
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit

# Initialize Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Server")

app = Flask(__name__, static_url_path='/static')
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')

# Global state
radio_thread = None
thread_lock = threading.Lock()
stop_thread = False

# Try to import Radio
try:
    from rfm69 import RFM69
    HARDWARE_AVAILABLE = True
except (ImportError, RuntimeError) as e:
    logger.warning(f"Radio hardware not available: {e}. Starting in MOCK MODE.")
    HARDWARE_AVAILABLE = False
    RFM69 = None

class MockRadio:
    """Generates fake telemetry for testing."""
    def __init__(self):
        self.start_time = time.time()
        self.lat = 0.0
        self.lon = 0.0
        self.alt = 0.0
        logger.info("Mock Radio initialized.")

    def receive_packet(self):
        time.sleep(1.0) # Simulate delay
        elapsed = time.time() - self.start_time
        
        # Simulate simple flight path
        self.alt = min(1000, elapsed * 10) if elapsed < 100 else max(0, 1000 - (elapsed - 100)*10)
        self.lat = 51.5 + (elapsed * 0.0001)
        self.lon = -0.1 + (elapsed * 0.0001)
        
        # "T:12:01:00,S:5,L:0.00,0.00,A:100.0,Imu:0,0,1"
        return (f"T:{time.strftime('%H:%M:%S')},S:8,"
                f"L:{self.lat:.4f},{self.lon:.4f},A:{self.alt:.1f},"
                f"Imu:0.1,0.2,-9.8").encode('utf-8'), -50

def parse_packet(payload_bytes, rssi):
    """
    Parses 'T:...,S:...,L:...,...,A:...,Imu:...,...,...'
    Returns JSON dict.
    """
    try:
        text = payload_bytes.decode('utf-8')
        # Simple parsing logic based on User's format
        # Format: "T:12:01:00,S:5,L:0.00,0.00,A:0,Imu:100,0,0"
        
        data = {'rssi': rssi, 'raw': text}
        parts = text.split(',')
        
        for part in parts:
            if part.startswith('T:'):
                data['time'] = part.split(':')[1]
            elif part.startswith('S:'):
                data['sats'] = int(part.split(':')[1])
            elif part.startswith('L:'):
                # L:lat,lon is a bit tricky if split by comma. 
                # But based on user string "L:{d['lat']:.4f},{d['lon']:.4f}"
                # The split(',') earlier means we might have ['L:0.00', '0.00']
                pass # Handled below by iterating index safely? 
                
        # Robust parsing:
        # Re-split carefully or logic based on known positions
        # Let's assume the format is somewhat fixed but comma delimited
        # User format: T:..,S:..,L:lat,lon,A:alt,Imu:ax,ay,az
        
        # Let's clean parse by values
        vals = text.split(',')
        if len(vals) >= 8:
             # vals[0] -> T:12:01:00
             data['time'] = vals[0].split(':')[1]
             # vals[1] -> S:5
             data['sats'] = int(vals[1].split(':')[1])
             # vals[2] -> L:51.5000
             data['lat'] = float(vals[2].split(':')[1])
             # vals[3] -> -0.1000 (just number)
             data['lon'] = float(vals[3])
             # vals[4] -> A:100.0
             data['alt'] = float(vals[4].split(':')[1])
             # vals[5] -> Imu:0.1
             data['ax'] = float(vals[5].split(':')[1])
             # vals[6] -> 0.2
             data['ay'] = float(vals[6])
             # vals[7] -> -9.8
             data['az'] = float(vals[7])
             
        return data

    except Exception as e:
        logger.error(f"Parse error: {e}")
        return {'error': str(e), 'raw': payload_bytes.decode('utf-8', errors='ignore')}

def background_thread():
    """Reads from radio and emits to socketio."""
    global stop_thread
    
    if HARDWARE_AVAILABLE:
        try:
            radio = RFM69()
            logger.info("Real Radio Driver Loaded")
        except Exception as e:
            logger.error(f"Failed to load radio, falling back to mock: {e}")
            radio = MockRadio()
    else:
        radio = MockRadio()
        logger.info("Mock Radio Driver Loaded")

    while not stop_thread:
        packet_data = radio.receive_packet()
        if packet_data:
            payload, rssi = packet_data
            telemetry = parse_packet(payload, rssi)
            logger.info(f"Emitting: {telemetry}")
            socketio.emit('telemetry', telemetry)
            socketio.emit('log', {'msg': f"RSSI: {rssi}dBm | {telemetry.get('raw','').strip()}"})
        
        # Small sleep to prevent CPU hogging in loop if receive_packet returns None immediately
        # The real driver has some sleeps, mock has sleeps.
        socketio.sleep(0.01) 

    if hasattr(radio, 'close'):
        radio.close()

@app.route('/')
def index():
    return app.send_static_file('index.html')

@socketio.on('connect')
def test_connect():
    emit('log', {'msg': 'Connected to Ground Station Server'})

@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    # Start background thread
    # Start background thread
    # global radio_thread - Removed unnecessary global declaration in main scope
    with thread_lock:
        if radio_thread is None:
            radio_thread = socketio.start_background_task(background_thread)
            
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        stop_thread = True
