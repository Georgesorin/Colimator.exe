"""
RAY WARS
════════
16x32 LED matrix game. Two teams fight across a 2-row dividing line.

Layout:
  Rows  0-14  → Team A territory (fires rays DOWNWARD, direction +1)
  Rows 15-16  → Dividing line (2 rows — equal halves: 15 each)
  Rows 17-31  → Team B territory (fires rays UPWARD, direction -1)

Rules:
  - A player standing on the same tile for CHARGE_TIME seconds fires a ray.
  - Every active tile fires independently — no cap on concurrent rays.
  - Ray is RAY_LENGTH LEDs tall, travels straight toward the enemy half.
  - If any ray cell overlaps an enemy player's tile → that team loses 1 heart.
  - Hit shows a yellow cross (center + N/S/E/W neighbors) for 0.35s.
  - 5 hearts per team. Lose all 5 → game over.
  - Ray speed increases over time.
  - Team A rays are always RED. Team B rays are always BLUE.

Input:
  Physical tile activation received as a 1373-byte UDP packet.
  Each lit tile = 0xCC in the channel payload; dark = 0x00.
  No virtual buttons — the only input is where players physically stand.

Networking:
  UDP framing: 0x75 header, 0x3344 start / 0x8877 data / 0x5566 end.
"""

import socket
import time
import threading
import random
import json
import os

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ray_wars_config.json")

def _load_config():
    defaults = {
        "device_ip":  "127.0.0.1",
        "send_port":  6766,
        "recv_port":  6767,
    }
    try:
        if os.path.exists(_CFG_FILE):
            with open(_CFG_FILE, encoding="utf-8") as f:
                return {**defaults, **json.load(f)}
    except Exception:
        pass
    return defaults

CONFIG          = _load_config()
UDP_SEND_IP     = CONFIG["device_ip"]
UDP_SEND_PORT   = CONFIG["send_port"]
UDP_LISTEN_PORT = CONFIG["recv_port"]

# ──────────────────────────────────────────────────────────────
# Matrix constants
# ──────────────────────────────────────────────────────────────
BOARD_W      = 16
BOARD_H      = 32
NUM_CHANNELS = 8
LEDS_PER_CH  = 64
FRAME_LEN    = NUM_CHANNELS * LEDS_PER_CH * 3   # 1536 bytes

# Divider is 2 rows wide — gives each team exactly 15 rows of play area
DIVIDER_TOP    = 15   # first divider row  — Team A plays rows  0..14
DIVIDER_BOTTOM = 16   # second divider row — Team B plays rows 17..31

# ──────────────────────────────────────────────────────────────
# Game parameters
# ──────────────────────────────────────────────────────────────
MAX_HEARTS      = 5
RAY_LENGTH      = 4      # cells
CHARGE_TIME     = 1.5    # seconds standing still to fire
# No cap on rays — every active tile fires independently

GAMEOVER_IDLE_DELAY = 10.0   # seconds before win screen clears

# Speed presets — (ray_speed_start, ray_speed_min, accel_interval, accel_step)
# Adjust after testing as needed.
SPEED_PRESETS = {
    "slow":   (0.28, 0.08, 10.0, 0.02),
    "medium": (0.20, 0.04,  6.7, 0.02),
    "fast":   (0.12, 0.02,  4.0, 0.02),
}
DEFAULT_SPEED = "medium"

# Active values (set by start_game)
RAY_SPEED_START = SPEED_PRESETS[DEFAULT_SPEED][0]
RAY_SPEED_MIN   = SPEED_PRESETS[DEFAULT_SPEED][1]
ACCEL_INTERVAL  = SPEED_PRESETS[DEFAULT_SPEED][2]
ACCEL_STEP      = SPEED_PRESETS[DEFAULT_SPEED][3]

