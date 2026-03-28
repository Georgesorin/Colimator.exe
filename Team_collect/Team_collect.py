"""
Evil Eye Game Controller
========================
Simulator mode  : python3 Simulator.py  then  python3 evil_eye_game.py
Hardware mode   : run python3 evil_eye_game.py, use "Discover" on the setup
                  screen to find the real device on the LAN, then START.

Hardware layout (from wiki):
    4 walls, each with:
        LED 0      = Eye  (motion sensor)
        LEDs 1-10  = Pressure tiles (buttons)
    One eye is active across the ENTIRE room at any time.

Network (real hardware):
    Send light commands → device UDP :4626   (4-packet sequence, 8 ms gaps)
    Receive button events ← device UDP :7800  (687-byte packets, 0x88 header)
    Discovery            → broadcast UDP :4626 (0x67 packet), listen on :7800

Channels / Teams:
    ch1 = North wall  -> Team A
    ch2 = East  wall  -> Team A
    ch3 = South wall  -> Team B
    ch4 = West  wall  -> Team B

Game rules:
    POINTS (per-team pools)
      - Each team owns 7 points that spawn ONLY on their own walls (2 active at once).
      - ANY player can claim a point — the presser's team scores.
      - Replacement spawns immediately from the wall-owner's pool.
      - Win by points: claim all 7 of the opponent's points, or timer ends.

    POWER-UPS (per-team pools, spawn only on own walls, 1 active at a time)
      EASY mode  – pool per team: redirect x3
          redirect -> moves the active eye to one of the OPPONENT's walls
      HARD mode  – pool per team: redirect x2, lock x1, hide x2
          redirect -> moves the active eye to one of the OPPONENT's walls
          lock     -> freezes the current eye in place for one extra cycle
          hide     -> blacks out ALL tiles on the opponent's walls for 5 seconds
      Only the OWNING team can claim their own power-ups.

    EYE (global, one at a time)
      - EASY: 10 s cycle (6 s active red, 4 s yellow warning on next wall).
        HARD:  6 s cycle (4 s active red, 2 s yellow warning on next wall).
      - Idle eyes (not the current or next) show white.
      - The eye LED (LED 0) shows motion. If all players of a team are standing
        on their own walls while the eye is open on one of those walls, that team
        LOSES immediately (the eye "sees" them all).
      - Eye-elimination: if the number of triggered eye sensors on a team's walls
        equals or exceeds the team's player count, that team loses.
"""

import os
import sys
import random
import socket
import time
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
from Controller import LightService, LEDS_PER_CHANNEL

# ── Constants ────────────────────────────────────────────────────────────────
GAME_DURATION_SEC  = 300
# Eye timing per difficulty
EYE_CYCLE_HARD     = 6    # total cycle length (seconds)
EYE_WARN_HARD      = 2    # warning (yellow) phase before move (seconds)
EYE_CYCLE_EASY     = 10
EYE_WARN_EASY      = 4
# Opening sequence timing
OPENING_SOLID_SEC  = 6.7  # solid team-colour phase before flashing
OPENING_FLASH_SEC  = 2.0  # flash + first-eye-warning phase before game starts
TOTAL_POINTS       = 7
MAX_MAP_POINTS     = 2   # active point slots per team
MAX_MAP_POWERUPS   = 1   # active power-up slots per team

ALL_CHANNELS = [1, 2, 3, 4]
TEAM_A_CH    = [1, 2]   # North, East
TEAM_B_CH    = [3, 4]   # South, West
TEAM_CH      = {0: TEAM_A_CH, 1: TEAM_B_CH}
WALL_NAME    = {1: "North", 2: "East", 3: "South", 4: "West"}

# Power-up pools by difficulty
POWERUP_POOL_EASY = ["redirect", "redirect", "redirect"]
POWERUP_POOL_HARD = ["redirect", "redirect", "lock", "hide", "hide"]

HIDE_DURATION_SEC = 5   # seconds opponent tiles stay blacked-out

# LED colours (r, g, b)
C_OFF        = (0,   0,   0)
C_POINT      = (255, 220, 0)    # yellow       – point tile
C_PU_REDIRECT= (255, 0,   0)    # red          – redirect power-up
C_PU_LOCK    = (0,   100, 255)  # blue         – lock power-up
C_PU_HIDE    = (180, 0,   255)  # purple       – hide power-up
C_EYE_IDLE   = (255, 255, 255)  # white        – idle eye (off-cycle)
C_EYE_WARN   = (255, 220, 0)    # yellow       – warning: eye about to move here
C_EYE_ON     = (255, 0,   0)    # bright red   – active eye (open, locked, or redirected)
C_HIDDEN     = (0,   0,   0)    # off          – tile blacked out by hide PU
C_IDLE_A     = (40,  40,  40)   # dim white    – Team A idle tile
C_IDLE_B     = (40,  40,  40)   # dim white    – Team B idle tile

POWERUP_COLOR = {
    "redirect": C_PU_REDIRECT,
    "lock":     C_PU_LOCK,
    "hide":     C_PU_HIDE,
}

# UI palette
BG    = "#0c0f18"
PANEL = "#131927"
COL_A = "#0073ff"
COL_B = "#00ff73"
GOLD  = "#ffd000"
DIM   = "#3a4050"
WHITE = "#dde2ee"
RED   = "#ff0000"


