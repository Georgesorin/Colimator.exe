import socket
import threading
import time
import random
import json
import os
import math
import sys

# ==============================================================================
# FIX PATHING & FONTURI
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(BASE_DIR)
matrix_dir = os.path.join(parent_dir, 'Matrix')

if matrix_dir not in sys.path: 
    sys.path.append(matrix_dir)

try:
    import small_font
except ImportError:
    print("[!] Warning: Could not import Matrix/small_font.py. Text might not render correctly.")
    small_font = None

_CFG_FILE = os.path.join(BASE_DIR, "config_game.json")

def _load_config():
    defaults = {"device_ip": "127.0.0.1", "send_port": 6766, "recv_port": 6767}
    try:
        if os.path.exists(_CFG_FILE):
            with open(_CFG_FILE, "r", encoding="utf-8") as f:
                return {**defaults, **json.load(f)}
    except: pass
    return defaults

CONFIG = _load_config()

# ==============================================================================
# AUDIO SYSTEM
# ==============================================================================
try:
    import pygame
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.mixer.init()
except ImportError:
    pass

def play_sound(filename, volume=1.0):
    path = os.path.join(BASE_DIR, "sounds", filename)
    if os.path.exists(path):
        try:
            s = pygame.mixer.Sound(path)
            s.set_volume(volume)
            s.play()
        except: pass

def play_bgm(filename, volume=0.4):
    path = os.path.join(BASE_DIR, "sounds", filename)
    if os.path.exists(path):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(-1)
        except: pass

# ==============================================================================
# CONSTANTE JOC
# ==============================================================================
NUM_CHANNELS, LEDS_PER_CHANNEL = 8, 64
FRAME_DATA_LENGTH = NUM_CHANNELS * LEDS_PER_CHANNEL * 3
MAZE_SIZE = 14
MAX_WINS = 5
STUN_DURATION = 2.0 

P1_COLOR = (0, 255, 255)       
P2_COLOR = (255, 0, 255)       
P1_TRAIL = (0, 60, 60)         
P2_TRAIL = (60, 0, 60)         
WALL_COLOR = (0, 255, 0)       
PERIMETER_COLOR = (0, 255, 0)  
WHT = (255, 255, 255)          

# ==============================================================================
# MOTOR MATRICE & LABIRINT
# ==============================================================================
class MatrixEngine:
    def __init__(self):
        self.target_ip = CONFIG.get("device_ip", "127.0.0.1")
        self.send_port = CONFIG.get("send_port", 6766)
        self.recv_port = CONFIG.get("recv_port", 6767)
        self.buffer = bytearray(FRAME_DATA_LENGTH)
        self.active_touches = set()
        self.running = True
        self.sequence_number = 0
        self.lock = threading.Lock()
        
        self.sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_send.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try: self.sock_recv.bind(("0.0.0.0", self.recv_port))
        except: pass
        
        threading.Thread(target=self._send_loop, daemon=True).start()
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def set_pixel(self, x, y, r, g, b):
        if x < 0 or x >= 16 or y < 0 or y >= 32: return
        channel, row = y // 4, y % 4
        led_index = row * 16 + x if row % 2 == 0 else row * 16 + (15 - x)
        offset = led_index * 24 + channel
        with self.lock:
            if offset + 16 < FRAME_DATA_LENGTH:
                self.buffer[offset] = g; self.buffer[offset + 8] = r; self.buffer[offset + 16] = b

    def clear(self):
        with self.lock: self.buffer = bytearray(FRAME_DATA_LENGTH)

    def get_touches(self):
        coords = []
        with self.lock:
            for ch, led_idx in self.active_touches:
                r, c = led_idx // 16, led_idx % 16
                coords.append((c if r % 2 == 0 else 15 - c, ch * 4 + r))
        return coords

    def _send_loop(self):
        while self.running:
            with self.lock: frame_data = bytes(self.buffer)
            self.sequence_number = (self.sequence_number + 1) & 0xFFFF
            if self.sequence_number == 0: self.sequence_number = 1
            
            p_start = bytearray([0x75, 0, 0, 0, 0x08, 0x02, 0, 0, 0x33, 0x44, (self.sequence_number >> 8) & 0xFF, self.sequence_number & 0xFF, 0, 0, 0, 0x0E, 0])
            self.sock_send.sendto(p_start, (self.target_ip, self.send_port))
            
            chunk_size = 984
            p_idx = 1
            for i in range(0, len(frame_data), chunk_size):
                chunk = frame_data[i:i+chunk_size]
                internal = bytearray([0x02, 0, 0, 0x88, 0x77, (p_idx >> 8) & 0xFF, p_idx & 0xFF, (len(chunk) >> 8) & 0xFF, len(chunk) & 0xFF]) + chunk
                length = len(internal) - 1
                p_data = bytearray([0x75, 0, 0, (length >> 8) & 0xFF, length & 0xFF]) + internal + bytearray([0x1E, 0])
                self.sock_send.sendto(p_data, (self.target_ip, self.send_port))
                p_idx += 1; time.sleep(0.001)
            
            p_end = bytearray([0x75, 0, 0, 0, 0x08, 0x02, 0, 0, 0x55, 0x66, (self.sequence_number >> 8) & 0xFF, self.sequence_number & 0xFF, 0, 0, 0, 0x0E, 0])
            self.sock_send.sendto(p_end, (self.target_ip, self.send_port))
            time.sleep(0.04)

    def _recv_loop(self):
        while self.running:
            try:
                data, _ = self.sock_recv.recvfrom(2048)
                if len(data) >= 1373 and data[0] == 0x88:
                    touches = set()
                    for ch in range(8):
                        base = 2 + ch * 171
                        for led in range(64):
                            if data[base + 1 + led] == 0xCC: touches.add((ch, led))
                    with self.lock: self.active_touches = touches
            except: pass
    def stop(self): self.running = False

