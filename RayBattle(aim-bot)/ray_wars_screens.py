import tkinter as tk
from tkinter import font
import time
import math

class RayWarsScreens:
    def __init__(self, game):
        self.game = game
        
        # --- 1. FEREASTRA PRINCIPALA (STAFF CONTROL - MONITOR 1) ---
        self.root = tk.Tk()
        self.root.title("RAY WARS - Staff Control Panel")
        self.root.geometry("1920x1080+0+0") 
        self.root.configure(bg="#1e1e1e")
        self.root.attributes("-fullscreen", True) 
        
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
        
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
        self.view.geometry("1920x1080+1920+0") 
        self.view.configure(bg="black")
        self.view.attributes("-fullscreen", True) 
        
        self.view.bind("<Escape>", lambda e: self.view.attributes("-fullscreen", False))
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
    # UI STAFF 
    # ==========================================
    def setup_staff_ui(self):
        title_font = font.Font(family="Helvetica", size=48, weight="bold")
        lbl_font = font.Font(family="Helvetica", size=28, weight="bold")
        btn_font = font.Font(family="Helvetica", size=32, weight="bold")
        start_font = font.Font(family="Helvetica", size=40, weight="bold")
        
        tk.Frame(self.root, bg="#1e1e1e", height=80).pack() 
        
        tk.Label(self.root, text="🎮 RAY WARS - SETĂRI MECI", font=title_font, bg="#1e1e1e", fg="white").pack(pady=40)
        
        f_red = tk.Frame(self.root, bg="#1e1e1e")
        f_red.pack(pady=20)
        tk.Label(f_red, text="Jucători ROȘU (Sus):", font=lbl_font, bg="#1e1e1e", fg="#ff4444", width=28, anchor="e").pack(side=tk.LEFT, padx=20)
        for i in range(1, 6):
            btn = tk.Button(f_red, text=str(i), font=btn_font, width=4, height=1,
                            command=lambda n=i: self.select_pa(n), relief=tk.FLAT)
            btn.pack(side=tk.LEFT, padx=10)
            self.btn_pa[i] = btn
            
        f_blue = tk.Frame(self.root, bg="#1e1e1e")
        f_blue.pack(pady=20)
        tk.Label(f_blue, text="Jucători ALBASTRU (Jos):", font=lbl_font, bg="#1e1e1e", fg="#4444ff", width=28, anchor="e").pack(side=tk.LEFT, padx=20)
        for i in range(1, 6):
            btn = tk.Button(f_blue, text=str(i), font=btn_font, width=4, height=1,
                            command=lambda n=i: self.select_pb(n), relief=tk.FLAT)
            btn.pack(side=tk.LEFT, padx=10)
            self.btn_pb[i] = btn

        f_spd = tk.Frame(self.root, bg="#1e1e1e")
        f_spd.pack(pady=40)
        tk.Label(f_spd, text="Viteză Meci:", font=lbl_font, bg="#1e1e1e", fg="#ffaa00", width=28, anchor="e").pack(side=tk.LEFT, padx=20)
        
        speeds = [("SLOW", "slow"), ("MEDIUM", "medium"), ("FAST", "fast")]
        for text, val in speeds:
            btn = tk.Button(f_spd, text=text, font=btn_font, width=8, height=1,
                            command=lambda v=val: self.select_speed(v), relief=tk.FLAT)
            btn.pack(side=tk.LEFT, padx=10)
            self.btn_spd[val] = btn

        self.select_pa(1)
        self.select_pb(1)
        self.select_speed("medium")

        f_act = tk.Frame(self.root, bg="#1e1e1e")
        f_act.pack(pady=80)
        
        tk.Button(f_act, text="▶ START MECI", font=start_font, bg="#00cc44", fg="white", 
                  width=20, height=2, command=self.start_match, relief=tk.RAISED).pack(pady=20)
                  
        tk.Button(f_act, text="✖ OPREȘTE TOT", font=btn_font, bg="#555555", fg="white", 
                  width=15, command=self.stop_game, relief=tk.FLAT).pack(pady=20)

    # ==========================================
    # UI VIEW SCREEN (JUCATORI)
    # ==========================================
    def setup_view_ui(self):
        self.lbl_title = tk.Label(self.view, text="RAY WARS", font=("Impact", 80), bg="black", fg="white")
        self.lbl_title.pack(pady=(10, 0)) 
        
        # --- RÂNDUL 1: SCORUL (Acum e independent de hexagoane) ---
        f_scores = tk.Frame(self.view, bg="black")
        f_scores.pack(fill=tk.X, pady=(0, 10)) 
        
        # Aliniem la E (dreapta) ca sa se lipeasca de centrul ecranului
        self.lbl_score_red = tk.Label(f_scores, text="0", font=("Impact", 220), bg="black", fg="#ff4444")
        self.lbl_score_red.pack(side=tk.LEFT, expand=True, anchor=tk.E, padx=(0, 40))
        
        # Am adaugat un impuls (pady=(0, 30)) pt a ridica liniuta perfect la jumatatea cifrelor
        tk.Label(f_scores, text="-", font=("Impact", 150), bg="black", fg="#555555").pack(side=tk.LEFT, pady=(0, 30))
        
        # Aliniem la W (stanga) ca sa se lipeasca de centrul ecranului
        self.lbl_score_blue = tk.Label(f_scores, text="0", font=("Impact", 220), bg="black", fg="#4444ff")
        self.lbl_score_blue.pack(side=tk.LEFT, expand=True, anchor=tk.W, padx=(40, 0))
        
        # --- RÂNDUL 2: BARELE DE HP ---
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

        # Status text 
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

            # --- HP ROSU ---
            self.can_red_hp.delete("all") 
            h_red = hearts[0]
            for i in range(h_red):
                cx = start_x_red_fixed + i * spacing_x
                cy = cy_base
                if i % 2 == 1: cy += zigzag_offset_y
                self.draw_hexagon(self.can_red_hp, cx, cy, R, color_red_hex, color_black_hex, outline_w)

            # --- HP ALBASTRU ---
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