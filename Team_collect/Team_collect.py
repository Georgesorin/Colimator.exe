"""
Evil Eye – Arena Game
=====================
Two teams, two walls each, LED panels, pressure tiles and a motion-sensor Eye.

Hardware layout  (per wall / channel):
  LED 0  = The Eye  (motion sensor)
  LED 1-10 = Pressure tiles

Channels / walls:
  Team A : channels 1 (South) and 2 (East)
  Team B : channels 3 (North) and 4 (West)

Run with:  python EvilEyeGame.py
"""

import json, os, queue, random, socket, threading, time, tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import struct

# ─────────────────────────────────────────────────────────────────────────────
# Protocol constants  (identical to Controller.py)
# ─────────────────────────────────────────────────────────────────────────────
UDP_DEVICE_PORT   = 4626
UDP_RECEIVER_PORT = 7800
NUM_CHANNELS      = 4
LEDS_PER_CHANNEL  = 11
FRAME_DATA_LEN    = LEDS_PER_CHANNEL * NUM_CHANNELS * 3   # 132 bytes

HARDWARE_IP       = "169.254.182.44"   # real hardware target

PASSWORD_ARRAY = [
    35,  63, 187,  69, 107, 178,  92,  76,  39,  69, 205,  37, 223, 255, 165, 231,
    16, 220,  99,  61,  25, 203, 203, 155, 107,  30,  92, 144, 218, 194, 226,  88,
   196, 190,  67, 195, 159, 185, 209,  24, 163,  65,  25, 172, 126,  63, 224,  61,
   160,  80, 125,  91, 239, 144,  25, 141, 183, 204, 171, 188, 255, 162, 104, 225,
   186,  91, 232,   3, 100, 208,  49, 211,  37, 192,  20,  99,  27,  92, 147, 152,
    86, 177,  53, 153,  94, 177, 200,  33, 175, 195,  15, 228, 247,  18, 244, 150,
   165, 229, 212,  96,  84, 200, 168, 191,  38, 112, 171, 116, 121, 186, 147, 203,
    30, 118, 115, 159, 238, 139,  60,  57, 235, 213, 159, 198, 160,  50,  97, 201,
   253, 242, 240,  77, 102,  12, 183, 235, 243, 247,  75,  90,  13, 236,  56, 133,
   150, 128, 138, 190, 140,  13, 213,  18,   7, 117, 255,  45,  69, 214, 179,  50,
    28,  66, 123, 239, 190,  73, 142, 218, 253,   5, 212, 174, 152,  75, 226, 226,
   172,  78,  35,  93, 250, 238,  19,  32, 247, 223,  89, 123,  86, 138, 150, 146,
   214, 192,  93, 152, 156, 211,  67,  51, 195, 165,  66,  10,  10,  31,   1, 198,
   234, 135,  34, 128, 208, 200, 213, 169, 238,  74, 221, 208, 104, 170, 166,  36,
    76, 177, 196,   3, 141, 167, 127,  56, 177, 203,  45, 107,  46,  82, 217, 139,
   168,  45, 198,   6,  43,  11,  57,  88, 182,  84, 189,  29,  35, 143, 138, 171,
]

# ─────────────────────────────────────────────────────────────────────────────
# Protocol helpers
# ─────────────────────────────────────────────────────────────────────────────
def _chk(data):
    idx = sum(data) & 0xFF
    return PASSWORD_ARRAY[idx] if idx < len(PASSWORD_ARRAY) else 0

def build_start_packet(seq):
    pkt = bytearray([0x75, random.randint(0,127), random.randint(0,127),
                     0x00, 0x08, 0x02, 0x00, 0x00, 0x33, 0x44,
                     (seq>>8)&0xFF, seq&0xFF, 0x00, 0x00])
    pkt.append(_chk(pkt)); return bytes(pkt)

def build_end_packet(seq):
    pkt = bytearray([0x75, random.randint(0,127), random.randint(0,127),
                     0x00, 0x08, 0x02, 0x00, 0x00, 0x55, 0x66,
                     (seq>>8)&0xFF, seq&0xFF, 0x00, 0x00])
    pkt.append(_chk(pkt)); return bytes(pkt)

def build_fff0_packet(seq):
    payload = bytearray()
    for _ in range(NUM_CHANNELS):
        payload += bytes([(LEDS_PER_CHANNEL>>8)&0xFF, LEDS_PER_CHANNEL&0xFF])
    return build_command_packet(0x8877, 0xFFF0, bytes(payload), seq)

def build_command_packet(data_id, msg_loc, payload, seq):
    internal = bytes([0x02, 0x00, 0x00,
                      (data_id>>8)&0xFF, data_id&0xFF,
                      (msg_loc>>8)&0xFF, msg_loc&0xFF,
                      (len(payload)>>8)&0xFF, len(payload)&0xFF]) + payload
    hdr = bytes([0x75, random.randint(0,127), random.randint(0,127),
                 (len(internal)>>8)&0xFF, len(internal)&0xFF])
    pkt = bytearray(hdr + internal)
    pkt[10] = (seq>>8)&0xFF; pkt[11] = seq&0xFF
    pkt.append(_chk(pkt)); return bytes(pkt)

