import socket
import time
import threading
import random
import os
import json
import math
import sys

# ==============================================================================
# --- Fix Pathing for moving file to Sandrun/ Sandrun.py ---
# ==============================================================================
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)

matrix_dir = os.path.join(parent_dir, 'Matrix')
example_dir = os.path.join(parent_dir, 'Example')

if matrix_dir not in sys.path: sys.path.append(matrix_dir)
if example_dir not in sys.path: sys.path.append(example_dir)

try:
    import small_font
except ImportError:
    print("[!] Warning: Could not import Matrix/small_font.py. Text might not render.")
    small_font = None

try:
    import pygame
    pygame.mixer.init()
    sfx_dir = os.path.join(parent_dir, '_sfx')
    sounds = {
        'drop': pygame.mixer.Sound(os.path.join(sfx_dir, 'drop.wav')),
        'gameover': pygame.mixer.Sound(os.path.join(sfx_dir, 'gameover.wav')),
        'move': pygame.mixer.Sound(os.path.join(sfx_dir, 'move.wav')),
        'line': pygame.mixer.Sound(os.path.join(sfx_dir, 'line.wav'))
    }
except:
    sounds = None
    print("[!] Sounds not loaded. Check pygame and _sfx folder.")

# ==============================================================================
# --- Configuration ---
# ==============================================================================
_CFG_FILE = os.path.join(current_script_dir, "config_game.json")

def _load_config():
    defaults = {
        "device_ip": "127.0.0.1",
        "send_port": 6766,
        "recv_port": 6767,
        "bind_ip": "0.0.0.0"
    }
    try:
        if os.path.exists(_CFG_FILE):
            with open(_CFG_FILE, encoding="utf-8") as f:
                return {**defaults, **json.load(f)}
    except: pass
    return defaults

CONFIG = _load_config()

# --- Networking Constants ---
UDP_SEND_IP = CONFIG.get("device_ip", "127.0.0.1")
UDP_SEND_PORT = CONFIG.get("send_port", 6766)
UDP_LISTEN_PORT = CONFIG.get("recv_port", 6767)

# --- Matrix Constants ---
NUM_CHANNELS = 8
LEDS_PER_CHANNEL = 64
FRAME_DATA_LENGTH = NUM_CHANNELS * LEDS_PER_CHANNEL * 3

BOARD_WIDTH = 16
BOARD_HEIGHT = 32

# --- Round Mechanics ---
MAX_LAVA_HITS = 10
ROUND_DURATION = 60 # seconds

# --- Treasure Hunt Mechanics ---
TARGET_GEMS = 15 # Numarul de comori necesar pentru a CÂȘTIGA
MAX_ON_SCREEN_GEMS = 3 # Cate comori sunt active pe ecran simultan

# --- Colors (R, G, B) ---
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
SAND = (230, 190, 50)     
WARNING = (255, 100, 0)   
LAVA = (255, 0, 0)        
LAVA_HIT_COLOR = (128, 0, 128) 
GEM_COLOR = (0, 255, 255) 
RED = (255, 0, 0)