# ──────────────────────────────────────────────────────────────
# Colors  (R, G, B)
# ──────────────────────────────────────────────────────────────
BLACK        = (0,   0,   0)
WHITE        = (255, 255, 255)
GRAY         = (55,  55,  55)
TEAM_A_COLOR = (220,  40,  40)   # red  — Team A players + rays
TEAM_B_COLOR = ( 30,  80, 220)   # blue — Team B players + rays
HEART_FULL   = (220,  30,  30)
HEART_EMPTY  = ( 55,   0,   0)
HIT_COLOR    = (255, 220,   0)   # yellow cross on hit


def _dim(color, f):
    return tuple(max(0, min(255, int(c * f))) for c in color)


# ──────────────────────────────────────────────────────────────
# Pixel buffer helpers
# ──────────────────────────────────────────────────────────────
def make_buf():
    return [[BLACK] * BOARD_W for _ in range(BOARD_H)]

def px(buf, col, row, color):
    if 0 <= col < BOARD_W and 0 <= row < BOARD_H:
        buf[row][col] = color

def px_cross(buf, col, row, color):
    """Draw center + 4-neighbor cross."""
    for dc, dr in [(0,0),(0,1),(0,-1),(1,0),(-1,0)]:
        px(buf, col + dc, row + dr, color)


# ──────────────────────────────────────────────────────────────
# Input packet decoder
# ──────────────────────────────────────────────────────────────
def decode_input(data):
    """Convert 1373-byte hardware packet → set of active (col, row) tiles."""
    active = set()
    if len(data) < 1373 or data[0] != 0x88 or data[1] != 0x01:
        return active
    for ch in range(NUM_CHANNELS):
        base = 2 + ch * 171
        for led in range(64):
            if data[base + 1 + led] == 0xCC:
                row_in_ch = led // 16
                col_raw   = led % 16
                col = col_raw if row_in_ch % 2 == 0 else (15 - col_raw)
                row = ch * 4 + row_in_ch
                active.add((col, row))
    return active


# ──────────────────────────────────────────────────────────────
# Frame encoder
# ──────────────────────────────────────────────────────────────
def encode_frame(buf):
    """2D color buffer → raw LED frame bytes."""
    frame      = bytearray(FRAME_LEN)
    block_size = NUM_CHANNELS * 3
    for row in range(BOARD_H):
        ch        = row // 4
        row_in_ch = row % 4
        for col in range(BOARD_W):
            led = (row_in_ch * 16 + col) if row_in_ch % 2 == 0 \
                  else (row_in_ch * 16 + (15 - col))
            off = led * block_size + ch
            r, g, b = buf[row][col]
            if off + NUM_CHANNELS * 2 < FRAME_LEN:
                frame[off]                  = g   # hardware G-first swap
                frame[off + NUM_CHANNELS]   = r
                frame[off + NUM_CHANNELS*2] = b
    return frame


# ──────────────────────────────────────────────────────────────
# Ray
# ──────────────────────────────────────────────────────────────
class Ray:
    """
    Travels along a fixed column.
    direction = +1  →  downward  (Team A → Team B)
    direction = -1  →  upward    (Team B → Team A)
    head = leading row index.
    """
    def __init__(self, col, head, direction, owner_team):
        self.col        = col
        self.head       = head
        self.direction  = direction
        self.owner_team = owner_team          # 0 = A (red), 1 = B (blue)
        self.color      = TEAM_A_COLOR if owner_team == 0 else TEAM_B_COLOR
        self.alive      = True

    def step(self):
        self.head += self.direction

    def cells(self):
        """(col, row) from head to tail."""
        return [
            (self.col, self.head - i * self.direction)
            for i in range(RAY_LENGTH)
        ]

    def fully_out(self):
        tail = self.head - (RAY_LENGTH - 1) * self.direction
        return (self.direction == 1  and tail >= BOARD_H) or \
               (self.direction == -1 and tail < 0)


