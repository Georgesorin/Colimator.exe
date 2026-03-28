"""
ray_wars_screens.py
═══════════════════
External monitor UI for Ray Wars.

Two Tkinter windows, each pinned to an external monitor:

  TOUCH SCREEN  (monitor index 1, default)
    — Full-screen Tkinter window
    — Shows 4 big buttons: SLOW / MEDIUM / FAST / EXIT
    — Shown only when game is in LOBBY or IDLE state
    — Clicking/touching a speed button calls game.start_game(speed)
    — Touch = left-click on every OS/touchscreen driver we've tested

  STATUS SCREEN  (monitor index 2, default)
    — Full-screen Tkinter window (read-only)
    — Left half:  Team A hearts (red) with label
    — Right half: Team B hearts (blue) with label
    — Separated by a vertical white divider line
    — Updates at ~10 Hz via root.after()

Monitor positions are read from ray_wars_config.json:

  "touch_monitor":   { "x": 1920, "y": 0 }   ← top-left corner of that monitor
  "status_monitor":  { "x": 3840, "y": 0 }

Set x/y to the pixel offset of each monitor in your desktop layout.
If the keys are absent the defaults below are used (assumes three monitors
arranged left-to-right each at 1920 px width).

Run from RayBattle.py — do not run this file directly.
"""

import tkinter as tk
import threading
import time
import json
import os

# ── defaults (override in ray_wars_config.json) ──────────────────
_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ray_wars_config.json")

