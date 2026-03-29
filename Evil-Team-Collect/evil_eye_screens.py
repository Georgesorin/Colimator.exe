import tkinter as tk
from tkinter import font
import time

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception: pass

try:
    import screeninfo
    HAS_SCREENINFO = True
except ImportError:
    HAS_SCREENINFO = False

def get_geom_str(w, h, x, y):
    x_str = f"+{int(x)}" if int(x) >= 0 else str(int(x))
    y_str = f"+{int(y)}" if int(y) >= 0 else str(int(y))
    return f"{int(w)}x{int(h)}{x_str}{y_str}"

class EvilEyeScreens:
    def __init__(self, game):
        self.game = game
        self.is_dev_mode = False 
        
        if HAS_SCREENINFO:
            try:
                monitors = screeninfo.get_monitors()
                monitors.sort(key=lambda m: m.x) 
                if len(monitors) >= 2:
                    m_staff, m_view = monitors[0], monitors[1]  
                else:
                    self.is_dev_mode = True
                    m_staff = m_view = monitors[0] 
            except:
                self.is_dev_mode = True
        else:
            self.is_dev_mode = True
            
        if self.is_dev_mode:
            class DummyMon:
                def __init__(self): self.width, self.height, self.x, self.y = 1280, 720, 0, 0
            m_staff = m_view = DummyMon()

        # --- 1. FEREASTRA STAFF (Control) ---
        self.root = tk.Tk()
        self.root.title("EVIL EYE - Staff Control" + (" [DEV MODE]" if self.is_dev_mode else ""))
        self.root.configure(bg="#0A0A0A")
        
        if not self.is_dev_mode:
            self.root.geometry(get_geom_str(m_staff.width, m_staff.height, m_staff.x, m_staff.y))
            self.root.overrideredirect(True)
            self.root.lift()
        else:
            self.root.geometry("1280x720+0+0")
            
        self.root.bind("<Escape>", lambda e: self.stop_all())
        
        self.sel_lives = 5
        self.sel_diff = "hard"
        
        self.btn_lives = {}
        self.btn_diff = {}
        
        self.setup_staff_ui()
        
        # --- 2. FEREASTRA JUCATORI (Scoreboard) ---
        self.view = tk.Toplevel(self.root)
        self.view.title("EVIL EYE - Live Scoreboard" + (" [DEV MODE]" if self.is_dev_mode else ""))
        self.view.configure(bg="#050505")
        
        if not self.is_dev_mode:
            self.view.geometry(get_geom_str(m_view.width, m_view.height, m_view.x, m_view.y)) 
            self.view.overrideredirect(True)
            self.view.lift()
            self.view.bind("<Escape>", lambda e: self.view.overrideredirect(False))
        else:
            self.view.geometry("1280x720+50+50")
        
        self.setup_view_ui()
        self.update_loop()

    def stop_all(self):
        self.game.running = False
        self.root.destroy()

    def start_match(self):
        self.game.start_game(self.sel_lives, self.sel_diff)

    def set_lives(self, num):
        self.sel_lives = num
        for n, btn in self.btn_lives.items():
            if n == num:
                btn.configure(bg="#00E676", fg="black")
            else:
                btn.configure(bg="#333", fg="white")
                
    def set_diff(self, diff):
        self.sel_diff = diff
        for d, btn in self.btn_diff.items():
            if d == diff:
                btn.configure(bg="#FF1744", fg="white")
            else:
                btn.configure(bg="#333", fg="white")

    def setup_staff_ui(self):
        title_font = font.Font(family="Impact", size=50, weight="bold")
        
        tk.Label(self.root, text="👁️ EVIL EYE: THE VAULT 👁️", font=title_font, bg="#0A0A0A", fg="#FF1744").pack(pady=(20, 10))
        tk.Label(self.root, text="MOD JOC: Echipa care ajunge la 7 Puncte câștigă!", font=("Helvetica", 14), bg="#0A0A0A", fg="#AAA").pack(pady=5)
        tk.Label(self.root, text="ECHIPA A: NORD / EST (Cyan) | ECHIPA B: SUD / VEST (Magenta)", font=("Helvetica", 14), bg="#0A0A0A", fg="#AAA").pack(pady=5)

        # Selectie Dificultate (Standard Tkinter)
        f_diff = tk.Frame(self.root, bg="#111", padx=10, pady=10)
        f_diff.pack(pady=15)
        
        tk.Label(f_diff, text="Setează Dificultatea:", font=("Helvetica", 16, "bold"), bg="#111", fg="white").pack(side=tk.LEFT, padx=20)
        for val, text in [("easy", "UȘOR (Doar Lock)"), ("hard", "GREU (Toate puterile)")]:
            b = tk.Button(f_diff, text=text, font=("Helvetica", 14, "bold"), width=20, height=2,
                          command=lambda v=val: self.set_diff(v), relief=tk.FLAT)
            b.pack(side=tk.LEFT, padx=10)
            self.btn_diff[val] = b

        # Selectie Vieti (Standard Tkinter)
        f_lives = tk.Frame(self.root, bg="#111", padx=10, pady=10)
        f_lives.pack(pady=15)
        
        tk.Label(f_lives, text="Setează Viețile:", font=("Helvetica", 16, "bold"), bg="#111", fg="white").pack(side=tk.LEFT, padx=20)
        for val in [3, 5, 7, 10]:
            b = tk.Button(f_lives, text=f"{val} Vieți", font=("Helvetica", 14, "bold"), width=10, height=2,
                          command=lambda v=val: self.set_lives(v), relief=tk.FLAT)
            b.pack(side=tk.LEFT, padx=10)
            self.btn_lives[val] = b
            
        self.set_diff("hard")
        self.set_lives(5) 

        # Action Buttons
        f_act = tk.Frame(self.root, bg="#0A0A0A")
        f_act.pack(pady=20)
        
        tk.Button(f_act, text="▶ START RUNDĂ", font=("Helvetica", 20, "bold"), bg="#D50000", fg="white", width=20, height=2, command=self.start_match, relief=tk.RAISED).pack(pady=10)
        tk.Button(f_act, text="✖ OPREȘTE TOT", font=("Helvetica", 14, "bold"), bg="#333", fg="white", width=15, command=self.stop_all, relief=tk.FLAT).pack(pady=10)

    def setup_view_ui(self):
        self.lbl_title = tk.Label(self.view, text="EVIL EYE", font=("Impact", 100), bg="#050505", fg="#FF1744")
        self.lbl_title.pack(pady=(20, 10)) 
        
        self.lbl_timer = tk.Label(self.view, text="05:00", font=("Impact", 80), bg="#050505", fg="white")
        self.lbl_timer.pack(pady=(0, 20))
        
        f_main = tk.Frame(self.view, bg="#050505")
        f_main.pack(fill=tk.X, pady=20, padx=50)
        
        # --- ECHIPA A (CYAN) ---
        f_cyan = tk.Frame(f_main, bg="#050505")
        f_cyan.pack(side=tk.LEFT, expand=True)
        tk.Label(f_cyan, text="ECHIPA NORD/EST", font=("Helvetica", 35, "bold"), bg="#050505", fg="#00FFFF").pack(pady=(0, 10))
        self.lbl_score_cyan = tk.Label(f_cyan, text="0 / 7", font=("Impact", 200), bg="#050505", fg="white")
        self.lbl_score_cyan.pack()
        self.lbl_lives_cyan = tk.Label(f_cyan, text="VIEȚI: 5", font=("Impact", 50), bg="#050505", fg="#00FFFF")
        self.lbl_lives_cyan.pack()
        
        tk.Label(f_main, text="VS", font=("Impact", 100), bg="#050505", fg="#333").pack(side=tk.LEFT, padx=20)
        
        # --- ECHIPA B (MAGENTA) ---
        f_magenta = tk.Frame(f_main, bg="#050505")
        f_magenta.pack(side=tk.LEFT, expand=True)
        tk.Label(f_magenta, text="ECHIPA SUD/VEST", font=("Helvetica", 35, "bold"), bg="#050505", fg="#FF00FF").pack(pady=(0, 10))
        self.lbl_score_magenta = tk.Label(f_magenta, text="0 / 7", font=("Impact", 200), bg="#050505", fg="white")
        self.lbl_score_magenta.pack()
        self.lbl_lives_magenta = tk.Label(f_magenta, text="VIEȚI: 5", font=("Impact", 50), bg="#050505", fg="#FF00FF")
        self.lbl_lives_magenta.pack()
        
        self.lbl_status = tk.Label(self.view, text="AȘTEPTARE JUCĂTORI...", font=("Helvetica", 60, "bold"), bg="#050505", fg="#aaaaaa")
        self.lbl_status.pack(side=tk.BOTTOM, pady=60)

    def update_loop(self):
        if not self.game.running:
            self.root.destroy()
            return
            
        with self.game.lock:
            state = self.game.state
            score_a = self.game.team_a_score
            score_b = self.game.team_b_score
            lives_a = self.game.team_a_lives
            lives_b = self.game.team_b_lives
            start_t = self.game.start_time
            now = time.time()
            
            if state == 'PLAYING':
                elapsed = int(now - start_t)
                rem = max(0, self.game.MAX_TIME - elapsed) 
            else:
                rem = self.game.MAX_TIME
                
            mins, secs = divmod(rem, 60)
            time_str = f"{mins:02d}:{secs:02d}"

        self.lbl_score_cyan.config(text=f"{score_a} / 7")
        self.lbl_score_magenta.config(text=f"{score_b} / 7")
        
        self.lbl_lives_cyan.config(text=f"VIEȚI: {lives_a}")
        self.lbl_lives_magenta.config(text=f"VIEȚI: {lives_b}")
        
        self.lbl_timer.config(text=time_str)

        if lives_a == 1 and int(time.time() * 4) % 2 == 0: self.lbl_lives_cyan.config(fg="#FF1744")
        else: self.lbl_lives_cyan.config(fg="#00FFFF")
        
        if lives_b == 1 and int(time.time() * 4) % 2 == 0: self.lbl_lives_magenta.config(fg="#FF1744")
        else: self.lbl_lives_magenta.config(fg="#FF00FF")

        if rem <= 30 and state == 'PLAYING':
            self.lbl_timer.config(fg="#FF1744" if int(time.time() * 4) % 2 == 0 else "white")
        else:
            self.lbl_timer.config(fg="white")

        if state == "LOBBY":
            self.lbl_status.config(text="AȘTEPTARE JUCĂTORI...", fg="#aaaaaa")
        elif state == "STARTUP":
            self.lbl_status.config(text="PREGĂTIRE JOC... FIȚI GATA!", fg="#FFEA00")
        elif state == "PLAYING":
            self.lbl_status.config(text="🔥 OCHIUL VĂ PRIVEȘTE! CULEGEȚI PUNCTELE! 🔥", fg="#FF1744")
        elif state == "GAMEOVER":
            self.lbl_status.config(text=self.game.gameover_text, fg="#00E676")

        self.root.after(100, self.update_loop)

def launch(game):
    app = EvilEyeScreens(game)
    app.root.mainloop()