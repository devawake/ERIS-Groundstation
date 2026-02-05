#!/usr/bin/env python3
"""
RFM69HCW Driver Module
"""

import time
import logging

try:
    import spidev
    import RPi.GPIO as GPIO
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("[WARN] spidev or RPi.GPIO not found. Radio hardware cannot be used.")

# ============================================
# CONSTANTS & REGISTERS
# ============================================
REG_FIFO = 0x00
REG_OPMODE = 0x01
REG_DATAMODUL = 0x02
REG_BITRATEMSB = 0x03
REG_BITRATELSB = 0x04
REG_FDEVMSB = 0x05
REG_FDEVLSB = 0x06
REG_FRFMSB = 0x07
REG_FRFMID = 0x08
REG_FRFLSB = 0x09
REG_VERSION = 0x10
REG_PALEVEL = 0x11
REG_OCP = 0x13
REG_LNA = 0x18
REG_RXBW = 0x19
REG_AFCBW = 0x1A
REG_RSSICONFIG = 0x23
REG_RSSIVALUE = 0x24
REG_DIOMAPPING1 = 0x25
REG_IRQFLAGS1 = 0x27
REG_IRQFLAGS2 = 0x28
REG_RSSITHRESH = 0x29
REG_SYNCCONFIG = 0x2E
REG_SYNCVALUE1 = 0x2F
REG_SYNCVALUE2 = 0x30
REG_PACKETCONFIG1 = 0x37
REG_PAYLOADLENGTH = 0x38
REG_NODEADRS = 0x39
REG_BROADCASTADRS = 0x3A
REG_FIFOTHRESH = 0x3C
REG_PACKETCONFIG2 = 0x3D
REG_TESTPA1 = 0x5A
REG_TESTPA2 = 0x5C
REG_TESTDAGC = 0x6F

# Operating modes
MODE_SLEEP = 0x00
MODE_STANDBY = 0x04
MODE_FS = 0x08
MODE_TX = 0x0C
MODE_RX = 0x10

# FXOSC = 32MHz
FXOSC = 32000000
FSTEP = FXOSC / 524288  # 2^19