# ──────────────────────────────────────────────────────────────
# Game
# ──────────────────────────────────────────────────────────────
class RayWarsGame:

    def __init__(self):
        self.lock         = threading.Lock()
        self.running      = True
        self.active_tiles: set = set()   # updated by network thread
        self.idle_event   = threading.Event()  # set when game enters IDLE
        self._init_state()

    # ── init / reset ──────────────────────────────────────────
    def _init_state(self):
        self.state  = "LOBBY"
        self.hearts = [MAX_HEARTS, MAX_HEARTS]
        self.rays: list[Ray] = []

        # Speed attrs — overwritten by start_game; use module defaults here
        self._speed_start    = RAY_SPEED_START
        self._speed_min      = RAY_SPEED_MIN
        self._accel_interval = ACCEL_INTERVAL
        self._accel_step     = ACCEL_STEP
        self.ray_speed       = RAY_SPEED_START
        self._next_step_t    = 0.0
        self._last_accel_t   = 0.0

        # (col, row) → timestamp when the player first stood still there
        self._charge: dict = {}

        # Flash effects: list of (col, row, color, expire_time)
        self._flashes = []

        self._winner      = None
        self._gameover_t  = 0.0
        self._countdown_t = 0.0

    # ── idle callback (called from tick, lock held) ──────────
    def _on_idle(self):
        """Called when gameover screen expires → clears board and wakes terminal."""
        self.idle_event.set()

    # ── public ────────────────────────────────────────────────
    def start_game(self, speed="medium"):
        with self.lock:
            self._init_state()
            preset = SPEED_PRESETS.get(speed, SPEED_PRESETS[DEFAULT_SPEED])
            self._speed_start    = preset[0]
            self._speed_min      = preset[1]
            self._accel_interval = preset[2]
            self._accel_step     = preset[3]
            self.ray_speed       = self._speed_start
            self.state           = "COUNTDOWN"
            self._countdown_t    = time.time()
            print(f"[RayWars] Countdown started! Speed: {speed}")

    # ── main tick (~60 Hz) ────────────────────────────────────
    def tick(self):
        now = time.time()
        with self.lock:
            if self.state in ("LOBBY", "IDLE"):
                return
            if self.state == "COUNTDOWN":
                self._tick_countdown(now)
                return
            if self.state == "GAMEOVER":
                if now - self._gameover_t >= GAMEOVER_IDLE_DELAY:
                    self.state = "IDLE"
                    self._on_idle()   # signal terminal thread
                return
            self._tick_speed(now)
            self._tick_charge(now)
            self._tick_rays(now)
            self._tick_hits(now)
            self._clean_flashes(now)

    # ── countdown ─────────────────────────────────────────────
    def _tick_countdown(self, now):
        if now - self._countdown_t >= 3.5:
            self.state         = "PLAYING"
            self._next_step_t  = now + self.ray_speed
            self._last_accel_t = now
            print("[RayWars] FIGHT!")

    def _countdown_num(self):
        elapsed = time.time() - self._countdown_t
        return max(1, 3 - int(elapsed))

    # ── speed ramp ────────────────────────────────────────────
    def _tick_speed(self, now):
        if now - self._last_accel_t >= self._accel_interval:
            self.ray_speed     = max(self._speed_min, self.ray_speed - self._accel_step)
            self._last_accel_t = now

    # ── charge & fire ─────────────────────────────────────────
    def _tick_charge(self, now):
        tiles = self.active_tiles

        # Drop charge for tiles no longer active
        for pos in list(self._charge):
            if pos not in tiles:
                del self._charge[pos]

        for (col, row) in tiles:
            # Ignore divider rows and out-of-bounds
            if DIVIDER_TOP <= row <= DIVIDER_BOTTOM:
                continue
            if row < 0 or row >= BOARD_H:
                continue

            team = 0 if row < DIVIDER_TOP else 1
            pos  = (col, row)

            if pos not in self._charge:
                self._charge[pos] = now
            elif now - self._charge[pos] >= CHARGE_TIME:
                self._fire(col, row, team)
                self._charge[pos] = now   # reset — must stand again to re-fire

    def _fire(self, col, row, team):
        direction = +1 if team == 0 else -1
        head      = row + direction   # one step ahead of the player
        self.rays.append(Ray(col, head, direction, team))
        print(f"[RayWars] Team {'A' if team==0 else 'B'} fired — col={col} row={row}")

    # ── ray movement ──────────────────────────────────────────
    def _tick_rays(self, now):
        if now < self._next_step_t:
            return
        self._next_step_t = now + self.ray_speed

        alive = []
        for ray in self.rays:
            ray.step()
            if not ray.fully_out():
                alive.append(ray)
        self.rays = alive

    # ── hit detection ─────────────────────────────────────────
    def _tick_hits(self, now):
        tiles = self.active_tiles
        for ray in list(self.rays):
            if not ray.alive:
                continue
            for (rcol, rrow) in ray.cells():
                if (rcol, rrow) not in tiles:
                    continue
                # Skip divider zone
                if DIVIDER_TOP <= rrow <= DIVIDER_BOTTOM:
                    continue
                hit_team = 0 if rrow < DIVIDER_TOP else 1
                # Rays don't hurt their own team
                if hit_team == ray.owner_team:
                    continue

                # ── HIT ──
                self.hearts[hit_team] = max(0, self.hearts[hit_team] - 1)

                # Yellow cross flash at hit location
                for dc, dr in [(0,0),(0,1),(0,-1),(1,0),(-1,0)]:
                    self._flashes.append((rcol+dc, rrow+dr, HIT_COLOR, now + 0.35))

                ray.alive = False

                if self.hearts[hit_team] == 0:
                    self._winner    = 1 - hit_team
                    self.state      = "GAMEOVER"
                    self._gameover_t = now
                    print(f"[RayWars] GAME OVER! "
                          f"Team {'A' if self._winner==0 else 'B'} WINS!")
                break   # one hit per ray per tick

        self.rays = [r for r in self.rays if r.alive]

    def _clean_flashes(self, now):
        self._flashes = [(c, r, col, e) for c, r, col, e in self._flashes if e > now]

    # ──────────────────────────────────────────────────────────
    # Renderer
    # ──────────────────────────────────────────────────────────
    def render(self):
        with self.lock:
            buf = make_buf()
            if   self.state == "LOBBY":     self._r_lobby(buf)
            elif self.state == "COUNTDOWN": self._r_countdown(buf)
            elif self.state == "PLAYING":   self._r_playing(buf)
            elif self.state == "GAMEOVER":  self._r_gameover(buf)
            # IDLE: buf stays all-black (make_buf default)
            return encode_frame(buf)

    # ── shared draw helpers ───────────────────────────────────
    def _divider(self, buf):
        for c in range(BOARD_W):
            px(buf, c, DIVIDER_TOP,    GRAY)
            px(buf, c, DIVIDER_BOTTOM, GRAY)

    def _hearts(self, buf):
        start = (BOARD_W - MAX_HEARTS) // 2
        for i in range(MAX_HEARTS):
            px(buf, start + i, 1,          HEART_FULL if i < self.hearts[0] else HEART_EMPTY)
            px(buf, start + i, BOARD_H - 2, HEART_FULL if i < self.hearts[1] else HEART_EMPTY)

    def _players(self, buf):
        """Draw all active player tiles with their team color + charge glow."""
        now = time.time()
        for (col, row) in self.active_tiles:
            if DIVIDER_TOP <= row <= DIVIDER_BOTTOM:
                continue
            team  = 0 if row < DIVIDER_TOP else 1
            color = TEAM_A_COLOR if team == 0 else TEAM_B_COLOR
            px(buf, col, row, color)

            # Charge glow: pixel ahead of player brightens as charge builds
            pos = (col, row)
            if pos in self._charge:
                prog  = min(1.0, (now - self._charge[pos]) / CHARGE_TIME)
                ahead = row + (1 if team == 0 else -1)
                px(buf, col, ahead, _dim(WHITE, prog * 0.65))

    def _rays_draw(self, buf):
        for ray in self.rays:
            cells = ray.cells()
            n     = len(cells)
            for i, (c, r) in enumerate(cells):
                brightness = 1.0 - (i / n) * 0.70   # head full, tail 30%
                px(buf, c, r, _dim(ray.color, brightness))

    def _flashes_draw(self, buf):
        now = time.time()
        for col, row, color, exp in self._flashes:
            if exp > now:
                px(buf, col, row, color)

    # ── state screens ─────────────────────────────────────────
    def _r_lobby(self, buf):
        self._divider(buf)
        t     = time.time()
        blink = (t % 1.0) < 0.5
        strip = _dim(GRAY, 0.5) if blink else GRAY
        for c in range(BOARD_W):
            px(buf, c, DIVIDER_TOP,    strip)
            px(buf, c, DIVIDER_BOTTOM, strip)
        # Faint team color hints
        for c in range(BOARD_W):
            px(buf, c, 3,           _dim(TEAM_A_COLOR, 0.35))
            px(buf, c, BOARD_H - 4, _dim(TEAM_B_COLOR, 0.35))

    def _r_countdown(self, buf):
        self._divider(buf)
        self._hearts(buf)
        n = self._countdown_num()
        self._digit(buf, n, col=6, row=5,  color=TEAM_A_COLOR)
        self._digit(buf, n, col=6, row=20, color=TEAM_B_COLOR)

    def _r_playing(self, buf):
        self._divider(buf)
        self._hearts(buf)
        self._rays_draw(buf)
        self._players(buf)
        self._flashes_draw(buf)   # drawn last so cross is always visible

    # ── "WIN" 5×5 pixel font (col-offset, row-offset) per letter ─
    #   Each letter is drawn in a 5-wide × 5-tall cell.
    #   Letters: W, I, N  — total width = 5+1+3+1+5 = 15 cols (fits in 16)
    _WIN_GLYPHS = {
        'W': [
            (0,0),(4,0),
            (0,1),(4,1),
            (0,2),(2,2),(4,2),
            (0,3),(2,3),(4,3),
            (1,4),(3,4),
        ],
        'I': [
            (0,0),(1,0),(2,0),
            (1,1),
            (1,2),
            (1,3),
            (0,4),(1,4),(2,4),
        ],
        'N': [
            (0,0),(4,0),
            (0,1),(1,1),(4,1),
            (0,2),(2,2),(4,2),
            (0,3),(3,3),(4,3),
            (0,4),(4,4),
        ],
    }

    def _draw_win(self, buf, top_row, color):
        """Draw 'WIN' centred horizontally in the band starting at top_row."""
        # W=5 wide, I=3 wide, N=5 wide, 1-px gap between → total 15, fits in 16
        letters   = [('W', 5), ('I', 3), ('N', 5)]
        gap       = 1
        total_w   = sum(w for _, w in letters) + gap * (len(letters) - 1)
        start_col = (BOARD_W - total_w) // 2  # centre horizontally

        col = start_col
        for ch, w in letters:
            for dc, dr in self._WIN_GLYPHS[ch]:
                px(buf, col + dc, top_row + dr, color)
            col += w + gap

    def _r_gameover(self, buf):
        self._divider(buf)
        self._hearts(buf)
        if self._winner is None:
            return

        now  = time.time()
        wc   = TEAM_A_COLOR if self._winner == 0 else TEAM_B_COLOR

        # Pulsing background glow on the winner's half
        pulse = 0.25 + 0.20 * abs((((now - self._gameover_t) * 1.5) % 2.0) - 1.0)
        if self._winner == 0:
            rows = range(0, DIVIDER_TOP)
        else:
            rows = range(DIVIDER_BOTTOM + 1, BOARD_H)
        for r in rows:
            for c in range(BOARD_W):
                px(buf, c, r, _dim(wc, pulse * 0.4))

        # "WIN" text — centred vertically in the winner's zone, row 4 or 22
        if self._winner == 0:
            text_top = (DIVIDER_TOP - 5) // 2          # centre in rows 0-14
        else:
            text_top = DIVIDER_BOTTOM + 1 + ((BOARD_H - DIVIDER_BOTTOM - 1 - 5) // 2)

        # Bright flash: text alternates between full and dimmed brightness
        flash_bright = int((now - self._gameover_t) * 3) % 2 == 0
        text_color   = wc if flash_bright else _dim(wc, 0.45)
        self._draw_win(buf, text_top, text_color)

    # ── 3×5 digit ─────────────────────────────────────────────
    _SEGS = {
        1: [(1,0),(1,1),(1,2),(1,3),(1,4)],
        2: [(0,0),(1,0),(2,0),(2,1),(1,2),(0,2),(0,3),(0,4),(1,4),(2,4)],
        3: [(0,0),(1,0),(2,0),(2,1),(1,2),(2,2),(2,3),(0,4),(1,4),(2,4)],
    }

    def _digit(self, buf, n, col, row, color):
        for dc, dr in self._SEGS.get(n, []):
            px(buf, col + dc, row + dr, color)


# ──────────────────────────────────────────────────────────────
# Network Manager
# ──────────────────────────────────────────────────────────────
class NetworkManager:

    def __init__(self, game: RayWarsGame):
        self.game    = game
        self.running = True
        self._seq    = 0

        self._tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._tx.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        self._rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._rx.settimeout(0.5)
        try:
            self._rx.bind(("0.0.0.0", UDP_LISTEN_PORT))
            print(f"[Net] RX on :{UDP_LISTEN_PORT}")
        except Exception as e:
            print(f"[Net] Cannot bind RX: {e}")
            self.running = False

    def _send(self, pkt):
        try: self._tx.sendto(pkt, (UDP_SEND_IP,  UDP_SEND_PORT))
        except: pass
        try: self._tx.sendto(pkt, ("127.0.0.1",  UDP_SEND_PORT))
        except: pass

    def _send_frame(self, frame):
        self._seq = (self._seq % 0xFFFF) + 1
        s = self._seq
        r = lambda: random.randint(0, 127)

        # 1. Start (0x3344)
        self._send(bytearray([
            0x75, r(), r(), 0x00, 0x08,
            0x02, 0x00, 0x00, 0x33, 0x44,
            s >> 8, s & 0xFF, 0x00, 0x00, 0x00, 0x0E, 0x00]))

        # 2. Channel config (0xFFF0)
        pl = bytearray()
        for _ in range(NUM_CHANNELS):
            pl += bytes([LEDS_PER_CH >> 8, LEDS_PER_CH & 0xFF])
        inner = bytearray([0x02, 0x00, 0x00, 0x88, 0x77,
                            0xFF, 0xF0, len(pl) >> 8, len(pl) & 0xFF]) + pl
        n = len(inner) - 1
        pkt = bytearray([0x75, r(), r(), n >> 8, n & 0xFF]) + inner + bytearray([0x1E, 0x00])
        self._send(pkt)

        # 3. Data chunks (0x8877)
        CHUNK = 984
        idx   = 1
        for i in range(0, len(frame), CHUNK):
            chunk = frame[i:i + CHUNK]
            inner = bytearray([0x02, 0x00, 0x00, 0x88, 0x77,
                                idx >> 8, idx & 0xFF,
                                len(chunk) >> 8, len(chunk) & 0xFF]) + chunk
            n   = len(inner) - 1
            pkt = bytearray([0x75, r(), r(), n >> 8, n & 0xFF]) + inner
            pkt += bytearray([0x1E if len(chunk) == CHUNK else 0x36, 0x00])
            self._send(pkt)
            idx += 1
            time.sleep(0.004)

        # 4. End (0x5566)
        self._send(bytearray([
            0x75, r(), r(), 0x00, 0x08,
            0x02, 0x00, 0x00, 0x55, 0x66,
            s >> 8, s & 0xFF, 0x00, 0x00, 0x00, 0x0E, 0x00]))

    def _send_loop(self):
        while self.running:
            self._send_frame(self.game.render())
            time.sleep(0.04)

    def _recv_loop(self):
        while self.running:
            try:
                data, _ = self._rx.recvfrom(2048)
                if len(data) >= 1373 and data[0] == 0x88 and data[1] == 0x01:
                    tiles = decode_input(data)
                    with self.game.lock:
                        self.game.active_tiles = tiles
            except socket.timeout:
                pass
            except Exception:
                pass

    def start(self):
        for fn in (self._send_loop, self._recv_loop):
            threading.Thread(target=fn, daemon=True).start()


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────
def _game_loop(game):
    while game.running:
        game.tick()
        time.sleep(0.016)

if __name__ == "__main__":
    # ── optional: import external screen manager ──────────────
    try:
        import ray_wars_screens as _screens
        _HAS_SCREENS = True
    except ImportError:
        _HAS_SCREENS = False

    game = RayWarsGame()
    net  = NetworkManager(game)
    net.start()
    threading.Thread(target=_game_loop, args=(game,), daemon=True).start()

    SPEED_HELP = (
        "  slow   — relaxed pace, rays start slow and stay slow\n"
        "  medium — balanced pace (default)\n"
        "  fast   — aggressive pace, rays accelerate quickly\n"
    )

    def print_banner():
        print(f"""
╔═══════════════════════════════════════════╗
║              RAY WARS                    ║
╠═══════════════════════════════════════════╣
║  slow   — start a slow game              ║
║  medium — start a medium game            ║
║  fast   — start a fast game              ║
║  status — print live state              ║
║  quit   — exit                          ║
╚═══════════════════════════════════════════╝

  Team A (RED)  = rows  0-14   fires DOWN
  Divider       = rows 15-16
  Team B (BLUE) = rows 17-31   fires UP

  Stand still {CHARGE_TIME}s on any tile to fire a ray.
  Every foot = a potential ray. No cap.
  First team to lose all {MAX_HEARTS} hearts loses.
""")

    def prompt_speed():
        """Print play-again prompt and return chosen speed (or None to quit)."""
        print("\n╔═══════════════════════════════════════════╗")
        print("║          PLAY AGAIN?                    ║")
        print("╠═══════════════════════════════════════════╣")
        print("║  slow / medium / fast — pick a speed    ║")
        print("║  quit                 — exit            ║")
        print("╚═══════════════════════════════════════════╝")

    print_banner()

    def idle_watcher():
        """Background thread: wakes the main input loop when IDLE is reached."""
        while game.running:
            game.idle_event.wait()
            if not game.running:
                break
            game.idle_event.clear()
            prompt_speed()

    threading.Thread(target=idle_watcher, daemon=True).start()

    # ── terminal input loop (runs in a background thread when screens are active)
    def _terminal_loop():
        try:
            while game.running:
                cmd = input("> ").strip().lower()
                if cmd in ("quit", "q", "exit"):
                    game.running = False
                    net.running  = False
                    game.idle_event.set()
                elif cmd in ("slow", "medium", "fast"):
                    game.start_game(speed=cmd)
                elif cmd == "status":
                    with game.lock:
                        print(f"  state  : {game.state}")
                        print(f"  hearts : A={game.hearts[0]}  B={game.hearts[1]}")
                        print(f"  rays   : {len(game.rays)} active")
                        print(f"  speed  : {game.ray_speed:.3f}s/step")
                        print(f"  tiles  : {sorted(game.active_tiles)}")
                else:
                    print("Commands: slow | medium | fast | status | quit")
        except (KeyboardInterrupt, EOFError):
            game.running = False
            net.running  = False
            game.idle_event.set()

    if _HAS_SCREENS:
        # Terminal runs in background; Tkinter mainloop owns the main thread
        print("[Screens] External monitors active. Terminal still accepts commands.")
        threading.Thread(target=_terminal_loop, daemon=True).start()
        try:
            _screens.launch(game)
        except Exception as e:
            print(f"[Screens] Tkinter error: {e} — falling back to terminal only.")
            _terminal_loop()
    else:
        print("[Screens] ray_wars_screens.py not found — terminal only mode.")
        _terminal_loop()

    net.running = False
    print("Bye.")