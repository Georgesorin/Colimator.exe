import time
import random
import math
from matrix_engine import MatrixEngine

# --- Theming & Colors ---
P1_COLOR = (0, 255, 255)       # Bright Cyan
P2_COLOR = (255, 0, 255)       # Bright Magenta
P1_TRAIL = (0, 50, 50)         # Darker Cyan Trail
P2_TRAIL = (50, 0, 50)         # Darker Magenta Trail
WALL_COLOR = (0, 255, 0)       # NEON GREEN for all walls
PERIMETER_COLOR = (0, 255, 0)  # NEON GREEN for borders
STUN_COLOR = (255, 0, 0)       # Red for Heart
FINISH_COLOR = (255, 255, 0)   # Yellow finish for both sides
POWERUP_COLOR = (0, 100, 255)  # Blue Reveal Powerup
WHT = (255, 255, 255)          # Pure White for ALL text

MAZE_SIZE = 14
MAX_WINS = 5
MAX_LIVES = 5
STUN_DURATION = 3.5 
TRAIL_LIFETIME = 60.0

FONT_3x5 = {
    ' ': [0,0,0], '!': [0, 23, 0], '"': [3, 0, 3], '#': [31, 10, 31],
    '$': [18, 31, 9], '%': [28, 4, 7], '&': [21, 21, 14], '\'': [0, 3, 0],
    '(': [0, 14, 17], ')': [17, 14, 0], '*': [10, 4, 10], '+': [4, 14, 4],
    ',': [0, 24, 0], '-': [4, 4, 4], '.': [0, 16, 0], '/': [24, 4, 3],
    '0': [31, 17, 31], '1': [0, 31, 0], '2': [29, 21, 23], '3': [21, 21, 31],
    '4': [7, 4, 31], '5': [23, 21, 29], '6': [31, 21, 29], '7': [1, 1, 31],
    '8': [31, 21, 31], '9': [23, 21, 31], ':': [0, 10, 0], ';': [0, 26, 0],
    '<': [4, 10, 17], '=': [10, 10, 10], '>': [17, 10, 4], '?': [1, 21, 7],
    '@': [14, 21, 22], 'A': [30, 5, 30], 'B': [31, 21, 10], 'C': [14, 17, 17],
    'D': [31, 17, 14], 'E': [31, 21, 21], 'F': [31, 5, 5], 'G': [14, 21, 29],
    'H': [31, 4, 31], 'I': [17, 31, 17], 'J': [8, 16, 15], 'K': [31, 4, 27],
    'L': [31, 16, 16], 'M': [31, 2, 31], 'N': [31, 2, 28], 'O': [14, 17, 14],
    'P': [31, 5, 2], 'Q': [14, 17, 30], 'R': [31, 5, 26], 'S': [18, 21, 9],
    'T': [1, 31, 1], 'U': [15, 16, 15], 'V': [7, 24, 7], 'W': [31, 8, 31],
    'X': [27, 4, 27], 'Y': [3, 28, 3], 'Z': [25, 21, 19], '[': [31, 17, 0],
    '\\': [3, 4, 24], ']': [0, 17, 31], '^': [2, 1, 2], '_': [16, 16, 16],
    '`': [0, 1, 2], 'a': [10, 21, 31], 'b': [31, 20, 8], 'c': [14, 17, 17],
    'd': [8, 20, 31], 'e': [14, 21, 21], 'f': [4, 31, 5], 'g': [18, 21, 15],
    'h': [31, 4, 24], 'i': [0, 29, 0], 'j': [16, 16, 13], 'k': [31, 4, 27],
    'l': [0, 31, 0], 'm': [30, 2, 30], 'n': [28, 4, 24], 'o': [14, 17, 14],
    'p': [31, 5, 2], 'q': [2, 5, 31], 'r': [28, 4, 4], 's': [18, 21, 9],
    't': [4, 31, 20], 'u': [15, 16, 15], 'v': [7, 24, 7], 'w': [31, 8, 31],
    'x': [27, 4, 27], 'y': [3, 28, 31], 'z': [25, 21, 19], '{': [4, 27, 17],
    '|': [0, 31, 0], '}': [17, 27, 4], '~': [2, 1, 2]
}