def build_frame_data(led_states):
    """led_states: {(ch 1-4, led 0-10): (r,g,b)}"""
    frame = bytearray(FRAME_DATA_LEN)
    for (ch, led), (r, g, b) in led_states.items():
        ci = ch - 1
        if 0 <= ci < NUM_CHANNELS and 0 <= led < LEDS_PER_CHANNEL:
            frame[led*12 + ci]     = g
            frame[led*12 + 4 + ci] = r
            frame[led*12 + 8 + ci] = b
    return bytes(frame)

# ─────────────────────────────────────────────────────────────────────────────
# Lightweight network service  (send + receive)
# ─────────────────────────────────────────────────────────────────────────────
class NetService:
    def __init__(self, device_ip, send_port=4626, recv_port=7800):
        self._ip   = device_ip
        self._sp   = send_port
        self._rp   = recv_port
        self._seq  = 0
        self._lock = threading.Lock()
        self._sq   = queue.Queue(maxsize=6)
        self._running = True

        self.on_button = None   # callback(ch, led)  – rising edge only
        self._prev     = {}

        threading.Thread(target=self._send_loop, daemon=True).start()
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def _next_seq(self):
        with self._lock:
            self._seq = (self._seq + 1) & 0xFFFF
            return self._seq

    def push_frame(self, led_states):
        frame = build_frame_data(led_states)
        try: self._sq.put_nowait((self._ip, frame))
        except queue.Full: pass

    def _send_loop(self):
        while self._running:
            try: ip, frame = self._sq.get(timeout=0.5)
            except queue.Empty: continue
            seq = self._next_seq()
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                ep = (ip, self._sp)
                s.sendto(build_start_packet(seq), ep);   time.sleep(0.008)
                s.sendto(build_fff0_packet(seq), ep);    time.sleep(0.008)
                s.sendto(build_command_packet(0x8877, 0x0000, frame, seq), ep); time.sleep(0.008)
                s.sendto(build_end_packet(seq), ep)
                s.close()
            except: pass
            self._sq.task_done()

    def _recv_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.5)
        try: sock.bind(("0.0.0.0", self._rp))
        except: pass
        while self._running:
            try: data, _ = sock.recvfrom(1024)
            except socket.timeout: continue
            except: break
            if len(data) != 687 or data[0] != 0x88: continue
            if sum(data[:-1]) & 0xFF != data[-1]:   continue
            for ch in range(1, NUM_CHANNELS+1):
                base = 2 + (ch-1)*171
                for idx in range(LEDS_PER_CHANNEL):
                    val   = data[base + 1 + idx]
                    trig  = (val == 0xCC)
                    prev  = self._prev.get((ch, idx), False)
                    if trig and not prev:          # rising edge
                        if self.on_button: self.on_button(ch, idx)
                    self._prev[(ch, idx)] = trig

    def stop(self):
        self._running = False

# ─────────────────────────────────────────────────────────────────────────────
# Game constants
# ─────────────────────────────────────────────────────────────────────────────
# Colors  (r, g, b)
C_OFF      = (0,   0,   0)
C_WHITE    = (200, 200, 200)
C_YELLOW   = (255, 180,   0)
C_BLUE     = (0,    80, 255)
C_RED      = (220,   0,   0)
C_RED_DIM  = (80,    0,   0)
C_PURPLE   = (160,   0, 200)
C_GREEN    = (0,   200,   0)
C_BLINK    = (255, 255,   0)   # eye blinking colour
C_GOLD     = (255, 200,   0)   # incoming eye wall highlight

# Tile types
IDLE       = "idle"
POINT      = "point"
REDIRECT   = "redirect"   # easy powerup / hard powerup-A
STOP       = "stop"        # hard powerup-B
HIDE       = "hide"        # hard powerup-C

# Teams
TEAM_A = "A"   # channels 1 & 2
TEAM_B = "B"   # channels 3 & 4
TEAM_CHANNELS = {TEAM_A: [1, 2], TEAM_B: [3, 4]}
CHANNEL_TEAM  = {1: TEAM_A, 2: TEAM_A, 3: TEAM_B, 4: TEAM_B}

WALL_NAMES    = {1: "South", 2: "East", 3: "North", 4: "West"}

POINTS_TO_WIN = 7
GAME_DURATION = 5 * 60   # 5 minutes in seconds

# ─────────────────────────────────────────────────────────────────────────────
# Game state
# ─────────────────────────────────────────────────────────────────────────────
class GameState:
    def __init__(self, difficulty, players_per_team):
        self.difficulty        = difficulty   # "easy" | "hard"
        self.players_per_team  = players_per_team
        self.scores            = {TEAM_A: 0, TEAM_B: 0}
        self.tile_types        = {}   # (ch, led) -> tile type str
        self.tile_colors       = {}   # (ch, led) -> (r,g,b) currently shown
        self.hidden_team       = None   # team whose tiles are hidden (hide powerup)
        self.hidden_until      = 0.0
        self.eye_stopped       = False
        self.eye_stop_until    = 0.0
        self.eye_channel       = None   # current wall the eye is on (1-4)
        self.eye_blinking      = False
        self.next_eye_channel  = None
        self.start_time        = None
        self.ended             = False
        self.winner            = None
        self.end_reason        = None

    def elapsed(self):
        if not self.start_time: return 0
        return time.time() - self.start_time

    def remaining(self):
        return max(0, GAME_DURATION - self.elapsed())

