"""
RAY WARS - eSPORTS EDITION (Best of 5)
══════════════════════════════════════
16x32 LED matrix game. Two teams fight across a 2-row dividing line.
Rays actively track opponents ahead, but with a sharp 3:1 forward-to-lateral ratio.
Features: Configurable players, speed presets, max 2 *charging* rays/player, anti-camping, 
          dynamic health bar, ray fade effects, charge-up glow, Best-of-5 Match System,
          VORTEX SHOCKWAVE round-end animation, and Ambient BGM!
"""

import socket
import time
import threading
import random
import json
import os
import sys
import math

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
    
    # --- Incarcare Muzica Ambientala ---
    bgm_path = os.path.join(sfx_dir, 'ray_ambient.mp3')
    if os.path.exists(bgm_path):
        pygame.mixer.music.load(bgm_path)
        pygame.mixer.music.set_volume(0.4) 
        pygame.mixer.music.play(-1)        
    else:
        print(f"[!] Warning: BGM not found at {bgm_path}")

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
CHARGE_TIME = 0.67     
RAY_LENGTH = 4        
HOMING_RATIO = 4      

SPEED_PRESETS = {
    "slow":   (0.28, 0.08, 10.0, 0.02),
    "medium": (0.20, 0.04,  6.7, 0.02),
    "fast":   (0.12, 0.02,  4.0, 0.02),
}

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
DIVIDER_COLOR = (50, 50, 50)
TEAM_A_COLOR = (255, 0, 0)   
TEAM_B_COLOR = (0, 0, 255)   
HEART_COLOR = (255, 20, 147) 
EXPLOSION_COLOR = (255, 255, 0) 

def _dim(color, f):
    return tuple(max(0, min(255, int(c * f))) for c in color)

