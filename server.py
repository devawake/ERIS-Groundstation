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
        self.lat = 51.5074
        self.lon = -0.1278
        self.alt = 0.0
        self.max_alt = 0.0
        self.state = 'I'  # I=Idle, A=Ascent, L=Landing, etc.
        logger.info("Mock Radio initialized.")

    def receive_packet(self):
        time.sleep(1.0) # Simulate delay
        elapsed = time.time() - self.start_time
        
        # Simulate simple flight path with states
        if elapsed < 5:
            self.state = 'I'  # Idle
            self.alt = 0
        elif elapsed < 30:
            self.state = 'A'  # Ascent
            self.alt = min(1000, (elapsed - 5) * 40)
        elif elapsed < 35:
            self.state = 'C'  # Coast
            self.alt = 1000
        else:
            self.state = 'D'  # Descent
            self.alt = max(0, 1000 - (elapsed - 35) * 30)
            
        self.max_alt = max(self.max_alt, self.alt)
        self.lat = 51.5074 + (elapsed * 0.00001)
        self.lon = -0.1278 + (elapsed * 0.00001)
        azimuth = int((elapsed * 10) % 360)  # Simulate rotating azimuth
        
        # New Protocol: "St:X,T:time,S:sats,L:lat,lon,A:alt,Z:az,Max:maxalt"
        packet = (f"St:{self.state},T:{int(elapsed)},S:8,"
                  f"L:{self.lat:.4f},{self.lon:.4f},A:{self.alt:.1f},"
                  f"Z:{azimuth},Max:{self.max_alt:.1f}")
        return packet.encode('utf-8'), -50

def parse_packet(payload_bytes, rssi):
    """
    Parses new protocol: 'St:X,T:time,S:sats,L:lat,lon,A:alt,Z:az,Max:maxalt'
    Returns JSON dict.
    """
    try:
        text = payload_bytes.decode('utf-8')
        logger.info(f"Parsing packet: {text}")
        
        data = {'rssi': rssi, 'raw': text}
        
        # Split by comma
        parts = text.split(',')
        
        for i, part in enumerate(parts):
            part = part.strip()
            
            if part.startswith('St:'):
                data['state'] = part.split(':')[1]
            elif part.startswith('T:'):
                data['time'] = int(part.split(':')[1])
            elif part.startswith('S:'):
                data['sats'] = int(part.split(':')[1])
            elif part.startswith('L:'):
                # L:lat followed by next part being lon
                data['lat'] = float(part.split(':')[1])
                if i + 1 < len(parts):
                    data['lon'] = float(parts[i + 1])
            elif part.startswith('A:'):
                data['alt'] = float(part.split(':')[1])
            elif part.startswith('Z:'):
                data['az'] = int(part.split(':')[1])
            elif part.startswith('Max:'):
                data['max_alt'] = float(part.split(':')[1])
        
        # Set defaults for any missing fields
        data.setdefault('state', 'U')  # Unknown
        data.setdefault('time', 0)
        data.setdefault('sats', 0)
        data.setdefault('lat', 0.0)
        data.setdefault('lon', 0.0)
        data.setdefault('alt', 0.0)
        data.setdefault('az', 0)
        data.setdefault('max_alt', 0.0)
        
        return data

    except Exception as e:
        logger.error(f"Parse error: {e}")
        return {
            'error': str(e),
            'raw': payload_bytes.decode('utf-8', errors='ignore'),
            'state': 'E',
            'time': 0,
            'sats': 0,
            'lat': 0.0,
            'lon': 0.0,
            'alt': 0.0,
            'az': 0,
            'max_alt': 0.0
        }

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
