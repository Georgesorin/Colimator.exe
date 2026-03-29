import tkinter as tk
from tkinter import font
import time

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import screeninfo

def get_geom_str(w, h, x, y):
    x_str = f"+{int(x)}" if int(x) >= 0 else str(int(x))
    y_str = f"+{int(y)}" if int(y) >= 0 else str(int(y))
    return f"{int(w)}x{int(h)}{x_str}{y_str}"

class SandrunScreens:
    def __init__(self, game):
        self.game = game
        
        # PRELUARE DIRECTA MONITOARE (Obligatoriu 2 ecrane)
        monitors = screeninfo.get_monitors()
        monitors.sort(key=lambda m: m.x) 
        
        m_staff = monitors[0] 
        m_view = monitors[1] if len(monitors) > 1 else monitors[0] # Fallback mic daca pica mufa

        # --- FEREASTRA STAFF (Monitor 1) ---
        self.root = tk.Tk()
        self.root.title("SAND RUN - Staff Control")
        self.root.configure(bg="#1e1e1e")
        self.root.geometry(get_geom_str(m_staff.width, m_staff.height, m_staff.x, m_staff.y))
        self.root.overrideredirect(True)
        self.root.lift()
        self.root.bind("<Escape>", lambda e: self.stop_game())
        
        self.sel_diff = "medium"
        self.btn_diff = {}
        self.setup_staff_ui()
        
        # --- FEREASTRA JUCATORI (Monitor 2) ---
        self.view = tk.Toplevel(self.root)
        self.view.title("SAND RUN - Scoreboard")
        self.view.configure(bg="black")
        self.view.geometry(get_geom_str(m_view.width, m_view.height, m_view.x, m_view.y)) 
        self.view.overrideredirect(True)
        self.view.lift()
        
        self.view.bind("<Escape>", lambda e: self.view.overrideredirect(False))
        self.setup_view_ui()
        self.update_loop()

    def select_diff(self, diff):
        self.sel_diff = diff
        for d, btn in self.btn_diff.items():
            btn.configure(bg="#ffaa00" if d == diff else "#4a3500", fg="white" if d == diff else "#888888")

    def start_match(self):
        self.game.start_game(self.sel_diff)

    def stop_game(self):
        self.game.running = False
        self.root.destroy()

    def setup_staff_ui(self):
        title_font = font.Font(family="Helvetica", size=28, weight="bold")
        lbl_font = font.Font(family="Helvetica", size=18, weight="bold")
        btn_font = font.Font(family="Helvetica", size=20, weight="bold")
        start_font = font.Font(family="Helvetica", size=24, weight="bold")
        
        tk.Frame(self.root, bg="#1e1e1e", height=40).pack() 
        tk.Label(self.root, text="🏜️ SAND RUN - SETĂRI MECI", font=title_font, bg="#1e1e1e", fg="#e6be8a").pack(pady=20)
        
        f_diff = tk.Frame(self.root, bg="#1e1e1e")
        f_diff.pack(pady=20)
        tk.Label(f_diff, text="Dificultate Joc:", font=lbl_font, bg="#1e1e1e", fg="white", width=15, anchor="e").pack(side=tk.LEFT, padx=15)
        
        difficulties = [("UȘOR", "easy"), ("MEDIU", "medium"), ("GREU", "hard")]
        for text, val in difficulties:
            btn = tk.Button(f_diff, text=text, font=btn_font, width=8, height=1, command=lambda v=val: self.select_diff(v), relief=tk.FLAT)
            btn.pack(side=tk.LEFT, padx=10)
            self.btn_diff[val] = btn

        self.select_diff("medium")

        f_act = tk.Frame(self.root, bg="#1e1e1e")
        f_act.pack(pady=40)
        tk.Button(f_act, text="▶ START RUNDĂ", font=start_font, bg="#00cc44", fg="white", width=20, height=2, command=self.start_match, relief=tk.RAISED).pack(pady=10)
        tk.Button(f_act, text="✖ OPREȘTE TOT", font=btn_font, bg="#555555", fg="white", width=15, command=self.stop_game, relief=tk.FLAT).pack(pady=15)

    def setup_view_ui(self):
        self.lbl_title = tk.Label(self.view, text="SAND RUN", font=("Impact", 100), bg="black", fg="#e6be8a")
        self.lbl_title.pack(pady=(40, 20)) 
        
        f_main = tk.Frame(self.view, bg="black")
        f_main.pack(fill=tk.X, pady=40, padx=50)
        
        f_gems = tk.Frame(f_main, bg="black")
        f_gems.pack(side=tk.LEFT, expand=True)
        tk.Label(f_gems, text="COMORI COLECTATE", font=("Helvetica", 35, "bold"), bg="black", fg="#00ffff").pack(pady=(0, 20))
        self.lbl_gems = tk.Label(f_gems, text="0 / 15", font=("Impact", 130), bg="black", fg="white")
        self.lbl_gems.pack()
        
        f_time = tk.Frame(f_main, bg="black")
        f_time.pack(side=tk.LEFT, expand=True)
        tk.Label(f_time, text="TIMP RĂMAS", font=("Helvetica", 35, "bold"), bg="black", fg="#e6be8a").pack(pady=(0, 20))
        self.lbl_time = tk.Label(f_time, text="60s", font=("Impact", 180), bg="black", fg="white")
        self.lbl_time.pack()
        
        f_lava = tk.Frame(f_main, bg="black")
        f_lava.pack(side=tk.LEFT, expand=True)
        tk.Label(f_lava, text="LOVITURI LAVA", font=("Helvetica", 35, "bold"), bg="black", fg="#ff4444").pack(pady=(0, 20))
        self.lbl_hits = tk.Label(f_lava, text="0 / 10", font=("Impact", 130), bg="black", fg="white")
        self.lbl_hits.pack()
        
        self.lbl_status = tk.Label(self.view, text="AȘTEPTARE JUCĂTORI...", font=("Helvetica", 60, "bold"), bg="black", fg="#aaaaaa")
        self.lbl_status.pack(side=tk.BOTTOM, pady=80, ipady=15)

    def update_loop(self):
        if not self.game.running:
            self.root.destroy()
            return
            
        with self.game.lock:
            state = self.game.state
            gems = self.game.gems_collected
            hits = self.game.hits_count
            survive_time = self.game.survive_time
            gameover_reason = self.game.gameover_reason
            startup_step = self.game.startup_step
            target_gems = self.game.target_gems
            max_hits = self.game.max_hits
            round_dur = self.game.round_duration
            diff = self.game.difficulty

        if state in ["LOBBY", "STARTUP"]:
            time_left = round_dur
        else:
            time_left = max(0, round_dur - int(survive_time))

        self.lbl_gems.config(text=f"{gems} / {target_gems}")
        self.lbl_hits.config(text=f"{hits} / {max_hits}")
        self.lbl_time.config(text=f"{time_left}s")

        if time_left <= 10 and state == "PLAYING":
            self.lbl_time.config(fg="#ff4444" if int(time.time() * 5) % 2 == 0 else "white")
        else:
            self.lbl_time.config(fg="white")
            
        self.lbl_gems.config(fg="#00cc44" if gems >= target_gems else "white")
        self.lbl_hits.config(fg="#ff4444" if hits >= max_hits - 2 and int(time.time() * 5) % 2 == 0 else "white")

        if state == "LOBBY": self.lbl_status.config(text="AȘTEPTARE JUCĂTORI...", fg="#aaaaaa")
        elif state == "STARTUP": self.lbl_status.config(text=f"ÎNCEPE ÎN {startup_step}...", fg="#ffaa00")
        elif state == "PLAYING": self.lbl_status.config(text=f"FUGIȚI DUPĂ COMORI! (Dificultate: {diff.upper()})", fg="#e6be8a")
        elif state == "GAMEOVER":
            if "WON" in gameover_reason: self.lbl_status.config(text="VICTORIE! AȚI COLECTAT COMORILE!", fg="#00cc44")
            else: self.lbl_status.config(text="JOC TERMINAT! PREA MULTE LOVITURI DE LAVĂ!", fg="#ff4444")

        self.root.after(100, self.update_loop)

def launch(game):
    app = SandrunScreens(game)
    app.root.mainloop()