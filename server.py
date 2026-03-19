#!/usr/bin/env python3
import time
import threading
import json
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

# Import Radio driver
try:
    from rfm69 import RFM69
except (ImportError, RuntimeError) as e:
    logger.error(f"Radio driver import failed: {e}")
    RFM69 = None

def parse_packet(payload_bytes, rssi):
    """
    Parses protocol: 'St:STATE,T:time,S:sats,L:lat,lon,A:alt,Z:az,Max:maxalt'
    STATE is a full word: IDLE, ARMED, ASCENT, DESCENT, LANDED
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
                try:
                    val = part.split(':')[1]
                    data['time'] = int(val) if val and val != 'None' else 0
                except (ValueError, TypeError):
                    data['time'] = 0
            elif part.startswith('S:'):
                try:
                    val = part.split(':')[1]
                    data['sats'] = int(val) if val and val != 'None' else 0
                except (ValueError, TypeError):
                    data['sats'] = 0
            elif part.startswith('L:'):
                # L:lat followed by next part being lon
                try:
                    data['lat'] = float(part.split(':')[1])
                except (ValueError, TypeError):
                    data['lat'] = 0.0
                if i + 1 < len(parts):
                    try:
                        data['lon'] = float(parts[i + 1])
                    except (ValueError, TypeError):
                        data['lon'] = 0.0
            elif part.startswith('A:'):
                try:
                    data['alt'] = float(part.split(':')[1])
                except (ValueError, TypeError):
                    data['alt'] = 0.0
            elif part.startswith('Z:'):
                try:
                    val = part.split(':')[1]
                    data['az'] = int(val) if val and val != 'None' else 0
                except (ValueError, TypeError):
                    data['az'] = 0
            elif part.startswith('Max:'):
                try:
                    data['max_alt'] = float(part.split(':')[1])
                except (ValueError, TypeError):
                    data['max_alt'] = 0.0
        
        # Set defaults for any missing fields
        data.setdefault('state', 'UNKNOWN')
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
            'state': 'ERROR',
            'time': 0,
            'sats': 0,
            'lat': 0.0,
            'lon': 0.0,
            'alt': 0.0,
            'az': 0,
            'max_alt': 0.0
        }

def background_thread():
    """Reads from radio and emits telemetry to connected clients."""
    global stop_thread

    if RFM69 is None:
        logger.error("Radio driver unavailable — background thread exiting. Check rfm69.py and hardware.")
        socketio.emit('log', {'msg': 'ERROR: Radio driver unavailable. No telemetry.'})
        return

    try:
        radio = RFM69()
        logger.info("Radio driver loaded OK")
        socketio.emit('log', {'msg': 'Radio initialised OK'})
    except Exception as e:
        logger.error(f"Radio init failed: {e}")
        socketio.emit('log', {'msg': f'ERROR: Radio init failed — {e}'})
        return

    while not stop_thread:
        packet_data = radio.receive_packet()
        if packet_data:
            payload, rssi = packet_data
            telemetry = parse_packet(payload, rssi)
            logger.info(f"Emitting: {telemetry}")
            socketio.emit('telemetry', telemetry)
            socketio.emit('log', {'msg': f"RSSI: {rssi}dBm | {telemetry.get('raw','').strip()}"})

        socketio.sleep(0.01)

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
