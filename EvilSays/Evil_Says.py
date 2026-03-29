import json, os, queue, random, socket, threading, time, math
import tkinter as tk
from tkinter import ttk

# ─────────────────────────────────────────────────────────────────────────────
# PROTOCOL HARDWARE / SIMULATOR
# ─────────────────────────────────────────────────────────────────────────────
UDP_DEVICE_PORT   = 4626
UDP_RECEIVER_PORT = 7800
FRAME_DATA_LEN    = 132

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

def _chk(data): return PASSWORD_ARRAY[sum(data) & 0xFF]

class NetService:
    def __init__(self, target_ip="127.0.0.1"):
        self._ip = target_ip; self._seq = 0; self._sq = queue.Queue(maxsize=30)
        self._running = True; self.on_button = None; self._prev = {}
        threading.Thread(target=self._send_loop, daemon=True).start()
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def push_frame(self, leds):
        f = bytearray(FRAME_DATA_LEN)
        for (ch, led), (r, g, b) in leds.items():
            if 1 <= ch <= 4 and 0 <= led <= 10:
                f[led*12 + (ch-1)] = g; f[led*12 + 4 + (ch-1)] = r; f[led*12 + 8 + (ch-1)] = b
        try: self._sq.put_nowait(bytes(f))
        except: pass

    def _send_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while self._running:
            try: frame = self._sq.get(timeout=1.0)
            except: continue
            self._seq = (self._seq + 1) & 0xFFFF
            ep = (self._ip, UDP_DEVICE_PORT)
            p_s = bytearray([0x75, 0, 0, 0, 8, 2, 0, 0, 0x33, 0x44, (self._seq>>8)&0xFF, self._seq&0xFF, 0, 0])
            p_s.append(_chk(p_s)); sock.sendto(p_s, ep); time.sleep(0.005)
            p_i = self._build_cmd(0x8877, 0xFFF0, bytearray([0,11]*4))
            p_i.append(_chk(p_i)); sock.sendto(p_i, ep); time.sleep(0.005)
            p_d = self._build_cmd(0x8877, 0x0000, frame)
            p_d.append(_chk(p_d)); sock.sendto(p_d, ep); time.sleep(0.005)
            p_e = bytearray([0x75, 0, 0, 0, 8, 2, 0, 0, 0x55, 0x66, (self._seq>>8)&0xFF, self._seq&0xFF, 0, 0])
            p_e.append(_chk(p_e)); sock.sendto(p_e, ep)

    def _build_cmd(self, d_id, loc, pay):
        inner = bytes([2,0,0, (d_id>>8)&0xFF, d_id&0xFF, (loc>>8)&0xFF, loc&0xFF, (len(pay)>>8)&0xFF, len(pay)&0xFF]) + pay
        h = bytearray([0x75, 0, 0, (len(inner)>>8)&0xFF, len(inner)&0xFF]) + inner
        h[10], h[11] = (self._seq>>8)&0xFF, self._seq&0xFF
        return h

    def _recv_loop(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", UDP_RECEIVER_PORT))
        while self._running:
            try:
                data, _ = s.recvfrom(1024)
                if len(data) == 687:
                    for ch in range(1, 5):
                        base = 2 + (ch-1)*171
                        for led in range(11):
                            pressed = (data[base + 1 + led] == 0xCC)
                            if pressed and not self._prev.get((ch, led)):
                                if self.on_button: self.on_button(ch, led)
                            self._prev[(ch, led)] = pressed
            except: pass

# ─────────────────────────────────────────────────────────────────────────────
# LOGICA JOCULUI
# ─────────────────────────────────────────────────────────────────────────────
C_OFF=(0,0,0); C_CYAN=(0,255,255); C_GREEN=(0,255,0); C_RED=(255,0,0); 
C_GOLD=(255,180,0); C_PURPLE=(200,0,255); C_WHITE=(255,255,255); C_YELLOW=(255,255,0)
WALL_NAMES = {1: "Sud", 2: "Est", 3: "Nord", 4: "Vest"}

class EvilMemoryGame:
    def __init__(self, net, ui, diff):
        self.net = net; self.ui = ui; self.diff = diff
        self.score = 0; self.round = 1; self.ended = False
        self.pattern = set(); self.guessed = set(); self.wrong_pressed = set(); self.frenzy_tiles = set()
        self.phase = "START_ANIMATION"; self.eye_state = "OFF"; self.eye_timer = time.time(); self.eye_wall = 0
        
        cfg = {"EASY":(2,4,3), "MEDIUM":(3,5,2), "HARD":(5,6,1)} 
        self.base_tiles, self.T_GAZE, self.T_WARN = cfg[diff]

    def start(self):
        threading.Thread(target=self._main_loop, daemon=True).start()

    def _generate_round(self):
        # Dificultate progresivă bazată pe scor
        num_tiles = self.base_tiles + (self.score // 5)
        valid_slots = [(c,l) for c in range(1,5) for l in range(1,11)]
        self.pattern = set(random.sample(valid_slots, min(num_tiles, 35)))
        self.guessed.clear(); self.wrong_pressed.clear(); self.frenzy_tiles.clear()
        self.ui.on_game_event("log", f"🎯 Misiune Nouă! Memorați cele {len(self.pattern)} puncte.")

    def _run_start_animation(self):
        self.ui.on_game_event("log", "🌀 Inițializare sistem...")
        start_time = time.time()
        delay = 0.1; curr_wall = 1
        while time.time() - start_time < 3.0:
            states = { (c,l): C_OFF for c in range(1,5) for l in range(11) }
            for l in range(1, 11): states[(curr_wall, l)] = C_CYAN
            self.net.push_frame(states); time.sleep(delay)
            delay = max(0.02, delay * 0.85); curr_wall = (curr_wall % 4) + 1

    def _run_roulette(self):
        self.ui.on_game_event("log", "👁️ Ochiul Malefic scanează...")
        curr = random.randint(1,4)
        for i in range(15):
            # Trimitere pachet de curățare (doar ochiul alb, restul OFF)
            states = { (c,l): C_OFF for c in range(1,5) for l in range(11) }
            states[(curr, 0)] = C_WHITE
            self.net.push_frame(states)
            time.sleep(0.04 + i*0.02)
            curr = (curr%4)+1
        self.eye_wall = curr

    def _main_loop(self):
        self._run_start_animation()
        self._generate_round()
        
        while not self.ended:
            now = time.time()

            # --- START RULETĂ ---
            if self.eye_state == "OFF":
                self.phase = "ROULETTE"
                # Curățăm ecranele înainte de ruletă
                self.guessed.clear(); self.wrong_pressed.clear()
                self._run_roulette()
                self.eye_state = "WARNING"; self.eye_timer = time.time()
                self.ui.on_game_event("log", f"⚠️ Atenție! Ochiul s-a oprit pe {WALL_NAMES[self.eye_wall]}!")

            # --- WARNING (LICĂRIRE) ---
            elif self.eye_state == "WARNING":
                if now - self.eye_timer > self.T_WARN:
                    if random.random() < 0.2: # Surprise Factor
                        self.eye_state = "FRENZY"
                        self.frenzy_tiles = set((self.eye_wall, l) for l in random.sample(range(1,11), 4))
                        self.ui.on_game_event("log", "🌟 FEBRA DE AUR! Loviți MOV!")
                    else:
                        self.eye_state = "GAZE"
                        self.ui.on_game_event("log", "🔴 OCHI DESCHIS! NU VĂ MIȘCAȚI!")
                    self.eye_timer = now; self._refresh()
                else:
                    col = C_YELLOW if int(now*10)%2==0 else C_OFF
                    # Menținem restul pereților stinși în timpul warning-ului
                    st = { (c,l): C_OFF for c in range(1,5) for l in range(11) }
                    st[(self.eye_wall, 0)] = col
                    self.net.push_frame(st)

            # --- GAZE / FRENZY (OCHIUL TE VEDE) ---
            elif self.eye_state in ["GAZE", "FRENZY"]:
                if now - self.eye_timer > self.T_GAZE:
                    self.eye_state = "ACTION"; self.eye_timer = now
                    self.ui.on_game_event("log", "🟢 Ochi închis! ACȚIONAȚI!"); self._refresh()
                else:
                    self._refresh()

            # --- ACTION (AI VOIE SĂ APESI) ---
            elif self.eye_state == "ACTION":
                if len(self.guessed) == len(self.pattern):
                    # AUTOMATIC NEXT ROUND
                    self.ui.on_game_event("log", "🎉 EXCELENT! Generare rundă nouă...")
                    self.round += 1; self._generate_round()
                    self.eye_state = "OFF" # Declanșează ruleta imediat
                elif now - self.eye_timer > 10.0: # Timeout
                    self.ui.on_game_event("log", "🔄 Timp expirat! Reset pattern."); 
                    self.eye_state = "OFF"
                self._refresh()

            elif self.phase == "STUNNED":
                if now - self.phase_timer > 2.0:
                    self.phase = "ROULETTE"; self.eye_state = "OFF"
                else:
                    self._set_all_stun(C_RED if int(now*10)%2==0 else C_OFF)

            time.sleep(0.05)

    def on_button(self, ch, led):
        if self.ended or led == 0 or self.phase == "STUNNED": return

        # INTERZIS ÎN GAZE
        if self.eye_state == "GAZE":
            self.score = max(0, self.score - 5)
            self.phase = "STUNNED"; self.phase_timer = time.time()
            self.ui.on_game_event("log", "☠️ TE-A VĂZUT MIȘCÂNDU-TE! -5 pct."); self.ui.on_game_event("update_score", self.score)
            return

        # FRENZY MODE (MOV)
        if self.eye_state == "FRENZY" and ch == self.eye_wall:
            if (ch, led) in self.frenzy_tiles:
                self.score += 3; self.frenzy_tiles.remove((ch, led))
                self.ui.on_game_event("update_score", self.score); self._refresh(); return

        # ACTION MODE (CYAN)
        if self.eye_state == "ACTION":
            if (ch, led) in self.pattern:
                if (ch, led) not in self.guessed: 
                    self.guessed.add((ch, led)); self.score += 1
            else:
                if (ch, led) not in self.wrong_pressed: 
                    self.score = max(0, self.score - 2); self.wrong_pressed.add((ch, led))
            self.ui.on_game_event("update_score", self.score); self._refresh()

    def _refresh(self):
        states = {}
        for ch in range(1, 5):
            for l in range(1, 11):
                # Pattern-ul apare doar în GAZE sau ACTION
                if (self.eye_state in ["GAZE", "ACTION"]) and (ch, l) in self.pattern and (ch, l) not in self.guessed:
                    col = C_CYAN
                elif (ch, l) in self.guessed: col = C_GREEN
                elif (ch, l) in self.wrong_pressed: col = C_RED
                elif (ch, l) in self.frenzy_tiles: col = C_PURPLE
                else: col = C_OFF
                states[(ch, l)] = col
            
            # Ochiul
            if self.eye_state == "GAZE" and ch == self.eye_wall: states[(ch, 0)] = C_RED
            elif self.eye_state == "FRENZY" and ch == self.eye_wall: states[(ch, 0)] = C_GOLD
            else: states[(ch, 0)] = C_OFF
        self.net.push_frame(states)

    def _set_all_stun(self, col):
        st = {(c,l): col for c in range(1,5) for l in range(11)}; self.net.push_frame(st)

# ─────────────────────────────────────────────────────────────────────────────
# UI 
# ─────────────────────────────────────────────────────────────────────────────
class MemoryGameUI(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("Evil Eye: Final Edition"); self.geometry("450x600"); self.configure(bg="#0a0a0a")
        self.net = NetService(); self.game = None
        self.menu = tk.Frame(self, bg="#0a0a0a"); self.menu.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(self.menu, text="EYE: CO-OP MEMORY", font=("Arial", 20, "bold"), fg="cyan", bg="#0a0a0a").pack(pady=20)
        self.d_var = tk.StringVar(value="MEDIUM")
        for d in ["EASY", "MEDIUM", "HARD"]: tk.Radiobutton(self.menu, text=d, variable=self.d_var, value=d, fg="white", bg="#0a0a0a", font=("Arial", 11)).pack()
        tk.Button(self.menu, text="START MISSION", command=self.start, font=("Arial", 12), bg="#008080", fg="white", relief="flat", padx=20).pack(pady=20)

    def start(self):
        self.menu.destroy()
        self.lbl = tk.Label(self, text="SCORE: 0", font=("Arial", 30, "bold"), fg="white", bg="#0a0a0a"); self.lbl.pack(pady=10)
        self.txt = tk.Text(self, height=12, bg="black", fg="#00ced1", font=("Consolas", 10)); self.txt.pack(fill="x", side="bottom")
        self.game = EvilMemoryGame(self.net, self, self.d_var.get()); self.net.on_button = self.game.on_button; self.game.start()

    def on_game_event(self, event, *args):
        if event == "update_score": self.lbl.config(text=f"SCORE: {args[0]}")
        elif event == "log": self.txt.insert("1.0", f"[{time.strftime('%H:%M:%S')}] {args[0]}\n")

if __name__ == "__main__":
    MemoryGameUI().mainloop()