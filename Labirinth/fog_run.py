import socket
import threading
import time
import random
import json
import os
import math
import pygame

# ==============================================================================
# CONFIGURARE ȘI NETWORKING
# ==============================================================================

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
    except Exception:
        pass
    return defaults

CONFIG = _load_config()

# Constante Matrice
NUM_CHANNELS = 8
LEDS_PER_CHANNEL = 64
FRAME_DATA_LENGTH = NUM_CHANNELS * LEDS_PER_CHANNEL * 3

# Socket pentru Dashboard
SB_IP = "127.0.0.1"
SB_PORT = 5005
sb_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# ==============================================================================
# CULORI (TURCOAZ VS MAGENTA)
# ==============================================================================

P1_COLOR = (0, 255, 255)       # TURCOAZ (Cyan Electric)
P2_COLOR = (255, 0, 255)       # MAGENTA (Roz-Mov Neon)
P1_TRAIL = (0, 60, 60)         # Urmă Turcoaz Întunecat
P2_TRAIL = (60, 0, 60)         # Urmă Magenta Întunecat
WALL_COLOR = (0, 255, 0)       # Ziduri Verzi
PERIMETER_COLOR = (0, 255, 0)  # Margini Verzi
STUN_COLOR = (255, 0, 0)       # Alertă Roșie
FINISH_COLOR = (255, 255, 0)   # Galben Victorie
WHT = (255, 255, 255)          # Text Alb

# Setări Globale
MAZE_SIZE = 14
MAX_WINS = 5
STUN_DURATION = 2.0 

# ==============================================================================
# FONTURI COMPLETE (Pentru evitarea crash-urilor vizuale)
# ==============================================================================

FONT_3x5 = {
    ' ': [0, 0, 0],
    '0': [31, 17, 31],
    '1': [0, 31, 0],
    '2': [29, 21, 23],
    '3': [21, 21, 31],
    '4': [7, 4, 31],
    '5': [23, 21, 29],
    '6': [31, 21, 29],
    '7': [1, 1, 31],
    '8': [31, 21, 31],
    '9': [23, 21, 31],
    'A': [31, 5, 31],
    'B': [31, 21, 10],
    'C': [31, 17, 17],
    'D': [31, 17, 14],
    'E': [31, 21, 21],
    'F': [31, 5, 1],
    'G': [31, 17, 25],
    'H': [31, 4, 31],
    'I': [17, 31, 17],
    'J': [24, 16, 31],
    'K': [31, 4, 27],
    'L': [31, 16, 16],
    'M': [31, 6, 31],
    'N': [31, 1, 31],
    'O': [31, 17, 31],
    'P': [31, 5, 7],
    'Q': [14, 17, 30],
    'R': [31, 5, 27],
    'S': [18, 21, 9],
    'T': [1, 31, 1],
    'U': [31, 16, 31],
    'V': [7, 24, 7],
    'W': [31, 8, 31],
    'X': [27, 4, 27],
    'Y': [3, 28, 3],
    'Z': [25, 21, 19],
    '!': [0, 29, 0],
    '?': [1, 21, 7],
    '.': [0, 16, 0],
    '-': [4, 4, 4],
    ':': [0, 10, 0]
}

FONT_4x7 = {
    '0': [62, 65, 65, 62],
    '1': [0, 66, 127, 64],
    '2': [98, 81, 73, 70],
    '3': [34, 73, 73, 54],
    '4': [24, 20, 18, 127],
    '5': [39, 69, 69, 57],
    '6': [62, 73, 73, 50],
    '7': [1, 1, 121, 7],
    '8': [54, 73, 73, 54],
    '9': [38, 73, 73, 62],
    'G': [62, 65, 73, 58],
    'O': [62, 65, 65, 62],
    '-': [8, 8, 8, 8],
    '!': [0, 95, 0, 0]
}

# ==============================================================================
# MOTORUL DE COMUNICARE (UDP)
# ==============================================================================