def _cfg():
    try:
        if os.path.exists(_CFG_FILE):
            with open(_CFG_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

# ── colours (mirrored from RayBattle constants) ───────────────────
_BG          = "#0a0a0a"
_TEAM_A      = "#DC2828"   # red
_TEAM_B      = "#1E50DC"   # blue
_DIVIDER     = "#ffffff"
_BTN_SLOW    = "#1a3a1a"
_BTN_MEDIUM  = "#1a2a3a"
_BTN_FAST    = "#3a1a1a"
_BTN_EXIT    = "#2a2a2a"
_BTN_HOVER_FACTOR = 1.6    # brightness multiplier on hover
_HEART_ON_A  = "#DC1E1E"
_HEART_OFF_A = "#370000"
_HEART_ON_B  = "#1E50DC"
_HEART_OFF_B = "#000A37"
_LABEL_FG    = "#cccccc"


def _brighten(hex_col, factor):
    """Return a brighter version of a hex colour string."""
    hex_col = hex_col.lstrip("#")
    r, g, b = int(hex_col[0:2], 16), int(hex_col[2:4], 16), int(hex_col[4:6], 16)
    r = min(255, int(r * factor))
    g = min(255, int(g * factor))
    b = min(255, int(b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


# ─────────────────────────────────────────────────────────────────
# Touch-screen window  (speed selection / lobby menu)
# ─────────────────────────────────────────────────────────────────
class TouchScreen:
    """
    Full-screen window on the touch monitor.
    Visible only when game.state in ('LOBBY', 'IDLE').
    Shows 4 large tap targets: SLOW / MEDIUM / FAST / EXIT.
    """

    def __init__(self, root: tk.Tk, game, monitor_x: int, monitor_y: int):
        self.game  = game
        self._visible = False

        # Toplevel so it lives on a different monitor from root
        self.win = tk.Toplevel(root)
        self.win.title("Ray Wars – Menu")
        self.win.configure(bg=_BG)
        self.win.overrideredirect(True)   # borderless
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", lambda: None)  # prevent accidental close

        # Position on the correct monitor and go full-screen
        self.win.geometry(f"+{monitor_x}+{monitor_y}")
        self.win.attributes("-fullscreen", True)
        self.win.lift()

        # Canvas fills the whole window
        self.canvas = tk.Canvas(self.win, bg=_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Button definitions: (label, bg_colour, speed_arg | None)
        self._buttons = [
            ("SLOW",   _BTN_SLOW,   "slow"),
            ("MEDIUM", _BTN_MEDIUM, "medium"),
            ("FAST",   _BTN_FAST,   "fast"),
            ("EXIT",   _BTN_EXIT,   None),
        ]

        self._btn_rects = {}   # label → canvas rect id
        self._btn_texts = {}   # label → canvas text id
        self._hover     = None # currently hovered label

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<ButtonPress-1>",   self._on_tap)
        self.canvas.bind("<Motion>",          self._on_hover)
        self.canvas.bind("<Leave>",           self._on_leave)

        # Touch devices often emit <TouchBegin> on some Linux setups
        try:
            self.canvas.bind("<TouchBegin>", self._on_tap)
        except Exception:
            pass

        self._draw()
        self._schedule_update()

    # ── layout ───────────────────────────────────────────────────

    def _draw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()  or self.win.winfo_screenwidth()
        h = self.canvas.winfo_height() or self.win.winfo_screenheight()

        n    = len(self._buttons)
        pad  = max(8, h // 60)
        btn_h = (h - pad * (n + 1)) // n

        self._layout = []   # list of (x1,y1,x2,y2, label)

        # Title
        title_h = max(40, h // 18)
        self.canvas.create_text(
            w // 2, pad // 2 + 4,
            text="RAY WARS", fill="#ffffff",
            font=("Helvetica", max(14, title_h // 2), "bold"),
            anchor="n"
        )

        for i, (label, bg, _) in enumerate(self._buttons):
            x1 = pad
            y1 = pad + i * (btn_h + pad)
            x2 = w - pad
            y2 = y1 + btn_h

            rid = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=bg, outline="#444444", width=3
            )
            font_size = max(16, btn_h // 4)
            tid = self.canvas.create_text(
                (x1 + x2) // 2, (y1 + y2) // 2,
                text=label, fill="#ffffff",
                font=("Helvetica", font_size, "bold")
            )
            self._btn_rects[label] = rid
            self._btn_texts[label] = tid
            self._layout.append((x1, y1, x2, y2, label))

    def _on_resize(self, event=None):
        self._draw()

    # ── interaction ──────────────────────────────────────────────

    def _label_at(self, ex, ey):
        for x1, y1, x2, y2, label in self._layout:
            if x1 <= ex <= x2 and y1 <= ey <= y2:
                return label
        return None

    def _on_hover(self, event):
        label = self._label_at(event.x, event.y)
        if label == self._hover:
            return
        # Restore old
        if self._hover:
            _, orig_bg, _ = next(b for b in self._buttons if b[0] == self._hover)
            self.canvas.itemconfig(self._btn_rects[self._hover], fill=orig_bg)
        # Highlight new
        self._hover = label
        if label:
            _, orig_bg, _ = next(b for b in self._buttons if b[0] == label)
            self.canvas.itemconfig(self._btn_rects[label], fill=_brighten(orig_bg, _BTN_HOVER_FACTOR))

    def _on_leave(self, event):
        if self._hover:
            _, orig_bg, _ = next(b for b in self._buttons if b[0] == self._hover)
            self.canvas.itemconfig(self._btn_rects[self._hover], fill=orig_bg)
            self._hover = None

    def _on_tap(self, event):
        label = self._label_at(event.x, event.y)
        if label is None:
            return
        _, _, speed = next(b for b in self._buttons if b[0] == label)
        if speed is None:
            # EXIT
            self.game.running = False
        else:
            self.game.start_game(speed=speed)
            # Hide immediately — game state will transition to COUNTDOWN
            self._set_visible(False)

    # ── visibility ───────────────────────────────────────────────

    def _set_visible(self, show: bool):
        if show == self._visible:
            return
        self._visible = show
        if show:
            self.win.deiconify()
            self.win.lift()
            self.win.attributes("-fullscreen", True)
        else:
            self.win.withdraw()

    # ── periodic state sync ───────────────────────────────────────

    def _schedule_update(self):
        self._update()
        self.win.after(200, self._schedule_update)

    def _update(self):
        with self.game.lock:
            state = self.game.state
        self._set_visible(state in ("LOBBY", "IDLE"))


# ─────────────────────────────────────────────────────────────────
# Status (display-only) window  — team hearts
# ─────────────────────────────────────────────────────────────────
class StatusScreen:
    """
    Full-screen window on the display-only monitor.

    Layout (landscape):

      ┌─────────────────┬─────────────────┐
      │   TEAM A (RED)  │  TEAM B (BLUE)  │
      │                 │                 │
      │   ♥ ♥ ♥ ♥ ♥    │   ♥ ♥ ♥ ♥ ♥    │
      │                 │                 │
      │    [state]      │    [state]      │
      └─────────────────┴─────────────────┘

    The heart icons scale with window size.
    """

    # Tiny heart bitmap (16×14) drawn with canvas polygons — no image file needed
    # Points are relative; scaled at draw time.
    _HEART_POLY = [
        0.25, 0.0,
        0.5,  0.25,
        0.75, 0.0,
        1.0,  0.25,
        1.0,  0.5,
        0.5,  1.0,
        0.0,  0.5,
        0.0,  0.25,
    ]

    def __init__(self, root: tk.Tk, game, monitor_x: int, monitor_y: int):
        self.game = game

        self.win = tk.Toplevel(root)
        self.win.title("Ray Wars – Status")
        self.win.configure(bg=_BG)
        self.win.overrideredirect(True)
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", lambda: None)

        self.win.geometry(f"+{monitor_x}+{monitor_y}")
        self.win.attributes("-fullscreen", True)
        self.win.lift()

        self.canvas = tk.Canvas(self.win, bg=_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self._last_hearts = [-1, -1]
        self._last_state  = ""

        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self._schedule_update()

    # ── drawing ──────────────────────────────────────────────────

    def _heart_points(self, cx, cy, size):
        """Return flat list of canvas coords for a heart polygon centred at cx,cy."""
        pts = []
        hw = size * 0.6   # half-width
        hh = size * 0.5   # half-height
        # Two bumps on top + V at bottom, approximated as octagon
        for i in range(0, len(self._HEART_POLY), 2):
            px = cx - hw + self._HEART_POLY[i]     * size * 1.2
            py = cy - hh + self._HEART_POLY[i + 1] * size
            pts += [px, py]
        return pts

    def _draw_heart(self, cx, cy, size, filled, team):
        on_col  = _HEART_ON_A  if team == 0 else _HEART_ON_B
        off_col = _HEART_OFF_A if team == 0 else _HEART_OFF_B
        color   = on_col if filled else off_col
        pts = self._heart_points(cx, cy, size)
        self.canvas.create_polygon(pts, fill=color, outline=color, smooth=False)

    def _redraw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()  or self.win.winfo_screenwidth()
        h = self.canvas.winfo_height() or self.win.winfo_screenheight()

        with self.game.lock:
            hearts = list(self.game.hearts)
            state  = self.game.state
            winner = self.game._winner

        half_w = w // 2

        # ── vertical divider ─────────────────────────────────────
        divider_x = half_w
        self.canvas.create_line(
            divider_x, 0, divider_x, h,
            fill=_DIVIDER, width=4
        )

        # ── each half ────────────────────────────────────────────
        for team in range(2):
            left_x   = 0       if team == 0 else half_w + 4
            right_x  = half_w  if team == 0 else w
            panel_w  = right_x - left_x
            cx       = left_x + panel_w // 2
            label    = "TEAM A" if team == 0 else "TEAM B"
            t_color  = _TEAM_A  if team == 0 else _TEAM_B

            # Team label
            label_font_sz = max(14, h // 12)
            self.canvas.create_text(
                cx, h * 0.12,
                text=label, fill=t_color,
                font=("Helvetica", label_font_sz, "bold")
            )

            # Hearts row
            n_hearts  = hearts[team]
            max_h     = 5                         # MAX_HEARTS
            heart_sz  = min(panel_w // (max_h + 2), h // 5)
            gap       = heart_sz * 1.6
            total_w   = gap * (max_h - 1)
            start_x   = cx - total_w / 2

            heart_y = h * 0.45
            for i in range(max_h):
                hx = start_x + i * gap
                self._draw_heart(hx, heart_y, heart_sz, i < n_hearts, team)

            # State label below hearts
            state_txt = state
            if state == "GAMEOVER":
                state_txt = ("TEAM A WINS!" if winner == 0 else "TEAM B WINS!") if winner is not None else "GAME OVER"
            elif state == "COUNTDOWN":
                state_txt = "GET READY!"
            elif state == "PLAYING":
                state_txt = "PLAYING"
            elif state == "LOBBY":
                state_txt = "WAITING..."
            elif state == "IDLE":
                state_txt = "SELECT SPEED"

            state_font_sz = max(10, h // 18)
            self.canvas.create_text(
                cx, h * 0.75,
                text=state_txt, fill=_LABEL_FG,
                font=("Helvetica", state_font_sz, "bold")
            )

    # ── periodic refresh ─────────────────────────────────────────

    def _schedule_update(self):
        self._update()
        self.win.after(100, self._schedule_update)   # ~10 Hz

    def _update(self):
        with self.game.lock:
            hearts = list(self.game.hearts)
            state  = self.game.state
        if hearts != self._last_hearts or state != self._last_state:
            self._last_hearts = hearts
            self._last_state  = state
            self._redraw()


# ─────────────────────────────────────────────────────────────────
# Public entry-point
# ─────────────────────────────────────────────────────────────────
def launch(game):
    """
    Create the Tkinter root (hidden) and both external screen windows.
    Blocks until the game ends (runs Tkinter mainloop on this thread).

    Call this from the main thread after starting all game/network threads.

    Monitor positions come from ray_wars_config.json:
      "touch_monitor":  {"x": 1920, "y": 0}
      "status_monitor": {"x": 3840, "y": 0}
    """
    cfg = _cfg()

    touch_pos  = cfg.get("touch_monitor",  {"x": 1920, "y": 0})
    status_pos = cfg.get("status_monitor", {"x": 3840, "y": 0})

    root = tk.Tk()
    root.withdraw()   # hide the root window — we only use Toplevels

    touch  = TouchScreen( root, game, touch_pos["x"],  touch_pos["y"])
    status = StatusScreen(root, game, status_pos["x"], status_pos["y"])

    # Poll game.running so we can exit the mainloop cleanly
    def _check_running():
        if not game.running:
            root.quit()
        else:
            root.after(200, _check_running)

    root.after(200, _check_running)
    root.mainloop()