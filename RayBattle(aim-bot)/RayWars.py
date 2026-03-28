"""
RAY WARS - HOMING EDITION (V2)
══════════════════════════════
16x32 LED matrix game. Two teams fight across a 2-row dividing line.
Rays now actively track opponents ahead, but with a sharp 3:1 forward-to-lateral ratio.
Original hearts display restored.
"""

import socket
import time
import threading
import random
import json
import os
import sys

# ==============================================================================
# --- Fix Pathing for local imports ---
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
    small_font = None

try:
    import pygame
    pygame.mixer.init()
    sfx_dir = os.path.join(parent_dir, '_sfx')
    sounds = {
        'drop': pygame.mixer.Sound(os.path.join(sfx_dir, 'drop.wav')),
        'gameover': pygame.mixer.Sound(os.path.join(sfx_dir, 'gameover.wav')),
        'line': pygame.mixer.Sound(os.path.join(sfx_dir, 'ray_sfx.mp3'))
    }
except:
    sounds = None

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

UDP_SEND_IP = CONFIG.get("device_ip", "127.0.0.1")
UDP_SEND_PORT = CONFIG.get("send_port", 6766)
UDP_LISTEN_PORT = CONFIG.get("recv_port", 6767)

NUM_CHANNELS = 8
LEDS_PER_CHANNEL = 64
FRAME_DATA_LENGTH = NUM_CHANNELS * LEDS_PER_CHANNEL * 3
BOARD_WIDTH = 16
BOARD_HEIGHT = 32

# --- Game Rules ---
MAX_HEARTS = 5
CHARGE_TIME = 1.0     
RAY_LENGTH = 4        # Coada razei vizibila pe ecran
START_SPEED = 0.08    
HOMING_RATIO = 3      # Pași înainte necesari pentru 1 pas lateral

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
DIVIDER_COLOR = (50, 50, 50)
TEAM_A_COLOR = (255, 0, 0)   
TEAM_B_COLOR = (0, 0, 255)   
HEART_COLOR = (255, 20, 147) 
EXPLOSION_COLOR = (255, 255, 0) 