# ─────────────────────────────────────────────────────────────────────────────
# Game logic
# ─────────────────────────────────────────────────────────────────────────────
class GameState:
    """
    All mutable game state lives here.
    Methods return plain dicts so the UI can react without digging into internals.
    """
    def __init__(self):
        self.difficulty   = "hard"   # "easy" | "hard"
        self.team_sizes   = {0: 2, 1: 2}  # number of players per team
        self.reset()

    def reset(self):
        self.running     = False
        self.winner      = None       # None | 0 | 1 | "draw"
        self.score       = {0: 0, 1: 0}
        self.start_time  = None

        pool = POWERUP_POOL_EASY if self.difficulty == "easy" else POWERUP_POOL_HARD
        self.pool_points   = {0: TOTAL_POINTS, 1: TOTAL_POINTS}
        self.pool_powerups = {
            0: random.sample(pool, len(pool)),
            1: random.sample(pool, len(pool)),
        }

        # Active items on the map: (ch, led) -> {"type": "point"|"powerup", "sub": str|None, "owner": team}
        self.map_items: dict = {}

        # Eye state
        self.eye_channel  = None   # which channel currently has the eye open
        self.eye_locked   = False  # if True, skip the next natural rotation
        self.eye_redirect = False  # if True, eye was redirected this cycle
        self.eye_warning_channel = None  # channel showing yellow warning (next eye)

        # Hide state: which team's tiles are currently hidden (blacked-out), or None
        self.hidden_team: int | None = None

        # Points claimed from each team's walls (win condition tracker)
        self.pts_taken_from = {0: 0, 1: 0}

        # Eye sensors currently triggered per channel (for elimination check)
        self.eye_triggered: set = set()  # set of ch values

    # ── Team helpers ──────────────────────────────────────────────────────────
    def ch_team(self, ch):
        return 0 if ch in TEAM_A_CH else 1

    def _free_tiles_for(self, team):
        occupied = set(self.map_items)
        # Eye (LED 0) is never a tile
        return [
            (ch, led)
            for ch in TEAM_CH[team]
            for led in range(1, LEDS_PER_CHANNEL)
            if (ch, led) not in occupied
        ]

    # ── Spawning ──────────────────────────────────────────────────────────────
    def spawn_for(self, team):
        """Fill up to MAX slots for `team` on their own walls. Returns new positions."""
        spawned = []

        cur_pts = sum(
            1 for v in self.map_items.values()
            if v["owner"] == team and v["type"] == "point"
        )
        cur_pow = sum(
            1 for v in self.map_items.values()
            if v["owner"] == team and v["type"] == "powerup"
        )

        while cur_pts < MAX_MAP_POINTS and self.pool_points[team] > 0:
            free = self._free_tiles_for(team)
            if not free:
                break
            pos = random.choice(free)
            self.map_items[pos] = {"type": "point", "sub": None, "owner": team}
            self.pool_points[team] -= 1
            cur_pts += 1
            spawned.append(pos)

        while cur_pow < MAX_MAP_POWERUPS and self.pool_powerups[team]:
            free = self._free_tiles_for(team)
            if not free:
                break
            pos = random.choice(free)
            sub = self.pool_powerups[team].pop(0)
            self.map_items[pos] = {"type": "powerup", "sub": sub, "owner": team}
            cur_pow += 1
            spawned.append(pos)

        return spawned

    def spawn_all(self):
        return self.spawn_for(0) + self.spawn_for(1)

    # ── Claiming ──────────────────────────────────────────────────────────────
    def claim(self, ch, led):
        """Process a tile press. Returns an event dict or None."""
        if not self.running:
            return None
        pos     = (ch, led)
        presser = self.ch_team(ch)

        # Tiles on a hidden team's walls cannot be pressed (they can't see them)
        if self.hidden_team is not None and ch in TEAM_CH[self.hidden_team]:
            return {"event": "hidden", "ch": ch, "led": led}

        item = self.map_items.get(pos)
        if item is None:
            return None

        wall_owner = item["owner"]

        # Power-ups are only claimable by the owning team
        if item["type"] == "powerup" and presser != wall_owner:
            return {"event": "blocked", "ch": ch, "led": led, "claimer": presser}

        del self.map_items[pos]

        if item["type"] == "point":
            self.score[presser] += 1
            self.pts_taken_from[wall_owner] += 1
            self.spawn_for(wall_owner)

            if self.pts_taken_from[0] >= TOTAL_POINTS or \
               self.pts_taken_from[1] >= TOTAL_POINTS:
                self._end()

            return {
                "event": "point",
                "claimer": presser,
                "wall_owner": wall_owner,
                "ch": ch,
                "led": led,
            }

        # Power-up claimed by owning team
        self._apply_powerup(item["sub"], presser)
        self.spawn_for(wall_owner)
        return {
            "event": "powerup",
            "sub": item["sub"],
            "claimer": presser,
            "ch": ch,
            "led": led,
        }

    def _apply_powerup(self, sub, team):
        opp_ch = TEAM_CH[1 - team]

        if sub == "redirect":
            # Move the active eye immediately to one of the OPPONENT's walls.
            # Also cancel any in-progress warning (the pre-picked next channel is
            # now invalid since the eye jumped).
            choices = list(opp_ch)
            if self.eye_channel in choices and len(choices) > 1:
                choices.remove(self.eye_channel)
            self.eye_channel         = random.choice(choices)
            self.eye_redirect        = True
            self.eye_warning_channel = None   # warning was for old cycle — discard

        elif sub == "lock":
            # Freeze the eye for one extra cycle (skip next rotation).
            self.eye_locked = True

        elif sub == "hide":
            # Black-out all tiles on the opponent's walls for HIDE_DURATION_SEC.
            # The controller schedules the reveal timer; we just set the flag here.
            self.hidden_team = 1 - team

    # ── Eye sensor (motion detection) ─────────────────────────────────────────
    def eye_sensor_changed(self, ch, is_triggered):
        """
        Called when an eye LED (LED 0) changes state.
        Returns an elimination event dict if the condition is met, else None.
        """
        if is_triggered:
            self.eye_triggered.add(ch)
        else:
            self.eye_triggered.discard(ch)

        # Check elimination: if all walls of a team have their eyes triggered
        # simultaneously AND the eye is currently active on one of those walls,
        # that team loses.
        return self._check_eye_elimination()

    def _check_eye_elimination(self):
        if not self.running:
            return None
        if self.eye_channel is None:
            return None

        for team in (0, 1):
            team_walls = TEAM_CH[team]
            # Eye must be on one of the team's own walls
            if self.eye_channel not in team_walls:
                continue
            # Count how many of the team's walls have their eye triggered
            triggered_count = sum(
                1 for ch in team_walls if ch in self.eye_triggered
            )
            if triggered_count >= self.team_sizes[team]:
                # Eye has seen all players on this team's side → they lose
                loser = team
                self.winner = 1 - loser
                self.running = False
                return {
                    "event": "eye_elimination",
                    "loser": loser,
                    "winner": 1 - loser,
                }
        return None

    # ── Eye cycle ─────────────────────────────────────────────────────────────
    def pick_next_eye(self):
        """Choose the next eye channel (without applying it). Used for the warning phase."""
        old = self.eye_channel
        choices = ALL_CHANNELS[:]
        if old in choices and len(choices) > 1:
            choices.remove(old)
        return random.choice(choices)

    def cycle_eyes(self, next_ch=None):
        """
        Rotate the single global eye to a new random wall (or `next_ch` if given).
        Returns a result dict describing what happened.
        """
        if self.eye_locked:
            self.eye_locked          = False
            self.eye_redirect        = False
            self.eye_warning_channel = None
            return {"action": "locked", "channel": self.eye_channel}

        old = self.eye_channel
        self.eye_channel         = next_ch if next_ch is not None else self.pick_next_eye()
        self.eye_redirect        = False
        self.eye_warning_channel = None
        return {"action": "moved", "old": old, "channel": self.eye_channel}

    # ── End ───────────────────────────────────────────────────────────────────
    def _end(self, timeout=False):
        self.running = False
        a, b = self.score[0], self.score[1]
        if self.winner is None:   # not already set by eye elimination
            self.winner = "draw" if a == b else (0 if a > b else 1)

    def remaining(self):
        if not self.start_time:
            return GAME_DURATION_SEC
        return max(0.0, GAME_DURATION_SEC - (time.time() - self.start_time))