class RayWarsGame:
    VORTEX_ROTATION_SPEED = 12.0 
    VORTEX_TIGHTNESS = 1.3      
    VORTEX_EXPANSION_SPEED = 18.0 
    VORTEX_ARM_THICKNESS = 0.8  

    def __init__(self):
        self.button_states = [[False for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]
        self.running = True
        self.state = 'LOBBY' 
        
        self.max_health = 2
        self.hearts = [self.max_health, self.max_health] 
        self.rays = []
        self.active_tiles = set()
        self.charge_timers = {}
        self.exhausted_tiles = set() 
        self.hit_explosions = []
        
        self.score = [0, 0] 
        self.score_timer = 0
        
        self.start_time = 0
        self.last_ray_step = 0
        self.ray_speed = 0.20
        self.gameover_text = ""
        self.gameover_timer = 0
        
        self.last_hit_coords = (8, 16) 
        self.vortex_color = WHITE
        
        self.players_a = 1
        self.players_b = 1
        self.speed_preset = "medium"
        
        self.lock = threading.RLock()
        self.sounds = sounds

    def start_game(self, p_a, p_b, speed):
        with self.lock:
            self.players_a = p_a
            self.players_b = p_b
            self.speed_preset = speed
            self.score = [0, 0] 
            
            print(f"\n[!] MATCH STARTED! Best of 5! (Speed: {speed.upper()} | {p_a} vs {p_b})")
            self.start_round()

    def start_round(self):
        with self.lock:
            self.max_health = 2 * max(self.players_a, self.players_b)
            self.hearts = [self.max_health, self.max_health]
            
            self.state = 'STARTUP'
            self.rays.clear()
            self.charge_timers.clear()
            self.exhausted_tiles.clear()
            self.hit_explosions.clear()
            self.start_time = time.time()
            
            self.r_start, self.r_min, self.r_interval, self.r_step = SPEED_PRESETS[self.speed_preset]
            self.ray_speed = self.r_start
            
            print(f"-> ROUND STARTING... Score: {self.score[0]} - {self.score[1]}")

    def end_round(self, winner_team):
        self.score[winner_team] += 1
        self.gameover_timer = time.time()
        team_name = "ROSU" if winner_team == 0 else "ALBASTRU"
        
        self.vortex_color = TEAM_A_COLOR if winner_team == 0 else TEAM_B_COLOR

        if self.score[winner_team] >= 3:
            self.state = 'MATCH_OVER'
            self.gameover_text = f"{team_name} A CASTIGAT MECIUL !!!"
            print(f"\n[!!!] {self.gameover_text} [!!!]")
        else:
            self.state = 'GAMEOVER'
            self.gameover_text = "" # FARA TEXT intre runde
            print(f"\n[!] {team_name} a castigat runda! (Scor: {self.score[0]}-{self.score[1]})")
            
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
                # Lasam Vortexul sa se extinda fix 3 secunde inainte sa apara scorul
                if now - self.gameover_timer >= 3.0:
                    self.state = 'SHOW_SCORE'
                    self.score_timer = now
                return
                
            elif self.state == 'SHOW_SCORE':
                if now - self.score_timer >= 2.5:
                    self.start_round() 
                return
                
            elif self.state == 'MATCH_OVER':
                return

            charging_a = sum(1 for (cx, cy) in self.charge_timers if cy <= 14)
            charging_b = sum(1 for (cx, cy) in self.charge_timers if cy > 14)

            current_active = set()
            for y in range(BOARD_HEIGHT):
                if y in (15, 16): continue
                for x in range(BOARD_WIDTH):
                    if self.button_states[y][x]:
                        current_active.add((x, y))
                        
                        if (x, y) not in self.charge_timers and (x, y) not in self.exhausted_tiles:
                            team = 0 if y <= 14 else 1
                            max_allowed = (self.players_a * 2) if team == 0 else (self.players_b * 2)
                            current_charging = charging_a if team == 0 else charging_b
                            
                            if current_charging < max_allowed:
                                self.charge_timers[(x, y)] = now
                                if team == 0: charging_a += 1
                                else: charging_b += 1
                    else:
                        if (x, y) in self.exhausted_tiles:
                            self.exhausted_tiles.remove((x, y))

            self.active_tiles = current_active
            self.hit_explosions = [e for e in self.hit_explosions if now - e["time"] < 0.35]

            elapsed = now - self.start_time
            intervals_passed = int(elapsed / self.r_interval)
            self.ray_speed = max(self.r_min, self.r_start - (intervals_passed * self.r_step))

            if now - self.last_ray_step > self.ray_speed:
                self.last_ray_step = now
                to_remove = []
                
                for r in self.rays:
                    hx, hy = r["path"][-1]
                    best_target = None
                    min_dist = 9999
                    
                    for (tx, ty) in self.active_tiles:
                        if r["team"] == 0 and ty < 17: continue
                        if r["team"] == 1 and ty > 14: continue
                        if (ty - hy) * r["dir"] <= 0: continue
                        
                        dist = abs(tx - hx) + abs(ty - hy)
                        if dist < min_dist:
                            min_dist = dist
                            best_target = (tx, ty)
                    
                    desired_dx = 0
                    if best_target:
                        tx, ty = best_target
                        if tx > hx: desired_dx = 1
                        elif tx < hx: desired_dx = -1
                    
                    next_x = hx
                    next_y = hy + r["dir"]

                    r["steps_straight"] += 1
                    if r["steps_straight"] >= HOMING_RATIO:
                        next_x += desired_dx
                        if desired_dx != 0: r["steps_straight"] = 0
                        else: r["steps_straight"] = HOMING_RATIO
                    
                    next_x = max(0, min(BOARD_WIDTH - 1, next_x))
                    r["path"].append((next_x, next_y))
                    
                    if len(r["path"]) > RAY_LENGTH:
                        r["path"].pop(0)
                        
                    if next_y < 0 or next_y >= BOARD_HEIGHT:
                        to_remove.append(r)
                        continue
                        
                    if r["team"] == 0 and next_y >= 17:
                        if (next_x, next_y) in self.active_tiles:
                            self.hearts[1] -= 1
                            self.hit_explosions.append({"x": next_x, "y": next_y, "time": now})
                            to_remove.append(r)
                            if self.sounds and 'drop' in self.sounds: self.sounds['drop'].play()
                            
                            if self.hearts[1] <= 0: 
                                self.last_hit_coords = (next_x, next_y)
                                self.end_round(0) 
                            continue
                            
                    elif r["team"] == 1 and next_y <= 14:
                        if (next_x, next_y) in self.active_tiles:
                            self.hearts[0] -= 1
                            self.hit_explosions.append({"x": next_x, "y": next_y, "time": now})
                            to_remove.append(r)
                            if self.sounds and 'drop' in self.sounds: self.sounds['drop'].play()
                            
                            if self.hearts[0] <= 0: 
                                self.last_hit_coords = (next_x, next_y)
                                self.end_round(1) 
                            continue
                
                for r in to_remove:
                    if r in self.rays: self.rays.remove(r)

            for (x, y), ts in list(self.charge_timers.items()):
                if (x, y) not in self.active_tiles:
                    del self.charge_timers[(x, y)]
                    continue
                
                if now - ts >= CHARGE_TIME:
                    direction = 1 if y <= 14 else -1
                    team = 0 if y <= 14 else 1
                    
                    self.rays.append({
                        "path": [(x, y)],
                        "dir": direction,
                        "team": team,
                        "steps_straight": 0
                    })
                    
                    self.exhausted_tiles.add((x, y))
                    del self.charge_timers[(x, y)]
                    
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
                for y in range(BOARD_HEIGHT):
                    for x in range(BOARD_WIDTH):
                        if y in (15, 16):
                            self.set_led(buffer, x, y, DIVIDER_COLOR)
                        else:
                            if self.button_states[y][x]:
                                color = (100, 100, 100) if (x, y) in self.exhausted_tiles else WHITE
                                self.set_led(buffer, x, y, color)
                
                for (x, y), ts in self.charge_timers.items():
                    prog = min(1.0, (now - ts) / CHARGE_TIME)
                    direction = 1 if y <= 14 else -1
                    ahead_y = y + direction
                    if 0 <= ahead_y < BOARD_HEIGHT:
                        glow_color = _dim(WHITE, prog * 0.65)
                        self.set_led(buffer, x, ahead_y, glow_color)
                
                start_x = max(0, (BOARD_WIDTH - self.max_health) // 2)
                for i in range(self.hearts[0]):
                    if start_x + i < BOARD_WIDTH:
                        self.set_led(buffer, start_x + i, 14, HEART_COLOR)
                for i in range(self.hearts[1]):
                    if start_x + i < BOARD_WIDTH:
                        self.set_led(buffer, start_x + i, 17, HEART_COLOR)
                
                for r in self.rays:
                    base_color = TEAM_A_COLOR if r["team"] == 0 else TEAM_B_COLOR
                    path_len = len(r["path"])
                    for i, (rx, ry) in enumerate(reversed(r["path"])):
                        brightness = 1.0 - (i / path_len) * 0.70
                        self.set_led(buffer, rx, ry, _dim(base_color, brightness))
                
                for e in self.hit_explosions:
                    ex, ey = e["x"], e["y"]
                    for dx, dy in [(0,0), (-1,0), (1,0), (0,-1), (0,1)]:
                        self.set_led(buffer, ex+dx, ey+dy, EXPLOSION_COLOR)

            elif self.state in ['GAMEOVER', 'MATCH_OVER']:
                time_in_state = now - self.gameover_timer
                
                # --- ANIMATIE VORTEX SHOCKWAVE ---
                cx, cy = self.last_hit_coords
                max_r = time_in_state * self.VORTEX_EXPANSION_SPEED 
                min_r = max(0, (time_in_state - 1.25) * self.VORTEX_EXPANSION_SPEED)
                
                for y in range(BOARD_HEIGHT):
                    for x in range(BOARD_WIDTH):
                        dx = x - cx
                        dy = y - cy
                        dist = math.hypot(dx, dy) 
                        
                        if min_r < dist < max_r:
                            angle = math.atan2(dy, dx)
                            wave_arg = dist * self.VORTEX_TIGHTNESS + angle * 2.0 - time_in_state * self.VORTEX_ROTATION_SPEED
                            p_raw = (math.sin(wave_arg) + 1.0) / 2.0
                            p = math.pow(p_raw, self.VORTEX_ARM_THICKNESS * 2.0)

                            edge_fade = max(0.0, min(1.0, (max_r - dist) / 3.0))
                            inner_fade = max(0.0, min(1.0, (dist - min_r) / 3.0))
                            
                            final_p = p * edge_fade * inner_fade
                            color_mod = 0.2 + 0.8 * final_p
                            
                            intensity = edge_fade * inner_fade
                            led_color = _dim(self.vortex_color, color_mod * intensity)
                            
                            self.set_led(buffer, x, y, led_color)

                # --- TEXT SCROLLING (Doar daca a castigat MECIUL) ---
                if self.state == 'MATCH_OVER':
                    text_color = WHITE 
                    scroll_speed = 12
                    txt_len = len(self.gameover_text) * 4
                    total_dist = BOARD_HEIGHT + txt_len
                    
                    cy_text = BOARD_HEIGHT - int((time_in_state * scroll_speed) % total_dist)
                    self.draw_string_90(buffer, self.gameover_text, 12, cy_text, text_color)
                
            elif self.state == 'SHOW_SCORE':
                self.draw_char_90(buffer, str(self.score[0]), 10, 10, TEAM_A_COLOR)
                self.draw_char_90(buffer, '-', 10, 14, WHITE)
                self.draw_char_90(buffer, str(self.score[1]), 10, 18, TEAM_B_COLOR)
                
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
    
    print("\n" + "="*45)
    print(" RAY WARS - FULL FX BEST-OF-5 EDITION ")
    print("="*45)
    print("Commands: 'start', 'quit'")
    
    try:
        while game.running:
            cmd = input("> ").strip().lower()
            if cmd in ('quit', 'q', 'exit'):
                game.running = False
            elif cmd == 'start':
                try:
                    pa = int(input("Jucatori Echipa ROSIE (Sus): "))
                    pb = int(input("Jucatori Echipa ALBASTRA (Jos): "))
                    sp = input("Viteza (slow/medium/fast): ").strip().lower()
                    
                    if sp not in SPEED_PRESETS:
                        print("Viteza invalida! Se foloseste 'medium'.")
                        sp = "medium"
                        
                    game.start_game(pa, pb, sp)
                except ValueError:
                    print("Eroare: Trebuie sa introduci un numar valid de jucatori!")
    except KeyboardInterrupt:
        game.running = False

    net.running = False

if __name__ == "__main__":
    main()