class RayWarsGame:
    def __init__(self):
        self.button_states = [[False for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]
        self.running = True
        self.state = 'LOBBY' 
        
        self.hearts = [MAX_HEARTS, MAX_HEARTS] 
        self.rays = []
        self.active_tiles = set()
        self.charge_timers = {}
        self.hit_explosions = []
        
        self.start_time = 0
        self.last_ray_step = 0
        self.ray_speed = START_SPEED
        self.gameover_text = ""
        self.gameover_timer = 0
        
        self.lock = threading.RLock()
        self.sounds = sounds

    def start_game(self):
        with self.lock:
            self.state = 'STARTUP'
            self.hearts = [MAX_HEARTS, MAX_HEARTS]
            self.rays.clear()
            self.charge_timers.clear()
            self.hit_explosions.clear()
            self.start_time = time.time()
            print("RAY WARS - PREPARE TO FIGHT!")

    def end_game(self, text):
        self.state = 'GAMEOVER'
        self.gameover_text = text
        self.gameover_timer = time.time()
        print(f"\n[!] {text}")
        if self.sounds and 'gameover' in self.sounds:
            self.sounds['gameover'].play()

    def tick(self):
        now = time.time()
        with self.lock:
            if self.state == 'LOBBY':
                return
            elif self.state == 'STARTUP':
                if now - self.start_time > 3.0:
                    self.state = 'PLAYING'
                    self.start_time = now
                    self.last_ray_step = now
                return
            elif self.state == 'GAMEOVER':
                return

            # Update active tiles from current buttons
            self.active_tiles.clear()
            for y in range(BOARD_HEIGHT):
                if y in (15, 16): continue
                for x in range(BOARD_WIDTH):
                    if self.button_states[y][x]:
                        self.active_tiles.add((x, y))
                        if (x, y) not in self.charge_timers:
                            self.charge_timers[(x, y)] = now

            self.hit_explosions = [e for e in self.hit_explosions if now - e["time"] < 0.35]

            elapsed = now - self.start_time
            self.ray_speed = max(0.02, START_SPEED - (elapsed * 0.0005))

            # --- PROCESS RAYS (HOMING LOGIC 3:1) ---
            if now - self.last_ray_step > self.ray_speed:
                self.last_ray_step = now
                to_remove = []
                
                for r in self.rays:
                    # Coordonatele curente ale 'capului' razei
                    hx, hy = r["path"][-1]
                    
                    # Cautam cea mai apropiata tinta valida
                    best_target = None
                    min_dist = 9999
                    
                    for (tx, ty) in self.active_tiles:
                        if r["team"] == 0 and ty < 17: continue
                        if r["team"] == 1 and ty > 14: continue
                        
                        # HOMING RULE 1: Ignora daca tinta e la acelasi nivel sau in spate
                        if (ty - hy) * r["dir"] <= 0: continue
                        
                        dist = abs(tx - hx) + abs(ty - hy)
                        if dist < min_dist:
                            min_dist = dist
                            best_target = (tx, ty)
                    
                    # Determinam directia laterala dorita
                    desired_dx = 0
                    if best_target:
                        tx, ty = best_target
                        if tx > hx: desired_dx = 1
                        elif tx < hx: desired_dx = -1
                    
                    next_x = hx
                    # HOMING RULE 3: Avanseaza intotdeauna inainte pe Y
                    next_y = hy + r["dir"]

                    # --- Implementare LOGICA 3:1 ---
                    # Incremetam contorul de pasi facuti drept
                    r["steps_straight"] += 1

                    # Dacă am făcut 3 pași drept, putem face 1 pas lateral (dacă e nevoie)
                    if r["steps_straight"] >= HOMING_RATIO:
                        next_x += desired_dx
                        # Resetăm contorul doar dacă am virat (ca să nu piardă "virajul" dacă ținta e departe)
                        if desired_dx != 0:
                            r["steps_straight"] = 0
                        else:
                            # Dacă nu e nevoie să vireze, păstrăm contorul la prag ca să poată vira imediat turul următor
                            r["steps_straight"] = HOMING_RATIO
                    
                    next_x = max(0, min(BOARD_WIDTH - 1, next_x))
                    
                    # Adaugam noua coordonata la path
                    r["path"].append((next_x, next_y))
                    
                    # Taie "coada" razei
                    if len(r["path"]) > RAY_LENGTH:
                        r["path"].pop(0)
                        
                    # Check Bounds
                    if next_y < 0 or next_y >= BOARD_HEIGHT:
                        to_remove.append(r)
                        continue
                        
                    # Check Collision cu inamicii
                    if r["team"] == 0 and next_y >= 17:
                        if (next_x, next_y) in self.active_tiles:
                            self.hearts[1] -= 1
                            self.hit_explosions.append({"x": next_x, "y": next_y, "time": now})
                            to_remove.append(r)
                            if self.sounds and 'drop' in self.sounds: self.sounds['drop'].play()
                            if self.hearts[1] <= 0:
                                self.end_game("TEAM RED WINS!")
                            continue
                    elif r["team"] == 1 and next_y <= 14:
                        if (next_x, next_y) in self.active_tiles:
                            self.hearts[0] -= 1
                            self.hit_explosions.append({"x": next_x, "y": next_y, "time": now})
                            to_remove.append(r)
                            if self.sounds and 'drop' in self.sounds: self.sounds['drop'].play()
                            if self.hearts[0] <= 0:
                                self.end_game("TEAM BLUE WINS!")
                            continue
                
                for r in to_remove:
                    if r in self.rays:
                        self.rays.remove(r)

            # --- RAY SPAWNING ---
            for (x, y), ts in list(self.charge_timers.items()):
                if (x, y) not in self.active_tiles:
                    del self.charge_timers[(x, y)]
                    continue
                
                if now - ts >= CHARGE_TIME:
                    direction = 1 if y <= 14 else -1
                    team = 0 if y <= 14 else 1
                    
                    # Adaugam `steps_straight` pentru a urmari ratia de homing
                    self.rays.append({
                        "path": [(x, y)],
                        "dir": direction,
                        "team": team,
                        "steps_straight": 0 # Începe contorizarea de la lansare
                    })
                    self.charge_timers[(x, y)] = now
                    if self.sounds and 'line' in self.sounds: self.sounds['line'].play()

    def set_led(self, buffer, x, y, color):
        if x < 0 or x >= 16 or y < 0 or y >= 32: return
        channel = y // 4
        if channel >= 8: return
        row_in_channel = y % 4
        if row_in_channel % 2 == 0: led_index = row_in_channel * 16 + x
        else: led_index = row_in_channel * 16 + (15 - x)
        
        offset = led_index * NUM_CHANNELS * 3 + channel
        if offset + NUM_CHANNELS*2 < len(buffer):
            buffer[offset] = color[1]
            buffer[offset + NUM_CHANNELS] = color[0]
            buffer[offset + NUM_CHANNELS*2] = color[2]

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

    # --- RESTAURARE AFISAJ INIMA ORIGINAL ---
    def draw_heart(self, buffer, center_x, center_y, color):
        # Folosim exact punctele stilizate din fisierul original al prietenului tau
        pts = [(0,0), (-1,-1), (1,-1), (-1,0), (1,0), (0,1)]
        for dx, dy in pts:
            self.set_led(buffer, center_x + dx, center_y + dy, color)

    def render(self):
        buffer = bytearray(FRAME_DATA_LENGTH)
        now = time.time()
        
        with self.lock:
            if self.state == 'LOBBY':
                pass 
                
            elif self.state == 'STARTUP':
                if int(now * 4) % 2 == 0:
                    for y in range(BOARD_HEIGHT):
                        for x in range(BOARD_WIDTH):
                            c = TEAM_A_COLOR if y <= 15 else TEAM_B_COLOR
                            self.set_led(buffer, x, y, c)

            elif self.state == 'PLAYING':
                # Background
                for y in range(BOARD_HEIGHT):
                    for x in range(BOARD_WIDTH):
                        if y in (15, 16):
                            self.set_led(buffer, x, y, DIVIDER_COLOR)
                        else:
                            if self.button_states[y][x]:
                                self.set_led(buffer, x, y, WHITE)
                
                # Hearts (La coordonatele Y originale 14 si 17)
                for i in range(self.hearts[0]):
                    self.draw_heart(buffer, 2 + i*3, 14, HEART_COLOR)
                for i in range(self.hearts[1]):
                    self.draw_heart(buffer, 2 + i*3, 17, HEART_COLOR)
                
                # Rays (Desenam path-ul complet)
                for r in self.rays:
                    color = TEAM_A_COLOR if r["team"] == 0 else TEAM_B_COLOR
                    for (rx, ry) in r["path"]:
                        self.set_led(buffer, rx, ry, color)
                
                # Explosions
                for e in self.hit_explosions:
                    ex, ey = e["x"], e["y"]
                    for dx, dy in [(0,0), (-1,0), (1,0), (0,-1), (0,1)]:
                        self.set_led(buffer, ex+dx, ey+dy, EXPLOSION_COLOR)

            elif self.state == 'GAMEOVER':
                text_color = TEAM_A_COLOR if "RED" in self.gameover_text else TEAM_B_COLOR
                scroll_speed = 12
                elapsed = now - self.gameover_timer
                txt_len = len(self.gameover_text) * 4
                cy = BOARD_HEIGHT - int(elapsed * scroll_speed)
                
                if cy < -txt_len:
                    self.gameover_timer = now
                self.draw_string_90(buffer, self.gameover_text, 12, cy, text_color)
                
        return buffer

class NetworkManager:
    def __init__(self, game):
        self.game = game
        self.sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_send.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running = True
        self.seq = 0
        
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
                            row_in_channel = led_idx // 16
                            col_raw = led_idx % 16
                            x = col_raw if row_in_channel % 2 == 0 else 15 - col_raw
                            y = ch * 4 + row_in_channel
                            if y < 32 and x < 16:
                                self.game.button_states[y][x] = (val == 0xCC)
            except: pass

    def send_packet(self, frame_data):
        self.seq = (self.seq + 1) & 0xFFFF
        if self.seq == 0: self.seq = 1
        port = UDP_SEND_PORT
        
        start_packet = bytearray([0x75, random.randint(0,127), random.randint(0,127), 0x00, 0x08, 0x02, 0x00, 0x00, 0x33, 0x44, (self.seq >> 8) & 0xFF, self.seq & 0xFF, 0x00, 0x00, 0x00, 0x0E, 0x00])
        self.sock_send.sendto(start_packet, (UDP_SEND_IP, port))
        self.sock_send.sendto(start_packet, ("127.0.0.1", port))

        fff0_payload = bytearray()
        for _ in range(NUM_CHANNELS):
            fff0_payload += bytes([(LEDS_PER_CHANNEL >> 8) & 0xFF, LEDS_PER_CHANNEL & 0xFF])
        fff0_internal = bytearray([0x02, 0x00, 0x00, 0x88, 0x77, 0xFF, 0xF0, (len(fff0_payload) >> 8) & 0xFF, (len(fff0_payload) & 0xFF)]) + fff0_payload
        fff0_len = len(fff0_internal) - 1
        fff0_packet = bytearray([0x75, random.randint(0,127), random.randint(0,127), (fff0_len >> 8) & 0xFF, (fff0_len & 0xFF)]) + fff0_internal
        fff0_packet.extend([0x1E, 0x00])
        self.sock_send.sendto(fff0_packet, (UDP_SEND_IP, port))
        self.sock_send.sendto(fff0_packet, ("127.0.0.1", port))

        chunk_size = 984 
        pkt_idx = 1
        for i in range(0, len(frame_data), chunk_size):
            chunk = frame_data[i:i+chunk_size]
            internal = bytearray([0x02, 0x00, 0x00, 0x88, 0x77, (pkt_idx >> 8) & 0xFF, pkt_idx & 0xFF, (len(chunk) >> 8) & 0xFF, len(chunk) & 0xFF]) + chunk
            payload_len = len(internal) - 1 
            pkt = bytearray([0x75, random.randint(0,127), random.randint(0,127), (payload_len >> 8) & 0xFF, payload_len & 0xFF]) + internal
            pkt.extend([0x1E if len(chunk) == 984 else 0x36, 0x00])
            self.sock_send.sendto(pkt, (UDP_SEND_IP, port))
            self.sock_send.sendto(pkt, ("127.0.0.1", port))
            pkt_idx += 1
            time.sleep(0.002) 

        end_packet = bytearray([0x75, random.randint(0,127), random.randint(0,127), 0x00, 0x08, 0x02, 0x00, 0x00, 0x55, 0x66, (self.seq >> 8) & 0xFF, self.seq & 0xFF, 0x00, 0x00, 0x00, 0x0E, 0x00])
        self.sock_send.sendto(end_packet, (UDP_SEND_IP, port))
        self.sock_send.sendto(end_packet, ("127.0.0.1", port))

    def start_bg(self):
        t1 = threading.Thread(target=self.send_loop, daemon=True)
        t2 = threading.Thread(target=self.recv_loop, daemon=True)
        t1.start()
        t2.start()

def main():
    game = RayWarsGame()
    net = NetworkManager(game)
    net.start_bg()
    
    gt = threading.Thread(target=lambda: [game.tick() or time.sleep(0.01) for _ in iter(lambda: game.running, False)], daemon=True)
    gt.start()
    
    print("\n" + "="*40)
    print(" RAY WARS - HOMING EDITION (3:1) ")
    print("="*40)
    print("Commands: 'start', 'quit'")
    
    try:
        while game.running:
            cmd = input("> ").strip().lower()
            if cmd in ('quit', 'q', 'exit'):
                game.running = False
            elif cmd == 'start':
                game.start_game()
    except KeyboardInterrupt:
        game.running = False

    net.running = False

if __name__ == "__main__":
    main()