# ─────────────────────────────────────────────────────────────────────────────
# Hardware discovery helpers (Evil Eye protocol)
# ─────────────────────────────────────────────────────────────────────────────
_PASSWORD_ARRAY = [
    35, 63, 187, 69, 107, 178, 92, 76, 39, 69, 205, 37, 223, 255, 165, 231,
    16, 220, 99, 61, 25, 203, 203, 155, 107, 30, 92, 144, 218, 194, 226, 88,
    196, 190, 67, 195, 159, 185, 209, 24, 163, 65, 25, 172, 126, 63, 224, 61,
    160, 80, 125, 91, 239, 144, 25, 141, 183, 204, 171, 188, 255, 162, 104, 225,
    186, 91, 232, 3, 100, 208, 49, 211, 37, 192, 20, 99, 27, 92, 147, 152,
    86, 177, 53, 153, 94, 177, 200, 33, 175, 195, 15, 228, 247, 18, 244, 150,
    165, 229, 212, 96, 84, 200, 168, 191, 38, 112, 171, 116, 121, 186, 147, 203,
    30, 118, 115, 159, 238, 139, 60, 57, 235, 213, 159, 198, 160, 50, 97, 201,
    253, 242, 240, 77, 102, 12, 183, 235, 243, 247, 75, 90, 13, 236, 56, 133,
    150, 128, 138, 190, 140, 13, 213, 18, 7, 117, 255, 45, 69, 214, 179, 50,
    28, 66, 123, 239, 190, 73, 142, 218, 253, 5, 212, 174, 152, 75, 226, 226,
    172, 78, 35, 93, 250, 238, 19, 32, 247, 223, 89, 123, 86, 138, 150, 146,
    214, 192, 93, 152, 156, 211, 67, 51, 195, 165, 66, 10, 10, 31, 1, 198,
    234, 135, 34, 128, 208, 200, 213, 169, 238, 74, 221, 208, 104, 170, 166, 36,
    76, 177, 196, 3, 141, 167, 127, 56, 177, 203, 45, 107, 46, 82, 217, 139,
    168, 45, 198, 6, 43, 11, 57, 88, 182, 84, 189, 29, 35, 143, 138, 171,
]

def _calc_sum(data: bytes | bytearray) -> int:
    return _PASSWORD_ARRAY[sum(data) & 0xFF]


def _build_discovery_packet():
    """Build the 0x67 Evil Eye discovery broadcast packet."""
    rand1 = random.randint(0, 127)
    rand2 = random.randint(0, 127)
    payload = bytearray([0x0A, 0x02, *b"KX-HC04", 0x03,
                         0x00, 0x00, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x14])
    pkt = bytearray([0x67, rand1, rand2, len(payload)]) + payload
    pkt.append(_calc_sum(pkt))
    return bytes(pkt), rand1, rand2


def _get_local_interfaces():
    """Return [(iface_name, ip, broadcast), ...] for all active IPv4 interfaces."""
    results = []
    try:
        import psutil
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and addr.address != "127.0.0.1":
                    # Compute broadcast from netmask, fall back to 255.255.255.255
                    try:
                        import ipaddress
                        net = ipaddress.IPv4Network(
                            f"{addr.address}/{addr.netmask}", strict=False)
                        bcast = str(net.broadcast_address)
                    except Exception:
                        bcast = "255.255.255.255"
                    results.append((iface, addr.address, bcast))
    except ImportError:
        # psutil not available — fall back to gethostbyname
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip != "127.0.0.1":
                results.append(("default", ip, "255.255.255.255"))
        except Exception:
            pass
    # Always offer loopback for simulator testing
    results.append(("loopback (simulator)", "127.0.0.1", "127.0.0.1"))
    return results


def _run_discovery(bind_ip: str, broadcast_ip: str, timeout: float = 3.0) -> str | None:
    """
    Broadcast a discovery packet and return the first responding device IP,
    or None if nothing is found within `timeout` seconds.
    Binds on port 7800 (the standard Evil Eye receive port).
    """
    pkt, rand1, rand2 = _build_discovery_packet()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(0.5)
    try:
        sock.bind((bind_ip if bind_ip != "127.0.0.1" else "0.0.0.0", 7800))
    except OSError:
        try:
            sock.bind(("0.0.0.0", 7800))
        except OSError:
            sock.close()
            return None

    try:
        sock.sendto(pkt, (broadcast_ip, 4626))
    except OSError:
        sock.close()
        return None

    found = None
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data, addr = sock.recvfrom(1024)
            # Valid response: 0x68 header + matching random bytes
            if (len(data) >= 30 and data[0] == 0x68
                    and data[1] == rand1 and data[2] == rand2):
                found = addr[0]
                break
        except socket.timeout:
            continue
        except OSError:
            break
    sock.close()
    return found