class RFM69:
    """RFM69HCW driver using spidev."""
    
    def __init__(self, freq_mhz=433.0, node_id=0x02, broadcast_id=0xFF, spi_bus=0, spi_device=0, reset_pin=25):
        if not HARDWARE_AVAILABLE:
            raise RuntimeError("Hardware dependencies (spidev/RPi.GPIO) missing.")

        self.freq_mhz = freq_mhz
        self.node_id = node_id
        self.broadcast_id = broadcast_id
        self.reset_pin = reset_pin
        self.last_rssi = 0
        self.mode = MODE_STANDBY
        self.logger = logging.getLogger("RFM69")
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.reset_pin, GPIO.OUT)
        
        # Setup SPI
        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_device)
        self.spi.max_speed_hz = 4000000  # 4 MHz
        self.spi.mode = 0b00
        
        # Reset and Init
        self._reset()
        
        # Verify chip
        version = self._read_reg(REG_VERSION)
        self.logger.info(f"Chip version: 0x{version:02X}")
        if version != 0x24:
            raise RuntimeError(f"Invalid RFM69 version: 0x{version:02X} (expected 0x24)")
        
        self._init_radio()
    
    def _reset(self):
        """Perform hardware reset."""
        GPIO.output(self.reset_pin, GPIO.HIGH)
        time.sleep(0.1)
        GPIO.output(self.reset_pin, GPIO.LOW)
        time.sleep(0.1)
    
    def _read_reg(self, addr):
        resp = self.spi.xfer2([addr & 0x7F, 0x00])
        return resp[1]
    
    def _write_reg(self, addr, value):
        self.spi.xfer2([addr | 0x80, value])
    
    def _read_fifo(self, length):
        resp = self.spi.xfer2([REG_FIFO] + [0x00] * length)
        return resp[1:]
    
    def _init_radio(self):
        # Go to standby first
        self._write_reg(REG_OPMODE, MODE_STANDBY)
        time.sleep(0.01)
        
        config = [
            # Packet mode, FSK, no shaping
            (REG_DATAMODUL, 0x00),
            
            # Bit rate: 4.8 kbps
            (REG_BITRATEMSB, 0x1A),
            (REG_BITRATELSB, 0x0B),
            
            # Frequency deviation: 5 kHz
            (REG_FDEVMSB, 0x00),
            (REG_FDEVLSB, 0x52),
            
            # RX bandwidth
            (REG_RXBW, 0x55),
            (REG_AFCBW, 0x8B),
            
            # Preamble length: 4 bytes
            (0x2C, 0x00),
            (0x2D, 0x04),
            
            # Sync word config: on, 2 bytes
            (REG_SYNCCONFIG, 0x88),
            (REG_SYNCVALUE1, 0x2D),
            (REG_SYNCVALUE2, 0xD4),
            
            # Packet config: variable length, CRC on, no address filtering
            (REG_PACKETCONFIG1, 0x90),
            
            # Max payload length
            (REG_PAYLOADLENGTH, 66),
            
            # FIFO threshold
            (REG_FIFOTHRESH, 0x8F),
            
            # Packet config 2
            (REG_PACKETCONFIG2, 0x02),
            
            # Improved sensitivity for RFM69HCW
            (REG_TESTDAGC, 0x30),
            
            # LNA settings
            (REG_LNA, 0x88),
            
            # RSSI threshold
            (REG_RSSITHRESH, 0xE4),
        ]
        
        for reg, val in config:
            self._write_reg(reg, val)
        
        self._set_frequency(self.freq_mhz)
        
        # Set node address
        self._write_reg(REG_NODEADRS, self.node_id)
        self._write_reg(REG_BROADCASTADRS, self.broadcast_id)
        
        # For RX, ensure high power boost is OFF
        self._write_reg(REG_TESTPA1, 0x55)
        self._write_reg(REG_TESTPA2, 0x70)
        
        self.logger.info("Radio initialized.")

    def _set_frequency(self, freq_mhz):
        frf = int((freq_mhz * 1000000) / FSTEP)
        self._write_reg(REG_FRFMSB, (frf >> 16) & 0xFF)
        self._write_reg(REG_FRFMID, (frf >> 8) & 0xFF)
        self._write_reg(REG_FRFLSB, frf & 0xFF)
    
    def _set_mode(self, mode):
        if mode == self.mode:
            return
        
        self._write_reg(REG_OPMODE, mode)
        
        # Wait for mode ready
        timeout = time.time() + 1.0
        while not (self._read_reg(REG_IRQFLAGS1) & 0x80):
            if time.time() > timeout:
                self.logger.error("Mode change timeout!")
                break
            time.sleep(0.001)
        
        self.mode = mode

    def read_rssi(self):
        self._write_reg(REG_RSSICONFIG, 0x01)
        timeout = time.time() + 0.1
        while not (self._read_reg(REG_RSSICONFIG) & 0x02):
            if time.time() > timeout:
                break
            time.sleep(0.001)
        return -(self._read_reg(REG_RSSIVALUE) // 2)

    def receive_packet(self):
        """
        Check for packet.
        Returns (payload_bytes, rssi) if packet received, else None.
        This is non-blocking check loop logic, but we still need to manage modes.
        """
        # Ensure we are in RX mode
        if self.mode != MODE_RX:
            self._set_mode(MODE_RX)

        # Check for PayloadReady
        irq2 = self._read_reg(REG_IRQFLAGS2)
        
        if irq2 & 0x04:  # PayloadReady
            # Read RSSI
            rssi = -(self._read_reg(REG_RSSIVALUE) // 2)
            self.last_rssi = rssi
            
            # Read length
            length = self._read_reg(REG_FIFO)
            
            if 0 < length <= 66:
                payload = self._read_fifo(length)
                # Go briefly to standby to reset FIFO tracking if needed, often good practice
                self._set_mode(MODE_STANDBY)
                return bytes(payload), rssi
            else:
                self.logger.warning(f"Invalid payload length: {length}")
                self._set_mode(MODE_STANDBY)
                self._set_mode(MODE_RX)
                return None
        
        return None

    def close(self):
        self._set_mode(MODE_SLEEP)
        if hasattr(self, 'spi'):
            self.spi.close()
        GPIO.cleanup()
