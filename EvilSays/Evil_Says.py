import socket
import threading
import time
import random
import queue
import os
import tkinter as tk

try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except ImportError:
    CTK_AVAILABLE = False
    print("EROARE: customtkinter nu este instalat. Rulați: pip install customtkinter")

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("Avertisment: pygame nu este instalat. Sunetul a fost dezactivat.")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURARE PARAMETRI FIXI
# ─────────────────────────────────────────────────────────────────────────────
UDP_PORT_SEND = 4626
UDP_PORT_RECV = 7800
HARDWARE_TARGET_IP = "169.254.182.11"
SIMULATOR_TARGET_IP = "127.0.0.1"

PASSWORDS = [
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

def calc_chk(data):
    return PASSWORDS[sum(data) & 0xFF]

# ─────────────────────────────────────────────────────────────────────────────
# MANAGER AUDIO 
# ─────────────────────────────────────────────────────────────────────────────
class AudioManager:
    def __init__(self):
        self.enabled = False
        if not PYGAME_AVAILABLE: return
        
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
            self.enabled = True
            
            base_dir = os.path.dirname(os.path.abspath(__file__))
            sounds_dir = os.path.join(base_dir, "sounds")
            
            detected_path = os.path.join(sounds_dir, "WrongButton.mp3")
            self.bgm_path = os.path.join(sounds_dir, "EvilSays.mp3")
            correct_path  = os.path.join(sounds_dir, "Correct.mp3")

            self.snd_detected = pygame.mixer.Sound(detected_path) if os.path.exists(detected_path) else None
            self.snd_correct = pygame.mixer.Sound(correct_path) if os.path.exists(correct_path) else None
        except Exception:
            self.enabled = False

    def play_bgm(self):
        if self.enabled and hasattr(self, 'bgm_path') and os.path.exists(self.bgm_path):
            try:
                pygame.mixer.music.load(self.bgm_path)
                pygame.mixer.music.set_volume(0.4) 
                pygame.mixer.music.play(-1) 
            except Exception: pass

    def play_detected(self):
        if self.enabled and self.snd_detected: self.snd_detected.play()
    
    def play_correct(self):
        if self.enabled and self.snd_correct: self.snd_correct.play()

# ─────────────────────────────────────────────────────────────────────────────
# MANAGER REȚEA
# ─────────────────────────────────────────────────────────────────────────────
class NetManager:
    def __init__(self, target_ip, local_ip):
        self.target_ip = target_ip
        self.local_ip = local_ip
        self.seq = 0
        self.running = True
        self.q = queue.Queue(maxsize=15)
        self.on_press = None
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        if self.local_ip != "127.0.0.1":
            try: self.sock.bind((self.local_ip, 0))
            except: pass

        threading.Thread(target=self._sender, daemon=True).start()
        threading.Thread(target=self._receiver, daemon=True).start()

    def _sender(self):
        while self.running:
            try:
                frame = self.q.get(timeout=1.0)
                self.seq = (self.seq + 1) & 0xFFFF
                dest = (self.target_ip, UDP_PORT_SEND)

                p1 = bytearray([0x75, 0, 0, 0, 8, 2, 0, 0, 0x33, 0x44, (self.seq>>8)&0xFF, self.seq&0xFF, 0, 0])
                p1.append(calc_chk(p1)); self.sock.sendto(p1, dest); time.sleep(0.008)

                p2_inner = bytes([2,0,0, 0x88, 0x77, 0xFF, 0xF0, 0, 8]) + bytearray([0,11]*4)
                p2 = bytearray([0x75, 0, 0, 0, len(p2_inner)]) + p2_inner
                p2[10], p2[11] = (self.seq>>8)&0xFF, self.seq&0xFF
                p2.append(calc_chk(p2)); self.sock.sendto(p2, dest); time.sleep(0.008)

                p3_inner = bytes([2,0,0, 0x88, 0x77, 0, 0, 0, 132]) + frame
                p3 = bytearray([0x75, 0, 0, 0, len(p3_inner)]) + p3_inner
                p3[10], p3[11] = (self.seq>>8)&0xFF, self.seq&0xFF
                p3.append(calc_chk(p3)); self.sock.sendto(p3, dest); time.sleep(0.008)

                p4 = bytearray([0x75, 0, 0, 0, 8, 2, 0, 0, 0x55, 0x66, (self.seq>>8)&0xFF, self.seq&0xFF, 0, 0])
                p4.append(calc_chk(p4)); self.sock.sendto(p4, dest)
            except queue.Empty: continue

    def _receiver(self):
        rsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: rsock.bind((self.local_ip, UDP_PORT_RECV))
        except: rsock.bind(("0.0.0.0", UDP_PORT_RECV))
        
        last_state = {}
        while self.running:
            try:
                data, _ = rsock.recvfrom(1024)
                if len(data) == 687 and data[0] == 0x88:
                    for ch in range(1, 5):
                        base = 2 + (ch-1)*171
                        for l in range(11):
                            pressed = (data[base+1+l] == 0xCC)
                            if pressed and not last_state.get((ch,l)):
                                if self.on_press: self.on_press(ch, l)
                            last_state[(ch,l)] = pressed
            except: pass

    def push(self, led_dict):
        buf = bytearray(132)
        is_simulator = (self.target_ip == "127.0.0.1")

        for (ch, logic_led), (r, g, b) in led_dict.items():
            if not (1 <= ch <= 4 and 0 <= logic_led <= 10): continue
            
            if is_simulator: hw_led, c1, c2, c3 = logic_led, g, r, b
            else: hw_led, c1, c2, c3 = (10 if logic_led == 0 else logic_led - 1), r, g, b
            
            idx = hw_led * 12 + (ch - 1)
            buf[idx], buf[idx + 4], buf[idx + 8] = c1, c2, c3

        try: self.q.put(bytes(buf), block=False)
        except queue.Full: pass

# ─────────────────────────────────────────────────────────────────────────────
# LOGICA JOCULUI
# ─────────────────────────────────────────────────────────────────────────────
class GameEngine:
    def __init__(self, net, ui, diff, num_players, target_score):
        self.net, self.ui, self.diff = net, ui, diff
        self.num_players = num_players
        self.target_score = target_score
        self.audio = AudioManager() 
        self.running = True
        
        self.score = 0
        self.pattern, self.guessed, self.wrong_guessed, self.frenzy = set(), set(), set(), set()
        self.eye_wall = 1
        self.state = "OFF"
        
        configs = {"EASY": (2, 3, 5), "MEDIUM": (4, 2, 5), "HARD": (6, 1, 5)}
        self.base_tiles, self.t_warn, self.t_gaze = configs[diff]
        self.base_tiles += (num_players - 2) 

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _draw(self):
        f = {}
        for ch in range(1, 5):
            for l in range(1, 11):
                if (ch, l) in self.guessed: col = (0, 255, 0)
                elif (ch, l) in self.wrong_guessed: col = (255, 0, 0)
                elif self.state == "GAZE" and (ch, l) in self.pattern: col = (0, 255, 255)
                elif self.state == "GAZE" and (ch, l) in self.frenzy: col = (200, 0, 255)
                else: col = (0, 0, 0)
                f[(ch, l)] = col
            ec = (0,0,0)
            if self.state == "ROULETTE": ec = (255,255,255) if ch == self.eye_wall else (0,0,0)
            elif self.state == "WARNING": ec = (255,255,0) if ch == self.eye_wall and int(time.time()*10)%2==0 else (0,0,0)
            elif self.state == "GAZE": ec = (255,150,0) if self.frenzy and ch == self.eye_wall else ((255,0,0) if ch == self.eye_wall else (0,0,0))
            f[(ch, 0)] = ec
        self.net.push(f)

    def _run(self):
        self.ui.update_status("🌀 INIȚIALIZARE SISTEME...")
        st = time.time(); w = 1
        while time.time() - st < 3.0 and self.running:
            frame = {(c, l): (0, 255, 255) if c == w and l > 0 else (0,0,0) for c in range(1,5) for l in range(11)}
            self.net.push(frame); time.sleep(0.08); w = (w % 4) + 1

        self.audio.play_bgm()

        while self.running:
            num = min(self.base_tiles + (self.score // 5), 35)
            self.pattern = set(random.sample([(c,l) for c in range(1,5) for l in range(1,11)], num))
            self.guessed.clear(); self.wrong_guessed.clear(); self.frenzy.clear()

            self.state = "ROULETTE"
            self.ui.update_status("👁️ OCHIUL SCANEAZĂ SECTOARELE...")
            curr = random.randint(1,4)
            for i in range(15):
                if not self.running: break
                self.eye_wall = curr; self._draw(); time.sleep(0.05 + i*0.02); curr = (curr % 4) + 1
            self.eye_wall = curr

            self.state = "WARNING"; st = time.time()
            self.ui.update_status(f"⚠️ ATENȚIE LA PERETELE {self.eye_wall}!")
            while time.time() - st < self.t_warn and self.running: self._draw(); time.sleep(0.1)

            self.state = "GAZE"
            if random.random() < 0.2:
                self.frenzy = set((self.eye_wall, l) for l in random.sample(range(1,11), 4))
                self.ui.update_status("🌟 FEBRA DE AUR! Loviți portalurile MOV!")
            else: self.ui.update_status("🔴 OCHI DESCHIS! MEMORAȚI, NU MIȘCAȚI!")
            
            st = time.time()
            while time.time() - st < self.t_gaze and self.running:
                if self.state == "STUN": break
                self._draw(); time.sleep(0.1)

            if self.state == "STUN":
                for _ in range(12):
                    if not self.running: break
                    self.net.push({(c,l): (255,0,0) for c in range(1,5) for l in range(11)})
                    time.sleep(0.2)
                    self.net.push({(c,l): (0,0,0) for c in range(1,5) for l in range(11)})
                    time.sleep(0.2)
                continue

            self.state = "ACTION"; self.ui.update_status("🟢 OCHI ÎNCHIS! REFACETI PATTERN-UL!")
            st = time.time()
            while time.time() - st < 7.0 and self.running:
                self._draw()
                if len(self.guessed) >= len(self.pattern):
                    self.score += 5; self.ui.update_score(self.score)
                    if self.score >= self.target_score:
                        self.state = "WIN"
                    else:
                        self.ui.update_status("🎉 RUNDĂ COMPLETĂ!")
                    break
                time.sleep(0.1)
            else: 
                if self.running: self.ui.update_status("⌛ Timp expirat!")
            
            if self.state == "WIN":
                self.ui.update_status("🏆 MISIUNE ÎNDEPLINITĂ! 🏆")
                self.audio.play_correct() 
                while self.running:
                    self.net.push({(c,l): (0,255,0) for c in range(1,5) for l in range(11)})
                    time.sleep(0.5)
                    self.net.push({(c,l): (0,0,0) for c in range(1,5) for l in range(11)})
                    time.sleep(0.5)

            time.sleep(1)

    def on_press(self, ch, l):
        if l == 0 or self.state == "WIN" or not self.running: return
        
        if self.state == "GAZE":
            if self.frenzy and ch == self.eye_wall and (ch, l) in self.frenzy:
                self.score += 3; self.frenzy.remove((ch, l)); self.ui.update_score(self.score)
            else:
                self.score = max(0, self.score - 5); self.ui.update_score(self.score)
                self.state = "STUN"; self.ui.update_status("☠️ TE-A VĂZUT! (Penalizare -5)")
                self.audio.play_detected() 
                
        elif self.state == "ACTION":
            if (ch, l) in self.pattern:
                if (ch, l) not in self.guessed: 
                    self.guessed.add((ch, l)); self.score += 1; self.ui.update_score(self.score)
            else:
                if (ch, l) not in self.wrong_guessed:
                    self.wrong_guessed.add((ch, l)); self.score = max(0, self.score - 2); self.ui.update_score(self.score)

# ─────────────────────────────────────────────────────────────────────────────
# UI PRINCIPAL (E-Sports / Escape Room Edition)
# ─────────────────────────────────────────────────────────────────────────────
if CTK_AVAILABLE:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

class EsportsApp(ctk.CTk if CTK_AVAILABLE else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Configurare Evil Eye - E-Sports Edition")
        self.attributes('-fullscreen', True)
        self.configure(bg="#0A0A12" if not CTK_AVAILABLE else None)
        if CTK_AVAILABLE: self.configure(fg_color="#0A0A12")
        
        self.bind("<Escape>", lambda e: self.quit_app())
        self.bind("<F12>", self.toggle_simulator)

        self.target_ip = HARDWARE_TARGET_IP
        self.local_ip = self.auto_detect_ip()
        self.is_simulator = False

        self.selected_players = None
        self.selected_difficulty = None
        self.target_score = 50 

        self.canvas = tk.Canvas(self, bg="#0A0A12", highlightthickness=0)
        self.canvas.place(relwidth=1, relheight=1)
        self.init_animated_bg()

        self.setup_fonts()
        self.build_frames()
        self.show_players_screen()

    def auto_detect_ip(self):
        try:
            import psutil
            for iface, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if a.family == socket.AF_INET and a.address.startswith("169.254."):
                        return a.address
        except: pass
        return "0.0.0.0"

    def toggle_simulator(self, event=None):
        self.is_simulator = not self.is_simulator
        if self.is_simulator:
            self.target_ip = SIMULATOR_TARGET_IP
            self.local_ip = "127.0.0.1"
            print("SIMULATOR ACTIVAT")
        else:
            self.target_ip = HARDWARE_TARGET_IP
            self.local_ip = self.auto_detect_ip()
            print("HARDWARE ACTIVAT")

    def init_animated_bg(self):
        self.particles = []
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        for _ in range(70):
            x = random.randint(0, screen_w)
            y = random.randint(-screen_h, screen_h)
            speed = random.uniform(1.0, 3.5)
            length = random.randint(50, 300)
            color = random.choice(["#002233", "#220022", "#111122"])
            self.particles.append([x, y, speed, length, color])
        self.animate_bg()

    def animate_bg(self):
        self.canvas.delete("all")
        screen_h = self.winfo_screenheight()
        for p in self.particles:
            p[1] += p[2]
            if p[1] > screen_h:
                p[1] = -p[3]
                p[0] = random.randint(0, self.winfo_screenwidth())
            self.canvas.create_line(p[0], p[1], p[0], p[1] + p[3], fill=p[4], width=3, capstyle=tk.ROUND)
        self.after(30, self.animate_bg)

    def setup_fonts(self):
        self.f_super = ("Helvetica", 87, "bold")
        self.f_title = ("Helvetica", 50, "bold")
        self.f_btn = ("Helvetica", 40, "bold")
        self.f_btn_small = ("Helvetica", 25, "bold")
        self.f_desc = ("Helvetica", 32)
        self.f_info = ("Helvetica", 50, "bold")
        self.f_hud_score = ("Courier New", 180, "bold")
        self.f_hud_status = ("Consolas", 35, "bold")

    def build_frames(self):
        # ─────────────────────────────────────────────────────────────────────
        # ECRAN 1: CÂȚI JUCĂTORI / INFO
        # ─────────────────────────────────────────────────────────────────────
        self.players_frame = ctk.CTkFrame(self, fg_color="transparent") if CTK_AVAILABLE else tk.Frame(self, bg="#0A0A12")
        self.add_label(self.players_frame, "EVIL EYE", self.f_super, "#FF003C").pack(pady=(30, 10))
        self.add_label(self.players_frame, "CÂȚI JUCĂTORI PARTICIPĂ?", self.f_info, "white").pack(pady=(0, 30))
        
        btn_kw = {"font": self.f_btn, "width": 650, "height": 130, "corner_radius": 30, "border_width": 4} if CTK_AVAILABLE else {"font": self.f_btn, "width": 20, "height": 3}
        
        self.add_button(self.players_frame, "2 JUCĂTORI", "#00BFFF", "#00E5FF", lambda: self.select_players(2), hover_color="#00BFFF", **btn_kw).pack(pady=15)
        self.add_button(self.players_frame, "3 JUCĂTORI", "#FF0055", "#FF3377", lambda: self.select_players(3), hover_color="#FF0055", **btn_kw).pack(pady=15)
        self.add_button(self.players_frame, "4 JUCĂTORI", "#00E676", "#69FF9E", lambda: self.select_players(4), hover_color="#00E676", **btn_kw).pack(pady=15)
        
        # Buton Info (stilizat fixat cu fundal negruț)
        self.add_button(self.players_frame, "ℹ️ CUM SE JOACĂ?", "#1A1A24", "#00E5FF", self.show_info_screen, width=350, height=60, corner_radius=20, border_width=2, font=self.f_btn_small, text_color="#00E5FF", hover_color="#2A2A35").pack(pady=(30, 10))
        
        # FIX BORDER TRANSPARENT: Buton Închidere (pe prima pagină) folosește #0A0A12 pentru border_color
        self.add_button(self.players_frame, "ÎNCHIDERE SISTEM", "transparent", "#0A0A12", self.quit_app, width=200, height=50, font=self.f_btn_small, text_color="#666666", hover_color="#111111").pack(pady=(10, 0))

        # ─────────────────────────────────────────────────────────────────────
        # ECRAN INFO: CUM SE JOACĂ?
        # ─────────────────────────────────────────────────────────────────────
        self.info_frame = ctk.CTkFrame(self, fg_color="#12121A", corner_radius=40, border_width=3, border_color="#00E5FF") if CTK_AVAILABLE else tk.Frame(self, bg="#12121A", bd=5)
        if CTK_AVAILABLE:
            self.info_frame.configure(width=1300, height=800)
            self.info_frame.pack_propagate(False)

        self.add_label(self.info_frame, "INFORMAȚII MISIUNE", self.f_title, "white").pack(pady=(50, 30))
        
        info_text = (
            "1. MEMORARE (CYAN)\n"
            "Când Ochiul este Deschis (Roșu), panourile vor lumina în CYAN.\n"
            "NU VĂ MIȘCAȚI ȘI NU ATINGEȚI PEREȚII! Doar memorați tiparul.\n\n"
            "2. ACȚIUNE (VERDE)\n"
            "Când Ochiul se închide, luminile se vor stinge.\n"
            "Acum puteți să apăsați pe locațiile pe care le-ați memorat.\n\n"
            "3. FEBRA DE AUR (MOV)\n"
            "Dacă vedeți lumini MOV în timp ce Ochiul vă privește, este o șansă bonus!\n"
            "Atingeți-le rapid pentru a câștiga +3 Puncte.\n\n"
            "Orice mișcare greșită va alerta Ochiul și veți pierde 5 puncte!"
        )
        self.add_label(self.info_frame, info_text, self.f_desc, "#E0E0E0").pack(expand=True, padx=50)
        
        self.add_button(self.info_frame, "ÎNȚELES (ÎNAPOI)", "#00E676", "#00C853", self.show_players_screen, width=350, height=80, corner_radius=20, font=self.f_btn, text_color="black").pack(pady=(0, 50))

        # ─────────────────────────────────────────────────────────────────────
        # ECRAN 2: DIFICULTATE
        # ─────────────────────────────────────────────────────────────────────
        self.diff_frame = ctk.CTkFrame(self, fg_color="transparent") if CTK_AVAILABLE else tk.Frame(self, bg="#0A0A12")
        self.lbl_p_subtitle = self.add_label(self.diff_frame, "JUCĂTORI SELECTAȚI: X", self.f_info, "#00E5FF")
        self.lbl_p_subtitle.pack(pady=(0, 5))
        self.add_label(self.diff_frame, "NIVEL DE DIFICULTATE", self.f_super, "white").pack(pady=(0, 40))

        # Scorurile modificate: EASY 50, MEDIUM 75, HARD 100
        self.add_button(self.diff_frame, "UȘOR", "transparent", "#00E676", lambda: self.show_details("EASY", 50), text_color="#00E676", hover_color="#004422", **btn_kw).pack(pady=15)
        self.add_button(self.diff_frame, "MEDIU", "transparent", "#00BFFF", lambda: self.show_details("MEDIUM", 75), text_color="#00BFFF", hover_color="#003344", **btn_kw).pack(pady=15)
        self.add_button(self.diff_frame, "GREU", "transparent", "#FF0055", lambda: self.show_details("HARD", 100), text_color="#FF0055", hover_color="#440011", **btn_kw).pack(pady=15)
        
        # FIX BORDER TRANSPARENT: Buton Înapoi (stilizat)
        self.add_button(self.diff_frame, "< ÎNAPOI LA ECHIPAJ", "#1A1A24", "#1A1A24", self.show_players_screen, width=350, height=60, corner_radius=20, font=self.f_btn_small, text_color="#AAAAAA", hover_color="#2A2A35").pack(pady=(40, 0))
        
        # ─────────────────────────────────────────────────────────────────────
        # ECRAN 3: DETALII / CONFIRMARE
        # ─────────────────────────────────────────────────────────────────────
        self.details_frame = ctk.CTkFrame(self, fg_color="#12121A", corner_radius=40, border_width=3, border_color="#00E5FF") if CTK_AVAILABLE else tk.Frame(self, bg="#12121A", bd=5)
        if CTK_AVAILABLE:
            self.details_frame.configure(width=1300, height=800)
            self.details_frame.pack_propagate(False)
        
        self.lbl_det_title = self.add_label(self.details_frame, "CONFIRMARE", self.f_title, "white")
        self.lbl_det_title.pack(pady=(60, 40))
        
        desc_box = ctk.CTkFrame(self.details_frame, fg_color="transparent") if CTK_AVAILABLE else tk.Frame(self.details_frame, bg="#12121A")
        desc_box.pack(expand=True, fill="both", padx=80)
        
        self.lbl_det_desc = self.add_label(desc_box, "", self.f_desc, "#E0E0E0")
        self.lbl_det_desc.pack(expand=True)
        
        b_box = ctk.CTkFrame(self.details_frame, fg_color="transparent") if CTK_AVAILABLE else tk.Frame(self.details_frame, bg="#12121A")
        b_box.pack(side="bottom", pady=(0, 60))
        
        self.add_button(b_box, "ANULEAZĂ", "#444", "#555", self.show_diff_screen, width=300, height=90, corner_radius=20, font=self.f_btn).pack(side="left", padx=20)
        self.add_button(b_box, "START MISIUNE >", "#00E676", "#00C853", self.prep_game, width=450, height=90, corner_radius=20, font=self.f_btn, text_color="black").pack(side="left", padx=20)

        # ─────────────────────────────────────────────────────────────────────
        # ECRAN 4: LOADING
        # ─────────────────────────────────────────────────────────────────────
        self.load_frame = ctk.CTkFrame(self, fg_color="transparent") if CTK_AVAILABLE else tk.Frame(self, bg="#0A0A12")
        self.add_label(self.load_frame, "SE INIȚIALIZEAZĂ OCHIUL...", self.f_super, "#FF003C").pack(pady=20)
        if CTK_AVAILABLE:
            self.progress_bar = ctk.CTkProgressBar(self.load_frame, width=800, height=30, corner_radius=15, progress_color="#FF003C", fg_color="#222")
            self.progress_bar.set(0)
            self.progress_bar.pack(pady=20)

        # ─────────────────────────────────────────────────────────────────────
        # ECRAN 5: SCOREBOARD FULLSCREEN
        # ─────────────────────────────────────────────────────────────────────
        self.score_frame = ctk.CTkFrame(self, fg_color="transparent") if CTK_AVAILABLE else tk.Frame(self, bg="#0A0A12")
        
        # HEADER
        header = ctk.CTkFrame(self.score_frame, fg_color="#12121A", corner_radius=20, border_width=2, border_color="#333") if CTK_AVAILABLE else tk.Frame(self.score_frame, bg="#12121A")
        header.pack(side="top", fill="x", padx=40, pady=40, ipadx=20, ipady=20)
        
        self.lbl_hud_players = self.add_label(header, "JUCĂTORI: 4", self.f_btn_small, "#00E5FF")
        self.lbl_hud_players.pack(side="left")
        self.lbl_hud_diff = self.add_label(header, "MOD: HARD", self.f_btn_small, "#FF003C")
        self.lbl_hud_diff.pack(side="right")
        
        # FOOTER (EXIT BUTTON)
        footer = ctk.CTkFrame(self.score_frame, fg_color="transparent") if CTK_AVAILABLE else tk.Frame(self.score_frame, bg="#0A0A12")
        footer.pack(side="bottom", pady=(0, 40))
        
        btn_exit = self.add_button(footer, "🚪 ABANDON MISIUNE", "transparent", "#FF003C", self.quit_app, text_color="#FF003C")
        if CTK_AVAILABLE:
            btn_exit.configure(font=self.f_btn_small, width=300, height=60, corner_radius=15, border_width=2, hover_color="#440011")
        btn_exit.pack()

        # STATUS BOX
        status_box = ctk.CTkFrame(self.score_frame, fg_color="#12121A", corner_radius=20, border_width=2, border_color="#00E5FF") if CTK_AVAILABLE else tk.Frame(self.score_frame, bg="#12121A", bd=3)
        status_box.pack(side="bottom", fill="x", padx=40, pady=(0, 20), ipady=30)
        
        self.lbl_hud_status = self.add_label(status_box, "AȘTEPTARE...", self.f_hud_status, "#00E5FF")
        self.lbl_hud_status.pack()

        # SCOR URIAȘ
        center_box = ctk.CTkFrame(self.score_frame, fg_color="transparent") if CTK_AVAILABLE else tk.Frame(self.score_frame, bg="#0A0A12")
        center_box.pack(expand=True, fill="both")
        
        self.add_label(center_box, "SCOR CURENT", self.f_title, "#888").pack(pady=(20, 0))
        self.lbl_hud_score = self.add_label(center_box, "0", self.f_hud_score, "white")
        self.lbl_hud_score.pack()
        
        self.lbl_hud_target = self.add_label(center_box, "TARGET: 50", self.f_title, "#ffd000")
        self.lbl_hud_target.pack(pady=(0, 20))

    # --- Helpers UI ---
    def add_label(self, parent, text, font, color):
        if CTK_AVAILABLE: return ctk.CTkLabel(parent, text=text, font=font, text_color=color)
        else: return tk.Label(parent, text=text, font=font, fg=color, bg=parent["bg"])

    def add_button(self, parent, text, fg_col, border_col, command, text_color="white", **kwargs):
        if CTK_AVAILABLE:
            return ctk.CTkButton(parent, text=text, fg_color=fg_col, border_color=border_col, text_color=text_color, command=command, **kwargs)
        else:
            return tk.Button(parent, text=text, bg=fg_col if fg_col != "transparent" else "#222", fg=text_color, command=command, font=kwargs.get("font"))

    def hide_all(self):
        for f in [self.players_frame, self.diff_frame, self.details_frame, self.load_frame, self.score_frame, self.info_frame]:
            f.place_forget()
            if not CTK_AVAILABLE: f.pack_forget()

    # --- Navigare ---
    def show_players_screen(self):
        self.hide_all()
        if CTK_AVAILABLE: self.players_frame.place(relx=0.5, rely=0.5, anchor="center")
        else: self.players_frame.pack(expand=True)
        
    def show_info_screen(self):
        self.hide_all()
        if CTK_AVAILABLE: self.info_frame.place(relx=0.5, rely=0.5, anchor="center")
        else: self.info_frame.pack(expand=True)

    def select_players(self, n):
        self.selected_players = n
        if CTK_AVAILABLE: self.lbl_p_subtitle.configure(text=f"ECHIPAJ: {n} JUCĂTORI")
        else: self.lbl_p_subtitle.config(text=f"ECHIPAJ: {n} JUCĂTORI")
        self.show_diff_screen()

    def show_diff_screen(self):
        self.hide_all()
        if CTK_AVAILABLE: self.diff_frame.place(relx=0.5, rely=0.5, anchor="center")
        else: self.diff_frame.pack(expand=True)

    def show_details(self, diff, target):
        self.selected_difficulty = diff
        self.target_score = target
        self.hide_all()
        
        title, desc = "", ""
        if diff == "EASY":
            title = "NIVEL: UȘOR"
            desc = f"• Obiectiv: {target} Puncte\n• Timp de memorare generos.\n• Ochiul iartă greșelile minore.\n• Recomandat pentru începători."
        elif diff == "MEDIUM":
            title = "NIVEL: MEDIU"
            desc = f"• Obiectiv: {target} Puncte\n• Timp de memorare scurtat.\n• Pattern-uri mai complexe.\n• Recomandat pentru echipe echilibrate."
        else:
            title = "NIVEL: GREU"
            desc = f"• Obiectiv: {target} Puncte\n• Timp de memorare extrem de scurt!\n• Ochiul este absolut nemilos!\n• Dificultate extremă, supraviețuire redusă."

        if CTK_AVAILABLE:
            self.lbl_det_title.configure(text=title)
            self.lbl_det_desc.configure(text=desc)
            self.details_frame.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.lbl_det_title.config(text=title)
            self.lbl_det_desc.config(text=desc)
            self.details_frame.pack(expand=True)

    def prep_game(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        pkt = bytearray([0x67, 1, 2, 12, 10, 2, 75, 88, 45, 72, 67, 48, 52, 3, 0, 0, 255, 255, 0, 0, 0, 20])
        pkt.append(calc_chk(pkt)); s.sendto(pkt, ("255.255.255.255", 4626)); s.close()

        self.hide_all()
        if CTK_AVAILABLE:
            self.load_frame.place(relx=0.5, rely=0.5, anchor="center")
            self.animate_loading(0.0)
        else:
            self.start_engine()

    def animate_loading(self, val):
        if not CTK_AVAILABLE: return
        self.progress_bar.set(val)
        if val < 1.0: self.after(30, self.animate_loading, val + 0.04)
        else: self.start_engine()

    def start_engine(self):
        self.hide_all()
        
        if CTK_AVAILABLE:
            self.lbl_hud_players.configure(text=f"JUCĂTORI: {self.selected_players}")
            self.lbl_hud_diff.configure(text=f"MOD: {self.selected_difficulty}")
            self.lbl_hud_target.configure(text=f"TARGET: {self.target_score}")
            self.score_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=1, relheight=1)
        else:
            self.score_frame.pack(expand=True, fill="both")
        
        self.net = NetManager(self.target_ip, self.local_ip)
        self.eng = GameEngine(self.net, self, self.selected_difficulty, self.selected_players, self.target_score)
        self.net.on_press = self.eng.on_press
        self.eng.start()

    def quit_app(self):
        if hasattr(self, 'eng'): self.eng.running = False
        if hasattr(self, 'net'):
            try:
                self.net.push({(c,l): (0,0,0) for c in range(1,5) for l in range(11)})
                time.sleep(0.1)
                self.net.running = False
            except: pass
        self.destroy()

    # --- Metode chemate de GameEngine ---
    def update_status(self, msg):
        if CTK_AVAILABLE: self.lbl_hud_status.configure(text=msg)
        else: self.lbl_hud_status.config(text=msg)
    
    def update_score(self, s):
        if CTK_AVAILABLE: self.lbl_hud_score.configure(text=str(s))
        else: self.lbl_hud_score.config(text=str(s))

if __name__ == "__main__":
    app = EsportsApp()
    app.mainloop()