# ─────────────────────────────────────────────────────────────────────────────
# Setup screen (difficulty + player count + device discovery)
# ─────────────────────────────────────────────────────────────────────────────
class SetupScreen(tk.Frame):
    """Shown before the game starts so players can configure the match."""

    def __init__(self, master, on_start):
        super().__init__(master, bg=BG)
        self._on_start = on_start
        self._build()

    def _build(self):
        tk.Label(self, text="👁  EVIL EYE", fg=GOLD, bg=BG,
                 font=("Courier New", 28, "bold")).pack(pady=(30, 4))
        tk.Label(self, text="Configure your match", fg=DIM, bg=BG,
                 font=("Courier New", 11)).pack(pady=(0, 24))

        # ── Difficulty ────────────────────────────────────────────────────────
        tk.Label(self, text="DIFFICULTY", fg=WHITE, bg=BG,
                 font=("Courier New", 10, "bold")).pack()

        self._diff = tk.StringVar(value="hard")
        diff_frame = tk.Frame(self, bg=BG)
        diff_frame.pack(pady=6)

        for label, value, desc in [
            ("EASY", "easy", "Power-ups: Redirect ×3 only"),
            ("HARD", "hard", "Power-ups: Redirect ×2, Lock ×1, Hide ×2"),
        ]:
            col = COL_B if value == "easy" else RED
            f = tk.Frame(diff_frame, bg=PANEL, bd=1, relief="solid")
            f.pack(side="left", padx=10, ipadx=10, ipady=6)
            tk.Radiobutton(
                f, text=label, variable=self._diff, value=value,
                fg=col, bg=PANEL, selectcolor=PANEL, activebackground=PANEL,
                font=("Courier New", 14, "bold"), indicatoron=False,
                relief="flat", padx=16, pady=6,
            ).pack()
            tk.Label(f, text=desc, fg=DIM, bg=PANEL,
                     font=("Courier New", 7)).pack()

        # ── Player count per team ─────────────────────────────────────────────
        tk.Label(self, text="PLAYERS PER TEAM", fg=WHITE, bg=BG,
                 font=("Courier New", 10, "bold")).pack(pady=(20, 4))
        tk.Label(
            self,
            text="(Eye elimination triggers when this many players are seen at once)",
            fg=DIM, bg=BG, font=("Courier New", 8),
        ).pack()

        counts_frame = tk.Frame(self, bg=BG)
        counts_frame.pack(pady=10)

        self._team_a_size = tk.IntVar(value=2)
        self._team_b_size = tk.IntVar(value=2)

        for label, col, var in [
            ("Team A (North+East)", COL_A, self._team_a_size),
            ("Team B (South+West)", COL_B, self._team_b_size),
        ]:
            f = tk.Frame(counts_frame, bg=PANEL, bd=1, relief="solid")
            f.pack(side="left", padx=14, ipadx=12, ipady=8)
            tk.Label(f, text=label, fg=col, bg=PANEL,
                     font=("Courier New", 9, "bold")).pack()
            spin = tk.Spinbox(
                f, from_=1, to=10, textvariable=var, width=4,
                bg=PANEL, fg=WHITE, font=("Courier New", 16, "bold"),
                buttonbackground=PANEL, insertbackground=WHITE,
                justify="center", relief="flat",
            )
            spin.pack(pady=4)
            tk.Label(f, text="players", fg=DIM, bg=PANEL,
                     font=("Courier New", 8)).pack()

        # ── Powerup legend ────────────────────────────────────────────────────
        tk.Label(self, text="POWER-UP COLOURS", fg=WHITE, bg=BG,
                 font=("Courier New", 9, "bold")).pack(pady=(16, 4))

        legend = tk.Frame(self, bg=BG)
        legend.pack()
        for col, name, tip in [
            ("#ff0000", "Redirect", "Moves eye to opponent's wall"),
            ("#0064ff", "Lock",     "Eye stays for an extra cycle (Hard only)"),
            ("#b400ff", "Hide",     "Blinds opponent tiles for 5 s (Hard only)"),
            ("#ffdc00", "Point",    "Score a point — anyone can grab these"),
            ("#ffffff", "Normal",   "Idle pressure tile"),
        ]:
            f = tk.Frame(legend, bg=BG)
            f.pack(side="left", padx=10)
            tk.Label(f, text="■", fg=col, bg=BG,
                     font=("Courier New", 18)).pack()
            tk.Label(f, text=name, fg=WHITE, bg=BG,
                     font=("Courier New", 8, "bold")).pack()
            tk.Label(f, text=tip, fg=DIM, bg=BG,
                     font=("Courier New", 7), wraplength=110,
                     justify="center").pack()

        # ── Network / Device section ──────────────────────────────────────────
        tk.Label(self, text="NETWORK & DEVICE", fg=WHITE, bg=BG,
                 font=("Courier New", 9, "bold")).pack(pady=(18, 4))

        net_frame = tk.Frame(self, bg=PANEL, bd=1, relief="solid")
        net_frame.pack(padx=30, fill="x")

        # Row 1: interface selector
        row1 = tk.Frame(net_frame, bg=PANEL)
        row1.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(row1, text="Interface:", fg=DIM, bg=PANEL,
                 font=("Courier New", 9)).pack(side="left")
        self._iface_var = tk.StringVar()
        self._iface_combo = ttk.Combobox(row1, textvariable=self._iface_var,
                                         state="readonly", width=34,
                                         font=("Courier New", 9))
        self._iface_combo.pack(side="left", padx=(6, 4))
        tk.Button(row1, text="↺ Refresh", command=self._refresh_interfaces,
                  bg="#222", fg=DIM, font=("Courier New", 8),
                  relief="flat", padx=6, pady=2).pack(side="left")
        self._refresh_interfaces()

        # Row 2: device IP (manual or filled by discovery)
        row2 = tk.Frame(net_frame, bg=PANEL)
        row2.pack(fill="x", padx=10, pady=4)
        tk.Label(row2, text="Device IP: ", fg=DIM, bg=PANEL,
                 font=("Courier New", 9)).pack(side="left")
        self._ip_var = tk.StringVar(value="127.0.0.1")
        tk.Entry(row2, textvariable=self._ip_var, width=18,
                 bg="#0a0a0a", fg=WHITE, insertbackground=WHITE,
                 font=("Courier New", 9), relief="flat").pack(side="left", padx=(0, 6))
        tk.Button(row2, text="🔍 Discover", command=self._discover,
                  bg="#1a2a3a", fg=COL_A, activebackground="#253545",
                  font=("Courier New", 9, "bold"), relief="flat",
                  padx=10, pady=3).pack(side="left")

        # Row 3: discovery status label
        self._discover_status = tk.Label(net_frame, text="", fg=DIM, bg=PANEL,
                                         font=("Courier New", 8), anchor="w")
        self._discover_status.pack(fill="x", padx=10, pady=(0, 8))

        # ── Start button ──────────────────────────────────────────────────────
        tk.Button(
            self, text="▶  START GAME",
            command=self._start,
            bg="#1a3a1a", fg=COL_B, activebackground="#2a5a2a",
            font=("Courier New", 14, "bold"), relief="flat", padx=18, pady=10,
        ).pack(pady=20)

    # ── Network helpers ───────────────────────────────────────────────────────
    def _refresh_interfaces(self):
        """Populate the interface combo with all IPv4 addresses on this machine."""
        ifaces = _get_local_interfaces()
        labels = [f"{name}  –  {ip}" for name, ip, _ in ifaces]
        self._iface_combo["values"] = labels if labels else ["(none found)"]
        if labels:
            self._iface_combo.current(0)
        self._ifaces_cache = ifaces  # [(name, ip, broadcast), ...]

    def _selected_interface(self):
        """Return (name, ip, broadcast) for the currently selected interface."""
        idx = self._iface_combo.current()
        ifaces = getattr(self, "_ifaces_cache", [])
        if ifaces and 0 <= idx < len(ifaces):
            return ifaces[idx]
        return None

    def _discover(self):
        """Send a discovery broadcast and populate Device IP if a device responds."""
        iface = self._selected_interface()
        if not iface:
            self._discover_status.config(text="⚠ Select an interface first.", fg=RED)
            return
        name, ip, bcast = iface
        self._discover_status.config(text=f"Scanning on {name} ({ip})…", fg=DIM)
        self.update_idletasks()

        found_ip = _run_discovery(ip, bcast)
        if found_ip:
            self._ip_var.set(found_ip)
            self._discover_status.config(
                text=f"✅ Found device at {found_ip}", fg=COL_B)
        else:
            self._discover_status.config(
                text="❌ No device found. Check cable / interface.", fg=RED)

    def _start(self):
        self._on_start(
            difficulty=self._diff.get(),
            team_a_size=self._team_a_size.get(),
            team_b_size=self._team_b_size.get(),
            ip=self._ip_var.get().strip() or "127.0.0.1",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Main game controller window
# ─────────────────────────────────────────────────────────────────────────────
class GameController(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Evil Eye — Game Controller")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(620, 520)

        self.gs  = GameState()
        self.svc = LightService()
        self.svc.on_button_state = self._on_hw_button
        self.svc.on_status       = lambda m: None

        self._eye_after          = None
        self._tick_after         = None
        self._hide_after         = None   # timer handle for the hide power-up reveal
        self._opening_flash_after= None   # timer handle during opening sequence
        self._next_eye_ch        = None   # pre-picked next eye channel for warning

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Setup screen (shown first)
        self._setup_frame = SetupScreen(self, self._on_setup_start)
        self._setup_frame.pack(fill="both", expand=True)

        # Game screen (hidden until game starts)
        self._game_frame = tk.Frame(self, bg=BG)
        self._build_game_ui(self._game_frame)

    def _build_game_ui(self, parent):
        # ── Score header ──────────────────────────────────────────────────────
        hdr = tk.Frame(parent, bg=BG)
        hdr.pack(fill="x", padx=14, pady=(12, 2))

        self.lbl_a = tk.Label(hdr, text="TEAM A  0", fg=COL_A, bg=BG,
                              font=("Courier New", 20, "bold"))
        self.lbl_a.pack(side="left")

        self.lbl_timer = tk.Label(hdr, text="5:00", fg=GOLD, bg=BG,
                                  font=("Courier New", 26, "bold"))
        self.lbl_timer.pack(side="left", expand=True)

        self.lbl_b = tk.Label(hdr, text="0  TEAM B", fg=COL_B, bg=BG,
                              font=("Courier New", 20, "bold"))
        self.lbl_b.pack(side="right")

        # ── Info row (pools + eye) ─────────────────────────────────────────────
        info_row = tk.Frame(parent, bg=BG)
        info_row.pack(fill="x", padx=14)

        self.lbl_pool_a = tk.Label(info_row, text="Pts: 7  PUs: —",
                                   fg=COL_A, bg=BG, font=("Courier New", 8))
        self.lbl_pool_a.pack(side="left")
        tk.Label(info_row, text="North+East", fg=COL_A, bg=BG,
                 font=("Courier New", 8)).pack(side="left", padx=6)

        self.lbl_eye = tk.Label(info_row, text="👁  —", fg=GOLD, bg=BG,
                                font=("Courier New", 8, "bold"))
        self.lbl_eye.pack(side="left", expand=True)

        tk.Label(info_row, text="South+West", fg=COL_B, bg=BG,
                 font=("Courier New", 8)).pack(side="right", padx=6)
        self.lbl_pool_b = tk.Label(info_row, text="Pts: 7  PUs: —",
                                   fg=COL_B, bg=BG, font=("Courier New", 8))
        self.lbl_pool_b.pack(side="right")

        # ── Difficulty / size display ─────────────────────────────────────────
        self.lbl_meta = tk.Label(parent, text="", fg=DIM, bg=BG,
                                 font=("Courier New", 8), anchor="center")
        self.lbl_meta.pack(fill="x", padx=14)

        # ── Status bar ────────────────────────────────────────────────────────
        self.lbl_status = tk.Label(
            parent, text="Press START to begin.",
            fg=DIM, bg=BG, font=("Courier New", 9), anchor="w",
        )
        self.lbl_status.pack(fill="x", padx=14, pady=4)

        # ── Map overview — 2×2 wall grid ──────────────────────────────────────
        map_outer = tk.Frame(parent, bg=BG)
        map_outer.pack(fill="both", expand=True, padx=14, pady=2)
        for r in range(2): map_outer.rowconfigure(r, weight=1)
        for c in range(2): map_outer.columnconfigure(c, weight=1)

        self.map_labels = {}
        layout = [
            (1, "North", 0, 0),
            (2, "East",  0, 1),
            (4, "West",  1, 0),
            (3, "South", 1, 1),
        ]
        for ch, name, row, col in layout:
            tc = COL_A if ch in TEAM_A_CH else COL_B
            frm = tk.Frame(map_outer, bg=PANEL, bd=1, relief="solid")
            frm.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            tk.Label(frm, text=f"{name}  (ch{ch})", fg=tc, bg=PANEL,
                     font=("Courier New", 8, "bold")).pack(anchor="w", padx=4, pady=(2, 0))
            row_frm = tk.Frame(frm, bg=PANEL)
            row_frm.pack(padx=4, pady=(1, 4))
            for led in range(LEDS_PER_CHANNEL):
                txt = "EYE" if led == 0 else str(led)
                lbl = tk.Label(
                    row_frm, text=txt, fg=DIM, bg="#0a0a0a",
                    font=("Courier New", 6), width=3,
                    relief="flat", bd=1, padx=1,
                )
                lbl.pack(side="left", padx=1)
                self.map_labels[(ch, led)] = lbl

        # ── Controls ──────────────────────────────────────────────────────────
        ctrl = tk.Frame(parent, bg=BG)
        ctrl.pack(fill="x", padx=14, pady=(4, 2))

        self.btn_stop = tk.Button(
            ctrl, text="STOP / BACK TO MENU",
            command=self._stop,
            bg="#3a1010", fg=RED, activebackground="#5a2020",
            font=("Courier New", 10, "bold"), relief="flat",
            padx=12, pady=3, state="disabled",
        )
        self.btn_stop.pack(side="left", padx=4)

        # ── Legend ────────────────────────────────────────────────────────────
        leg = tk.Frame(parent, bg=BG)
        leg.pack(pady=(2, 6))
        for c, t in [
            ("#ffdc00", "Point"),
            ("#ff0000", "Redirect PU"),
            ("#0064ff", "Lock PU"),
            ("#b400ff", "Hide PU"),
            ("#888888", "Tiles hidden"),
            ("#ff0000", "Eye active"),
            ("#ffdc00", "Eye warning"),
            ("#ffffff", "Eye idle"),
        ]:
            tk.Label(leg, text="■", fg=c, bg=BG,
                     font=("Courier New", 9)).pack(side="left", padx=1)
            tk.Label(leg, text=t, fg=DIM, bg=BG,
                     font=("Courier New", 7)).pack(side="left", padx=(0, 6))

    # ── Setup → Game transition ────────────────────────────────────────────────
    def _on_setup_start(self, difficulty, team_a_size, team_b_size, ip):
        self.gs.difficulty    = difficulty
        self.gs.team_sizes[0] = team_a_size
        self.gs.team_sizes[1] = team_b_size

        self.svc.set_device(ip)
        self.svc.start_receiver()
        self.svc.start_polling()

        self.gs.reset()

        # Swap to game frame immediately (so map labels exist for _send)
        self._setup_frame.pack_forget()
        self._game_frame.pack(fill="both", expand=True)

        pool_label = (
            "Easy: Redirect×3 per team"
            if difficulty == "easy"
            else "Hard: Redirect×2, Lock×1, Hide×2 per team"
        )
        self.lbl_meta.config(
            text=(
                f"{pool_label}  |  "
                f"Team A: {team_a_size} player(s)  |  "
                f"Team B: {team_b_size} player(s)"
            )
        )
        self._update_scores()
        self._update_pool_labels()
        self.lbl_eye.config(text="👁  —")
        self.lbl_timer.config(text="GET READY", fg=WHITE)
        self._status("Get ready! Identify your walls…")
        self.btn_stop.config(state="normal")

        self._next_eye_ch  = None
        self._opening_flash_after = None
        self._run_opening_sequence()

    def _run_opening_sequence(self):
        """
        Phase 1 (0 → OPENING_SOLID_SEC):   Team A walls solid red, Team B solid blue.
                                             All eye LEDs white (idle).
        Phase 2 (last OPENING_FLASH_SEC):   Walls flash their team colour.
                                             At 2 s before start, first eye goes yellow.
        Phase 3 (t=0):                      Game starts. First eye turns red. Tiles appear.
        """
        C_TEAM_A_OPEN = (255, 0,   0)    # solid red   – Team A identification
        C_TEAM_B_OPEN = (0,   0,   255)  # solid blue  – Team B identification

        solid_ms = int((OPENING_SOLID_SEC - OPENING_FLASH_SEC) * 1000)
        flash_ms = int(OPENING_FLASH_SEC * 1000)

        # ── Phase 1: solid colours ────────────────────────────────────────────
        for ch in range(1, 5):
            col = C_TEAM_A_OPEN if ch in TEAM_A_CH else C_TEAM_B_OPEN
            for led in range(LEDS_PER_CHANNEL):
                self._send(ch, led, C_EYE_IDLE if led == 0 else col)

        # ── Phase 2 starts after solid_ms ─────────────────────────────────────
        def start_flash():
            # Pick first eye channel and show yellow warning immediately
            first_eye = random.choice(ALL_CHANNELS)
            self._next_eye_ch = first_eye
            self.gs.eye_warning_channel = first_eye

            for ch in range(1, 5):
                col = C_TEAM_A_OPEN if ch in TEAM_A_CH else C_TEAM_B_OPEN
                # Eye LED: yellow on the warned channel, white elsewhere
                eye_col = C_EYE_WARN if ch == first_eye else C_EYE_IDLE
                self._send(ch, 0, eye_col)

            self.lbl_timer.config(text="FLASH!", fg=GOLD)
            self._status("Walls flashing — first eye warming up…")
            _do_flash(flashes=4, on=True, first_eye=first_eye,
                      col_a=C_TEAM_A_OPEN, col_b=C_TEAM_B_OPEN,
                      interval=flash_ms // 4)

        def _do_flash(flashes, on, first_eye, col_a, col_b, interval):
            if flashes <= 0:
                # Phase 3: actually start
                self.after(0, _start_game, first_eye)
                return
            for ch in range(1, 5):
                tile_col = (col_a if ch in TEAM_A_CH else col_b) if on else C_OFF
                eye_col  = C_EYE_WARN if ch == first_eye else (C_EYE_IDLE if on else C_OFF)
                for led in range(LEDS_PER_CHANNEL):
                    self._send(ch, led, eye_col if led == 0 else tile_col)
            self._opening_flash_after = self.after(
                interval, _do_flash, flashes - 1, not on,
                first_eye, col_a, col_b, interval
            )

        def _start_game(first_eye):
            self.gs.running    = True
            self.gs.start_time = time.time()
            self.gs.spawn_all()
            self.gs.eye_channel         = first_eye
            self.gs.eye_warning_channel = None

            self._refresh_leds()   # draws tiles + turns first eye red
            self._update_scores()
            self._update_pool_labels()
            self._update_eye_label()
            self.lbl_timer.config(fg=GOLD)
            self._status("Game on! Claim tiles to score.")

            self._schedule_eye()
            self._tick()

        self.after(solid_ms, start_flash)

    def _stop(self):
        self._cancel_afters()
        self.gs.running = False
        self._all_off()
        self.svc.stop_polling()
        self.svc.stop_receiver()
        self.btn_stop.config(state="disabled")
        self.lbl_timer.config(text="5:00", fg=GOLD)
        self.lbl_eye.config(text="👁  —")
        # Return to setup screen
        self._game_frame.pack_forget()
        self._setup_frame.pack(fill="both", expand=True)

    def _cancel_afters(self):
        for attr in ("_eye_after", "_tick_after", "_hide_after", "_opening_flash_after"):
            h = getattr(self, attr, None)
            if h:
                self.after_cancel(h)
            setattr(self, attr, None)
        # Clear any active hide effect so state is clean on next game
        self.gs.hidden_team = None

    # ── LED helpers ───────────────────────────────────────────────────────────
    def _send(self, ch, led, col):
        self.svc.set_led(ch, led, *col)
        lbl = self.map_labels.get((ch, led))
        if not lbl:
            return
        r, g, b = col
        bg = f"#{r:02x}{g:02x}{b:02x}" if (r or g or b) else "#0a0a0a"
        fg = WHITE if (r + g + b) > 60 else DIM
        lbl.config(bg=bg, fg=fg)

    def _refresh_leds(self):
        gs = self.gs
        for ch in range(1, 5):
            idle = C_IDLE_A if gs.ch_team(ch) == 0 else C_IDLE_B
            team = gs.ch_team(ch)
            tiles_hidden = (gs.hidden_team is not None and team == gs.hidden_team)

            # Eye (LED 0) — never hidden by the hide power-up
            if ch == gs.eye_channel:
                # Active eye — always bright red (redirect/lock don't change colour now)
                eye_col = C_EYE_ON
            elif ch == gs.eye_warning_channel:
                # Next eye warning — yellow
                eye_col = C_EYE_WARN
            else:
                # Idle eye — white
                eye_col = C_EYE_IDLE
            self._send(ch, 0, eye_col)

            # Tiles (LEDs 1-10)
            for led in range(1, LEDS_PER_CHANNEL):
                if tiles_hidden:
                    # Black out this team's tiles — opponents can't see them
                    col = C_HIDDEN
                else:
                    pos = (ch, led)
                    if pos in gs.map_items:
                        item = gs.map_items[pos]
                        col = C_POINT if item["type"] == "point" \
                              else POWERUP_COLOR.get(item["sub"], C_PU_REDIRECT)
                    else:
                        col = idle
                self._send(ch, led, col)

    def _all_off(self):
        for ch in range(1, 5):
            for led in range(LEDS_PER_CHANNEL):
                self._send(ch, led, C_OFF)

    def _update_pool_labels(self):
        gs = self.gs
        for team, lbl in ((0, self.lbl_pool_a), (1, self.lbl_pool_b)):
            pp = gs.pool_points[team]
            pu = len(gs.pool_powerups[team])
            lbl.config(text=f"Pts: {pp}  PUs: {pu}")

    def _update_eye_label(self):
        gs = self.gs
        ch = gs.eye_channel
        warn_ch = gs.eye_warning_channel
        if ch is None and warn_ch is None:
            self.lbl_eye.config(text="👁  —")
            return
        parts = []
        if ch is not None:
            name = WALL_NAME.get(ch, f"W{ch}")
            tag = ""
            if gs.eye_redirect:
                tag = " [REDIRECTED]"
            elif gs.eye_locked:
                tag = " [LOCKED]"
            parts.append(f"🔴 {name}{tag}")
        if warn_ch is not None and warn_ch != ch:
            parts.append(f"🟡 {WALL_NAME.get(warn_ch, f'W{warn_ch}')} (next)")
        hidden_note = (
            f"  |  {'A' if gs.hidden_team == 0 else 'B'} tiles HIDDEN"
            if gs.hidden_team is not None else ""
        )
        self.lbl_eye.config(text="  ".join(parts) + hidden_note)

    # ── Timers ────────────────────────────────────────────────────────────────
    def _eye_timing(self):
        """Return (active_ms, warn_ms) for current difficulty."""
        if self.gs.difficulty == "easy":
            cycle, warn = EYE_CYCLE_EASY, EYE_WARN_EASY
        else:
            cycle, warn = EYE_CYCLE_HARD, EYE_WARN_HARD
        return (cycle - warn) * 1000, warn * 1000

    def _schedule_eye(self):
        """Start the eye cycle: wait (cycle - warn) ms, then show warning."""
        active_ms, _ = self._eye_timing()
        # Pre-pick next channel now (unless currently locked — stays on current wall).
        # We store it so warning and actual move use the same target.
        if self.gs.eye_locked:
            self._next_eye_ch = self.gs.eye_channel  # locked → same wall
        else:
            self._next_eye_ch = self.gs.pick_next_eye()
        self._eye_after = self.after(active_ms, self._do_eye_warning)

    def _do_eye_warning(self):
        """Show yellow warning on the next eye channel, then schedule the actual move."""
        if not self.gs.running:
            return
        _, warn_ms = self._eye_timing()

        # If a redirect fired during the active phase, _next_eye_ch may be stale.
        # Re-sync: if the eye moved due to redirect, pick a fresh next from here.
        if self.gs.eye_redirect:
            # Eye already jumped — pick new next from current redirected position
            self._next_eye_ch = self.gs.pick_next_eye()

        # Show warning (yellow) on the target wall.
        # For a locked eye, the target is the same wall → keep it red (don't show yellow
        # on the active wall, that would be confusing). Just skip the visual warning.
        if self.gs.eye_locked:
            # Locked: no warning shown, eye stays red until cycle fires and clears lock
            pass
        else:
            self.gs.eye_warning_channel = self._next_eye_ch
            self._refresh_leds()
            self._update_eye_label()

        self._eye_after = self.after(warn_ms, self._do_eye_cycle)

    def _do_eye_cycle(self):
        if not self.gs.running:
            return
        # For a locked eye, cycle_eyes will keep eye_channel unchanged and clear the lock.
        # For a normal/redirected eye, pass the pre-picked (or re-synced) next channel.
        next_ch = None if self.gs.eye_locked else self._next_eye_ch
        result = self.gs.cycle_eyes(next_ch=next_ch)
        self._next_eye_ch = None
        action = result.get("action")
        if action == "locked":
            self._status(f"LOCK — eye stays on {WALL_NAME.get(result['channel'])}!")
        else:
            self._status(f"Eye moved to {WALL_NAME.get(result['channel'])}!")
        self._refresh_leds()
        self._update_eye_label()
        self._schedule_eye()

    def _tick(self):
        if not self.gs.running:
            return
        rem = self.gs.remaining()
        self.lbl_timer.config(text=f"{int(rem)//60}:{int(rem)%60:02d}")
        if rem <= 0:
            self.gs._end(timeout=True)
            self._game_over()
            return
        self._tick_after = self.after(250, self._tick)

    # ── Hardware button events ─────────────────────────────────────────────────
    def _on_hw_button(self, ch, led, is_triggered, is_disconnected):
        if led == 0:
            # Eye / motion sensor
            self.after(0, self._handle_eye_sensor, ch, is_triggered)
        elif is_triggered:
            self.after(0, self._handle_press, ch, led)

    def _handle_eye_sensor(self, ch, is_triggered):
        ev = self.gs.eye_sensor_changed(ch, is_triggered)
        if ev and ev.get("event") == "eye_elimination":
            loser  = ev["loser"]
            winner = ev["winner"]
            self.gs.winner = winner
            ln = "A" if loser == 0 else "B"
            wn = "B" if loser == 0 else "A"
            self._status(f"👁 EYE SEES ALL — Team {ln} eliminated! Team {wn} wins!")
            self._refresh_leds()
            self._game_over()

    def _handle_press(self, ch, led):
        ev = self.gs.claim(ch, led)
        if ev is None:
            return

        claimer = ev.get("claimer", -1)
        tname   = "TEAM A" if claimer == 0 else "TEAM B"
        wname   = WALL_NAME.get(ch, f"W{ch}")
        event   = ev["event"]

        if event == "hidden":
            # Tile press during hide blackout — silently ignore (no feedback
            # to avoid giving away that there's something there)
            return
        elif event == "blocked":
            self._status(f"[{wname}] {tname} cannot claim the opponent's power-up!")
        elif event == "point":
            own   = ev["wall_owner"]
            oname = "Team A's" if own == 0 else "Team B's"
            pts   = self.gs.score[claimer]
            self._status(
                f"POINT! {tname} grabbed {oname} tile on {wname}/{led}. ({pts} pts)"
            )
        elif event == "powerup":
            sub = ev["sub"]
            self._status(f"POWER-UP [{sub.upper()}] used by {tname} on {wname}!")
            if sub == "hide":
                self._start_hide_timer()
            elif sub == "redirect":
                # Eye jumped to opponent's wall; any pre-picked next channel is stale.
                # _do_eye_warning will re-sync when it fires.
                self._next_eye_ch = None

        self._refresh_leds()
        self._update_scores()
        self._update_pool_labels()
        self._update_eye_label()

        if not self.gs.running:
            self._game_over()

    def _start_hide_timer(self):
        """Start (or restart) the 5-second reveal timer for the hide power-up."""
        if self._hide_after is not None:
            self.after_cancel(self._hide_after)
        self._hide_after = self.after(HIDE_DURATION_SEC * 1000, self._reveal_hidden_tiles)

    def _reveal_hidden_tiles(self):
        """Called when the hide power-up duration expires — restore opponent tiles."""
        self._hide_after = None
        self.gs.hidden_team = None
        if self.gs.running:
            self._refresh_leds()
            self._update_eye_label()
            self._status("Tiles revealed — hide effect ended.")

    # ── Scores / status ───────────────────────────────────────────────────────
    def _update_scores(self):
        self.lbl_a.config(text=f"TEAM A  {self.gs.score[0]}")
        self.lbl_b.config(text=f"{self.gs.score[1]}  TEAM B")

    def _status(self, msg):
        self.lbl_status.config(
            text=f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        )

    # ── Game over ─────────────────────────────────────────────────────────────
    def _game_over(self):
        self._cancel_afters()
        gs = self.gs
        w  = gs.winner
        if w == "draw":
            msg, flash_chs, flash_rgb, col = \
                "DRAW!", ALL_CHANNELS, (255, 200, 0), GOLD
        elif w == 0:
            msg, flash_chs, flash_rgb, col = \
                f"TEAM A WINS! ({gs.score[0]}-{gs.score[1]})", TEAM_A_CH, (0, 80, 255), COL_A
        else:
            msg, flash_chs, flash_rgb, col = \
                f"TEAM B WINS! ({gs.score[1]}-{gs.score[0]})", TEAM_B_CH, (0, 255, 100), COL_B

        self.lbl_timer.config(text="END", fg=col)
        self._status(msg)

        def flash(n=6):
            c = flash_rgb if n % 2 == 0 else C_OFF
            for fch in flash_chs:
                for led in range(LEDS_PER_CHANNEL):
                    self._send(fch, led, c)
            if n > 0:
                self.after(350, flash, n - 1)

        flash()
        self.btn_stop.config(state="normal")

    def _on_close(self):
        self._cancel_afters()
        self.svc.stop_polling()
        self.svc.stop_receiver()
        self._all_off()
        self.destroy()


if __name__ == "__main__":
    GameController().mainloop()