# ─────────────────────────────────────────────────────────────────────────────
# Tile layout helpers
# ─────────────────────────────────────────────────────────────────────────────
def assign_team_tiles(difficulty, team):
    """
    Assign tile types across BOTH walls of a team (20 tiles total, LEDs 1-10
    on each of the two channels).

    Active tiles on the map at game start, per team (two walls combined):
      Easy : 2 POINT  + 1 REDIRECT  → 3 active,  17 IDLE
      Hard : 2 POINT  + 1 REDIRECT  → only 2 redirect total per team across
             the whole game, but the MAP starts with 2 POINT + 1 powerup too.
             Hard initial layout same as easy: 2 POINT + 1 powerup (chosen
             randomly from the hard pool for variety).

    The remaining tiles are all IDLE (white).
    """
    channels = TEAM_CHANNELS[team]
    # Build a flat list of 20 slots, all idle to start
    slots = [(ch, led) for ch in channels for led in range(1, 11)]

    # Choose initial active tiles: 2 points + 1 powerup
    chosen = random.sample(slots, 3)
    tile_map = {s: IDLE for s in slots}
    tile_map[chosen[0]] = POINT
    tile_map[chosen[1]] = POINT
    if difficulty == "easy":
        tile_map[chosen[2]] = REDIRECT
    else:
        # Hard: pick one powerup type at random from the hard pool for the
        # initial tile, but don't consume from the respawn pool yet
        tile_map[chosen[2]] = random.choice([REDIRECT, STOP, HIDE])

    return tile_map


def tile_color_for(ttype, hidden=False):
    """Return the (r,g,b) a tile should show in its current state."""
    if hidden:        return C_OFF
    if ttype == IDLE:     return C_WHITE
    if ttype == POINT:    return C_YELLOW
    if ttype == REDIRECT: return C_BLUE
    if ttype == STOP:     return C_RED_DIM
    if ttype == HIDE:     return C_PURPLE
    return C_WHITE


def powerup_pool_for(difficulty):
    """
    Respawn pool of powerups available to a team across the whole game.
    Easy : 3 redirects total (one is already on the map, 2 left to respawn)
    Hard : 2 redirect + 2 stop + 1 hide  (one already on map, rest to respawn)
    We keep the full pool here; the engine pops from it when a powerup is
    consumed and needs replacing.
    """
    if difficulty == "easy":
        return [REDIRECT, REDIRECT, REDIRECT]
    else:
        return [REDIRECT, REDIRECT, STOP, STOP, HIDE]