class MatrixEngine:
    def __init__(self):
        self.target_ip = CONFIG.get("device_ip", "127.0.0.1")
        self.send_port = CONFIG.get("send_port", 6766)
        self.recv_port = CONFIG.get("recv_port", 6767)
        self.buffer = bytearray(FRAME_DATA_LENGTH)
        self.active_touches = set()
        self.command_queue = [] 
        self.running = True
        self.sequence_number = 0
        self.lock = threading.Lock()
        
        self.sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_send.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_recv.bind(("0.0.0.0", self.recv_port))
        
        threading.Thread(target=self._send_loop, daemon=True).start()
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def set_pixel(self, x, y, r, g, b):
        if x < 0 or x >= 16 or y < 0 or y >= 32: return
        channel = y // 4
        row = y % 4
        led_index = row * 16 + x if row % 2 == 0 else row * 16 + (15 - x)
        offset = led_index * 24 + channel
        with self.lock:
            if offset + 16 < FRAME_DATA_LENGTH:
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
                r, c = led_idx // 16, led_idx % 16
                coords.append((c if r % 2 == 0 else 15 - c, ch * 4 + r))
        return coords

    def get_commands(self):
        with self.lock:
            cmds = list(self.command_queue)
            self.command_queue.clear()
            return cmds

    def _send_loop(self):
        while self.running:
            with self.lock: frame_data = bytes(self.buffer)
            self.sequence_number = (self.sequence_number + 1) & 0xFFFF
            if self.sequence_number == 0: self.sequence_number = 1
            
            p_start = bytearray([0x75, 0x00, 0x00, 0x00, 0x08, 0x02, 0x00, 0x00, 0x33, 0x44, (self.sequence_number >> 8) & 0xFF, self.sequence_number & 0xFF, 0x00, 0x00, 0x00, 0x0E, 0x00])
            self.sock_send.sendto(p_start, (self.target_ip, self.send_port))
            
            chunk_size = 984
            p_idx = 1
            for i in range(0, len(frame_data), chunk_size):
                chunk = frame_data[i:i+chunk_size]
                internal = bytearray([0x02, 0x00, 0x00, 0x88, 0x77, (p_idx >> 8) & 0xFF, p_idx & 0xFF, (len(chunk) >> 8) & 0xFF, len(chunk) & 0xFF]) + chunk
                length = len(internal) - 1
                p_data = bytearray([0x75, 0x00, 0x00, (length >> 8) & 0xFF, length & 0xFF]) + internal + bytearray([0x1E, 0x00])
                self.sock_send.sendto(p_data, (self.target_ip, self.send_port))
                p_idx += 1
                time.sleep(0.001)
            
            p_end = bytearray([0x75, 0x00, 0x00, 0x00, 0x08, 0x02, 0x00, 0x00, 0x55, 0x66, (self.sequence_number >> 8) & 0xFF, self.sequence_number & 0xFF, 0x00, 0x00, 0x00, 0x0E, 0x00])
            self.sock_send.sendto(p_end, (self.target_ip, self.send_port))
            time.sleep(0.04)

    def _recv_loop(self):
        while self.running:
            try:
                data, _ = self.sock_recv.recvfrom(2048)
                if data.startswith(b'{'):
                    try:
                        cmd = json.loads(data.decode('utf-8'))
                        with self.lock: self.command_queue.append(cmd)
                    except: pass
                elif len(data) >= 1373 and data[0] == 0x88:
                    touches = set()
                    for ch in range(8):
                        base = 2 + ch * 171
                        for led in range(64):
                            if data[base + 1 + led] == 0xCC: touches.add((ch, led))
                    with self.lock: self.active_touches = touches
            except: pass

    def stop(self): self.running = False

# ==============================================================================
# ALGORITMUL DE GENERARE LABIRINT
# ==============================================================================