# --- THIN 4x7 FONT (For Countdown & Scoreboard) ---
FONT_4x7 = {
    '0': [62, 65, 65, 62],  '1': [0, 66, 127, 64],  '2': [98, 81, 73, 70],
    '3': [34, 73, 73, 54],  '4': [24, 20, 18, 127], '5': [39, 69, 69, 57],
    '6': [62, 73, 73, 50],  '7': [1, 1, 121, 7],    '8': [54, 73, 73, 54],
    '9': [38, 73, 73, 62],  'G': [62, 65, 73, 58],  'O': [62, 65, 65, 62],
    '-': [8, 8, 8, 8]
}

class MazeGenerator:
    @staticmethod
    def generate_full_boot_maze():
        w, h = 16, 32
        grid = [[1 for _ in range(w)] for _ in range(h)]
        stack = [(0, 0)]
        grid[0][0] = 0
        while stack:
            cx, cy = stack[-1]
            nbs = []
            for nx, ny in [(cx-2, cy), (cx+2, cy), (cx, cy-2), (cx, cy+2)]:
                if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] == 1:
                    nbs.append((nx, ny))
            if nbs:
                nx, ny = random.choice(nbs)
                grid[ny][nx] = 0
                grid[(cy+ny)//2][(cx+nx)//2] = 0
                stack.append((nx, ny))
            else:
                stack.pop()
        return grid

    @staticmethod
    def generate():
        grid = [[1 for _ in range(MAZE_SIZE)] for _ in range(MAZE_SIZE)]
        start_y = random.randint(2, MAZE_SIZE - 3)
        finish_y = random.randint(2, MAZE_SIZE - 3)
        start_pos = (0, start_y)
        finish_pos = (13, finish_y)
        
        stack = [start_pos]
        grid[start_pos[1]][start_pos[0]] = 0
        
        while stack:
            cx, cy = stack[-1]
            neighbors = []
            for nx, ny in [(cx-2, cy), (cx+2, cy), (cx, cy-2), (cx, cy+2)]:
                if 0 < nx < MAZE_SIZE-1 and 0 < ny < MAZE_SIZE-1 and grid[ny][nx] == 1:
                    neighbors.append((nx, ny))
            if neighbors:
                nx, ny = random.choice(neighbors)
                grid[ny][nx] = 0
                grid[(cy + ny) // 2][(cx + nx) // 2] = 0
                stack.append((nx, ny))
            else:
                stack.pop()
                
        grid[finish_pos[1]][finish_pos[0]] = 0
        grid[finish_pos[1]][finish_pos[0]-1] = 0
        
        paths = [(x, y) for y in range(MAZE_SIZE) for x in range(MAZE_SIZE) if grid[y][x] == 0]
        mid_paths = [p for p in paths if 4 <= p[0] <= 9]
        powerup_pos = random.choice(mid_paths) if mid_paths else (6,6)
        
        return grid, start_pos, finish_pos, powerup_pos


class PlayerState:
    def __init__(self, offset_y):
        self.offset_x = 1
        self.offset_y = offset_y 
        self.score = 0
        self.lives = MAX_LIVES
        self.is_stunned = False
        self.stun_timer = 0
        self.visited = {}  
        self.last_pos = (0, 0)
        self.maze = [] 
        self.start_pos = (0, 0)
        self.finish_pos = (13, 0)
        self.powerup_pos = (6, 6)
        self.powerup_active = True
        self.reveal_timer = 0
        self.tuto_path = []
        
        # Anti-Cheat Reset Variables
        self.is_resetting = False
        self.reset_timer = 0
        
    def reset_round(self):
        self.lives = MAX_LIVES
        self.is_stunned = False
        self.stun_timer = 0
        self.visited.clear()
        self.powerup_active = True
        self.reveal_timer = 0
        self.is_resetting = False
        self.reset_timer = 0


class FogRunGame:
    def __init__(self):
        self.engine = MatrixEngine()
        self.running = True
        self.p1 = PlayerState(offset_y=1)   
        self.p2 = PlayerState(offset_y=17)  
        self.is_tutorial = False
        self.last_winner = None
        self.boot_maze = MazeGenerator.generate_full_boot_maze()
        
        self.ripples = [] 
        self.last_touches = set()
        
        self.generate_new_round()
        self.state = 'BOOT_ANIM'
        self.state_timer = time.time()
        self.WHT = (255, 255, 255)
        
    def generate_new_round(self):
        for p in [self.p1, self.p2]:
            m, s, f, pu = MazeGenerator.generate()
            p.maze, p.start_pos, p.finish_pos, p.powerup_pos = m, s, f, pu
            p.last_pos = s
            p.reset_round()

        p1_path = self._build_tuto_path(self.p1.maze, self.p1.start_pos, self.p1.powerup_pos, self.p1.finish_pos)
        p2_path = self._build_tuto_path(self.p2.maze, self.p2.start_pos, self.p2.powerup_pos, self.p2.finish_pos)
        
        p1_pre = p1_path[:-1]
        p2_pre = p2_path[:-1]
        max_len = max(len(p1_pre), len(p2_pre))
        
        p1_pre.extend([p1_pre[-1]] * (max_len - len(p1_pre) + 10))
        p2_pre.extend([p2_pre[-1]] * (max_len - len(p2_pre)))
        
        self.p1.tuto_path = p1_pre + [p1_path[-1]] * 5
        self.p2.tuto_path = p2_pre + [p2_path[-1]] * 5

    def _build_tuto_path(self, maze, start, powerup, finish):
        def bfs(s_n, e_n):
            q = [[s_n]]; vis = {s_n}
            while q:
                p = q.pop(0); curr = p[-1]
                if curr == e_n: return p
                for nx, ny in [(curr[0]-1, curr[1]), (curr[0]+1, curr[1]), (curr[0], curr[1]-1), (curr[0], curr[1]+1)]:
                    if 0 <= nx < MAZE_SIZE and 0 <= ny < MAZE_SIZE and maze[ny][nx] == 0 and (nx, ny) not in vis:
                        vis.add((nx, ny)); q.append(p + [(nx, ny)])
            return [s_n]
            
        res = bfs(start, powerup) + bfs(powerup, finish)[1:]
        final = []
        stun_injected = False
        for i, node in enumerate(res):
            final.append(node)
            if not stun_injected and i == 4:
                sx, sy = node
                for nx, ny in [(sx-1, sy), (sx+1, sy), (sx, sy-1), (sx, sy+1)]:
                    if 0 <= nx < MAZE_SIZE and 0 <= ny < MAZE_SIZE and maze[ny][nx] == 1:
                        final.append((nx, ny)) # Deliberately touch wall
                        final.extend([node] * 10) # Stand completely still during the stun animation
                        stun_injected = True
                        break
        for _ in range(5): final.append(finish)
        return final

    def _add_trail(self, player, x1, y1, x2, y2, now):
        player.visited[(x1, y1)] = now
        player.visited[(x2, y2)] = now
        if abs(x2 - x1) <= 2 and abs(y2 - y1) <= 2:
            mid_x, mid_y = (x1 + x2) // 2, (y1 + y2) // 2
            if player.maze[mid_y][mid_x] == 0:
                player.visited[(mid_x, mid_y)] = now

    def process_inputs(self):
        touches = self.engine.get_touches()
        now = time.time()
        
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
        
        # --- Handle Reset from Anti-Cheat Jump ---
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
                return # Ignore all other touches until they step on the start

        if player.is_stunned and now - player.stun_timer > STUN_DURATION:
            player.is_stunned = False
            
        if player.is_stunned: return 
            
        for mx, my in touches:
            if not (0 <= mx < MAZE_SIZE and 0 <= my < MAZE_SIZE): continue

            # --- ANTI-CHEAT STRICT ---
            if not is_tuto:
                valid_points = list(player.visited.keys()) + [player.start_pos]
                min_dist = min(max(abs(mx - vx), abs(my - vy)) for vx, vy in valid_points)
                
                # If they step more than 1 block away from their existing path (they jumped)
                if min_dist > 1:
                    if mx == player.finish_pos[0] and my == player.finish_pos[1]:
                        # Jumped straight to the finish line! Opponent wins immediately.
                        print(f"ANTI-CHEAT: {opponent_name} wins. Player jumped to finish!")
                        self._end_round(winner_name=opponent_name)
                        return
                    else:
                        # Jumped randomly in the maze! Reset their specific maze and punish them.
                        print("ANTI-CHEAT: Player jumped! Resetting their maze.")
                        m, s, f, pu = MazeGenerator.generate()
                        player.maze, player.start_pos, player.finish_pos, player.powerup_pos = m, s, f, pu
                        player.reset_round()
                        player.last_pos = s
                        player.is_resetting = True
                        player.reset_timer = now
                        return
                
            if player.maze[my][mx] == 1:
                player.is_stunned = True
                player.stun_timer = now
                if not is_tuto:
                    player.lives -= 1
                    if player.lives <= 0:
                        self._end_round(winner_name=opponent_name)
                return 
                
            elif player.maze[my][mx] == 0:
                self._add_trail(player, player.last_pos[0], player.last_pos[1], mx, my, now)
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
            self.p1.score += 1
            self.last_winner = self.p1
        else: 
            self.p2.score += 1
            self.last_winner = self.p2
        self._transition('WIN_REVEAL', time.time())

    def _draw_word_wide(self, word, color, center_y_shift=0):
        # Latimea totala pentru FONT_3x5 este 4 (3 litera + 1 spatiu)
        width = len(word) * 4 - 1
        start_y = (32 - width) // 2
        start_x_base = 6 + center_y_shift # Pozitia pe X
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
                curr_y += 4 # Spatiu pt urmatoarea litera
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

    def _draw_sliding_text(self, text, color, time_in_state, duration):
        text_width = len(text) * 4
        curr_y_offset = int(32.0 - (time_in_state / duration) * (32.0 + text_width))
        start_x_base = 6 
        for i, char in enumerate(text.upper()):
            if char in FONT_3x5:
                for c, col_data in enumerate(FONT_3x5[char]):
                    phys_y = curr_y_offset + (i * 4) + c
                    if 0 <= phys_y < 32:
                        for r in range(5):
                            if (col_data >> r) & 1:
                                phys_x = 15 - (start_x_base + r)
                                if 0 <= phys_x < 16:
                                    self.engine.set_pixel(phys_x, phys_y, *color)

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

    def render(self):
        self.engine.clear()
        now = time.time()
        time_in_state = now - self.state_timer
        WORD_DUR = 3.0 # Words stay for 3 seconds each!
        
        # --- STATE MACHINE FOR SEQUENCES ---

        if self.state == 'BOOT_ANIM':
            max_dist = time_in_state * 20.0 
            for y in range(32):
                for x in range(16):
                    if (x + y) < max_dist:
                        if self.boot_maze[y][x] == 1:
                            self.engine.set_pixel(x, y, 0, 100, 0)
            if time_in_state > 3.0: self._transition('TXT_WATCH', now)

        elif self.state == 'TXT_WATCH':
            self._draw_word_wide("WATCH", self.WHT)
            if time_in_state > WORD_DUR: 
                self.is_tutorial = True
                self._transition('TXT_THE_1', now)
                
        elif self.state == 'TXT_THE_1':
            self._draw_word_wide("THE", self.WHT)
            if time_in_state > WORD_DUR: self._transition('TXT_TUTO', now)
            
        elif self.state == 'TXT_TUTO':
            self._draw_word_wide("TUTORIAL", self.WHT)
            if time_in_state > WORD_DUR: self._transition('TUTO_PLAY', now)

        elif self.state == 'TUTO_PLAY':
            self.process_inputs()
            t_s = now - self.state_timer
            idx1 = min(int(t_s / 0.4), len(self.p1.tuto_path) - 1)
            idx2 = min(int(t_s / 0.4), len(self.p2.tuto_path) - 1)
            self._render_maze(self.p1, override_full=False, tuto_tchs=[self.p1.tuto_path[idx1]])
            self._render_maze(self.p2, override_full=False, tuto_tchs=[self.p2.tuto_path[idx2]])

        elif self.state == 'TXT_ARE':
            self._draw_word_wide("ARE", self.WHT); 
            if time_in_state > WORD_DUR: self._transition('TXT_YOU', now)
        elif self.state == 'TXT_YOU':
            self._draw_word_wide("YOU", self.WHT); 
            if time_in_state > WORD_DUR: self._transition('TXT_READY', now)
        elif self.state == 'TXT_READY':
            self._draw_word_wide("READY", self.WHT); 
            if time_in_state > WORD_DUR: self._transition('TXT_FIND', now)
        elif self.state == 'TXT_FIND':
            self._draw_word_wide("FIND", self.WHT); 
            if time_in_state > WORD_DUR: self._transition('TXT_THE_2', now)
        elif self.state == 'TXT_THE_2':
            self._draw_word_wide("THE", self.WHT); 
            if time_in_state > WORD_DUR: self._transition('TXT_END', now)
        elif self.state == 'TXT_END':
            self._draw_word_wide("END", self.WHT); 
            if time_in_state > WORD_DUR: self._transition('TXT_CHOOSE', now)
        elif self.state == 'TXT_CHOOSE':
            self._draw_word_wide("CHOOSE", self.WHT); 
            if time_in_state > WORD_DUR: self._transition('TXT_YOUR_1', now)
        elif self.state == 'TXT_YOUR_1':
            self._draw_word_wide("YOUR", self.WHT); 
            if time_in_state > WORD_DUR: self._transition('TXT_COLOUR', now)
        elif self.state == 'TXT_COLOUR':
            self._draw_word_wide("COLOUR", self.WHT); 
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
            if time_in_state > 5.0: self._transition('PICK_SHRINK', now)

        elif self.state == 'PICK_SHRINK':
            progress = time_in_state / 3.5
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
            if time_in_state > 3.5: self._transition('GO_TO_START', now)
            
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
                            
            if time_in_state > 5.0: self._transition('TXT_GET', now)

        elif self.state == 'TXT_GET':
            self._draw_word_wide("GET", self.WHT); 
            if time_in_state > WORD_DUR: self._transition('TXT_READY_P', now)
        elif self.state == 'TXT_READY_P':
            self._draw_word_wide("READY", self.WHT); 
            if time_in_state > WORD_DUR: self._transition('COUNT_5', now)

        # --- COUNTDOWN & PLAYING ---
        elif self.state.startswith('COUNT_') or self.state == 'PLAYING':
            if self.state.startswith('COUNT_'):
                val = self.state.split('_')[1]
                self._render_start_zone(self.p1)
                self._render_start_zone(self.p2)
                
                if val == 'GO':
                    self._draw_thin_large_text("GO", 8, P1_COLOR)
                    self._draw_thin_large_text("GO", 24, P2_COLOR)
                else:
                    self._draw_thin_large_text(val, 8, P1_COLOR)
                    self._draw_thin_large_text(val, 24, P2_COLOR)
                    
                if time_in_state > 1.0:
                    if val == 'GO': self._transition('PLAYING', now)
                    else:
                        next_val = str(int(val) - 1) if int(val) > 1 else 'GO'
                        self._transition(f'COUNT_{next_val}', now)
            else:
                self._render_maze(self.p1, override_full=False)
                self._render_maze(self.p2, override_full=False)

        # --- WIN / BREAK SEQUENCES ---
        elif self.state == 'WIN_REVEAL':
            self._render_maze(self.p1, override_full=True)
            self._render_maze(self.p2, override_full=True)
            if time_in_state > 5.0: self._transition('ROUND_WAVE', now)

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
                            
            if time_in_state > 4.0: 
                if self.is_tutorial:
                    self.is_tutorial = False
                    self.p1.score = 0 
                    self.p2.score = 0
                    if hasattr(self, 'tuto_won'): del self.tuto_won
                    self._transition('TXT_ARE', now)
                else:
                    self._transition('TXT_WINNER', now)
                
        elif self.state == 'TXT_WINNER':
            self._draw_word_wide("WINNER", self.WHT)
            if time_in_state > WORD_DUR: self._transition('TXT_IS', now)

        elif self.state == 'TXT_IS':
            self._draw_word_wide("IS", self.WHT)
            if time_in_state > WORD_DUR: self._transition('WIN_COLOR_SHOW', now)

        elif self.state == 'WIN_COLOR_SHOW':
            win_color = P1_COLOR if self.last_winner == self.p1 else P2_COLOR
            for y in range(32):
                for x in range(16):
                    dist = math.sqrt((x-8)**2 + (y-16)**2)
                    brightness = int(100 + 80 * math.sin(dist - time_in_state * 8)) 
                    f_col = (int(win_color[0]*brightness/255), int(win_color[1]*brightness/255), int(win_color[2]*brightness/255))
                    self.engine.set_pixel(x, y, *f_col)

            if time_in_state > 4.0: self._transition('TXT_NEW', now)
            
        elif self.state == 'TXT_NEW':
            self._draw_word_wide("NEW", self.WHT)
            if time_in_state > WORD_DUR: self._transition('TXT_SCORE', now)

        elif self.state == 'TXT_SCORE':
            self._draw_word_wide("SCORE", self.WHT)
            if time_in_state > WORD_DUR: self._transition('TXT_IS2', now)

        elif self.state == 'TXT_IS2':
            self._draw_word_wide("IS", self.WHT)
            if time_in_state > WORD_DUR: self._transition('SHOW_SCORE', now)

        elif self.state == 'SHOW_SCORE':
            self._draw_thin_large_text(str(self.p1.score), 10, P1_COLOR)
            self._draw_thin_large_text("-", 16, self.WHT)
            self._draw_thin_large_text(str(self.p2.score), 22, P2_COLOR)
            if time_in_state > 5.0: self._transition('TXT_TAKE', now)

        elif self.state == 'TXT_TAKE':
            self._draw_word_wide("TAKE", self.WHT)
            if time_in_state > WORD_DUR: self._transition('TXT_A', now)
            
        elif self.state == 'TXT_A':
            self._draw_word_wide("A", self.WHT)
            if time_in_state > WORD_DUR: self._transition('TXT_BREAK', now)
            
        elif self.state == 'TXT_BREAK':
            self._draw_word_wide("BREAK", self.WHT)
            if time_in_state > WORD_DUR: 
                self._transition('INTERACTIVE_BREAK', now)
                self.ripples.clear()
                self.last_touches = set(self.engine.get_touches())
                
        elif self.state == 'INTERACTIVE_BREAK':
            win_color = P1_COLOR if self.last_winner == self.p1 else P2_COLOR
            dim_win = (win_color[0]//8, win_color[1]//8, win_color[2]//8) 
            
            progress = (time_in_state / 15.0) * 48
            for y in range(32):
                for x in range(16):
                    if (x + y) < progress:
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

            if time_in_state > 15.0:
                if self.p1.score >= MAX_WINS or self.p2.score >= MAX_WINS: self._transition('GAME_OVER', now)
                else: self._transition('TXT_STAY', now)

        elif self.state == 'TXT_STAY':
            self._draw_word_wide("STAY", self.WHT)
            if time_in_state > WORD_DUR: self._transition('TXT_ON', now)
            
        elif self.state == 'TXT_ON':
            self._draw_word_wide("ON", self.WHT)
            if time_in_state > WORD_DUR: self._transition('TXT_YOUR_2', now)
            
        elif self.state == 'TXT_YOUR_2':
            self._draw_word_wide("YOUR", self.WHT)
            if time_in_state > WORD_DUR: self._transition('TXT_SIDE_P', now)
            
        elif self.state == 'TXT_SIDE_P':
            self._draw_word_wide("SIDE", self.WHT)
            if time_in_state > WORD_DUR: 
                self.generate_new_round()
                self._transition('GO_TO_START', now)

        elif self.state == 'GAME_OVER':
            win_color = P1_COLOR if self.p1.score > self.p2.score else P2_COLOR
            breath = int(50 + 80 * ((math.sin(now * 1.5) + 1) / 2)) 
            for y in range(32):
                for x in range(16):
                    self.engine.set_pixel(x, y, int(win_color[0]*breath/255), int(win_color[1]*breath/255), int(win_color[2]*breath/255))
            for _ in range(5): 
                self.engine.set_pixel(random.randint(1,14), random.randint(1,30), 255, 255, 255)
            self._draw_word_wide("OVERALL", self.WHT, -4)
            self._draw_word_wide("WINNER!", self.WHT, 4)

        # Desenam gardul verde in permanenta, cu exceptia animatiilor full-screen
        draw_perim_states = [
            'TUTO_PLAY', 
            'PICK_FULL', 'PICK_SHRINK', 'GO_TO_START', 
            'SPLIT', 'SHOW_MAZE', 'PLAYING', 'WIN_REVEAL'
        ]
        
        if self.state in draw_perim_states or self.state.startswith('COUNT_'):
            self._draw_perimeters()

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
            self._draw_rect(ox, oy, 14, 14, (0, 0, 0))
            self._render_start_zone(player)
            return

        if player.is_stunned:
            t_stun = now - player.stun_timer
            self._draw_rect(ox, oy, 14, 14, (0, 0, 0)) 
            heart_cx, heart_cy = 8, oy + 6 
            
            if t_stun < 2.0:
                blink = int((math.sin(t_stun * 10) + 1) / 2 * 200) 
                self._draw_heart_centered(heart_cx, heart_cy, (blink, 0, 0))
            else:
                fade = max(0, 200 - int(((t_stun - 2.0) / 1.5) * 200))
                self._draw_heart_centered(heart_cx, heart_cy, (fade, 0, 0))
            return

        if now - player.reveal_timer < 1.5: override_full = True

        if tuto_tchs is not None:
            tchs = tuto_tchs
        else:
            touches = self.engine.get_touches()
            tchs = [(x - ox, y - oy) for x, y in touches if ox <= x < ox + 14 and oy <= y < oy + 14]
            if not tchs and player.last_pos: tchs = [player.last_pos]

        for my in range(MAZE_SIZE):
            for mx in range(MAZE_SIZE):
                is_visible = override_full 
                
                if not is_visible:
                    for px, py in tchs:
                        if abs(mx - px) <= 1 and abs(my - py) <= 1:
                            is_visible = True
                            break

                is_finish = (mx == player.finish_pos[0] and my == player.finish_pos[1])
                is_powerup = (mx == player.powerup_pos[0] and my == player.powerup_pos[1] and player.powerup_active)
                
                if is_visible or is_finish:
                    if is_finish:
                        p_val = int(100 + 80 * math.sin(now * 3))
                        self.engine.set_pixel(ox + mx, oy + my, p_val, p_val, 0) 
                    elif is_powerup:
                        p_val = int(80 + 100 * ((math.sin(now * 6) + 1) / 2))
                        self.engine.set_pixel(ox + mx, oy + my, 0, p_val//2, p_val) 
                    elif player.maze[my][mx] == 1: 
                        self.engine.set_pixel(ox + mx, oy + my, *WALL_COLOR)
                    else: 
                        self.engine.set_pixel(ox + mx, oy + my, *(P1_COLOR if player == self.p1 else P2_COLOR))
                
                elif (mx, my) in player.visited:
                    age = now - player.visited[(mx, my)]
                    if age < TRAIL_LIFETIME:
                        intensity = max(0, 1.0 - (age / TRAIL_LIFETIME))
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

    def run(self):
        print("BLIND LABYRINTH - Tournament Edition Running!")
        try:
            while self.engine.running:
                self.process_inputs()
                self.render()
                time.sleep(0.03) 
        except KeyboardInterrupt: pass
        finally: self.engine.stop()

if __name__ == "__main__":
    game = FogRunGame()
    game.run()