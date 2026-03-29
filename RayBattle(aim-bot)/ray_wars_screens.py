import tkinter as tk
from tkinter import font
import time
import math

# --- FIX PENTRU DPI (Taie zoom-ul automat din Windows) ---
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import screeninfo

class RayWarsScreens:
    # =======================================================
    # OFFSET MONITOR 2: Daca fereastra tot nu e unde trebuie,
    # incearca sa modifici valoarea in -1920 (daca e in stanga).
    # =======================================================
    MONITOR_2_OFFSET = 1920 

    def __init__(self, game):
        self.game = game
        
        # =======================================================
        # AUTODETECTARE MONITOARE
        # =======================================================
        try:
            monitors = screeninfo.get_monitors()
            # Sortam monitoarele dupa pozitia pe X pentru consistenta
            monitors.sort(key=lambda m: m.x) 
            
            if len(monitors) >= 2:
                m_staff = monitors[0] # Ecranul din stanga
                m_view = monitors[1]  # Ecranul din dreapta
            else:
                m_staff = monitors[0]
                m_view = monitors[0] # Fallback daca ai un singur ecran activ
                
        except Exception as e:
            print(f"[!] Eroare ScreenInfo: {e}. Se foloseste Fallback.")
            class DummyMonitor:
                def __init__(self, w, h, x, y):
                    self.width, self.height, self.x, self.y = w, h, x, y
            m_staff = DummyMonitor(1920, 1080, 0, 0)
            m_view = DummyMonitor(1920, 1080, 1920, 0)

        # --- 1. FEREASTRA PRINCIPALA (STAFF CONTROL - MONITOR 1) ---
        self.root = tk.Tk()
        self.root.title("RAY WARS - Staff Control Panel")
        self.root.configure(bg="#1e1e1e")
        
        # Setam fereastra EXACT pe coordonatele primului monitor fara margini
        self.root.geometry(f"{m_staff.width}x{m_staff.height}+{m_staff.x}+{m_staff.y}")
        self.root.overrideredirect(True)
        
        # Tasta ESC acum inchide tot programul pentru personal
        self.root.bind("<Escape>", lambda e: self.stop_game())
        
        self.sel_pa = 1
        self.sel_pb = 1
        self.sel_speed = "medium"
        
        self.btn_pa = {}
        self.btn_pb = {}
        self.btn_spd = {}
        
        self.setup_staff_ui()
        
        # --- 2. FEREASTRA SECUNDARA (VIEW SCREEN PT JUCATORI - MONITOR 2) ---
        self.view = tk.Toplevel(self.root)
        self.view.title("RAY WARS - Scoreboard")
        self.view.configure(bg="black")
        
        # TRUC PENTRU MULTI-MONITOR
        self.view.overrideredirect(True)
        self.view.geometry(f"{m_view.width}x{m_view.height}+{m_view.x}+{m_view.y}") 
        
        def force_fullscreen():
            self.view.attributes("-fullscreen", True)
        self.root.after(100, force_fullscreen)
        
        def escape_view(e):
            self.view.attributes("-fullscreen", False)
            self.view.overrideredirect(False) 
            
        self.view.bind("<Escape>", escape_view)
        self.setup_view_ui()
        
        self.update_loop()

    # ==========================================
    # LOGICA DE SELECTIE SI CULORI
    # ==========================================
    def select_pa(self, num):
        self.sel_pa = num
        for n, btn in self.btn_pa.items():
            btn.configure(bg="#ff4444" if n == num else "#4a1c1c", fg="white" if n == num else "#888888")

    def select_pb(self, num):
        self.sel_pb = num
        for n, btn in self.btn_pb.items():
            btn.configure(bg="#4444ff" if n == num else "#1c1c4a", fg="white" if n == num else "#888888")

    def select_speed(self, spd):
        self.sel_speed = spd
        for s, btn in self.btn_spd.items():
            btn.configure(bg="#ffaa00" if s == spd else "#4a3500", fg="white" if s == spd else "#888888")

    def start_match(self):
        self.game.start_game(self.sel_pa, self.sel_pb, self.sel_speed)

    def stop_game(self):
        self.game.running = False
        self.root.destroy()

    # ==========================================
    # UI STAFF - REDUS LA ~60%
    # ==========================================
    def setup_staff_ui(self):
        # Fonturi reduse la ~60%
        title_font = font.Font(family="Helvetica", size=28, weight="bold")
        lbl_font = font.Font(family="Helvetica", size=16, weight="bold")
        btn_font = font.Font(family="Helvetica", size=18, weight="bold")
        start_font = font.Font(family="Helvetica", size=24, weight="bold")
        
        tk.Frame(self.root, bg="#1e1e1e", height=40).pack() 
        
        tk.Label(self.root, text="🎮 RAY WARS - SETĂRI MECI", font=title_font, bg="#1e1e1e", fg="white").pack(pady=20)
        
        # --- ECHIPA ROSIE ---
        f_red = tk.Frame(self.root, bg="#1e1e1e")
        f_red.pack(pady=10)
        tk.Label(f_red, text="Jucători ROȘU (Sus):", font=lbl_font, bg="#1e1e1e", fg="#ff4444", width=25, anchor="e").pack(side=tk.LEFT, padx=10)
        for i in range(1, 6):
            btn = tk.Button(f_red, text=str(i), font=btn_font, width=4, height=1,
                            command=lambda n=i: self.select_pa(n), relief=tk.FLAT)
            btn.pack(side=tk.LEFT, padx=5)
            self.btn_pa[i] = btn
            
        # --- ECHIPA ALBASTRA ---
        f_blue = tk.Frame(self.root, bg="#1e1e1e")
        f_blue.pack(pady=10)
        tk.Label(f_blue, text="Jucători ALBASTRU (Jos):", font=lbl_font, bg="#1e1e1e", fg="#4444ff", width=25, anchor="e").pack(side=tk.LEFT, padx=10)
        for i in range(1, 6):
            btn = tk.Button(f_blue, text=str(i), font=btn_font, width=4, height=1,
                            command=lambda n=i: self.select_pb(n), relief=tk.FLAT)
            btn.pack(side=tk.LEFT, padx=5)
            self.btn_pb[i] = btn

        # --- VITEZA ---
        f_spd = tk.Frame(self.root, bg="#1e1e1e")
        f_spd.pack(pady=20)
        tk.Label(f_spd, text="Viteză Meci:", font=lbl_font, bg="#1e1e1e", fg="#ffaa00", width=25, anchor="e").pack(side=tk.LEFT, padx=10)
        
        speeds = [("SLOW", "slow"), ("MEDIUM", "medium"), ("FAST", "fast")]
        for text, val in speeds:
            btn = tk.Button(f_spd, text=text, font=btn_font, width=8, height=1,
                            command=lambda v=val: self.select_speed(v), relief=tk.FLAT)
            btn.pack(side=tk.LEFT, padx=5)
            self.btn_spd[val] = btn

        self.select_pa(1)
        self.select_pb(1)
        self.select_speed("medium")

        # --- BUTOANE ACTIUNE ---
        f_act = tk.Frame(self.root, bg="#1e1e1e")
        f_act.pack(pady=40)
        
        tk.Button(f_act, text="▶ START MECI", font=start_font, bg="#00cc44", fg="white", 
                  width=20, height=2, command=self.start_match, relief=tk.RAISED).pack(pady=10)
                  
        tk.Button(f_act, text="✖ OPREȘTE TOT", font=btn_font, bg="#555555", fg="white", 
                  width=15, command=self.stop_game, relief=tk.FLAT).pack(pady=10)

    # ==========================================
    # UI VIEW SCREEN (JUCATORI) - A RAMAS MARE
    # ==========================================
    def setup_view_ui(self):
        self.lbl_title = tk.Label(self.view, text="RAY WARS", font=("Impact", 80), bg="black", fg="white")
        self.lbl_title.pack(pady=(10, 0)) 
        
        f_scores = tk.Frame(self.view, bg="black")
        f_scores.pack(fill=tk.X, pady=(0, 10)) 
        
        self.lbl_score_red = tk.Label(f_scores, text="0", font=("Impact", 220), bg="black", fg="#ff4444")
        self.lbl_score_red.pack(side=tk.LEFT, expand=True, anchor=tk.E, padx=(0, 40))
        
        tk.Label(f_scores, text="-", font=("Impact", 150), bg="black", fg="#555555").pack(side=tk.LEFT, pady=(0, 30))
        
        self.lbl_score_blue = tk.Label(f_scores, text="0", font=("Impact", 220), bg="black", fg="#4444ff")
        self.lbl_score_blue.pack(side=tk.LEFT, expand=True, anchor=tk.W, padx=(40, 0))
        
        f_hps = tk.Frame(self.view, bg="black")
        f_hps.pack(fill=tk.X, pady=(0, 20))
        
        f_red_hp_col = tk.Frame(f_hps, bg="black")
        f_red_hp_col.pack(side=tk.LEFT, expand=True)
        
        f_blue_hp_col = tk.Frame(f_hps, bg="black")
        f_blue_hp_col.pack(side=tk.LEFT, expand=True)

        self.canvas_w = 880 
        self.canvas_h = 180 
        
        tk.Label(f_red_hp_col, text="HP ROȘU", font=("Helvetica", 28, "bold"), bg="black", fg="#ff4444").pack(pady=(10, 0))
        self.can_red_hp = tk.Canvas(f_red_hp_col, bg="black", highlightthickness=0, width=self.canvas_w, height=self.canvas_h)
        self.can_red_hp.pack()
        
        tk.Label(f_blue_hp_col, text="HP ALBASTRU", font=("Helvetica", 28, "bold"), bg="black", fg="#4444ff").pack(pady=(10, 0))
        self.can_blue_hp = tk.Canvas(f_blue_hp_col, bg="black", highlightthickness=0, width=self.canvas_w, height=self.canvas_h)
        self.can_blue_hp.pack()

        self.lbl_status = tk.Label(self.view, text="AȘTEPTARE JUCĂTORI...", font=("Helvetica", 52, "bold"), bg="black", fg="#aaaaaa")
        self.lbl_status.pack(pady=20, ipady=10)
        
        self.lbl_info = tk.Label(self.view, text="", font=("Helvetica", 35), bg="black", fg="#666666")
        self.lbl_info.pack(side=tk.BOTTOM, pady=20)

    # ==========================================
    # FUNCTIE DESENARE HEXAGON
    # ==========================================
    def draw_hexagon(self, canvas, x, y, radius, fill_color, outline_color, outline_width):
        points = []
        for i in range(6):
            angle_rad = math.pi / 3 * i
            px = x + radius * math.cos(angle_rad)
            py = y + radius * math.sin(angle_rad)
            points.append(px)
            points.append(py)
        canvas.create_polygon(points, fill=fill_color, outline=outline_color, width=outline_width)

    # ==========================================
    # UPDATE LOOP
    # ==========================================
    def update_loop(self):
        if not self.game.running:
            self.root.destroy()
            return
            
        with self.game.lock:
            state = self.game.state
            score_a, score_b = self.game.score
            text_gameover = self.game.gameover_text
            pa = self.game.players_a
            pb = self.game.players_b
            spd = self.game.speed_preset
            hearts = self.game.hearts
            max_hp = self.game.max_health
            
        self.lbl_score_red.config(text=str(score_a))
        self.lbl_score_blue.config(text=str(score_b))
        
        color_red_hex = "#ff0000"
        color_blue_hex = "#0000ff"
        color_black_hex = "#000000"
        
        R = 55 
        H_half = math.sqrt(3) * R / 2 
        spacing_x = 1.5 * R 
        zigzag_offset_y = H_half 
        cy_base = self.canvas_h / 2 - zigzag_offset_y / 2 
        outline_w = 4 
        
        if state == "LOBBY":
            self.lbl_status.config(text="AȘTEPTARE START...", fg="#aaaaaa")
            self.lbl_info.config(text="")
            self.can_red_hp.delete("all")
            self.can_blue_hp.delete("all")

        elif state == "STARTUP":
            self.lbl_status.config(text="FIȚI GATA!", fg="#ffaa00")
            self.lbl_info.config(text=f"Setări: {pa} vs {pb}  |  Viteză: {spd.upper()}")
            hearts = [max_hp, max_hp] 

        elif state == "PLAYING":
            self.lbl_status.config(text="", fg="white")
            
            total_w_max = (max_hp - 1) * spacing_x + 2 * R if max_hp > 0 else 0
            start_x_red_fixed = (self.canvas_w - total_w_max) / 2 + R
            start_x_blue_fixed = self.canvas_w - (self.canvas_w - total_w_max) / 2 - R

            self.can_red_hp.delete("all") 
            h_red = hearts[0]
            for i in range(h_red):
                cx = start_x_red_fixed + i * spacing_x
                cy = cy_base
                if i % 2 == 1: cy += zigzag_offset_y
                self.draw_hexagon(self.can_red_hp, cx, cy, R, color_red_hex, color_black_hex, outline_w)

            self.can_blue_hp.delete("all") 
            h_blue = hearts[1]
            for i in range(h_blue):
                cx = start_x_blue_fixed - i * spacing_x
                cy = cy_base
                if i % 2 == 1: cy += zigzag_offset_y
                self.draw_hexagon(self.can_blue_hp, cx, cy, R, color_blue_hex, color_black_hex, outline_w)

        elif state == "GAMEOVER":
            self.can_red_hp.delete("all")
            self.can_blue_hp.delete("all")
            if text_gameover == "":
                self.lbl_status.config(text="RUNDA S-A TERMINAT!", fg="#ffaa00")
            else:
                self.lbl_status.config(text=text_gameover, fg="#ffaa00")

        elif state == "SHOW_SCORE":
            self.lbl_status.config(text="PREGĂTIRE RUNDA URMĂTOARE...", fg="#aaaaaa")

        elif state == "MATCH_OVER":
            color = "#ff4444" if "ROSU" in text_gameover else "#4444ff"
            blink = "white" if int(time.time() * 4) % 2 == 0 else color
            self.lbl_status.config(text=text_gameover, fg=blink)

        self.root.after(100, self.update_loop)

def launch(game):
    app = RayWarsScreens(game)
    app.root.mainloop()