# ─────────────────────────────────────────────────────────────────────────────
# Main Game Engine
# ─────────────────────────────────────────────────────────────────────────────
class EvilEyeGame:
    """
    Encapsulates the game loop, eye behaviour, and tile logic.
    Communicates via a NetService; also drives a GameUI for display.
    """
    def __init__(self, net: NetService, ui, state: GameState):
        self._net    = net
        self._ui     = ui
        self._gs     = state
        self._lock   = threading.Lock()
        self._timers = []    # (deadline, callback) pending one-shot timers
        self._stop_ev = threading.Event()

        # Per-team powerup pools (drawn from on activation)
        self._pu_pool = {
            TEAM_A: powerup_pool_for(state.difficulty),
            TEAM_B: powerup_pool_for(state.difficulty),
        }

    # ── Start ─────────────────────────────────────────────────────────────────
    def start(self):
        gs = self._gs
        # Assign tiles per team (both walls together) so the map starts with
        # exactly 2 points + 1 powerup per team across their two combined walls.
        for team in (TEAM_A, TEAM_B):
            gs.tile_types.update(assign_team_tiles(gs.difficulty, team))

        gs.start_time = None   # will be set after intro
        threading.Thread(target=self._intro_sequence, daemon=True).start()

    def _intro_sequence(self):
        """Team identification + countdown before game starts."""
        gs = self._gs
        # Phase 1: show team colours (Team A=blue, Team B=red)
        states = {}
        for ch in range(1, 5):
            team = CHANNEL_TEAM[ch]
            col  = C_BLUE if team == TEAM_A else C_RED
            for led in range(1, 11):
                states[(ch, led)] = col
            states[(ch, 0)] = C_OFF   # eye off during intro
        self._send(states)
        self._ui_call("show_intro", "Team A = BLUE  |  Team B = RED", 3)
        time.sleep(3)

        # Phase 2: flash all tiles + turn first eye yellow (2 sec countdown)
        self._ui_call("show_intro", "GET READY!", 2)
        for _ in range(4):
            flash = {}
            for ch in range(1, 5):
                for led in range(0, 11):
                    flash[(ch, led)] = C_WHITE
            self._send(flash)
            time.sleep(0.25)
            self._send(states)
            time.sleep(0.25)

        # Choose starting eye channel
        gs.eye_channel = random.randint(1, 4)
        states[(gs.eye_channel, 0)] = C_BLINK
        self._send(states)
        time.sleep(0.5)
        states[(gs.eye_channel, 0)] = C_RED
        self._send(states)
        time.sleep(0.5)

        # Start proper tile colours
        self._refresh_all_tiles()
        gs.start_time = time.time()
        self._ui_call("game_started")

        # Launch loops
        threading.Thread(target=self._eye_loop,  daemon=True).start()
        threading.Thread(target=self._tick_loop, daemon=True).start()

    # ── Eye loop ──────────────────────────────────────────────────────────────
    def _eye_loop(self):
        gs = self._gs
        stay   = 6.7 if gs.difficulty == "easy" else 5.0
        blink  = 3.0 if gs.difficulty == "easy" else 2.0

        while not self._stop_ev.is_set() and not gs.ended:
            # Wait "stay – blink" time with eye solid red
            wait_solid = stay - blink
            t0 = time.time()
            while time.time() - t0 < wait_solid:
                if self._stop_ev.is_set() or gs.ended: return
                # Handle stop powerup
                if gs.eye_stopped and time.time() < gs.eye_stop_until:
                    time.sleep(0.1)
                    # Reset timer when stop is active
                    t0 = time.time()
                    continue
                else:
                    gs.eye_stopped = False
                time.sleep(0.1)

            if self._stop_ev.is_set() or gs.ended: return

            # Choose next wall
            other_walls = [c for c in range(1, 5) if c != gs.eye_channel]
            gs.next_eye_channel = random.choice(other_walls)
            gs.eye_blinking = True

            # Blink phase: current eye blinks red↔off, next wall turns yellow
            self._set_eye(gs.eye_channel, C_OFF)
            self._set_eye(gs.next_eye_channel, C_GOLD)
            blink_start = time.time()
            blink_state = True
            while time.time() - blink_start < blink:
                if self._stop_ev.is_set() or gs.ended: return
                self._set_eye(gs.eye_channel, C_RED if blink_state else C_OFF)
                blink_state = not blink_state
                time.sleep(0.3)

            # Move eye
            self._set_eye(gs.eye_channel, C_OFF)
            gs.eye_channel = gs.next_eye_channel
            gs.eye_blinking = False
            self._set_eye(gs.eye_channel, C_RED)
            self._ui_call("eye_moved", gs.eye_channel)

    def _set_eye(self, ch, color):
        self._send({(ch, 0): color})

    # ── Tick loop ─────────────────────────────────────────────────────────────
    def _tick_loop(self):
        while not self._stop_ev.is_set() and not self._gs.ended:
            time.sleep(0.5)
            gs = self._gs
            # Check hide expiry
            if gs.hidden_team and time.time() >= gs.hidden_until:
                gs.hidden_team = None
                self._refresh_all_tiles()
            self._ui_call("tick")
            # Time limit
            if gs.remaining() <= 0 and not gs.ended:
                self._end_game("time", None)

    # ── Button handler ────────────────────────────────────────────────────────
    def on_button(self, ch, led):
        """Called from NetService receiver thread on rising edge."""
        gs = self._gs
        if gs.ended or not gs.start_time: return
        if led == 0:
            # Eye / motion sensor
            self._on_eye_trigger(ch)
            return

        ttype = gs.tile_types.get((ch, led))
        if ttype is None: return
        team  = CHANNEL_TEAM[ch]

        if ttype == IDLE:
            return
        elif ttype == POINT:
            gs.scores[team] += 1
            # Remove tile (make idle)
            gs.tile_types[(ch, led)] = IDLE
            self._refresh_tile(ch, led)
            # Spawn a new point tile elsewhere on same walls if possible
            self._spawn_new_point(team)
            self._ui_call("score_update", team, gs.scores[team])
            if gs.scores[team] >= POINTS_TO_WIN:
                self._end_game("score", team)
        else:
            # Powerup
            self._activate_powerup(ch, led, ttype, team)
            gs.tile_types[(ch, led)] = IDLE
            self._refresh_tile(ch, led)
            self._spawn_new_powerup(team)

    def _on_eye_trigger(self, ch):
        """Motion sensor on given channel triggered."""
        gs = self._gs
        if not gs.start_time or gs.ended: return
        team = CHANNEL_TEAM[ch]
        # Check if player count = team size (game end condition)
        # We count triggers as 'players detected'; use a simple counter per team
        if not hasattr(self, "_eye_detections"):
            self._eye_detections = {TEAM_A: 0, TEAM_B: 0}
        self._eye_detections[team] = self._eye_detections.get(team, 0) + 1
        if self._eye_detections[team] >= gs.players_per_team:
            self._end_game("eye", team)

    # ── Powerup effects ───────────────────────────────────────────────────────
    def _activate_powerup(self, ch, led, ptype, activating_team):
        gs = self._gs
        enemy = TEAM_B if activating_team == TEAM_A else TEAM_A

        if ptype == REDIRECT:
            # Move eye to a random wall of the enemy team
            enemy_walls = TEAM_CHANNELS[enemy]
            new_wall = random.choice(enemy_walls)
            old_wall = gs.eye_channel
            self._set_eye(old_wall, C_OFF)
            gs.eye_channel = new_wall
            self._set_eye(new_wall, C_RED)
            self._ui_call("powerup_used", activating_team, "REDIRECT", f"Eye → {WALL_NAMES[new_wall]}")

        elif ptype == STOP:
            stop_duration = 5.0
            gs.eye_stopped   = True
            gs.eye_stop_until = time.time() + stop_duration
            self._ui_call("powerup_used", activating_team, "STOP", f"Eye frozen {stop_duration:.0f}s")

        elif ptype == HIDE:
            hide_duration = 5.0
            gs.hidden_team  = enemy
            gs.hidden_until = time.time() + hide_duration
            self._refresh_all_tiles()
            self._ui_call("powerup_used", activating_team, "HIDE", f"Enemy tiles hidden {hide_duration:.0f}s")

    # ── Tile spawning ─────────────────────────────────────────────────────────
    def _spawn_new_point(self, team):
        gs = self._gs
        idle_tiles = [(ch, led)
                      for ch in TEAM_CHANNELS[team]
                      for led in range(1, 11)
                      if gs.tile_types.get((ch, led)) == IDLE]
        if idle_tiles:
            ch, led = random.choice(idle_tiles)
            gs.tile_types[(ch, led)] = POINT
            self._refresh_tile(ch, led)

    def _spawn_new_powerup(self, team):
        gs = self._gs
        pool = self._pu_pool[team]
        if not pool: return
        ptype = pool.pop(0)
        idle_tiles = [(ch, led)
                      for ch in TEAM_CHANNELS[team]
                      for led in range(1, 11)
                      if gs.tile_types.get((ch, led)) == IDLE]
        if idle_tiles:
            ch, led = random.choice(idle_tiles)
            gs.tile_types[(ch, led)] = ptype
            self._refresh_tile(ch, led)

    # ── Rendering ─────────────────────────────────────────────────────────────
    def _refresh_tile(self, ch, led):
        gs     = self._gs
        team   = CHANNEL_TEAM[ch]
        hidden = (gs.hidden_team == team)
        ttype  = gs.tile_types.get((ch, led), IDLE)
        color  = tile_color_for(ttype, hidden)
        gs.tile_colors[(ch, led)] = color
        self._send({(ch, led): color})

    def _refresh_all_tiles(self):
        states = {}
        gs     = self._gs
        for ch in range(1, 5):
            team   = CHANNEL_TEAM[ch]
            hidden = (gs.hidden_team == team)
            for led in range(1, 11):
                ttype = gs.tile_types.get((ch, led), IDLE)
                color = tile_color_for(ttype, hidden)
                gs.tile_colors[(ch, led)] = color
                states[(ch, led)] = color
            # Preserve eye state
            states[(ch, 0)] = C_RED if ch == gs.eye_channel else C_OFF
        self._send(states)

    # ── End game ──────────────────────────────────────────────────────────────
    def _end_game(self, reason, winner_team):
        gs = self._gs
        if gs.ended: return
        gs.ended     = True
        gs.winner    = winner_team
        gs.end_reason = reason
        self._stop_ev.set()

        # Flash winner colours
        if winner_team:
            col = C_BLUE if winner_team == TEAM_A else C_RED
        else:
            # Draw: flash both
            col = C_WHITE

        def flash_end():
            for _ in range(6):
                states = {}
                for ch in range(1, 5):
                    for led in range(0, 11):
                        states[(ch, led)] = col
                self._send(states)
                time.sleep(0.3)
                blank = {(ch, led): C_OFF
                         for ch in range(1, 5)
                         for led in range(0, 11)}
                self._send(blank)
                time.sleep(0.3)

        threading.Thread(target=flash_end, daemon=True).start()
        self._ui_call("game_over", reason, winner_team, gs.scores)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _send(self, partial_states):
        # Merge partial into full LED state table held by the UI
        self._ui_call("update_leds", partial_states)
        self._net.push_frame(self._ui.get_led_states())

    def _ui_call(self, event, *args):
        if self._ui:
            self._ui.on_game_event(event, *args)


