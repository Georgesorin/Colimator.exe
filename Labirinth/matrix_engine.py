import socket
import threading
import time
import random
import json
import os

# --- Configuration ---
_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_joc.json")

def _load_config():
    defaults = {
        "device_ip": "127.0.0.1",
        "send_port": 6766,
        "recv_port": 6767
    }
    try:
        if os.path.exists(_CFG_FILE):
            with open(_CFG_FILE, "r", encoding="utf-8") as f:
                return {**defaults, **json.load(f)}
    except: pass
    return defaults

CONFIG = _load_config()

# --- Matrix Constants ---
NUM_CHANNELS = 8
LEDS_PER_CHANNEL = 64
FRAME_DATA_LENGTH = NUM_CHANNELS * LEDS_PER_CHANNEL * 3

# --- Classes ---

class MatrixEngine:
    def __init__(self):
        self.target_ip = CONFIG.get("device_ip", "127.0.0.1")
        self.send_port = CONFIG.get("send_port", 6766)
        self.recv_port = CONFIG.get("recv_port", 6767)
        
        # Buffer for 16x32 RGB
        self.buffer = bytearray(FRAME_DATA_LENGTH)
        
        # Input State
        self.active_touches = set()
        self.running = True
        self.sequence_number = 0
        self.lock = threading.Lock()
        
        # Network Setup
        self.sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_send.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        self.sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_recv.bind(("0.0.0.0", self.recv_port))
        
        # Background Threads
        threading.Thread(target=self._send_loop, daemon=True).start()
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def set_pixel(self, x, y, r, g, b):
        # Bounds check
        if x < 0 or x >= 16 or y < 0 or y >= 32:
            return
        
        channel = y // 4
        row_in_channel = y % 4
        
        # Zig-Zag mapping
        if row_in_channel % 2 == 0:
            led_index = row_in_channel * 16 + x
        else:
            led_index = row_in_channel * 16 + (15 - x)
            
        offset = led_index * 24 + channel
        
        with self.lock:
            if offset + 16 < FRAME_DATA_LENGTH:
                # Hardware requires GRB format
                self.buffer[offset] = g      
                self.buffer[offset + 8] = r
                self.buffer[offset + 16] = b

    def clear(self):
        with self.lock:
            self.buffer = bytearray(FRAME_DATA_LENGTH)

    def get_touches(self):
        coords = []
        with self.lock:
            for ch, led_idx in self.active_touches:
                row_in_channel = led_idx // 16
                col_raw = led_idx % 16
                
                x = col_raw if row_in_channel % 2 == 0 else 15 - col_raw
                y = ch * 4 + row_in_channel
                coords.append((x, y))
        return coords

    # --- Network Routines ---

    def _send_loop(self):
        while self.running:
            with self.lock:
                frame_data = bytes(self.buffer)
                
            self.sequence_number = (self.sequence_number + 1) & 0xFFFF
            if self.sequence_number == 0: 
                self.sequence_number = 1
                
            # 1. Start Packet
            self._send_start_packet()
            
            # 2. Config Packet (FFF0)
            self._send_fff0_packet()
            
            # 3. Data Chunk Packets
            chunk_size = 984
            packet_idx = 1
            
            for i in range(0, len(frame_data), chunk_size):
                chunk = frame_data[i:i+chunk_size]
                self._send_data_chunk(chunk, packet_idx)
                packet_idx += 1
                time.sleep(0.002) # Sub-chunk block delay strictly 2ms
                
            # 4. End Packet
            self._send_end_packet()
            
            time.sleep(0.05) # ~20 FPS

    def _send_start_packet(self):
        packet = bytearray([
            0x75, random.randint(0, 127), random.randint(0, 127), 0x00, 0x08, 
            0x02, 0x00, 0x00, 0x33, 0x44,   
            (self.sequence_number >> 8) & 0xFF, self.sequence_number & 0xFF,
            0x00, 0x00, 0x00 
        ])
        packet.extend([0x0E, 0x00]) # Force Checksum
        self.sock_send.sendto(packet, (self.target_ip, self.send_port))

    def _send_fff0_packet(self):
        payload = bytearray()
        for _ in range(NUM_CHANNELS):
            payload.extend([(LEDS_PER_CHANNEL >> 8) & 0xFF, LEDS_PER_CHANNEL & 0xFF])

        internal = bytearray([
            0x02, 0x00, 0x00, 0x88, 0x77, 0xFF, 0xF0, 
            (len(payload) >> 8) & 0xFF, len(payload) & 0xFF
        ]) + payload
        
        length = len(internal) - 1
        packet = bytearray([
            0x75, random.randint(0, 127), random.randint(0, 127), 
            (length >> 8) & 0xFF, length & 0xFF
        ]) + internal
        packet.extend([0x1E, 0x00])
        self.sock_send.sendto(packet, (self.target_ip, self.send_port))

    def _send_data_chunk(self, chunk, packet_idx):
        internal = bytearray([
            0x02, 0x00, 0x00, 0x88, 0x77, 
            (packet_idx >> 8) & 0xFF, packet_idx & 0xFF, 
            (len(chunk) >> 8) & 0xFF, len(chunk) & 0xFF 
        ]) + chunk
        
        length = len(internal) - 1 
        packet = bytearray([
            0x75, random.randint(0, 127), random.randint(0, 127),
            (length >> 8) & 0xFF, length & 0xFF
        ]) + internal
        
        packet.append(0x1E if len(chunk) == 984 else 0x36)
        packet.append(0x00)
        self.sock_send.sendto(packet, (self.target_ip, self.send_port))

    def _send_end_packet(self):
        packet = bytearray([
            0x75, random.randint(0, 127), random.randint(0, 127), 0x00, 0x08,
            0x02, 0x00, 0x00, 0x55, 0x66,
            (self.sequence_number >> 8) & 0xFF, self.sequence_number & 0xFF,
            0x00, 0x00, 0x00 
        ])
        packet.extend([0x0E, 0x00])
        self.sock_send.sendto(packet, (self.target_ip, self.send_port))

    def _recv_loop(self):
        while self.running:
            try:
                data, _ = self.sock_recv.recvfrom(2048)
                
                # Check for standard touch packet signature
                if len(data) >= 1373 and data[0] == 0x88:
                    current_touches = set()
                    
                    for ch in range(NUM_CHANNELS):
                        base = 2 + ch * 171
                        for led in range(LEDS_PER_CHANNEL):
                            if data[base + 1 + led] == 0xCC:
                                current_touches.add((ch, led))
                    
                    with self.lock:
                        self.active_touches = current_touches
            except Exception:
                pass

    def stop(self):
        self.running = False