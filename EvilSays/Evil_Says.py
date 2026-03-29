import socket
import threading
import time
import random
import queue
import tkinter as tk
from tkinter import ttk

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
# MANAGER REȚEA (Standard Evil Eye: Fără forțare pe Loopback)
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
        for (ch, led), (r, g, b) in led_dict.items():
            if 1 <= ch <= 4 and 0 <= led <= 10:
                idx = led * 12 + (ch-1)
                buf[idx], buf[idx+4], buf[idx+8] = g, r, b
        try: self.q.put(bytes(buf), block=False)
        except queue.Full: pass

# ─────────────────────────────────────────────────────────────────────────────
# LOGICA JOCULUI
# ─────────────────────────────────────────────────────────────────────────────
class GameEngine:
    def __init__(self, net, ui, diff):
        self.net, self.ui, self.diff = net, ui, diff
        self.score = 0
        self.pattern, self.guessed, self.wrong_guessed, self.frenzy = set(), set(), set(), set()
        self.eye_wall = 1
        self.state = "OFF"
        
        configs = {"EASY": (2, 3, 5), "MEDIUM": (4, 2, 5), "HARD": (6, 1, 5)}
        self.base_tiles, self.t_warn, self.t_gaze = configs[diff]

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
        self.ui.log("🌀 Pornire sistem...")
        st = time.time(); w = 1
        while time.time() - st < 3.0:
            frame = {(c, l): (0, 255, 255) if c == w and l > 0 else (0,0,0) for c in range(1,5) for l in range(11)}
            self.net.push(frame); time.sleep(0.08); w = (w % 4) + 1

        while True:
            num = min(self.base_tiles + (self.score // 5), 35)
            self.pattern = set(random.sample([(c,l) for c in range(1,5) for l in range(1,11)], num))
            self.guessed.clear(); self.wrong_guessed.clear(); self.frenzy.clear()

            self.state = "ROULETTE"
            self.ui.log("👁️ Scanează..."); curr = random.randint(1,4)
            for i in range(15):
                self.eye_wall = curr; self._draw(); time.sleep(0.05 + i*0.02); curr = (curr % 4) + 1
            self.eye_wall = curr

            self.state = "WARNING"; st = time.time()
            while time.time() - st < self.t_warn: self._draw(); time.sleep(0.1)

            self.state = "GAZE"
            if random.random() < 0.2:
                self.frenzy = set((self.eye_wall, l) for l in random.sample(range(1,11), 4))
                self.ui.log("🌟 FEBRA DE AUR!")
            else: self.ui.log("🔴 NU MIȘCAȚI!")
            
            st = time.time()
            while time.time() - st < self.t_gaze:
                if self.state == "STUN": break
                self._draw(); time.sleep(0.1)

            if self.state == "STUN":
                for _ in range(6):
                    self.net.push({(c,l): (255,0,0) for c in range(1,5) for l in range(11)})
                    time.sleep(0.2)
                    self.net.push({(c,l): (0,0,0) for c in range(1,5) for l in range(11)})
                    time.sleep(0.2)
                continue

            self.state = "ACTION"; self.ui.log("🟢 ACȚIONAȚI!")
            st = time.time()
            while time.time() - st < 7.0:
                self._draw()
                if len(self.guessed) >= len(self.pattern):
                    self.ui.log("🎉 RUNDĂ COMPLETĂ!"); self.score += 5; self.ui.update_score(self.score)
                    break
                time.sleep(0.1)
            else: self.ui.log("⌛ Timp expirat!")
            time.sleep(1)

    def on_press(self, ch, l):
        if l == 0: return
        if self.state == "GAZE":
            if self.frenzy and ch == self.eye_wall and (ch, l) in self.frenzy:
                self.score += 3; self.frenzy.remove((ch, l)); self.ui.update_score(self.score)
            else:
                self.score = max(0, self.score - 5); self.ui.update_score(self.score)
                self.state = "STUN"; self.ui.log("☠️ TE-A VĂZUT!")
        elif self.state == "ACTION":
            if (ch, l) in self.pattern:
                if (ch, l) not in self.guessed: self.guessed.add((ch, l)); self.score += 1; self.ui.update_score(self.score)
            else:
                if (ch, l) not in self.wrong_guessed:
                    self.wrong_guessed.add((ch, l)); self.score = max(0, self.score - 2); self.ui.update_score(self.score)

# ─────────────────────────────────────────────────────────────────────────────
# UI PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("Evil Says Launcher"); self.geometry("450x600"); self.configure(bg="#0c0f18")
        self.show_mode_selection()

    def show_mode_selection(self):
        self.frame = tk.Frame(self, bg="#0c0f18"); self.frame.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(self.frame, text="EVIL EYE GAME", font=("Courier New", 24, "bold"), fg="#ffd000", bg="#0c0f18").pack(pady=30)
        
        tk.Button(self.frame, text="🚀 HARDWARE MODE", font=("Arial", 14, "bold"), bg="#1a3a1a", fg="#00ff73", width=25, height=2,
                  command=self.mode_hardware).pack(pady=10)
        
        tk.Button(self.frame, text="💻 SOFTWARE MODE", font=("Arial", 14, "bold"), bg="#1a2a3a", fg="#0073ff", width=25, height=2,
                  command=self.mode_software).pack(pady=10)

    def mode_hardware(self):
        for w in self.frame.winfo_children(): w.destroy()
        tk.Label(self.frame, text="ALEGE INTERFAȚA ETHERNET", fg="white", bg="#0c0f18", font=("Arial", 12)).pack(pady=10)
        import psutil
        for iface, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family == socket.AF_INET and not a.address.startswith("127."):
                    tk.Button(self.frame, text=f"{iface}: {a.address}", width=35, command=lambda ip=a.address: self.setup_difficulty(ip, HARDWARE_TARGET_IP)).pack(pady=2)

    def mode_software(self):
        self.setup_difficulty("127.0.0.1", SIMULATOR_TARGET_IP)

    def setup_difficulty(self, local_ip, target_ip):
        self.local_ip = local_ip
        self.target_ip = target_ip
        
        # Discovery Handshake 0x67
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        pkt = bytearray([0x67, 1, 2, 12, 10, 2, 75, 88, 45, 72, 67, 48, 52, 3, 0, 0, 255, 255, 0, 0, 0, 20])
        pkt.append(calc_chk(pkt)); s.sendto(pkt, ("255.255.255.255", 4626)); s.close()

        for w in self.frame.winfo_children(): w.destroy()
        tk.Label(self.frame, text="DIFICULTATE", font=("Arial", 14), fg="white", bg="#0c0f18").pack(pady=10)
        self.dv = tk.StringVar(value="MEDIUM")
        for d in ["EASY", "MEDIUM", "HARD"]: tk.Radiobutton(self.frame, text=d, variable=self.dv, value=d, fg="white", bg="#0c0f18").pack()
        tk.Button(self.frame, text="START JOC", font=("Arial", 14, "bold"), bg="#ffd000", fg="black", command=self.start_game).pack(pady=20)

    def start_game(self):
        d = self.dv.get(); self.frame.destroy()
        self.sl = tk.Label(self, text="SCOR: 0", font=("Courier New", 30, "bold"), fg="white", bg="#0c0f18"); self.sl.pack(pady=20)
        self.tb = tk.Text(self, height=12, bg="black", fg="#00ff00", font=("Consolas", 10)); self.tb.pack(fill="x", side="bottom")
        
        self.net = NetManager(self.target_ip, self.local_ip)
        self.eng = GameEngine(self.net, self, d)
        self.net.on_press = self.eng.on_press; self.eng.start()

    def log(self, m): self.tb.insert("1.0", f"[{time.strftime('%H:%M:%S')}] {m}\n")
    def update_score(self, s): self.sl.config(text=f"SCOR: {s}")

if __name__ == "__main__":
    App().mainloop()