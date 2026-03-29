import customtkinter as ctk
import tkinter as tk
from tkinter import font
import time
import random

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception: pass

class LabyrinthScreens:
    def __init__(self, game):
        self.game = game
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # --- FEREASTRA STAFF (Laptop Mode) ---
        self.root = ctk.CTk()
        self.root.title("LABIRINT - Staff Control [LAPTOP MODE]")
        self.root.configure(fg_color="#0A0A12")
        self.root.geometry("1280x720+0+0")
        self.root.bind("<Escape>", lambda e: self.stop_all())
        
        # Fundal animat
        self.canvas = tk.Canvas(self.root, bg="#0A0A12", highlightthickness=0)
        self.canvas.place(relwidth=1, relheight=1)
        self.particles = []
        for _ in range(70):
            self.particles.append([random.randint(0, 1920), random.randint(-1080, 1080), random.uniform(1.0, 3.5), random.randint(50, 300), random.choice(["#002233", "#220022", "#111122"])])
        self.animate_bg()

        self.selected_category = None
        self.selected_difficulty = None
        self.setup_staff_ui()
        
        # --- FEREASTRA JUCATORI (Laptop Mode) ---
        self.view = ctk.CTkToplevel(self.root)
        self.view.title("LABIRINT - Live Scoreboard [LAPTOP MODE]")
        self.view.configure(fg_color="#0D0D14")
        self.view.geometry("1280x720+50+50") 
        
        self.setup_view_ui()
        self.update_loop()

    def animate_bg(self):
        self.canvas.delete("all")
        screen_h = self.root.winfo_screenheight()
        for p in self.particles:
            p[1] += p[2]
            if p[1] > screen_h: p[1] = -p[3]; p[0] = random.randint(0, self.root.winfo_screenwidth())
            self.canvas.create_line(p[0], p[1], p[0], p[1] + p[3], fill=p[4], width=3, capstyle=tk.ROUND)
        self.root.after(30, self.animate_bg)

    def stop_all(self):
        self.game.running = False
        self.root.destroy()

    def setup_staff_ui(self):
        self.cat_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.diff_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        
        f_super, f_info, f_btn = ("Helvetica", 60, "bold"), ("Helvetica", 35, "bold"), ("Helvetica", 28, "bold")
        
        # --- SCREEN 1: Category ---
        ctk.CTkLabel(self.cat_frame, text="RĂZBOIUL DE CEAȚĂ", font=f_super, text_color="#00E5FF").pack(pady=(30, 10))
        ctk.CTkLabel(self.cat_frame, text="SELECTEAZĂ MODUL DE JOC", text_color="white", font=f_info).pack(pady=(0, 40))
        
        ctk.CTkButton(self.cat_frame, text="COPIL", fg_color="#00BFFF", hover_color="#0088CC", font=f_btn, text_color="black", width=400, height=80, command=lambda: self.show_diff_screen("CHILD")).pack(pady=10)
        ctk.CTkButton(self.cat_frame, text="ADULT", fg_color="#FF0055", hover_color="#CC0044", font=f_btn, text_color="black", width=400, height=80, command=lambda: self.show_diff_screen("ADULT")).pack(pady=10)
        ctk.CTkButton(self.cat_frame, text="COPIL + ADULT", fg_color="#00E676", hover_color="#00B259", font=f_btn, text_color="black", width=400, height=80, command=lambda: self.show_diff_screen("MIXED")).pack(pady=10)

        # --- SCREEN 2: Difficulty ---
        self.lbl_diff_subtitle = ctk.CTkLabel(self.diff_frame, text="PROFIL SELECTAT", font=f_info, text_color="#00E5FF")
        self.lbl_diff_subtitle.pack(pady=(0, 40))
        
        self.btn_easy = ctk.CTkButton(self.diff_frame, text="UȘOR", font=f_btn, width=400, height=80, command=lambda: self.start_match("EASY"))
        self.btn_medium = ctk.CTkButton(self.diff_frame, text="MEDIU", font=f_btn, width=400, height=80, command=lambda: self.start_match("MEDIUM"))
        self.btn_hard = ctk.CTkButton(self.diff_frame, text="GREU", font=f_btn, width=400, height=80, command=lambda: self.start_match("HARD"))
        
        ctk.CTkButton(self.diff_frame, text="< INAPOI LA PROFIL", font=("Helvetica", 20, "bold"), text_color="#AAA", fg_color="#1A1A24", width=300, height=50, command=self.show_cat_screen).pack(pady=(40, 0))

        self.show_cat_screen()

    def show_cat_screen(self):
        self.diff_frame.place_forget()
        self.cat_frame.place(relx=0.5, rely=0.5, anchor="center")

    def show_diff_screen(self, cat):
        self.selected_category = cat
        self.lbl_diff_subtitle.configure(text=f"PROFIL SELECTAT: {cat}")
        self.cat_frame.place_forget()
        
        self.btn_easy.pack(pady=10); self.btn_medium.pack(pady=10); self.btn_hard.pack(pady=10)
        
        if cat == "MIXED":
            self.btn_medium.pack_forget()
            self.btn_easy.configure(text="VÂNĂTOARE DE COMORI (UȘOR)", fg_color="#111", text_color="#00E676")
            self.btn_hard.configure(text="LUMINA PARTAJATĂ (GREU)", fg_color="#111", text_color="#FF00FF")
        else:
            self.btn_easy.configure(text="MOD: UȘOR", fg_color="#111", text_color="#00E676")
            self.btn_medium.configure(text="MOD: MEDIU", fg_color="#111", text_color="#00BFFF")
            self.btn_hard.configure(text="MOD: GREU", fg_color="#111", text_color="#FF00FF")
            
        self.diff_frame.place(relx=0.5, rely=0.5, anchor="center")

    def start_match(self, diff):
        self.selected_difficulty = diff
        self.game.start_game_from_ui(self.selected_category, self.selected_difficulty)
        self.show_cat_screen()

    def setup_view_ui(self):
        self.header_frame = ctk.CTkFrame(self.view, fg_color="transparent")
        self.header_frame.pack(pady=(40, 20), fill="x")
        self.lbl_sys = ctk.CTkLabel(self.header_frame, text="TRANSMISIE LIVE // LABIRINT", text_color="#555", font=("Helvetica", 20, "bold"))
        self.lbl_sys.pack()
        self.lbl_round = ctk.CTkLabel(self.header_frame, text="ÎN AȘTEPTARE...", text_color="#FFEA00", font=("Helvetica", 45, "bold"))
        self.lbl_round.pack(pady=(10, 0))

        self.main_container = ctk.CTkFrame(self.view, fg_color="transparent")
        self.main_container.pack(expand=True, fill="both", padx=50, pady=20)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(1, weight=0, minsize=100) 
        self.main_container.grid_columnconfigure(2, weight=1)

        # --- CARD P1 ---
        self.p1_card = ctk.CTkFrame(self.main_container, fg_color="#1A1A24", corner_radius=30, border_width=4, border_color="#00FFFF")
        self.p1_card.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        ctk.CTkLabel(self.p1_card, text="JUCĂTORUL 1 (CYAN)", text_color="#00FFFF", font=("Helvetica", 35, "bold")).pack(pady=(40, 10))
        self.p1_score_lbl = ctk.CTkLabel(self.p1_card, text="0", text_color="#00FFFF", font=("Helvetica", 280, "bold"))
        self.p1_score_lbl.pack(expand=True)
        self.p1_hp_text = ctk.CTkLabel(self.p1_card, text="VIEȚI: 5 / 5", text_color="#AAA", font=("Helvetica", 30, "bold"))
        self.p1_hp_text.pack(pady=(0, 40))

        # --- CARD P2 ---
        self.p2_card = ctk.CTkFrame(self.main_container, fg_color="#1A1A24", corner_radius=30, border_width=4, border_color="#FF00FF")
        self.p2_card.grid(row=0, column=2, sticky="nsew", padx=20, pady=20)
        ctk.CTkLabel(self.p2_card, text="JUCĂTORUL 2 (ROZ)", text_color="#FF00FF", font=("Helvetica", 35, "bold")).pack(pady=(40, 10))
        self.p2_score_lbl = ctk.CTkLabel(self.p2_card, text="0", text_color="#FF00FF", font=("Helvetica", 280, "bold"))
        self.p2_score_lbl.pack(expand=True)
        self.p2_hp_text = ctk.CTkLabel(self.p2_card, text="VIEȚI: 5 / 5", text_color="#AAA", font=("Helvetica", 30, "bold"))
        self.p2_hp_text.pack(pady=(0, 40))
        
        self.flash_state = False

    def update_loop(self):
        if not self.game.running:
            self.root.destroy()
            return
            
        with self.game.engine.lock:
            p1_score, p2_score = self.game.p1.score, self.game.p2.score
            p1_lives, p2_lives = self.game.p1.lives, self.game.p2.lives
            p1_max, p2_max = self.game.p1.max_lives, self.game.p2.max_lives
            p1_stun = self.game.p1.is_stunned or self.game.p1.is_resetting
            p2_stun = self.game.p2.is_stunned or self.game.p2.is_resetting
            st = self.game.state

        if st == 'WAIT_START': self.lbl_round.configure(text="ÎN AȘTEPTARE...", text_color="#FFEA00")
        else: self.lbl_round.configure(text=f"RUNDA {(p1_score + p2_score + 1):02d}", text_color="white")

        self.p1_hp_text.configure(text=f"VIEȚI: {max(0, p1_lives)} / {p1_max}")
        self.p2_hp_text.configure(text=f"VIEȚI: {max(0, p2_lives)} / {p2_max}")
        
        self.flash_state = not self.flash_state
        
        if p1_stun:
            self.p1_card.configure(border_color="#FF1744" if self.flash_state else "#4A0000")
            self.p1_score_lbl.configure(text="⚠️", text_color="#FF1744")
        else:
            self.p1_card.configure(border_color="#00FFFF")
            self.p1_score_lbl.configure(text=str(p1_score), text_color="#00FFFF")
            
        if p2_stun:
            self.p2_card.configure(border_color="#FF1744" if self.flash_state else "#4A0000")
            self.p2_score_lbl.configure(text="⚠️", text_color="#FF1744")
        else:
            self.p2_card.configure(border_color="#FF00FF")
            self.p2_score_lbl.configure(text=str(p2_score), text_color="#FF00FF")

        self.root.after(200, self.update_loop)

def launch(game):
    app = LabyrinthScreens(game)
    app.root.mainloop()