# ─────────────────────────────────────────────────────────────────────────────
# Tkinter UI
# ─────────────────────────────────────────────────────────────────────────────
class GameUI(tk.Tk):
    """
    Full-screen game display with four wall canvases, score display,
    timer, and event log.  Also serves as a LED-state store for the engine.
    """
    def __init__(self):
        super().__init__()
        self.title("Evil Eye – Arena")
        self.configure(bg="#0a0a0a")
        self.attributes("-fullscreen", False)
        self.minsize(1024, 700)

        self._led_states: dict = {}   # (ch, led) -> (r,g,b)  – full mirror
        self._game: EvilEyeGame | None = None
        self._net:  NetService  | None = None
        self._gs:   GameState   | None = None

        self._build_menu_screen()
        self.bind("<F11>",  lambda e: self.attributes("-fullscreen", not self.attributes("-fullscreen")))
        self.bind("<Escape>", self._on_escape)

    # ── Menu screen ───────────────────────────────────────────────────────────
    def _build_menu_screen(self):
        self._clear_screen()
        self._screen = "menu"

        f = tk.Frame(self, bg="#0a0a0a")
        f.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(f, text="👁  EVIL EYE  ARENA  👁",
                 font=("Consolas", 28, "bold"), fg="#ff4444", bg="#0a0a0a").pack(pady=(0, 30))

        # ── Difficulty ───────────────────────────────────────────────────────
        tk.Label(f, text="DIFFICULTY", font=("Consolas", 12, "bold"),
                 fg="#888", bg="#0a0a0a").pack()
        diff_frame = tk.Frame(f, bg="#0a0a0a")
        diff_frame.pack(pady=8)
        self._diff_var = tk.StringVar(value="easy")
        for val, label in [("easy", "EASY"), ("hard", "HARD")]:
            rb = tk.Radiobutton(diff_frame, text=label, variable=self._diff_var, value=val,
                                font=("Consolas", 13, "bold"), fg="white", bg="#0a0a0a",
                                selectcolor="#222", activebackground="#0a0a0a",
                                activeforeground="white", indicatoron=0,
                                padx=20, pady=8, relief="raised", width=8,
                                cursor="hand2")
            rb.pack(side=tk.LEFT, padx=8)

        # ── Players per team ─────────────────────────────────────────────────
        tk.Label(f, text="PLAYERS PER TEAM", font=("Consolas", 12, "bold"),
                 fg="#888", bg="#0a0a0a").pack(pady=(20, 0))
        pf = tk.Frame(f, bg="#0a0a0a")
        pf.pack(pady=8)
        self._ppt_var = tk.IntVar(value=3)
        for n in range(1, 7):
            rb = tk.Radiobutton(pf, text=str(n), variable=self._ppt_var, value=n,
                                font=("Consolas", 13, "bold"), fg="white", bg="#0a0a0a",
                                selectcolor="#222", activebackground="#0a0a0a",
                                activeforeground="white", indicatoron=0,
                                padx=14, pady=8, relief="raised", width=3,
                                cursor="hand2")
            rb.pack(side=tk.LEFT, padx=4)

        # ── Hardware / simulator ──────────────────────────────────────────────
        tk.Label(f, text="TARGET", font=("Consolas", 12, "bold"),
                 fg="#888", bg="#0a0a0a").pack(pady=(20, 0))
        tf = tk.Frame(f, bg="#0a0a0a")
        tf.pack(pady=8)
        self._target_var = tk.StringVar(value="simulator")
        for val, label, tip in [
            ("simulator", "SIMULATOR\n(127.0.0.1)", "Software simulator on localhost"),
            ("hardware",  f"HARDWARE\n({HARDWARE_IP})", "Real LED panels"),
        ]:
            rb = tk.Radiobutton(tf, text=label, variable=self._target_var, value=val,
                                font=("Consolas", 10, "bold"), fg="white", bg="#0a0a0a",
                                selectcolor="#222", activebackground="#0a0a0a",
                                activeforeground="white", indicatoron=0,
                                padx=16, pady=10, relief="raised", width=14,
                                justify="center", cursor="hand2")
            rb.pack(side=tk.LEFT, padx=8)

        # ── Start button ─────────────────────────────────────────────────────
        tk.Button(f, text="▶  START GAME",
                  font=("Consolas", 16, "bold"), fg="white", bg="#226622",
                  activebackground="#338833", relief="flat", padx=30, pady=14,
                  cursor="hand2",
                  command=self._start_game).pack(pady=30)

        # Team layout hint
        hint = ("Team A (BLUE): Walls 1-South & 2-East\n"
                "Team B (RED):  Walls 3-North & 4-West\n"
                "Eye LED = motion sensor (LED 0)  |  Tiles = pressure pads (LED 1-10)")
        tk.Label(f, text=hint, font=("Consolas", 9), fg="#555", bg="#0a0a0a",
                 justify="center").pack(pady=(0, 10))

    # ── Start game ────────────────────────────────────────────────────────────
    def _start_game(self):
        diff = self._diff_var.get()
        ppt  = self._ppt_var.get()
        tgt  = self._target_var.get()
        ip   = "127.0.0.1" if tgt == "simulator" else HARDWARE_IP

        self._gs   = GameState(diff, ppt)
        self._net  = NetService(ip)
        self._net.on_button = self._on_button_hw

        self._build_game_screen()
        self._game = EvilEyeGame(self._net, self, self._gs)
        self._game.start()

    def _on_button_hw(self, ch, led):
        """Hardware button press; forward to game engine (thread-safe)."""
        if self._game:
            self.after(0, lambda: self._game.on_button(ch, led))

    # ── Game screen ───────────────────────────────────────────────────────────
    def _build_game_screen(self):
        self._clear_screen()
        self._screen = "game"
        self._led_states = {}

        root_f = tk.Frame(self, bg="#0a0a0a")
        root_f.pack(fill=tk.BOTH, expand=True)

        # ── Top bar ──────────────────────────────────────────────────────────
        top = tk.Frame(root_f, bg="#111", height=56)
        top.pack(fill=tk.X)
        top.pack_propagate(False)

        self._lbl_score_a = tk.Label(top, text="Team A  0",
                                     font=("Consolas", 18, "bold"), fg="#4488ff", bg="#111")
        self._lbl_score_a.pack(side=tk.LEFT, padx=20, pady=6)

        self._lbl_timer = tk.Label(top, text="5:00",
                                   font=("Consolas", 22, "bold"), fg="#ffcc00", bg="#111")
        self._lbl_timer.pack(side=tk.LEFT, expand=True)

        self._lbl_score_b = tk.Label(top, text="Team B  0",
                                     font=("Consolas", 18, "bold"), fg="#ff4444", bg="#111")
        self._lbl_score_b.pack(side=tk.RIGHT, padx=20, pady=6)

        # ── Wall canvases ────────────────────────────────────────────────────
        walls_f = tk.Frame(root_f, bg="#0a0a0a")
        walls_f.pack(fill=tk.BOTH, expand=True)
        walls_f.grid_columnconfigure(0, weight=1)
        walls_f.grid_columnconfigure(1, weight=1)
        walls_f.grid_rowconfigure(0, weight=1)
        walls_f.grid_rowconfigure(1, weight=1)

        WALL_LAYOUT = {1: (1, 0), 2: (0, 1), 3: (0, 0), 4: (1, 1)}  # ch: (row, col)
        self._wall_canvases = {}
        team_colors = {TEAM_A: "#1a2a4a", TEAM_B: "#2a1a1a"}
        for ch in range(1, 5):
            team = CHANNEL_TEAM[ch]
            row, col = WALL_LAYOUT[ch]
            bg = team_colors[team]
            lbl = f"WALL {ch} – {WALL_NAMES[ch]}  (Team {'A' if team==TEAM_A else 'B'})"
            wf = tk.LabelFrame(walls_f, text=lbl, bg=bg,
                               fg="#4488ff" if team==TEAM_A else "#ff4444",
                               font=("Consolas", 10, "bold"),
                               borderwidth=2, relief="groove")
            wf.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            wf.grid_rowconfigure(0, weight=1)
            wf.grid_columnconfigure(0, weight=1)
            cv = _WallDisplay(wf, ch, self._on_canvas_click, bg=bg)
            cv.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
            self._wall_canvases[ch] = cv

        # ── Event log ────────────────────────────────────────────────────────
        log_f = tk.Frame(root_f, bg="#111", height=80)
        log_f.pack(fill=tk.X, side=tk.BOTTOM)
        log_f.pack_propagate(False)
        self._event_log = tk.Text(log_f, bg="#0a0a0a", fg="#00cc44",
                                  font=("Consolas", 9), state="disabled",
                                  borderwidth=0, height=4)
        self._event_log.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # Status / info bar
        info_f = tk.Frame(root_f, bg="#111", height=24)
        info_f.pack(fill=tk.X)
        info_f.pack_propagate(False)
        self._lbl_status = tk.Label(info_f, text="",
                                    font=("Consolas", 9), fg="#888", bg="#111")
        self._lbl_status.pack(side=tk.LEFT, padx=8)
        tk.Label(info_f, text="F11: Fullscreen  |  ESC: Menu",
                 font=("Consolas", 8), fg="#444", bg="#111").pack(side=tk.RIGHT, padx=8)

        # Intro label (overlaid)
        self._intro_lbl = tk.Label(root_f, text="", font=("Consolas", 30, "bold"),
                                   fg="white", bg="#0a0a0a")
        self._intro_lbl.place(relx=0.5, rely=0.5, anchor="center")

        self._start_timer_tick()

    def _on_canvas_click(self, ch, led):
        """Mouse/touch click on a wall canvas – simulate button press for testing."""
        if self._game:
            self._game.on_button(ch, led)

    # ── LED state store ───────────────────────────────────────────────────────
    def get_led_states(self):
        return dict(self._led_states)

    def _apply_leds(self, partial):
        self._led_states.update(partial)
        for (ch, led), color in partial.items():
            if ch in self._wall_canvases:
                self._wall_canvases[ch].set_led(led, *color)

    # ── Game event dispatcher ─────────────────────────────────────────────────
    def on_game_event(self, event, *args):
        """Called from game engine (possibly background thread)."""
        self.after(0, lambda: self._dispatch(event, args))

    def _dispatch(self, event, args):
        if event == "update_leds":
            self._apply_leds(args[0])
        elif event == "show_intro":
            self._intro_lbl.configure(text=args[0])
        elif event == "game_started":
            self._intro_lbl.configure(text="")
            self._log_event("⚡ Game started!")
        elif event == "tick":
            self._update_timer()
        elif event == "score_update":
            team, score = args
            if team == TEAM_A:
                self._lbl_score_a.configure(text=f"Team A  {score}")
            else:
                self._lbl_score_b.configure(text=f"Team B  {score}")
            self._log_event(f"🎯 Team {team} scores! → {score}/{POINTS_TO_WIN}")
        elif event == "eye_moved":
            ch = args[0]
            self._lbl_status.configure(text=f"👁 Eye on {WALL_NAMES[ch]} (Wall {ch})")
        elif event == "powerup_used":
            team, pname, desc = args
            self._log_event(f"⚡ Team {team}: {pname} – {desc}")
        elif event == "game_over":
            reason, winner, scores = args
            self._show_game_over(reason, winner, scores)

    # ── Timer ─────────────────────────────────────────────────────────────────
    def _start_timer_tick(self):
        self._timer_after = self.after(500, self._update_timer)

    def _update_timer(self):
        gs = self._gs
        if not gs or gs.ended:
            return
        rem = gs.remaining()
        m, s = divmod(int(rem), 60)
        self._lbl_timer.configure(text=f"{m}:{s:02d}")
        color = "#ff4444" if rem < 30 else ("#ffcc00" if rem < 60 else "#ffcc00")
        self._lbl_timer.configure(fg=color)
        self._timer_after = self.after(500, self._update_timer)

    # ── Game over screen ──────────────────────────────────────────────────────
    def _show_game_over(self, reason, winner, scores):
        if hasattr(self, "_timer_after"):
            self.after_cancel(self._timer_after)

        ov = tk.Frame(self, bg="#000000")
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)

        reasons = {"score": "POINTS WIN!", "time": "TIME'S UP!", "eye": "EYE DETECTED FULL TEAM!"}
        reason_text = reasons.get(reason, "GAME OVER")

        if winner:
            win_text = f"TEAM {'A' if winner==TEAM_A else 'B'} WINS!"
            col = "#4488ff" if winner == TEAM_A else "#ff4444"
        else:
            win_text = "IT'S A DRAW!"
            col = "#ffcc00"

        tk.Label(ov, text="👁  GAME OVER  👁",
                 font=("Consolas", 30, "bold"), fg="#888", bg="#000").pack(pady=(60, 10))
        tk.Label(ov, text=reason_text,
                 font=("Consolas", 18), fg="#888", bg="#000").pack()
        tk.Label(ov, text=win_text,
                 font=("Consolas", 48, "bold"), fg=col, bg="#000").pack(pady=20)

        score_txt = f"Team A: {scores[TEAM_A]}   |   Team B: {scores[TEAM_B]}"
        tk.Label(ov, text=score_txt,
                 font=("Consolas", 20), fg="white", bg="#000").pack(pady=10)

        bf = tk.Frame(ov, bg="#000")
        bf.pack(pady=40)
        tk.Button(bf, text="▶  PLAY AGAIN",
                  font=("Consolas", 14, "bold"), fg="white", bg="#226622",
                  relief="flat", padx=20, pady=10, cursor="hand2",
                  command=self._restart).pack(side=tk.LEFT, padx=12)
        tk.Button(bf, text="✖  MAIN MENU",
                  font=("Consolas", 14, "bold"), fg="white", bg="#662222",
                  relief="flat", padx=20, pady=10, cursor="hand2",
                  command=self._return_to_menu).pack(side=tk.LEFT, padx=12)

    def _restart(self):
        self._cleanup()
        self._start_game()

    def _return_to_menu(self):
        self._cleanup()
        self._build_menu_screen()

    def _cleanup(self):
        if self._game:
            self._game._stop_ev.set()
        if self._net:
            self._net.stop()
        self._game = None
        self._net  = None
        self._gs   = None

    # ── Misc ──────────────────────────────────────────────────────────────────
    def _log_event(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self._event_log.configure(state="normal")
        self._event_log.insert(tk.END, f"[{ts}] {msg}\n")
        self._event_log.see(tk.END)
        self._event_log.configure(state="disabled")

    def _clear_screen(self):
        for w in self.winfo_children():
            w.destroy()

    def _on_escape(self, _=None):
        if self._screen == "game":
            if messagebox.askyesno("Quit", "Return to main menu?"):
                self._return_to_menu()
        else:
            self.attributes("-fullscreen", False)

    def destroy(self):
        self._cleanup()
        super().destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Wall canvas widget for game screen  (similar to Simulator's WallCanvas)
# ─────────────────────────────────────────────────────────────────────────────
class _WallDisplay(tk.Canvas):
    ROWS = 3
    COLS = 5

    def __init__(self, parent, channel, on_click, **kwargs):
        super().__init__(parent, bg=kwargs.pop("bg", "#111"),
                         highlightthickness=0, **kwargs)
        self._ch       = channel
        self._on_click = on_click
        self._colors   = [(0, 0, 0)] * LEDS_PER_CHANNEL
        self._items    = {}
        self.bind("<Configure>", self._redraw)
        self.bind("<ButtonPress-1>",  self._click)
        # Touch support (will work on touch screens too via standard Tk)
        self.bind("<Button-4>",  self._click)

    def set_led(self, index, r, g, b):
        self._colors[index] = (r, g, b)
        self._paint(index)

    def _paint(self, index):
        if index not in self._items: return
        r, g, b = self._colors[index]
        fill = f"#{r:02x}{g:02x}{b:02x}" if (r or g or b) else (
               "#0d0d0d" if index > 0 else "black")
        outline = fill if (r or g or b) else ("#ff2222" if index == 0 else "#1a1a1a")
        self.itemconfig(self._items[index], fill=fill, outline=outline)

    def _cell(self, idx, w, h, pad):
        cw = (w - 2*pad) / self.COLS
        ch = (h - 2*pad) / self.ROWS
        if idx == 0:
            cx, cy = w/2, pad + ch*0.5
            r = min(cw, ch) * 0.38
            return (cx-r, cy-r, cx+r, cy+r)
        btn = idx - 1
        row, col = btn // 5 + 1, btn % 5
        x1 = pad + col*cw + cw*0.07
        y1 = pad + row*ch + ch*0.07
        return (x1, y1, x1+cw*0.86, y1+ch*0.86)

    def _redraw(self, _=None):
        self.delete("all")
        self._items.clear()
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10: return
        pad = max(6, min(w, h)*0.04)
        cw  = (w - 2*pad)/self.COLS
        ch  = (h - 2*pad)/self.ROWS
        fs  = max(7, int(min(cw, ch)*0.22))

        # Eye
        x1, y1, x2, y2 = self._cell(0, w, h, pad)
        halo = max(4, (x2-x1)*0.12)
        self.create_oval(x1-halo, y1-halo, x2+halo, y2+halo,
                         fill=self["bg"], outline="#333", width=1)
        self._items[0] = self.create_oval(x1, y1, x2, y2,
                         fill="black", outline="#ff2222",
                         width=max(2, int(halo*0.5)))
        self.create_text(w/2, y2+max(4, halo), text="EYE",
                         fill="#444", font=("Consolas", fs-1))
        # Buttons
        for i in range(1, 11):
            x1, y1, x2, y2 = self._cell(i, w, h, pad)
            self._items[i] = self.create_rectangle(
                x1, y1, x2, y2, fill="#0a0a0a",
                outline="#1a1a1a", width=max(1, int((x2-x1)*0.04)))
            self.create_text((x1+x2)/2, (y1+y2)/2, text=str(i),
                             fill="#333", font=("Consolas", fs, "bold"))
            self._paint(i)
        self._paint(0)

    def _hit(self, x, y):
        w, h = self.winfo_width(), self.winfo_height()
        pad  = max(6, min(w, h)*0.04)
        for i in range(LEDS_PER_CHANNEL):
            x1, y1, x2, y2 = self._cell(i, w, h, pad)
            if x1 <= x <= x2 and y1 <= y <= y2:
                return i
        return None

    def _click(self, event):
        idx = self._hit(event.x, event.y)
        if idx is not None:
            self._on_click(self._ch, idx)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = GameUI()
    app.mainloop()