class MazeGenerator:
    @staticmethod
    def generate():
        grid = [[1 for _ in range(14)] for _ in range(14)]
        start_y, finish_y = random.randint(1, 12), random.randint(1, 12)
        start_pos, finish_pos = (0, start_y), (13, finish_y)
        stack = [start_pos]; grid[start_y][0] = 0
        while stack:
            cx, cy = stack[-1]
            neighbors = [(nx, ny) for nx, ny in [(cx-2, cy), (cx+2, cy), (cx, cy-2), (cx, cy+2)] if 0 <= nx < 14 and 0 <= ny < 14 and grid[ny][nx] == 1]
            if neighbors:
                nx, ny = random.choice(neighbors)
                grid[ny][nx] = 0; grid[(cy + ny) // 2][(cx + nx) // 2] = 0
                stack.append((nx, ny))
            else: stack.pop()
        grid[finish_y][13] = 0; grid[finish_y][12] = 0
        mid_paths = [p for p in [(x,y) for y in range(14) for x in range(14) if grid[y][x]==0] if 4 <= p[0] <= 9]
        return grid, start_pos, finish_pos, random.choice(mid_paths) if mid_paths else (6,6)

    @staticmethod
    def generate_full_boot_maze():
        grid = [[1 for _ in range(16)] for _ in range(32)]
        stack = [(0, 0)]; grid[0][0] = 0
        while stack:
            cx, cy = stack[-1]
            nbs = [(nx, ny) for nx, ny in [(cx-2, cy), (cx+2, cy), (cx, cy-2), (cx, cy+2)] if 0 <= nx < 16 and 0 <= ny < 32 and grid[ny][nx] == 1]
            if nbs:
                nx, ny = random.choice(nbs)
                grid[ny][nx] = 0; grid[(cy+ny)//2][(cx+nx)//2] = 0
                stack.append((nx, ny))
            else: stack.pop()
        return grid

# ==============================================================================
# LOGICA JOCULUI
# ==============================================================================
class PlayerState:
    def __init__(self, offset_y):
        self.offset_x, self.offset_y = 1, offset_y
        self.score, self.lives, self.max_lives = 0, 5, 5
        self.vis_radius, self.trail_life, self.full_reveal = 1, 20.0, False
        self.is_stunned, self.stun_timer = False, 0
        self.visited, self.last_pos = {}, (0, 0)
        self.maze, self.start_pos, self.finish_pos = [], (0,0), (13,0)
        self.powerup_pos, self.powerup_active, self.reveal_timer = (6,6), True, 0
        self.is_resetting, self.reset_timer = False, 0
        self.tuto_path = []

    def set_difficulty(self, category, diff, role="CHILD"):
        self.full_reveal = False
        if category == "MIXED":
            if role == "CHILD":
                if diff == "EASY": self.max_lives, self.vis_radius, self.trail_life, self.full_reveal = 10, 2, 9999.0, True
                else: self.max_lives, self.vis_radius, self.trail_life = 5, 1, 20.0
            else:
                if diff == "EASY": self.max_lives, self.vis_radius, self.trail_life = 5, 1, 20.0
                else: self.max_lives, self.vis_radius, self.trail_life = 3, 1, 0.0
        elif category == "CHILD":
            if diff == "EASY": self.max_lives, self.vis_radius, self.trail_life = 10, 2, 9999.0
            elif diff == "MEDIUM": self.max_lives, self.vis_radius, self.trail_life = 5, 1, 20.0
            else: self.max_lives, self.vis_radius, self.trail_life = 3, 1, 10.0
        else:
            if diff == "EASY": self.max_lives, self.vis_radius, self.trail_life = 5, 2, 25.0
            elif diff == "MEDIUM": self.max_lives, self.vis_radius, self.trail_life = 3, 1, 15.0
            else: self.max_lives, self.vis_radius, self.trail_life = 1, 1, 0.0
        self.lives = self.max_lives

    def reset_round(self):
        self.lives = self.max_lives; self.is_stunned = self.is_resetting = False
        self.visited.clear(); self.powerup_active = True
        self.reveal_timer = self.reset_timer = 0

class FogRunGame:
    def __init__(self):
        self.engine = MatrixEngine()
        self.p1, self.p2 = PlayerState(1), PlayerState(17)
        self.category, self.difficulty = "ADULT", "MEDIUM"
        self.state, self.state_timer = 'WAIT_START', time.time()
        self.boot_maze = MazeGenerator.generate_full_boot_maze()
        self.ripples, self.last_touches = [], set()
        self.is_tutorial, self.last_winner = False, None
        self.running = True
        
        play_bgm("maze_sound.mp3", 0.4)
        self.generate_new_round()

    def start_game_from_ui(self, category, difficulty):
        self.difficulty = difficulty
        self.category = category
        if self.category == "MIXED":
            self.p1.set_difficulty("MIXED", self.difficulty, role="CHILD")
            self.p2.set_difficulty("MIXED", self.difficulty, role="ADULT")
        else:
            self.p1.set_difficulty(self.category, self.difficulty, role="CHILD")
            self.p2.set_difficulty(self.category, self.difficulty, role="ADULT")
        self.p1.score = self.p2.score = 0
        self.generate_new_round()
        self.state = 'TXT_JOCUL_INCEPE'
        self.state_timer = time.time()

    def generate_new_round(self):
        m, s, f, pu = MazeGenerator.generate()
        if self.category == "MIXED":
            for p in [self.p1, self.p2]: p.maze, p.start_pos, p.finish_pos, p.powerup_pos = [row[:] for row in m], s, f, pu
        else:
            for p in [self.p1, self.p2]: p.maze, p.start_pos, p.finish_pos, p.powerup_pos = MazeGenerator.generate()
        for p in [self.p1, self.p2]:
            p.last_pos = p.start_pos; p.reset_round()
            p.tuto_path = self._build_tuto_path(p.maze, p.start_pos, p.finish_pos)

    def _build_tuto_path(self, maze, start, finish):
        def bfs(s_n, e_n):
            q = [[s_n]]; vis = {s_n}
            while q:
                p = q.pop(0); curr = p[-1]
                if curr == e_n: return p
                for nx, ny in [(curr[0]-1, curr[1]), (curr[0]+1, curr[1]), (curr[0], curr[1]-1), (curr[0], curr[1]+1)]:
                    if 0 <= nx < 14 and 0 <= ny < 14 and maze[ny][nx] == 0 and (nx, ny) not in vis:
                        vis.add((nx, ny)); q.append(p + [(nx, ny)])
            return [start]
        res = bfs(start, finish); final = []; stun_injected = False
        for i, node in enumerate(res):
            final.append(node)
            if not stun_injected and i == 4:
                sx, sy = node
                for nx, ny in [(sx-1, sy), (sx+1, sy), (sx, sy-1), (sx, sy+1)]:
                    if 0 <= nx < 14 and 0 <= ny < 14 and maze[ny][nx] == 1:
                        final.append((nx, ny)); final.extend([node] * 10); stun_injected = True; break
        for _ in range(5): final.append(finish)
        return final

    def _handle_player(self, player, touches, now, opponent_name, is_tuto=False):
        if player.is_resetting:
            cleared = False
            for mx, my in touches:
                if mx == player.start_pos[0] and my == player.start_pos[1]:
                    cleared = True; player.is_resetting = False; player.last_pos = (mx, my); player.visited[(mx, my)] = now; break
            if not cleared and now - player.reset_timer > 10.0: player.is_resetting = False 
            if player.is_resetting: return 

        if player.is_stunned and now - player.stun_timer > STUN_DURATION: player.is_stunned = False
        if player.is_stunned: return 
            
        for mx, my in touches:
            if not (0 <= mx < MAZE_SIZE and 0 <= my < MAZE_SIZE): continue
            if not is_tuto:
                valid_points = list(player.visited.keys()) + [player.start_pos]
                min_dist = min(max(abs(mx - vx), abs(my - vy)) for vx, vy in valid_points)
                if min_dist > 1:
                    if mx == player.finish_pos[0] and my == player.finish_pos[1]:
                        play_sound("blue_jumps.mp3" if player == self.p1 else "red_jumps.mp3")
                        self._end_round(winner_name=opponent_name)
                        return
                    else:
                        player.maze, player.start_pos, player.finish_pos, player.powerup_pos = MazeGenerator.generate()
                        player.is_stunned = False; player.visited.clear(); player.last_pos = player.start_pos
                        player.is_resetting = True; player.reset_timer = now
                        return
                
            if player.maze[my][mx] == 1:
                player.is_stunned = True; player.stun_timer = now
                play_sound("damage_heart.mp3")
                if not is_tuto:
                    player.lives -= 1
                    if self.category == "MIXED" and self.difficulty == "HARD" and player == self.p2: self.p1.reveal_timer = now + 1.5 
                    if player.lives <= 0: self._end_round(winner_name=opponent_name)
                return 
            elif player.maze[my][mx] == 0:
                player.visited[(player.last_pos[0], player.last_pos[1])] = now; player.visited[(mx, my)] = now
                x1, y1 = player.last_pos
                if abs(mx - x1) <= 2 and abs(my - y1) <= 2:
                    mid_x, mid_y = (x1 + mx) // 2, (y1 + my) // 2
                    if player.maze[mid_y][mid_x] == 0: player.visited[(mid_x, mid_y)] = now
                player.last_pos = (mx, my)
                
            if mx == player.powerup_pos[0] and my == player.powerup_pos[1] and player.powerup_active:
                player.powerup_active = False; player.reveal_timer = now
            if mx == player.finish_pos[0] and my == player.finish_pos[1]:
                if is_tuto: 
                    if getattr(self, 'tuto_won', False) == False: 
                        self.tuto_won = True; self.last_winner = player
                        self.state = 'WIN_REVEAL'; self.state_timer = now
                else: 
                    self._end_round(winner_name="P1" if player == self.p1 else "P2")

    def _end_round(self, winner_name):
        if winner_name == "P1": self.p1.score += 1; self.last_winner = self.p1
        else: self.p2.score += 1; self.last_winner = self.p2
        play_sound("win.mp3")
        self.state = 'WIN_REVEAL'; self.state_timer = time.time()

    def _draw_word_wide(self, word, color, center_y_shift=0):
        total_width = 0
        for char in word.upper():
            if char == ' ': total_width += 4
            elif small_font and hasattr(small_font, 'FONT_3x5') and char in small_font.FONT_3x5: total_width += len(small_font.FONT_3x5[char]) + 1
            else: total_width += 4
        total_width -= 1 

        start_y = (32 - total_width) // 2
        start_x_base = 5 + center_y_shift 
        curr_y = start_y
        
        for char in word.upper():
            if char == ' ':
                curr_y += 4
                continue
            if small_font and hasattr(small_font, 'FONT_3x5') and char in small_font.FONT_3x5:
                char_data = small_font.FONT_3x5[char]
                for c, col_data in enumerate(char_data):
                    for r in range(5):
                        if (col_data >> r) & 1:
                            phys_x = 15 - (start_x_base + r); phys_y = curr_y + c
                            if 0 <= phys_x < 16 and 0 <= phys_y < 32: self.engine.set_pixel(phys_x, phys_y, *color)
                curr_y += len(char_data) + 1 
            else: curr_y += 4

    def _draw_thin_large_text(self, text, center_y, color):
        total_width = 0
        for char in text.upper():
            if char == ' ': total_width += 5
            elif small_font and hasattr(small_font, 'FONT_4x7') and char in small_font.FONT_4x7: total_width += len(small_font.FONT_4x7[char]) + 1
            else: total_width += 5
        total_width -= 1
        
        start_y = center_y - total_width // 2
        start_x_base = 4 
        curr_y = start_y
        
        for char in text.upper():
            if char == ' ':
                curr_y += 5
                continue
            if small_font and hasattr(small_font, 'FONT_4x7') and char in small_font.FONT_4x7:
                char_data = small_font.FONT_4x7[char]
                for c, col_data in enumerate(char_data):
                    for r in range(7):
                        if (col_data >> r) & 1:
                            phys_x = 15 - (start_x_base + r); phys_y = curr_y + c
                            if 0 <= phys_x < 16 and 0 <= phys_y < 32: self.engine.set_pixel(phys_x, phys_y, *color)
                curr_y += len(char_data) + 1
            else: curr_y += 5

    def _draw_perimeters(self):
        for x in range(16): self.engine.set_pixel(x, 15, *PERIMETER_COLOR); self.engine.set_pixel(x, 16, *PERIMETER_COLOR)
        for y in range(32): self.engine.set_pixel(0, y, *PERIMETER_COLOR); self.engine.set_pixel(15, y, *PERIMETER_COLOR)
        for x in range(16): self.engine.set_pixel(x, 0, *PERIMETER_COLOR); self.engine.set_pixel(x, 31, *PERIMETER_COLOR)

    def _draw_heart_centered(self, cx, cy, color):
        pixels = [(2,-2),(2,-1),(2,2),(2,3),(1,-3),(1,-2),(1,-1),(1,0),(1,1),(1,2),(1,3),(1,4),
                  (0,-3),(0,-2),(0,-1),(0,0),(0,1),(0,2),(0,3),(0,4),(-1,-2),(-1,-1),(-1,0),(-1,1),(-1,2),(-1,3),
                  (-2,-1),(-2,0),(-2,1),(-2,2),(-3,0),(-3,1)]
        for dx, dy in pixels: self.engine.set_pixel(cx + dx, cy + dy, *color)

    def _render_start_zone(self, player):
        ox, oy = player.offset_x, player.offset_y
        sx, sy = player.start_pos
        for my in range(sy - 1, sy + 2):
            for mx in range(sx - 1, sx + 2):
                if mx < 0 or mx >= 14 or my < 0 or my >= 14: pass
                elif player.maze[my][mx] == 1: self.engine.set_pixel(ox + mx, oy + my, *WALL_COLOR)
                else: self.engine.set_pixel(ox + mx, oy + my, *(P1_TRAIL if player == self.p1 else P2_TRAIL))
        pulse = int(100 + 80 * ((math.sin(time.time() * 3) + 1) / 2)) 
        self.engine.set_pixel(ox + sx, oy + sy, pulse, pulse, 0)

    def _render_maze(self, player, override_full=False, tuto_tchs=None):
        ox, oy = player.offset_x, player.offset_y
        now = time.time()
        
        if player.is_resetting:
            for i in range(14):
                for j in range(14): self.engine.set_pixel(ox+i, oy+j, 0,0,0)
            self._render_start_zone(player)
            return

        if player.is_stunned:
            t_stun = now - player.stun_timer
            for i in range(14):
                for j in range(14): self.engine.set_pixel(ox+i, oy+j, 0,0,0)
            heart_cx, heart_cy = 8, oy + 6 
            if t_stun < 2.0: blink = int((math.sin(t_stun * 10) + 1) / 2 * 200); self._draw_heart_centered(heart_cx, heart_cy, (blink, 0, 0))
            else: fade = max(0, 200 - int(((t_stun - 2.0) / 1.5) * 200)); self._draw_heart_centered(heart_cx, heart_cy, (fade, 0, 0))
            return

        if now - player.reveal_timer < 3.0: override_full = True
        tchs = tuto_tchs if tuto_tchs else ([(x-ox, y-oy) for x, y in self.engine.get_touches() if ox <= x < ox + 14 and oy <= y < oy + 14] or [player.last_pos])

        for my in range(14):
            for mx in range(14):
                is_visible = override_full 
                if not is_visible:
                    for px, py in tchs:
                        if abs(mx - px) <= player.vis_radius and abs(my - py) <= player.vis_radius: is_visible = True; break

                is_finish = (mx == player.finish_pos[0] and my == player.finish_pos[1])
                is_powerup = (mx == player.powerup_pos[0] and my == player.powerup_pos[1] and player.powerup_active)
                is_wall = (player.maze[my][mx] == 1)
                
                if is_visible or is_finish:
                    if is_finish: p_val = int(100 + 80 * math.sin(now * 3)); self.engine.set_pixel(ox + mx, oy + my, p_val, p_val, 0) 
                    elif is_powerup: p_val = int(80 + 100 * ((math.sin(now * 6) + 1) / 2)); self.engine.set_pixel(ox + mx, oy + my, 0, p_val, p_val) 
                    elif is_wall: self.engine.set_pixel(ox + mx, oy + my, *WALL_COLOR)
                    else: self.engine.set_pixel(ox + mx, oy + my, *(P1_COLOR if player == self.p1 else P2_COLOR))
                elif player.full_reveal and is_wall: self.engine.set_pixel(ox + mx, oy + my, 0, 30, 0)
                elif (mx, my) in player.visited:
                    age = now - player.visited[(mx, my)]
                    if age < player.trail_life:
                        intensity = 1.0 if player.trail_life > 1000 else max(0, 1.0 - (age / player.trail_life))
                        tr_c = P1_TRAIL if player == self.p1 else P2_TRAIL
                        dim_c = (int(tr_c[0]*intensity), int(tr_c[1]*intensity), int(tr_c[2]*intensity))
                        self.engine.set_pixel(ox + mx, oy + my, *dim_c)
                    else: del player.visited[(mx, my)] 

    def tick(self):
        self.engine.clear()
        touches = self.engine.get_touches()
        now = time.time()
        time_in_state = now - self.state_timer
        WORD_DUR = 1.2 
        
        if self.state == 'INTERACTIVE_BREAK':
            curr_set = set(touches)
            new_touches = curr_set - self.last_touches
            for x, y in new_touches: self.ripples.append((x, y, P1_COLOR if y < 16 else P2_COLOR, now))
            self.last_touches = curr_set
            self.ripples = [r for r in self.ripples if now - r[3] < 2.0]
        elif self.state == 'PLAYING':
            p1_touches = [(x - 1, y - 1) for x, y in touches if 1 <= x <= 14 and 1 <= y <= 14]
            p2_touches = [(x - 1, y - 17) for x, y in touches if 1 <= x <= 14 and 17 <= y <= 30]
            self._handle_player(self.p1, p1_touches, now, "P2", False)
            if self.state == 'PLAYING': self._handle_player(self.p2, p2_touches, now, "P1", False)

        if self.state == 'WAIT_START':
            p = int(40 + 40 * math.sin(now * 3))
            self._draw_word_wide("ALEGE", (0, p, 0), -4)
            self._draw_word_wide("JOCUL", (0, p, 0), 4)

        elif self.state == 'TXT_JOCUL_INCEPE':
            progres = max(0.0, 1.0 - (time_in_state / 5.0))
            culoare_text = (0, int(255 * progres), 0)
            self._draw_word_wide("INCEPE", culoare_text, -4)
            self._draw_word_wide("JOCUL", culoare_text, 4)
            if time_in_state > 5.0: self.state = 'BOOT_ANIM'; self.state_timer = now

        elif self.state == 'BOOT_ANIM':
            max_dist = time_in_state * 5.0 
            for y in range(32):
                for x in range(16):
                    if (x + y) < max_dist and self.boot_maze[y][x] == 1: self.engine.set_pixel(x, y, 0, 100, 0)
            if time_in_state > 10.0: self.state = 'TXT_CUM'; self.state_timer = now

        elif self.state == 'TXT_CUM':
            self._draw_word_wide("CUM", WHT)
            self.is_tutorial = True
            if time_in_state > 1.0: self.state = 'TXT_SE'; self.state_timer = now
        elif self.state == 'TXT_SE':
            self._draw_word_wide("SE", WHT)
            if time_in_state > 1.0: self.state = 'TXT_JOACA'; self.state_timer = now
        elif self.state == 'TXT_JOACA':
            self._draw_word_wide("JOACA", WHT)
            if time_in_state > 1.0: self.state = 'PAUZA_MEA_1'; self.state_timer = now

        elif self.state == 'PAUZA_MEA_1':
            if time_in_state > 1.0: self.state = 'TUTO_PLAY'; self.state_timer = now

        elif self.state == 'TUTO_PLAY':
            t_s = now - self.state_timer
            idx1 = min(int(t_s / 0.4), len(self.p1.tuto_path) - 1)
            idx2 = min(int(t_s / 0.4), len(self.p2.tuto_path) - 1)
            self._handle_player(self.p1, [self.p1.tuto_path[idx1]], now, "P2", True)
            if self.state == 'TUTO_PLAY': self._handle_player(self.p2, [self.p2.tuto_path[idx2]], now, "P1", True)
            self._render_maze(self.p1, False, [self.p1.tuto_path[idx1]])
            self._render_maze(self.p2, False, [self.p2.tuto_path[idx2]])
            if t_s > max(len(self.p1.tuto_path), len(self.p2.tuto_path)) * 0.4 + 1.0: 
                self.is_tutorial = False; self.state = 'TXT_ACUM'; self.state_timer = now

        elif self.state == 'TXT_ACUM':
            self._draw_word_wide("ACUM", WHT) 
            if time_in_state > WORD_DUR: self.state = 'TXT_ALEGE'; self.state_timer = now
        elif self.state == 'TXT_ALEGE':
            self._draw_word_wide("ALEGE O", WHT) 
            if time_in_state > WORD_DUR: self.state = 'TXT_CULOARE'; self.state_timer = now
        elif self.state == 'TXT_CULOARE':
            self._draw_word_wide("CULOARE", WHT) 
            if time_in_state > WORD_DUR: self.generate_new_round(); self.state = 'PICK_FULL'; self.state_timer = now
                
        elif self.state == 'PICK_FULL':
            pulse = (math.sin(time_in_state * (0.5 + (time_in_state / 5.0) * 1.5) * math.pi * 2) + 1) / 2
            c1 = [int(x * (0.2 + 0.4 * pulse)) for x in P1_COLOR]; c2 = [int(x * (0.2 + 0.4 * pulse)) for x in P2_COLOR]
            for i in range(14):
                for j in range(14): self.engine.set_pixel(self.p1.offset_x+i, self.p1.offset_y+j, *c1); self.engine.set_pixel(self.p2.offset_x+i, self.p2.offset_y+j, *c2)
            if time_in_state > 3.0: self.state = 'PICK_SHRINK'; self.state_timer = now

        elif self.state == 'PICK_SHRINK':
            max_dist = 20 * (1.0 - (time_in_state / 2.0)) 
            for p, c in [(self.p1, P1_COLOR), (self.p2, P2_COLOR)]:
                cx, cy = p.offset_x + p.start_pos[0], p.offset_y + p.start_pos[1]
                for my in range(14):
                    for mx in range(14):
                        px, py = p.offset_x + mx, p.offset_y + my
                        if (abs(mx - p.start_pos[0]) <= 1 and abs(my - p.start_pos[1]) <= 1) or math.hypot(px - cx, py - cy) < max_dist:
                            self.engine.set_pixel(px, py, c[0]//3, c[1]//3, c[2]//3)
            if time_in_state > 2.0: self.state = 'GO_TO_START'; self.state_timer = now
            
        elif self.state == 'GO_TO_START':
            pulse = (math.sin(time_in_state * (0.5 + (time_in_state / 5.0) * 1.5) * math.pi * 2) + 1) / 2
            c1 = [int(x * (0.3 + 0.5 * pulse)) for x in P1_COLOR]; c2 = [int(x * (0.3 + 0.5 * pulse)) for x in P2_COLOR]
            for p, c in [(self.p1, c1), (self.p2, c2)]:
                ox, oy, sx, sy = p.offset_x, p.offset_y, p.start_pos[0], p.start_pos[1]
                for my in range(sy - 1, sy + 2):
                    for mx in range(sx - 1, sx + 2):
                        if 0 <= mx < 14 and 0 <= my < 14: self.engine.set_pixel(ox + mx, oy + my, *c)
            if time_in_state > 3.0: self.state = 'PRE_COUNT'; self.state_timer = now
            
        elif self.state == 'PRE_COUNT':
            self._render_start_zone(self.p1); self._render_start_zone(self.p2)
            if time_in_state > 1.0: play_sound("counter.mp3"); self.state = 'COUNT_3'; self.state_timer = now

        elif self.state.startswith('COUNT_') or self.state == 'PLAYING':
            if self.state.startswith('COUNT_'):
                val = self.state.split('_')[1]
                self._render_start_zone(self.p1); self._render_start_zone(self.p2)
                self._draw_thin_large_text(val, 8, P1_COLOR); self._draw_thin_large_text(val, 24, P2_COLOR)
                if time_in_state > 1.0:
                    if val == '0': self.state = 'PLAYING'; self.state_timer = now
                    else: self.state = f'COUNT_{int(val)-1}'; self.state_timer = now
            else:
                self._render_maze(self.p1, False); self._render_maze(self.p2, False)

        elif self.state == 'WIN_REVEAL':
            self._render_maze(self.p1, True); self._render_maze(self.p2, True)
            if time_in_state > 2.5: self.state = 'ROUND_WAVE'; self.state_timer = now

        elif self.state == 'ROUND_WAVE':
            win_color = P1_COLOR if self.last_winner == self.p1 else P2_COLOR
            winner = self.last_winner if self.last_winner else self.p1
            for my in range(14):
                for mx in range(14):
                    if mx == self.p1.finish_pos[0] and my == self.p1.finish_pos[1]: self.engine.set_pixel(self.p1.offset_x+mx, self.p1.offset_y+my, 255,255,0)
                    elif self.p1.maze[my][mx] == 1: self.engine.set_pixel(self.p1.offset_x+mx, self.p1.offset_y+my, *WALL_COLOR)
                    elif (mx,my) in self.p1.visited: self.engine.set_pixel(self.p1.offset_x+mx, self.p1.offset_y+my, *P1_TRAIL)
                    if mx == self.p2.finish_pos[0] and my == self.p2.finish_pos[1]: self.engine.set_pixel(self.p2.offset_x+mx, self.p2.offset_y+my, 255,255,0)
                    elif self.p2.maze[my][mx] == 1: self.engine.set_pixel(self.p2.offset_x+mx, self.p2.offset_y+my, *WALL_COLOR)
                    elif (mx,my) in self.p2.visited: self.engine.set_pixel(self.p2.offset_x+mx, self.p2.offset_y+my, *P2_TRAIL)
            
            cx, cy = winner.offset_x + winner.finish_pos[0], winner.offset_y + winner.finish_pos[1]
            for y in range(32):
                for x in range(16):
                    dist = math.hypot(x-cx, y-cy)
                    if dist < time_in_state * 20:
                        p = (math.sin(dist * 0.4 - time_in_state * 6) + 1) / 2
                        self.engine.set_pixel(x, y, *[int(c*(0.1+0.5*p)) for c in win_color])
                            
            if time_in_state > 3.0: 
                if self.is_tutorial:
                    self.is_tutorial = False; self.p1.score = self.p2.score = 0 
                    if hasattr(self, 'tuto_won'): del self.tuto_won
                    self.state = 'TXT_ACUM'; self.state_timer = now
                else:
                    self.state = 'TXT_WIN_1'; self.state_timer = now
                
        elif self.state == 'TXT_WIN_1':
            self._draw_word_wide("CYAN" if self.last_winner == self.p1 else "PINK", P1_COLOR if self.last_winner == self.p1 else P2_COLOR)
            if time_in_state > WORD_DUR: self.state = 'TXT_WIN_2'; self.state_timer = now
            
        elif self.state == 'TXT_WIN_2':
            self._draw_word_wide("WON", P1_COLOR if self.last_winner == self.p1 else P2_COLOR)
            if time_in_state > WORD_DUR: self.state = 'SHOW_SCORE_ONLY'; self.state_timer = now
                
        elif self.state == 'SHOW_SCORE_ONLY':
            self._draw_thin_large_text(str(self.p1.score), 10, P1_COLOR)
            self._draw_thin_large_text("-", 16, WHT)
            self._draw_thin_large_text(str(self.p2.score), 22, P2_COLOR)
            if time_in_state > 2.0:  
                self.state = 'INTERACTIVE_BREAK'; self.state_timer = now; self.ripples.clear(); self.last_touches = set(self.engine.get_touches())
                
        elif self.state == 'INTERACTIVE_BREAK':
            win_color = P1_COLOR if self.last_winner == self.p1 else P2_COLOR
            dim_win = (win_color[0]//8, win_color[1]//8, win_color[2]//8) 
            for y in range(32):
                for x in range(16): self.engine.set_pixel(x, y, *dim_win)
            for rx, ry, rc, rstart in self.ripples:
                rage = now - rstart
                if rage > 3.0: continue
                fade = max(0, 1.0 - (rage / 3.0))
                col = (int(rc[0]*fade*0.7), int(rc[1]*fade*0.7), int(rc[2]*fade*0.7))
                for y in range(32):
                    for x in range(16):
                        if abs(math.hypot(x-rx, y-ry) - rage*10.0) < 1.0: self.engine.set_pixel(x, y, *col)

            if time_in_state > 5.0:
                if self.p1.score >= MAX_WINS or self.p2.score >= MAX_WINS: self.state = 'GAME_OVER'; self.state_timer = now
                else: self.generate_new_round(); self.state = 'CLEAR_SCREEN_05'; self.state_timer = now

        elif self.state == 'CLEAR_SCREEN_05':
            if time_in_state > 0.5: self.state = 'PRE_COUNT'; self.state_timer = now

        elif self.state == 'GAME_OVER':
            win_color = P1_COLOR if self.p1.score > self.p2.score else P2_COLOR
            breath = int(50 + 80 * ((math.sin(now * 1.5) + 1) / 2)) 
            for y in range(32):
                for x in range(16): self.engine.set_pixel(x, y, int(win_color[0]*breath/255), int(win_color[1]*breath/255), int(win_color[2]*breath/255))
            for _ in range(5): self.engine.set_pixel(random.randint(1,14), random.randint(1,30), 255, 255, 255)
            self._draw_word_wide("CYAN" if self.p1.score > self.p2.score else "PINK", WHT, -4)
            self._draw_word_wide("WON!", WHT, 4)
            if time_in_state > 8.0: self.state = 'WAIT_START'; self.state_timer = now

        if self.state in ['TUTO_PLAY', 'PICK_FULL', 'PICK_SHRINK', 'GO_TO_START', 'PLAYING', 'WIN_REVEAL'] or self.state.startswith('COUNT_') or self.state == 'PRE_COUNT':
            self._draw_perimeters()

# ==============================================================================
# MAIN LOOP LOGIC
# ==============================================================================
if __name__ == "__main__":
    game = FogRunGame()
    
    def game_thread():
        while game.running:
            game.tick()
            time.sleep(0.03)
            
    threading.Thread(target=game_thread, daemon=True).start()
    
    print("\n=============================================")
    print("🚀 LABIRINT E-SPORTS (CORE ACTIVE) 🚀")
    print("=============================================\n")
    
    try:
        import labyrinth_screens
        labyrinth_screens.launch(game)
    except ImportError:
        print("[!] Eroare: Fisierul labyrinth_screens.py lipseste! Nu se poate afisa UI-ul.")
        while game.running:
            time.sleep(1)