class MazeGenerator:
    @staticmethod
    def generate():
        grid = [[1 for _ in range(14)] for _ in range(14)]
        start_y, finish_y = random.randint(1, 12), random.randint(1, 12)
        start_pos, finish_pos = (0, start_y), (13, finish_y)
        
        stack = [start_pos]
        grid[start_y][0] = 0
        
        while stack:
            cx, cy = stack[-1]
            neighbors = []
            for nx, ny in [(cx-2, cy), (cx+2, cy), (cx, cy-2), (cx, cy+2)]:
                if 0 <= nx < 14 and 0 <= ny < 14 and grid[ny][nx] == 1:
                    neighbors.append((nx, ny))
            
            if neighbors:
                nx, ny = random.choice(neighbors)
                grid[ny][nx] = 0
                grid[(cy + ny) // 2][(cx + nx) // 2] = 0
                stack.append((nx, ny))
            else:
                stack.pop()
        
        grid[finish_y][13] = 0
        grid[finish_y][12] = 0
        
        paths = [(x, y) for y in range(14) for x in range(14) if grid[y][x] == 0]
        mid_paths = [p for p in paths if 4 <= p[0] <= 9]
        powerup_pos = random.choice(mid_paths) if mid_paths else (6,6)
        
        return grid, start_pos, finish_pos, powerup_pos

    @staticmethod
    def generate_full_boot_maze():
        w, h = 16, 32
        grid = [[1 for _ in range(w)] for _ in range(h)]
        stack = [(0, 0)]; grid[0][0] = 0
        while stack:
            cx, cy = stack[-1]
            nbs = []
            for nx, ny in [(cx-2, cy), (cx+2, cy), (cx, cy-2), (cx, cy+2)]:
                if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] == 1: nbs.append((nx, ny))
            if nbs:
                nx, ny = random.choice(nbs)
                grid[ny][nx] = 0
                grid[(cy+ny)//2][(cx+nx)//2] = 0
                stack.append((nx, ny))
            else: stack.pop()
        return grid

# ==============================================================================
# LOGICĂ DE DIFICULTĂȚI ȘI STĂRI JUCĂTOR
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

        pygame.mixer.pre_init(44100, -16, 2, 2048)
        pygame.mixer.init()
        
        # PORNIM MUZICA DE FUNDAL
        bgm_path = os.path.join("sounds", "maze_sound.mp3") # asigura-te ca asa se numeste fisierul
        if os.path.exists(bgm_path):
            pygame.mixer.music.load(bgm_path)
            pygame.mixer.music.set_volume(0.4) # O punem la 40% ca să se audă SFX-urile peste ea
            pygame.mixer.music.play(-1)

    def set_difficulty(self, category, diff, role="CHILD"):
        self.full_reveal = False
        
        if category == "MIXED":
            if role == "CHILD":
                if diff == "EASY":
                    self.max_lives, self.vis_radius, self.trail_life, self.full_reveal = 10, 2, 9999.0, True
                else: 
                    self.max_lives, self.vis_radius, self.trail_life = 5, 1, 20.0
            else: # ADULT / Părinte
                if diff == "EASY":
                    self.max_lives, self.vis_radius, self.trail_life = 5, 1, 20.0
                else: 
                    self.max_lives, self.vis_radius, self.trail_life = 3, 1, 0.0
        elif category == "CHILD":
            if diff == "EASY": self.max_lives, self.vis_radius, self.trail_life = 10, 2, 9999.0
            elif diff == "MEDIUM": self.max_lives, self.vis_radius, self.trail_life = 5, 1, 20.0
            else: self.max_lives, self.vis_radius, self.trail_life = 3, 1, 10.0
        else: # ADULT
            if diff == "EASY": self.max_lives, self.vis_radius, self.trail_life = 5, 2, 25.0
            elif diff == "MEDIUM": self.max_lives, self.vis_radius, self.trail_life = 3, 1, 15.0
            else: self.max_lives, self.vis_radius, self.trail_life = 1, 1, 0.0

        self.lives = self.max_lives

    def reset_round(self):
        self.lives = self.max_lives
        self.is_stunned = self.is_resetting = False
        self.visited.clear()
        self.powerup_active = True
        self.reveal_timer = self.reset_timer = 0

# ==============================================================================
# LOGICA PRINCIPALĂ A JOCULUI
# ==============================================================================

class FogRunGame:
    def __init__(self):
        self.engine = MatrixEngine()
        self.p1, self.p2 = PlayerState(1), PlayerState(17)
        self.category, self.difficulty = "ADULT", "MEDIUM"
        self.state, self.state_timer = 'WAIT_START', time.time()
        self.boot_maze = MazeGenerator.generate_full_boot_maze()
        self.ripples, self.last_touches = [], set()
        self.is_tutorial, self.last_winner = False, None
        
        self.pending_event = None
        self.generate_new_round()

    def _transition(self, new_state, now):
        self.state, self.state_timer = new_state, now

    def process_commands(self):
        cmds = self.engine.get_commands()
        now = time.time()
        for cmd in cmds:
            if cmd.get("cmd") == "START_GAME":
                self.difficulty = cmd.get("difficulty", "MEDIUM")
                self.category = cmd.get("category", "ADULT")
                
                if self.category == "MIXED":
                    self.p1.set_difficulty("MIXED", self.difficulty, role="CHILD")
                    self.p2.set_difficulty("MIXED", self.difficulty, role="ADULT")
                else:
                    self.p1.set_difficulty(self.category, self.difficulty, role="CHILD")
                    self.p2.set_difficulty(self.category, self.difficulty, role="ADULT")
                
                self.p1.score = self.p2.score = 0
                self.generate_new_round()
                
                # TIMER INIȚIAL 5 SECUNDE 
                self._transition('TXT_JOCUL_INCEPE', now)
        
    def generate_new_round(self):
        m, s, f, pu = MazeGenerator.generate()
        if self.category == "MIXED":
            for p in [self.p1, self.p2]:
                p.maze, p.start_pos, p.finish_pos, p.powerup_pos = [row[:] for row in m], s, f, pu
        else:
            for p in [self.p1, self.p2]:
                m2, s2, f2, pu2 = MazeGenerator.generate()
                p.maze, p.start_pos, p.finish_pos, p.powerup_pos = m2, s2, f2, pu2
                
        for p in [self.p1, self.p2]:
            p.last_pos = p.start_pos
            p.reset_round()
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
            
        res = bfs(start, finish)
        final = []
        stun_injected = False
        for i, node in enumerate(res):
            final.append(node)
            if not stun_injected and i == 4:
                sx, sy = node
                for nx, ny in [(sx-1, sy), (sx+1, sy), (sx, sy-1), (sx, sy+1)]:
                    if 0 <= nx < MAZE_SIZE and 0 <= ny < MAZE_SIZE and maze[ny][nx] == 1:
                        final.append((nx, ny))
                        final.extend([node] * 10) 
                        stun_injected = True
                        break
        for _ in range(5): final.append(finish)
        return final

    def update_dashboard(self):
        data = {
            "p1_score": self.p1.score, "p1_lives": self.p1.lives,
            "p1_status": "STUNNED" if self.p1.is_stunned else ("RESETTING" if self.p1.is_resetting else "ACTIVE"),
            "p2_score": self.p2.score, "p2_lives": self.p2.lives,
            "p2_status": "STUNNED" if self.p2.is_stunned else ("RESETTING" if self.p2.is_resetting else "ACTIVE"),
            "difficulty": self.difficulty
        }
        
        if self.pending_event:
            data["event"] = self.pending_event
            self.pending_event = None
            
        try: sb_sock.sendto(json.dumps(data).encode(), (SB_IP, SB_PORT))
        except: pass

    def process_inputs(self):
        touches = self.engine.get_touches()
        now = time.time()
        
        # RIPPLES PENTRU PAUZE INTERACTIVE
        if self.state == 'INTERACTIVE_BREAK':
            curr_set = set(touches)
            new_touches = curr_set - self.last_touches
            for x, y in new_touches:
                c = P1_COLOR if y < 16 else P2_COLOR
                self.ripples.append((x, y, c, now))
            self.last_touches = curr_set
            self.ripples = [r for r in self.ripples if now - r[3] < 2.0]
            return

        if self.state == 'TUTO_PLAY':
            t_s = now - self.state_timer
            idx1 = min(int(t_s / 0.4), len(self.p1.tuto_path) - 1)
            idx2 = min(int(t_s / 0.4), len(self.p2.tuto_path) - 1)
            
            self._handle_player(self.p1, [self.p1.tuto_path[idx1]], now, "P2", is_tuto=True)
            if self.state != 'TUTO_PLAY': return 
            self._handle_player(self.p2, [self.p2.tuto_path[idx2]], now, "P1", is_tuto=True)
            return

        if self.state != 'PLAYING': return

        p1_touches = [(x - 1, y - 1) for x, y in touches if 1 <= x <= 14 and 1 <= y <= 14]
        p2_touches = [(x - 1, y - 17) for x, y in touches if 1 <= x <= 14 and 17 <= y <= 30]
                
        self._handle_player(self.p1, p1_touches, now, "P2", is_tuto=False)
        if self.state != 'PLAYING': return 
        self._handle_player(self.p2, p2_touches, now, "P1", is_tuto=False)

    def _handle_player(self, player, touches, now, opponent_name, is_tuto=False):
        if player.is_resetting:
            cleared = False
            for mx, my in touches:
                if mx == player.start_pos[0] and my == player.start_pos[1]:
                    cleared = True
                    player.is_resetting = False
                    player.last_pos = (mx, my)
                    player.visited[(mx, my)] = now
                    break
            
            if not cleared and now - player.reset_timer > 10.0:
                player.is_resetting = False 
                
            if player.is_resetting:
                return 

        if player.is_stunned and now - player.stun_timer > STUN_DURATION:
            player.is_stunned = False
            
        if player.is_stunned: return 
            
        for mx, my in touches:
            if not (0 <= mx < MAZE_SIZE and 0 <= my < MAZE_SIZE): continue

            if not is_tuto:
                valid_points = list(player.visited.keys()) + [player.start_pos]
                min_dist = min(max(abs(mx - vx), abs(my - vy)) for vx, vy in valid_points)
                
                if min_dist > 1:
                    if mx == player.finish_pos[0] and my == player.finish_pos[1]:
                        self._end_round(winner_name=opponent_name)
                        return
                    else:
                        m, s, f, pu = MazeGenerator.generate()
                        player.maze, player.start_pos, player.finish_pos, player.powerup_pos = m, s, f, pu
                        player.is_stunned = False
                        player.visited.clear()
                        player.last_pos = s
                        player.is_resetting = True
                        player.reset_timer = now
                        return
                
            if player.maze[my][mx] == 1:
                player.is_stunned = True
                player.stun_timer = now
                sfx_path = os.path.join("sounds", "damage_heart.mp3")
                if os.path.exists(sfx_path):
                    pygame.mixer.Sound(sfx_path).play()

                if not is_tuto:
                    player.lives -= 1
                    if self.category == "MIXED" and self.difficulty == "HARD" and player == self.p2:
                        # Îi dăm copilului 3 secunde de vedere când părintele ia Stun
                        self.p1.reveal_timer = now + 1.5 # (Aici rămâne așa dacă vrei să se adune la check-ul de 3.0 de mai sus)
                    
                    if player.lives <= 0:
                        self._end_round(winner_name=opponent_name)
                return 
                
            elif player.maze[my][mx] == 0:
                player.visited[(player.last_pos[0], player.last_pos[1])] = now
                player.visited[(mx, my)] = now
                x1, y1 = player.last_pos
                if abs(mx - x1) <= 2 and abs(my - y1) <= 2:
                    mid_x, mid_y = (x1 + mx) // 2, (y1 + my) // 2
                    if player.maze[mid_y][mid_x] == 0:
                        player.visited[(mid_x, mid_y)] = now
                
                player.last_pos = (mx, my)
                
            if mx == player.powerup_pos[0] and my == player.powerup_pos[1] and player.powerup_active:
                player.powerup_active = False
                player.reveal_timer = now
                
                
            if mx == player.finish_pos[0] and my == player.finish_pos[1]:
                if is_tuto: 
                    if getattr(self, 'tuto_won', False) == False: 
                        self.tuto_won = True
                        self.last_winner = player
                        self._transition('WIN_REVEAL', now)
                else: 
                    winner = "P1" if player == self.p1 else "P2"
                    self._end_round(winner_name=winner)

    def _end_round(self, winner_name):
        if winner_name == "P1": 
            self.p1.score += 1; self.last_winner = self.p1
        else: 
            self.p2.score += 1; self.last_winner = self.p2

        sfx_path = os.path.join("sounds", "win.mp3")
        if os.path.exists(sfx_path):
            pygame.mixer.Sound(sfx_path).play()
        
        self._transition('WIN_REVEAL', time.time())

    def _draw_word_wide(self, word, color, center_y_shift=0):
        width = len(word) * 4 - 1
        start_y = (32 - width) // 2
        start_x_base = 5 + center_y_shift 
        curr_y = start_y
        for char in word.upper():
            if char in FONT_3x5:
                for c, col_data in enumerate(FONT_3x5[char]):
                    for r in range(5):
                        if (col_data >> r) & 1:
                            phys_x = 15 - (start_x_base + r)
                            phys_y = curr_y + c
                            if 0 <= phys_x < 16 and 0 <= phys_y < 32:
                                self.engine.set_pixel(phys_x, phys_y, *color)
                curr_y += 4 
            else:
                curr_y += 4

    def _draw_word_wide_rotated(self, word, color, center_y_shift=0):
        """Desenează text 3x5 ROTIT LA 180 DE GRADE"""
        width = len(word) * 4 - 1
        start_y = (32 - width) // 2
        start_x_base = 6 + center_y_shift 
        curr_y = start_y
        for char in word.upper():
            if char in FONT_3x5:
                for c, col_data in enumerate(FONT_3x5[char]):
                    for r in range(5):
                        if (col_data >> r) & 1:
                            phys_x = start_x_base + r          # Rotire X
                            phys_y = 31 - (curr_y + c)         # Rotire Y
                            if 0 <= phys_x < 16 and 0 <= phys_y < 32:
                                self.engine.set_pixel(phys_x, phys_y, *color)
                curr_y += 4 
            else:
                curr_y += 4

    def _draw_thin_large_text(self, text, center_y, color):
        width = len(text) * 5 - 1
        start_y = center_y - width // 2
        start_x_base = 4 
        curr_y = start_y
        for char in text.upper():
            if char in FONT_4x7:
                for c, col_data in enumerate(FONT_4x7[char]):
                    for r in range(7):
                        if (col_data >> r) & 1:
                            phys_x = 15 - (start_x_base + r)
                            phys_y = curr_y + c
                            if 0 <= phys_x < 16 and 0 <= phys_y < 32:
                                self.engine.set_pixel(phys_x, phys_y, *color)
                curr_y += 5
            else:
                curr_y += 5

    def _draw_perimeters(self):
        for x in range(16):
            self.engine.set_pixel(x, 15, *PERIMETER_COLOR)
            self.engine.set_pixel(x, 16, *PERIMETER_COLOR)
        for y in range(32):
            self.engine.set_pixel(0, y, *PERIMETER_COLOR)
            self.engine.set_pixel(15, y, *PERIMETER_COLOR)
        for x in range(16):
            self.engine.set_pixel(x, 0, *PERIMETER_COLOR)
            self.engine.set_pixel(x, 31, *PERIMETER_COLOR)

    def _transition(self, new_state, time_now):
        self.state = new_state
        self.state_timer = time_now

    def _draw_heart_centered(self, cx, cy, color):
        pixels = [
            (2, -2), (2, -1),         (2, 2), (2, 3),
            (1, -3), (1, -2), (1, -1), (1, 0), (1, 1), (1, 2), (1, 3), (1, 4),
            (0, -3),  (0, -2),  (0, -1),  (0, 0),  (0, 1),  (0, 2),  (0, 3),  (0, 4),
            (-1, -2),  (-1, -1),  (-1, 0),   (-1, 1),  (-1, 2),  (-1, 3),
            (-2, -1),  (-2, 0),   (-2, 1),   (-2, 2),
            (-3, 0),   (-3, 1)  
        ]
        for dx, dy in pixels:
            if 0 <= cx+dx < 16 and 0 <= cy+dy < 32:
                self.engine.set_pixel(cx + dx, cy + dy, *color)

    def _render_start_zone(self, player):
        ox, oy = player.offset_x, player.offset_y
        sx, sy = player.start_pos
        for my in range(sy - 1, sy + 2):
            for mx in range(sx - 1, sx + 2):
                if mx < 0 or mx >= MAZE_SIZE or my < 0 or my >= MAZE_SIZE: pass
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
            
            if t_stun < 2.0:
                blink = int((math.sin(t_stun * 10) + 1) / 2 * 200) 
                self._draw_heart_centered(heart_cx, heart_cy, (blink, 0, 0))
            else:
                fade = max(0, 200 - int(((t_stun - 2.0) / 1.5) * 200))
                self._draw_heart_centered(heart_cx, heart_cy, (fade, 0, 0))
            return

        if now - player.reveal_timer < 3.0: override_full = True

        tchs = tuto_tchs if tuto_tchs else ([(x-ox, y-oy) for x, y in self.engine.get_touches() if ox <= x < ox + 14 and oy <= y < oy + 14] or [player.last_pos])

        for my in range(MAZE_SIZE):
            for mx in range(MAZE_SIZE):
                is_visible = override_full 
                
                if not is_visible:
                    for px, py in tchs:
                        if abs(mx - px) <= player.vis_radius and abs(my - py) <= player.vis_radius:
                            is_visible = True
                            break

                is_finish = (mx == player.finish_pos[0] and my == player.finish_pos[1])
                is_powerup = (mx == player.powerup_pos[0] and my == player.powerup_pos[1] and player.powerup_active)
                is_wall = (player.maze[my][mx] == 1)
                
                if is_visible or is_finish:
                    if is_finish:
                        p_val = int(100 + 80 * math.sin(now * 3))
                        self.engine.set_pixel(ox + mx, oy + my, p_val, p_val, 0) 
                    elif is_powerup:
                        p_val = int(80 + 100 * ((math.sin(now * 6) + 1) / 2))
                        self.engine.set_pixel(ox + mx, oy + my, 0, p_val, p_val) 
                    elif is_wall: 
                        self.engine.set_pixel(ox + mx, oy + my, *WALL_COLOR)
                    else: 
                        self.engine.set_pixel(ox + mx, oy + my, *(P1_COLOR if player == self.p1 else P2_COLOR))
                
                elif player.full_reveal and is_wall:
                    self.engine.set_pixel(ox + mx, oy + my, 0, 30, 0)

                elif (mx, my) in player.visited:
                    age = now - player.visited[(mx, my)]
                    if age < player.trail_life:
                        intensity = 1.0 if player.trail_life > 1000 else max(0, 1.0 - (age / player.trail_life))
                        tr_c = P1_TRAIL if player == self.p1 else P2_TRAIL
                        dim_c = (int(tr_c[0]*intensity), int(tr_c[1]*intensity), int(tr_c[2]*intensity))
                        self.engine.set_pixel(ox + mx, oy + my, *dim_c)
                    else:
                        del player.visited[(mx, my)] 

    def _render_maze_static(self, player):
        ox, oy = player.offset_x, player.offset_y
        for my in range(MAZE_SIZE):
            for mx in range(MAZE_SIZE):
                if mx == player.finish_pos[0] and my == player.finish_pos[1]: self.engine.set_pixel(ox + mx, oy + my, 255, 255, 0)
                elif player.maze[my][mx] == 1: self.engine.set_pixel(ox + mx, oy + my, *WALL_COLOR)
                elif (mx, my) in player.visited: self.engine.set_pixel(ox + mx, oy + my, *(P1_TRAIL if player == self.p1 else P2_TRAIL))
                else: self.engine.set_pixel(ox + mx, oy + my, 0, 0, 0)

    def _draw_rect(self, x, y, w, h, color):
        for i in range(w):
            for j in range(h): self.engine.set_pixel(x + i, y + j, *color)

    # ==============================================================================
    # MAȘINA DE STĂRI (STATE MACHINE) - FLUX RAPID ȘI CORECTAT
    # ==============================================================================

    def render(self):
        self.engine.clear()
        self.update_dashboard()
        self.process_commands()
        
        # PROCESĂM ATINGERILE MEREU PENTRU CA VALURILE SĂ MEARGĂ!
        self.process_inputs()
        
        now = time.time()
        time_in_state = now - self.state_timer
        WORD_DUR = 1.2 # TIMP RAPID DE TRANZIȚIE

        # 1. ALEGE JOCUL
        if self.state == 'WAIT_START':
            p = int(40 + 40 * math.sin(now * 3))
            self._draw_word_wide("ALEGE", (0, p, 0), -4)
            self._draw_word_wide("JOCUL", (0, p, 0), 4)

        # 2. TIMER DE 5 SECUNDE CU "JOCUL INCEPE"
        elif self.state == 'TXT_JOCUL_INCEPE':
            # Durata totală a animației
            durata_fade = 5.0
            
            # Calculăm progresul (de la 1.0 la 0.0)
            # max(0.0, ...) ne asigură că valoarea nu devine negativă
            progres = max(0.0, 1.0 - (time_in_state / durata_fade))
            
            # Calculăm intensitatea verdelui (255 * progres)
            verde_dinamic = int(255 * progres)
            culoare_text = (0, verde_dinamic, 0)
            
            # Desenăm textul cu culoarea care se stinge
            self._draw_word_wide("INCEPE", culoare_text, -4)
            self._draw_word_wide("JOCUL", culoare_text, 4)
            
            # Când timpul a expirat, trecem la animația de încărcare (BOOT_ANIM)
            if time_in_state > durata_fade:
                # Opțional: punem o mică pauză de 50ms de beznă totală înainte de boot
                self.engine.clear()
                time.sleep(0.05) 
                self._transition('BOOT_ANIM', now)

        elif self.state == 'BOOT_ANIM':
            max_dist = time_in_state * 5.0 
            for y in range(32):
                for x in range(16):
                    if (x + y) < max_dist and self.boot_maze[y][x] == 1:
                        self.engine.set_pixel(x, y, 0, 100, 0)
            
            # După 7 secunde, mergem la afișarea textului "CUM SE JOACĂ"
            if time_in_state > 10.0: 
                self._transition('TXT_CUM', now)

        # 3. TUTORIAL PENTRU EXACT 2.3 SECUNDE
        elif self.state == 'TXT_CUM':
            self._draw_word_wide("CUM", WHT)
            self.is_tutorial = True # Activăm tutorialul de aici
            if time_in_state > 1.0: self._transition('TXT_SE', now)

        elif self.state == 'TXT_SE':
            self._draw_word_wide("SE", WHT)
            if time_in_state > 1.0: self._transition('TXT_JOACA', now)

        elif self.state == 'TXT_JOACA':
            self._draw_word_wide("JOACA", WHT)
            if time_in_state > 1.0: 
                self._transition('PAUZA_MEA_1', now) # Trece în pauză

        # STAREA NOUĂ DE PAUZĂ
        elif self.state == 'PAUZA_MEA_1':
            # Aici NU desenezi niciun text. Ecranul va fi negru (sau doar cu borduri)
            if time_in_state > 1.0: # Așteaptă fix 1.0 secunde
                self._transition('TUTO_PLAY', now) # După 1 secundă, trece la tutorial

        elif self.state == 'TUTO_PLAY':
            t_s = now - self.state_timer
            idx1 = min(int(t_s / 0.4), len(self.p1.tuto_path) - 1)
            idx2 = min(int(t_s / 0.4), len(self.p2.tuto_path) - 1)
            
            self._handle_player(self.p1, [self.p1.tuto_path[idx1]], now, "P2", is_tuto=True)
            if self.state != 'TUTO_PLAY': return 
            self._handle_player(self.p2, [self.p2.tuto_path[idx2]], now, "P1", is_tuto=True)
            
            self._render_maze(self.p1, False, [self.p1.tuto_path[idx1]])
            self._render_maze(self.p2, False, [self.p2.tuto_path[idx2]])
            self._draw_perimeters()
            
            # Calcul durată completă tutorial ca să nu se închidă mai devreme
            tuto_dur = max(len(self.p1.tuto_path), len(self.p2.tuto_path)) * 0.4 + 1.0
            if t_s > tuto_dur: 
                self.is_tutorial = False
                self._transition('TXT_ACUM', now)

        # 4. ACUM ALEGE O CULOARE
        elif self.state == 'TXT_ACUM':
            self._draw_word_wide("ACUM", WHT) 
            if time_in_state > WORD_DUR: self._transition('TXT_ALEGE', now)
        elif self.state == 'TXT_ALEGE':
            self._draw_word_wide("ALEGE O", WHT) 
            if time_in_state > WORD_DUR: self._transition('TXT_CULOARE', now)
        elif self.state == 'TXT_CULOARE':
            self._draw_word_wide("CULOARE", WHT) 
            if time_in_state > WORD_DUR: 
                self.generate_new_round()
                self._transition('PICK_FULL', now)
                
        elif self.state == 'PICK_FULL':
            freq = 0.5 + (time_in_state / 5.0) * 1.5
            pulse = (math.sin(time_in_state * freq * math.pi * 2) + 1) / 2
            c1 = [int(x * (0.2 + 0.4 * pulse)) for x in P1_COLOR] 
            c2 = [int(x * (0.2 + 0.4 * pulse)) for x in P2_COLOR]
            self._draw_rect(self.p1.offset_x, self.p1.offset_y, 14, 14, c1)
            self._draw_rect(self.p2.offset_x, self.p2.offset_y, 14, 14, c2)
            if time_in_state > 3.0: self._transition('PICK_SHRINK', now)

        elif self.state == 'PICK_SHRINK':
            progress = time_in_state / 2.0
            max_dist = 20 * (1.0 - progress) 
            for p, c in [(self.p1, P1_COLOR), (self.p2, P2_COLOR)]:
                cx, cy = p.offset_x + p.start_pos[0], p.offset_y + p.start_pos[1]
                for my in range(14):
                    for mx in range(14):
                        px, py = p.offset_x + mx, p.offset_y + my
                        dist = math.hypot(px - cx, py - cy)
                        in_start_zone = abs(mx - p.start_pos[0]) <= 1 and abs(my - p.start_pos[1]) <= 1
                        if in_start_zone or dist < max_dist:
                            self.engine.set_pixel(px, py, c[0]//3, c[1]//3, c[2]//3)
            if time_in_state > 2.0: self._transition('GO_TO_START', now)
            
        elif self.state == 'GO_TO_START':
            freq = 0.5 + (time_in_state / 5.0) * 1.5
            pulse = (math.sin(time_in_state * freq * math.pi * 2) + 1) / 2
            c1 = [int(x * (0.3 + 0.5 * pulse)) for x in P1_COLOR]
            c2 = [int(x * (0.3 + 0.5 * pulse)) for x in P2_COLOR]
            
            for p, c in [(self.p1, c1), (self.p2, c2)]:
                ox, oy = p.offset_x, p.offset_y
                sx, sy = p.start_pos
                for my in range(sy - 1, sy + 2):
                    for mx in range(sx - 1, sx + 2):
                        if 0 <= mx < 14 and 0 <= my < 14:
                            self.engine.set_pixel(ox + mx, oy + my, *c)
                            
            if time_in_state > 3.0: self._transition('PRE_COUNT', now)
            
        elif self.state == 'PRE_COUNT':
            # ECRAN GOL TIMP DE 1 SECUNDĂ
            self._render_start_zone(self.p1)
            self._render_start_zone(self.p2)
            if time_in_state > 1.0:
                sfx_path = os.path.join("sounds", "counter.mp3")
                if os.path.exists(sfx_path):
                    pygame.mixer.Sound(sfx_path).play()
                self._transition('COUNT_3', now)

        # 6. COUNTDOWN 3, 2, 1, 0 -> PLAYING
        elif self.state.startswith('COUNT_') or self.state == 'PLAYING':
            if self.state.startswith('COUNT_'):
                val = self.state.split('_')[1]
                self._render_start_zone(self.p1)
                self._render_start_zone(self.p2)
                
                self._draw_thin_large_text(val, 8, P1_COLOR)
                self._draw_thin_large_text(val, 24, P2_COLOR)
                    
                if time_in_state > 1.0:
                    if val == '0': 
                        self._transition('PLAYING', now)
                    else:
                        next_val = str(int(val) - 1)
                        self._transition(f'COUNT_{next_val}', now)
            else:
                self._render_maze(self.p1, override_full=False)
                self._render_maze(self.p2, override_full=False)

        # 7. ANIMATII CÂȘTIGARE RUNDĂ
        elif self.state == 'WIN_REVEAL':
            self._render_maze(self.p1, override_full=True)
            self._render_maze(self.p2, override_full=True)
            if time_in_state > 2.5: self._transition('ROUND_WAVE', now)

        elif self.state == 'ROUND_WAVE':
            win_color = P1_COLOR if self.last_winner == self.p1 else P2_COLOR
            winner = self.last_winner if self.last_winner else self.p1
            
            self._render_maze_static(self.p1)
            self._render_maze_static(self.p2)
            
            cx, cy = winner.offset_x + winner.finish_pos[0], winner.offset_y + winner.finish_pos[1]
            max_r = time_in_state * 20 
            
            for y in range(32):
                for x in range(16):
                    dist = math.hypot(x-cx, y-cy)
                    if dist < max_r:
                        p = (math.sin(dist * 0.4 - time_in_state * 6) + 1) / 2
                        self.engine.set_pixel(x, y, *[int(c*(0.1+0.5*p)) for c in win_color])
                            
            if time_in_state > 3.0: 
                if self.is_tutorial:
                    self.is_tutorial = False
                    self.p1.score = 0 
                    self.p2.score = 0
                    if hasattr(self, 'tuto_won'): del self.tuto_won
                    self._transition('TXT_ACUM', now)
                else:
                    self._transition('TXT_WIN_1', now)
                
        # 8. AFIȘĂM "BLUE WON" / "RED WON" (Fără sunete redundante)
        elif self.state == 'TXT_WIN_1':
            nume = "CYAN" if self.last_winner == self.p1 else "PINK"
            cul = P1_COLOR if self.last_winner == self.p1 else P2_COLOR
            self._draw_word_wide(nume, cul)
            if time_in_state > WORD_DUR: self._transition('TXT_WIN_2', now)
            
        elif self.state == 'TXT_WIN_2':
            cul = P1_COLOR if self.last_winner == self.p1 else P2_COLOR
            self._draw_word_wide("WON", cul)
            if time_in_state > WORD_DUR: 
                self._transition('SHOW_SCORE_ONLY', now)
                
        # 9. AFIȘĂM DIRECT SCORUL PENTRU TIMP PRELUNGIT (4.0 Secunde)
        elif self.state == 'SHOW_SCORE_ONLY':
            self._draw_thin_large_text(str(self.p1.score), 10, P1_COLOR)
            self._draw_thin_large_text("-", 16, WHT)
            self._draw_thin_large_text(str(self.p2.score), 22, P2_COLOR)
            
            if time_in_state > 2.0:  # <--- AICI AM MODIFICAT DIN 4.0 in 2.0
                self._transition('INTERACTIVE_BREAK', now)
                self.ripples.clear()
                self.last_touches = set(self.engine.get_touches())
                
        # 10. PAUZĂ EXACT 5 SECUNDE CU VALURI ACTIVE!
        elif self.state == 'INTERACTIVE_BREAK':
            win_color = P1_COLOR if self.last_winner == self.p1 else P2_COLOR
            dim_win = (win_color[0]//8, win_color[1]//8, win_color[2]//8) 
            
            for y in range(32):
                for x in range(16):
                    self.engine.set_pixel(x, y, *dim_win)
                        
            for rx, ry, rc, rstart in self.ripples:
                rage = now - rstart
                radius = rage * 10.0 
                if rage > 3.0: continue
                fade = max(0, 1.0 - (rage / 3.0))
                col = (int(rc[0]*fade*0.7), int(rc[1]*fade*0.7), int(rc[2]*fade*0.7))
                for y in range(32):
                    for x in range(16):
                        dist = math.hypot(x-rx, y-ry)
                        if abs(dist - radius) < 1.0:
                            self.engine.set_pixel(x, y, *col)

            if time_in_state > 5.0:
                if self.p1.score >= MAX_WINS or self.p2.score >= MAX_WINS: 
                    self._transition('GAME_OVER', now)
                else: 
                    self.generate_new_round()
                    self._transition('CLEAR_SCREEN_05', now)

        # STINGE ECRANUL TIMP DE 0.5 SECUNDE PENTRU TRANZIȚIE CURATĂ
        elif self.state == 'CLEAR_SCREEN_05':
            if time_in_state > 0.5:
                self._transition('PRE_COUNT', now)

        elif self.state == 'GAME_OVER':
            win_color = P1_COLOR if self.p1.score > self.p2.score else P2_COLOR
            breath = int(50 + 80 * ((math.sin(now * 1.5) + 1) / 2)) 
            for y in range(32):
                for x in range(16):
                    self.engine.set_pixel(x, y, int(win_color[0]*breath/255), int(win_color[1]*breath/255), int(win_color[2]*breath/255))
            for _ in range(5): 
                self.engine.set_pixel(random.randint(1,14), random.randint(1,30), 255, 255, 255)
            
            castigator = "CYAN" if self.p1.score > self.p2.score else "PINK"
            self._draw_word_wide(castigator, WHT, -4)
            self._draw_word_wide("WON!", WHT, 4)
            
            if time_in_state > 8.0:
                self._transition('WAIT_START', now)

        draw_perim_states = ['TUTO_PLAY', 'PICK_FULL', 'PICK_SHRINK', 'GO_TO_START', 'PLAYING', 'WIN_REVEAL']
        if self.state in draw_perim_states or self.state.startswith('COUNT_') or self.state == 'PRE_COUNT':
            self._draw_perimeters()

    def run(self):
        print("BLIND LABYRINTH - TOURNAMENT EDITION RUNNING (V4.3)")
        try:
            while self.engine.running:
                self.render()
                time.sleep(0.03) 
        except KeyboardInterrupt: pass
        finally: self.engine.stop()

if __name__ == "__main__":
    FogRunGame().run()