# --- Game Class ---
class SandrunGame:
    def __init__(self):
        self.button_states = [[False for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]
        self.board_state = [['SAFE' for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]
        self.board_timers = [[0.0 for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]
        
        self.running = True
        self.state = 'LOBBY' 
        
        self.startup_step = 3
        self.startup_timer = 0
        
        self.start_time = 0
        self.survive_time = 0
        self.gameover_timer = 0
        self.gameover_reason = ""
        self.difficulty = "medium"

        self.hits_count = 0
        self.gems_collected = 0
        self.active_gems = set() 
        
        # Expunem limitele catre UI
        self.target_gems = TARGET_GEMS
        self.max_hits = MAX_LAVA_HITS
        self.round_duration = ROUND_DURATION
        
        self.lock = threading.RLock()

    def start_game(self, diff="medium"):
        with self.lock:
            self.difficulty = diff
            for y in range(BOARD_HEIGHT):
                for x in range(BOARD_WIDTH):
                    is_border = (x == 0 or x == (BOARD_WIDTH - 1) or y == 0 or y == (BOARD_HEIGHT - 1))
                    self.board_state[y][x] = 'LAVA' if is_border else 'SAFE'
                    self.board_timers[y][x] = 0.0
            
            self.hits_count = 0
            self.gems_collected = 0
            self.active_gems.clear()
            self.survive_time = 0
            self.gameover_reason = ""
            
            self.state = 'STARTUP'
            self.startup_step = 3
            self.startup_timer = time.time()
                
            print(f"Starting Round in 3... (Difficulty: {self.difficulty.upper()} | Target: {TARGET_GEMS} Gems)")

    def end_round(self, reason):
        if self.state != 'GAMEOVER':
            print(f"\n[!] ROUND OVER! Reason: {reason}")
            print(f"[!] Team Survived for: {self.survive_time:.2f} seconds")
            print(f"[!] Gems Collected: {self.gems_collected}/{TARGET_GEMS}")
            print(f"[!] Total Lava Hits: {self.hits_count}/{MAX_LAVA_HITS}\n")
            
            self.state = 'GAMEOVER'
            self.gameover_reason = reason
            self.gameover_timer = time.time()
            
            if sounds:
                if "WON" in reason and 'line' in sounds:
                    sounds['line'].play()
                elif 'gameover' in sounds:
                    sounds['gameover'].play()

    def get_dynamic_warning_duration(self):
        diff_settings = {
            'easy': (3.0, 0.75),
            'medium': (2.0, 0.67),
            'hard': (1.25, 0.5)
        }
        
        start_dur, end_dur = diff_settings.get(self.difficulty, diff_settings['medium'])
        
        now = time.time()
        if self.start_time == 0: 
            return start_dur
            
        elapsed = now - self.start_time
        progress = min(1.0, elapsed / ROUND_DURATION)
        
        current_dur = start_dur - (start_dur - end_dur) * progress
        return current_dur

    def tick(self):
        now = time.time()
        with self.lock:
            if self.state == 'LOBBY':
                return
                
            elif self.state == 'STARTUP':
                if now - self.startup_timer > 1.0:
                    self.startup_step -= 1
                    self.startup_timer = now
                    if self.startup_step > 0:
                        print(f"{self.startup_step}...")
                    else:
                        print("GO! RUN! COLLECT GEMS!")
                        self.state = 'PLAYING'
                        self.start_time = now
                return

            elif self.state == 'GAMEOVER':
                return

            self.survive_time = now - self.start_time
            
            if len(self.active_gems) < MAX_ON_SCREEN_GEMS:
                for _ in range(5):
                    rx = random.randint(1, BOARD_WIDTH - 2)
                    ry = random.randint(1, BOARD_HEIGHT - 2)
                    if self.board_state[ry][rx] == 'SAFE' and (rx, ry) not in self.active_gems and not self.button_states[ry][rx]:
                        self.active_gems.add((rx, ry))
                        break

            if self.survive_time >= ROUND_DURATION:
                if self.gems_collected >= TARGET_GEMS:
                    self.end_round(f"TIME UP! YOU WON! ({self.gems_collected} Gems)")
                else:
                    self.end_round(f"TIME UP! YOU LOST! (Only {self.gems_collected}/{TARGET_GEMS} Gems)")
                return

            warning_duration = self.get_dynamic_warning_duration()

            for y in range(BOARD_HEIGHT):
                for x in range(BOARD_WIDTH):
                    is_pressed = self.button_states[y][x]
                    current_tile_state = self.board_state[y][x]

                    if is_pressed:
                        if (x, y) in self.active_gems:
                            self.active_gems.remove((x, y))
                            self.gems_collected += 1
                            if sounds and 'line' in sounds: sounds['line'].play()
                            print(f"[+] GEM COLLECTED! Total: {self.gems_collected}")

                        if current_tile_state == 'SAFE':
                            self.board_state[y][x] = 'WARNING'
                            self.board_timers[y][x] = now
                            if sounds and 'move' in sounds: sounds['move'].play()
                        
                        elif current_tile_state == 'LAVA':
                            self.board_state[y][x] = 'LAVA_HIT'
                            self.hits_count += 1
                            print(f"[!] HIT! Stepped on Lava at X:{x} Y:{y}. Total Hits: {self.hits_count}")
                            if sounds and 'drop' in sounds: sounds['drop'].play()
                            
                            if self.hits_count >= MAX_LAVA_HITS:
                                if self.gems_collected >= TARGET_GEMS:
                                    self.end_round(f"MAX HITS REACHED! YOU WON! ({self.gems_collected} Gems)")
                                else:
                                    self.end_round("YOU LOST! Maximum Lava Hits Reached.")
                                return
                    
                    if current_tile_state == 'WARNING':
                        if now - self.board_timers[y][x] > warning_duration:
                            self.board_state[y][x] = 'LAVA'

    def set_led(self, buffer, x, y, color):
        if x < 0 or x >= 16 or y < 0 or y >= 32: return
        channel = y // 4
        if channel >= 8: return
        
        row_in_channel = y % 4
        if row_in_channel % 2 == 0: led_index = row_in_channel * 16 + x
        else: led_index = row_in_channel * 16 + (15 - x)
        
        block_size = NUM_CHANNELS * 3
        offset = led_index * block_size + channel
        
        if offset + NUM_CHANNELS*2 < len(buffer):
            buffer[offset] = color[1]                   # G
            buffer[offset + NUM_CHANNELS] = color[0]    # R
            buffer[offset + NUM_CHANNELS*2] = color[2]  # B

    def get_char_pixels(self, char):
        if small_font and hasattr(small_font, 'FONT_3x5') and char in small_font.FONT_3x5:
            return small_font.FONT_3x5[char]
        return [0, 0, 0] 

    def draw_char_90(self, buffer, char, start_x, start_y, color):
        cols = self.get_char_pixels(char)
        for x_offset, col_data in enumerate(cols):
            for y_offset in range(5):
                if (col_data >> y_offset) & 1:
                    new_x = start_x - y_offset
                    new_y = start_y + x_offset
                    self.set_led(buffer, new_x, new_y, color)
        return len(cols)

    def draw_string_90(self, buffer, text, x, y, color):
        curr_y = y
        for char in text:
            if char == ' ':
                curr_y += 2
                continue
            width = self.draw_char_90(buffer, char.upper(), x, curr_y, color)
            curr_y += width + 1

    def render(self):
        buffer = bytearray(FRAME_DATA_LENGTH)
        now = time.time()
        
        with self.lock:
            if self.state == 'LOBBY':
                intensity = int(180 + 50 * math.sin(now * 2))
                sand_breathe = (intensity, int(intensity * 0.8), 20)
                for y in range(BOARD_HEIGHT):
                    for x in range(BOARD_WIDTH):
                        self.set_led(buffer, x, y, sand_breathe)

            elif self.state == 'STARTUP':
                elapsed = now - self.startup_timer
                progress = min(1.0, elapsed / 3.0) 
                
                front_x = progress * 40.0 - 1.0

                for y in range(BOARD_HEIGHT):
                    for x in range(BOARD_WIDTH):
                        is_border = (x == 0 or x == (BOARD_WIDTH - 1) or y == 0 or y == (BOARD_HEIGHT - 1))
                        
                        if is_border:
                            self.set_led(buffer, x, y, RED)
                        else:
                            dist = x - front_x
                            if dist <= 0:
                                c = SAND if random.random() > 0.1 else WARNING
                            elif dist < 2:
                                c = SAND if random.random() > 0.5 else BLACK
                            else:
                                c = BLACK
                            self.set_led(buffer, x, y, c)

            elif self.state == 'PLAYING':
                fast_blink = int(now * 10) % 2 == 0
                slow_blink = int(now * 5) % 2 == 0

                for y in range(BOARD_HEIGHT):
                    for x in range(BOARD_WIDTH):
                        tile_state = self.board_state[y][x]
                        
                        if tile_state == 'SAFE':
                            c = SAND
                        elif tile_state == 'WARNING':
                            c = WARNING if fast_blink else SAND
                        elif tile_state == 'LAVA_HIT':
                            c = LAVA_HIT_COLOR if slow_blink else BLACK
                        else:
                            c = LAVA 
                            
                        if (x, y) in self.active_gems:
                            c = GEM_COLOR if fast_blink else WHITE

                        if self.button_states[y][x] and tile_state not in ['LAVA_HIT'] and tile_state != 'LAVA':
                            c = WHITE
                            
                        self.set_led(buffer, x, y, c)

            elif self.state == 'GAMEOVER':
                text_color = (0, 255, 0) if "WON" in self.gameover_reason else RED
                
                for y in range(BOARD_HEIGHT):
                    for x in range(BOARD_WIDTH):
                        self.set_led(buffer, x, y, BLACK)
                
                if small_font:
                    prefix = "WINNER" if "WON" in self.gameover_reason else "LOSER"
                    final_text = f"{prefix}  HITS:{self.hits_count}  GEMS:{self.gems_collected}  {int(self.survive_time)}S"
                    
                    text_pixel_length = len(final_text) * 4
                    scroll_speed = 10 
                    elapsed_time = now - self.gameover_timer
                    
                    current_y = BOARD_HEIGHT - int(elapsed_time * scroll_speed)
                    if current_y < -text_pixel_length:
                        self.gameover_timer = now 
                    
                    self.draw_string_90(buffer, final_text, 13, current_y, text_color)
                    
        return buffer

# --- Networking ---
class NetworkManager:
    def __init__(self, game):
        self.game = game
        self.sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_send.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running = True
        self.sequence_number = 0
        
        bind_ip = CONFIG.get("bind_ip", "0.0.0.0")
        if bind_ip != "0.0.0.0":
            try: self.sock_send.bind((bind_ip, 0))
            except: pass
        
        try:
            self.sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock_recv.bind(("0.0.0.0", UDP_LISTEN_PORT))
        except Exception as e:
            print(f"Network error (recv): {e}")
            self.running = False

    def send_loop(self):
        while self.running:
            frame = self.game.render()
            self.send_packet(frame)
            time.sleep(0.04) 
            
    def recv_loop(self):
        while self.running:
            try:
                data, _ = self.sock_recv.recvfrom(2048)
                if len(data) >= 1373 and data[0] == 0x88:
                    for ch in range(8):
                        offset = 2 + (ch * 171) + 1
                        ch_data = data[offset : offset + 64]
                        
                        for led_idx, val in enumerate(ch_data):
                            is_pressed = (val == 0xCC)
                            
                            row_in_channel = led_idx // 16
                            col_raw = led_idx % 16
                            
                            x = col_raw if row_in_channel % 2 == 0 else 15 - col_raw
                            y = ch * 4 + row_in_channel
                            
                            if y < 32 and x < 16:
                                self.game.button_states[y][x] = is_pressed
            except Exception: pass

    def send_packet(self, frame_data):
        self.sequence_number = (self.sequence_number + 1) & 0xFFFF
        if self.sequence_number == 0: self.sequence_number = 1
        port = UDP_SEND_PORT
        
        start_packet = bytearray([0x75, random.randint(0,127), random.randint(0,127), 0x00, 0x08, 0x02, 0x00, 0x00, 0x33, 0x44, (self.sequence_number >> 8) & 0xFF, self.sequence_number & 0xFF, 0x00, 0x00, 0x00])
        start_packet.append(0x0E); start_packet.append(0x00)
        self.sock_send.sendto(start_packet, (UDP_SEND_IP, port))
        self.sock_send.sendto(start_packet, ("127.0.0.1", port))

        fff0_payload = bytearray()
        for _ in range(NUM_CHANNELS):
            fff0_payload += bytes([(LEDS_PER_CHANNEL >> 8) & 0xFF, LEDS_PER_CHANNEL & 0xFF])
        fff0_internal = bytearray([0x02, 0x00, 0x00, 0x88, 0x77, 0xFF, 0xF0, (len(fff0_payload) >> 8) & 0xFF, (len(fff0_payload) & 0xFF)]) + fff0_payload
        fff0_len = len(fff0_internal) - 1
        fff0_packet = bytearray([0x75, random.randint(0,127), random.randint(0,127), (fff0_len >> 8) & 0xFF, (fff0_len & 0xFF)]) + fff0_internal
        fff0_packet.append(0x1E); fff0_packet.append(0x00)
        self.sock_send.sendto(fff0_packet, (UDP_SEND_IP, port))
        self.sock_send.sendto(fff0_packet, ("127.0.0.1", port))

        chunk_size = 984 
        data_packet_index = 1
        for i in range(0, len(frame_data), chunk_size):
            chunk = frame_data[i:i+chunk_size]
            internal_data = bytearray([0x02, 0x00, 0x00, (0x8877 >> 8) & 0xFF, (0x8877 & 0xFF), (data_packet_index >> 8) & 0xFF, (data_packet_index & 0xFF), (len(chunk) >> 8) & 0xFF, (len(chunk) & 0xFF)]) + chunk
            payload_len = len(internal_data) - 1 
            packet = bytearray([0x75, random.randint(0,127), random.randint(0,127), (payload_len >> 8) & 0xFF, (payload_len & 0xFF)]) + internal_data
            packet.append(0x1E if len(chunk) == 984 else 0x36) 
            packet.append(0x00)
            self.sock_send.sendto(packet, (UDP_SEND_IP, port))
            self.sock_send.sendto(packet, ("127.0.0.1", port))
            data_packet_index += 1
            time.sleep(0.002) 

        end_packet = bytearray([0x75, random.randint(0,127), random.randint(0,127), 0x00, 0x08, 0x02, 0x00, 0x00, 0x55, 0x66, (self.sequence_number >> 8) & 0xFF, self.sequence_number & 0xFF, 0x00, 0x00, 0x00])
        end_packet.append(0x0E); end_packet.append(0x00)
        self.sock_send.sendto(end_packet, (UDP_SEND_IP, port))
        self.sock_send.sendto(end_packet, ("127.0.0.1", port))

    def start_bg(self):
        t1 = threading.Thread(target=self.send_loop, daemon=True)
        t2 = threading.Thread(target=self.recv_loop, daemon=True)
        t1.start()
        t2.start()

def game_thread_func(game):
    while game.running:
        game.tick()
        time.sleep(0.01)

if __name__ == "__main__":
    game = SandrunGame()
    net = NetworkManager(game)
    net.start_bg()
    
    gt = threading.Thread(target=game_thread_func, args=(game,), daemon=True)
    gt.start()
    
    print("======================================")
    print("🏜️  SAND-RUN - FULL UI EDITION 🏜️")
    print("======================================")
    
    try:
        import sandrun_screens
        print("[!] S-a gasit fisierul GUI. Se lanseaza ecranele...")
        sandrun_screens.launch(game)
    except ImportError:
        print("[!] sandrun_screens.py nu a fost gasit. Mod terminal activat.")
        try:
            while game.running:
                cmd = input("> ").strip().lower()
                if cmd in ['quit', 'exit', 'q']:
                    game.running = False
                    break
                elif cmd.startswith('start'):
                    parts = cmd.split()
                    diff = "medium"
                    if len(parts) > 1 and parts[1] in ["easy", "medium", "hard"]:
                        diff = parts[1]
                    game.start_game(diff)
                else:
                     print("Unknown command. Type 'start easy', 'start medium', or 'start hard'.")
        except KeyboardInterrupt:
            game.running = False

    net.running = False
    print("Exiting...")