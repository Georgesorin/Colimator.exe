import socket
import threading
import time
import random
import os
import json
import multiprocessing
import tkinter as tk
from datetime import datetime

try:
    import psutil
except ImportError:
    pass

# ==============================================================================
# 1. IMPORTURI SI SETARI GLOBALE (CONFIG)
# ==============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CFG_FILE = os.path.join(BASE_DIR, "config_game.json")

def _load_config():
    defaults = {
        "hw_send_port": 4626,
        "hw_recv_port": 7800,
        "sim_listen_port": 6768,
        "sim_send_port": 6769
    }
    try:
        if not os.path.exists(_CFG_FILE):
            with open(_CFG_FILE, "w", encoding="utf-8") as f:
                json.dump(defaults, f, indent=4)
                
        with open(_CFG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            defaults.update(data)
    except: pass
    return defaults

CONFIG = _load_config()

PASSWORD_ARRAY = [
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

def calc_checksum_send(data):
    idx = sum(data) & 0xFF
    return PASSWORD_ARRAY[idx] if idx < len(PASSWORD_ARRAY) else 0

def play_sound(filename, volume=1.0):
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.pre_init(44100, -16, 2, 2048)
            pygame.mixer.init()
        path = os.path.join(BASE_DIR, "sounds", filename)
        if os.path.exists(path):
            s = pygame.mixer.Sound(path)
            s.set_volume(volume)
            s.play()
    except: pass


# ==============================================================================
# 2. PROTOCOLUL DE DISCOVERY (SCANARE RETEA)
# ==============================================================================

def get_local_interfaces():
    interfaces = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        parts = ip.split('.')
        bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
        interfaces.append(("Ethernet/Wi-Fi", ip, bcast))
    except: pass
    interfaces.append(("Loopback (Simulator)", "127.0.0.1", "127.255.255.255"))
    return interfaces

# ---> AICI ERA EROAREA (FUNCTIA LIPSA) <---
def calc_sum(pkt):
    return sum(pkt) & 0xFF

def build_discovery_packet():
    rand1, rand2 = random.randint(0, 127), random.randint(0, 127)
    payload = bytearray([0x0A, 0x02, *b"KX-HC04", 0x03, 0x00, 0x00, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x14])
    pkt = bytearray([0x67, rand1, rand2, len(payload)]) + payload
    pkt.append(calc_sum(pkt))
    return pkt, rand1, rand2

def run_discovery_flow():
    interfaces = get_local_interfaces()
    print("\n--- Scanare Retea Hardware Evil Eye ---")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.5)

    pkt, r1, r2 = build_discovery_packet()
    for name, ip, bcast in interfaces:
        try: sock.sendto(pkt, (bcast, CONFIG["hw_send_port"]))
        except: pass

    print("📡 Se asteapta raspuns de la Hardware (3 secunde)...")
    end_time = time.time() + 3
    devices = []

    while time.time() < end_time:
        try:
            data, addr = sock.recvfrom(1024)
            if len(data) >= 30 and data[0] == 0x68 and data[1] == r1 and data[2] == r2:
                if addr[0] not in [d['ip'] for d in devices]:
                    model = data[6:13].decode(errors='ignore').strip('\x00')
                    devices.append({'ip': addr[0], 'model': model})
                    print(f"✅ Gasit sistem [{model}] la adresa {addr[0]}")
        except socket.timeout: continue
        except Exception: pass
    sock.close()

    if devices:
        return devices[0]['ip']
    return None 


# ==============================================================================
# 3. SIMULATORUL HARDWARE
# ==============================================================================

class WallCanvas(tk.Canvas):
    LAYOUT_ROWS = 3
    LAYOUT_COLS = 5

    def __init__(self, parent, channel, on_press, on_release, **kwargs):
        super().__init__(parent, bg="#111", highlightthickness=0, **kwargs)
        self._ch = channel
        self._on_press = on_press
        self._on_rel = on_release
        self._colors = [(0, 0, 0)] * 11
        self._items = {}
        self.bind("<Configure>", self._redraw)
        self.bind("<ButtonPress-1>", self._click_press)
        self.bind("<ButtonRelease-1>", self._click_release)

    def set_color(self, index, r, g, b):
        self._colors[index] = (r, g, b)
        self._apply_color(index)

    def _apply_color(self, index):
        if index not in self._items: return
        iid = self._items[index]
        r, g, b = self._colors[index]
        fill = f"#{r:02x}{g:02x}{b:02x}" if (r or g or b) else ("black" if index == 0 else "#0a0a0a")
        self.itemconfig(iid, fill=fill)
        if index == 0:
            outline = fill if (r or g or b) else "#ff0000"
            self.itemconfig(iid, outline=outline)

    def _cell_rect(self, idx, w, h, pad):
        cell_w = (w - 2 * pad) / self.LAYOUT_COLS
        cell_h = (h - 2 * pad) / self.LAYOUT_ROWS
        if idx == 0:
            cx, cy = w / 2, pad + cell_h * 0.5
            r = min(cell_w, cell_h) * 0.38
            return (cx - r, cy - r, cx + r, cy + r)
        else:
            btn = idx - 1
            row, col = btn // 5 + 1, btn % 5
            x1 = pad + col * cell_w + cell_w * 0.08
            y1 = pad + row * cell_h + cell_h * 0.08
            return (x1, y1, x1 + cell_w * 0.84, y1 + cell_h * 0.84)

    def _redraw(self, event=None):
        self.delete("all")
        self._items.clear()
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10: return
        pad = max(6, min(w, h) * 0.04)
        cell_w, cell_h = (w - 2 * pad) / self.LAYOUT_COLS, (h - 2 * pad) / self.LAYOUT_ROWS
        font_size = max(7, int(min(cell_w, cell_h) * 0.25))

        x1, y1, x2, y2 = self._cell_rect(0, w, h, pad)
        halo = max(4, (x2 - x1) * 0.12)
        self.create_oval(x1 - halo, y1 - halo, x2 + halo, y2 + halo, fill="#111", outline="#333", width=1)
        self._items[0] = self.create_oval(x1, y1, x2, y2, fill="black", outline="#ff0000", width=max(2, halo * 0.5))
        self.create_text(w / 2, y2 + max(4, halo), text="THE EYE", fill="#555", font=("Consolas", font_size - 1))

        for i in range(1, 11):
            x1, y1, x2, y2 = self._cell_rect(i, w, h, pad)
            self._items[i] = self.create_rectangle(x1, y1, x2, y2, fill="#0a0a0a", outline="#333", width=max(1, int((x2 - x1) * 0.04)))
            self.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=str(i), fill="#444", font=("Consolas", font_size, "bold"))
            self._apply_color(i)
        self._apply_color(0)

    def _hit_test(self, x, y):
        w, h = self.winfo_width(), self.winfo_height()
        pad = max(6, min(w, h) * 0.04)
        for idx in range(11):
            x1, y1, x2, y2 = self._cell_rect(idx, w, h, pad)
            if x1 <= x <= x2 and y1 <= y <= y2: return idx
        return None

    def _click_press(self, event):
        idx = self._hit_test(event.x, event.y)
        if idx is not None: self._on_press(self._ch, idx)

    def _click_release(self, event):
        idx = self._hit_test(event.x, event.y)
        if idx is not None: self._on_rel(self._ch, idx)

class EvilEyeSimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hardware Simulator (Evil Eye)")
        self.root.configure(bg="#1a1a1a")

        self.led_timestamps = {(c, l): 0 for c in range(1, 5) for l in range(11)}
        self.pressed_leds = set()
        self._press_lock = threading.Lock()
        self._running = True
        
        self.listen_port = CONFIG.get("sim_listen_port", 6768)
        self.send_port = CONFIG.get("sim_send_port", 6769)
        self._bind_ip = "0.0.0.0"

        self._wall_canvases = {}
        self._build_ui()
        self._setup_network()

        threading.Thread(target=self._network_loop, daemon=True).start()
        threading.Thread(target=self._timeout_loop, daemon=True).start()

    def _build_ui(self):
        pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg="#1a1a1a", sashwidth=5)
        pane.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(pane, bg="#1a1a1a")
        pane.add(left, stretch="always")
        
        for ch in range(1, 5):
            row, col = (ch - 1) // 2, (ch - 1) % 2
            left.grid_rowconfigure(row, weight=1)
            left.grid_columnconfigure(col, weight=1)
            wf = tk.LabelFrame(left, text=f" WALL {ch} ", bg="#1a1a1a", fg="#ff4444", font=("Consolas", 11, "bold"), borderwidth=2)
            wf.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            wf.grid_rowconfigure(0, weight=1)
            wf.grid_columnconfigure(0, weight=1)
            cv = WallCanvas(wf, ch, self._on_press, self._on_release)
            cv.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
            self._wall_canvases[ch] = cv

    def _on_press(self, channel, index):
        with self._press_lock: self.pressed_leds.add((channel, index))
        self._send_trigger_packet()

    def _on_release(self, channel, index):
        with self._press_lock: self.pressed_leds.discard((channel, index))
        self._send_trigger_packet()

    def _setup_network(self):
        self._sock_listen = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_listen.settimeout(0.5)
        try: self._sock_listen.bind((self._bind_ip, self.listen_port))
        except: pass
        
        self._sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_send.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try: self._sock_send.bind((self._bind_ip, 0))
        except: pass

    def _network_loop(self):
        while self._running:
            try: data, addr = self._sock_listen.recvfrom(2048)
            except: continue
            
            if data[0] == 0x67: 
                self._handle_discovery(addr, data)
            elif data[0] == 0x75: 
                if self._handle_control(data):
                    self._send_trigger_packet()

    def _handle_discovery(self, addr, data):
        resp = bytearray(32)
        resp[0], resp[1], resp[2] = 0x68, data[1] if len(data)>1 else 0, data[2] if len(data)>2 else 0
        resp[6:13], resp[13:19], resp[20] = b"KX-HC04", b"\x00\x11\x22\x33\x44\x55", 0x04
        try: self._sock_send.sendto(bytes(resp), addr)
        except: pass

    def _handle_control(self, data):
        payload = data[5:]
        if len(payload) < 9: return False
        data_id, msg_loc = (payload[3] << 8) | payload[4], (payload[5] << 8) | payload[6]
        if data_id == 0x8877 and msg_loc != 0xFFF0:
            self._update_leds(payload[9:])
            return True
        return False

    def _update_leds(self, frame_data):
        now = time.time()
        for led_idx in range(min(len(frame_data) // 12, 11)):
            for ch_idx in range(4):
                offset = led_idx * 12 + ch_idx
                if offset + 8 < len(frame_data):
                    g, r, b = frame_data[offset], frame_data[offset + 4], frame_data[offset + 8]
                    if r or g or b: self.led_timestamps[(ch_idx+1, led_idx)] = now
                    self.root.after(0, lambda c=ch_idx+1, i=led_idx, clr=(r,g,b): self._set_led(c, i, clr))

    def _timeout_loop(self):
        while self._running:
            time.sleep(1.0)
            now = time.time()
            for (ch, idx), ts in list(self.led_timestamps.items()):
                if ts != 0 and (now - ts) > 3.0:
                    self.led_timestamps[(ch, idx)] = 0
                    self.root.after(0, lambda c=ch, i=idx: self._set_led(c, i, (0, 0, 0)))

    def _set_led(self, channel, index, color):
        if channel in self._wall_canvases: self._wall_canvases[channel].set_color(index, *color)

    def _send_trigger_packet(self):
        pkt = bytearray(687)
        pkt[0], pkt[1] = 0x88, 0x01
        with self._press_lock: snapshot = set(self.pressed_leds)
        for ch, idx in snapshot:
            if 1 <= ch <= 4 and 0 <= idx < 11: pkt[2 + (ch-1)*171 + 1 + idx] = 0xCC
        pkt[-1] = sum(pkt[:-1]) & 0xFF
        for addr in [("127.0.0.1", self.send_port), ("255.255.255.255", self.send_port)]:
            try: self._sock_send.sendto(bytes(pkt), addr)
            except: pass

def run_simulator_process():
    root = tk.Tk()
    root.geometry("900x620")
    sim = EvilEyeSimulatorApp(root)
    root.mainloop()


# ==============================================================================
# 4. DRIVER COMUNICARE 
# ==============================================================================

class EvilEyeEngine:
    def __init__(self, target_ip):
        self.target_ip = target_ip
        
        if target_ip == "127.0.0.1":
            self.send_port = CONFIG.get("sim_listen_port", 6768)
            self.recv_port = CONFIG.get("sim_send_port", 6769)
        else:
            self.send_port = CONFIG.get("hw_send_port", 4626)
            self.recv_port = CONFIG.get("hw_recv_port", 7800)
            
        self.colors = [[(0,0,0) for _ in range(11)] for _ in range(4)]
        self.active_touches = set()
        self.running = True
        self.seq = 0
        self.lock = threading.Lock()
        
        self.sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try: 
            self.sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock_recv.bind(("0.0.0.0", self.recv_port))
        except Exception as e: print(f"[!] Eroare Bind Receive: {e}")
        
        threading.Thread(target=self._send_loop, daemon=True).start()
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def set_led(self, wall, index, r, g, b):
        if 0 <= wall < 4 and 0 <= index < 11:
            with self.lock: self.colors[wall][index] = (r, g, b)

    def clear(self):
        with self.lock: self.colors = [[(0,0,0) for _ in range(11)] for _ in range(4)]

    def get_touches(self):
        with self.lock:
            t = list(self.active_touches)
            self.active_touches.clear()
            return t

    def _build_frame_data(self):
        data = bytearray(132) 
        for w in range(4):
            for i in range(11):
                r, g, b = self.colors[w][i]
                data[i * 12 + w] = g
                data[i * 12 + 4 + w] = r
                data[i * 12 + 8 + w] = b
        return bytes(data)

    def _build_command_packet(self, data_id, msg_loc, payload):
        rand1, rand2 = random.randint(0, 127), random.randint(0, 127)
        internal = bytes([0x02, 0x00, 0x00, (data_id >> 8) & 0xFF, data_id & 0xFF,
                          (msg_loc >> 8) & 0xFF, msg_loc & 0xFF,
                          (len(payload) >> 8) & 0xFF, len(payload) & 0xFF]) + payload
        hdr = bytes([0x75, rand1, rand2, (len(internal) >> 8) & 0xFF, len(internal) & 0xFF])
        pkt = bytearray(hdr + internal)
        pkt[10], pkt[11] = (self.seq >> 8) & 0xFF, self.seq & 0xFF
        pkt.append(calc_checksum_send(pkt))
        return pkt

    def _send_loop(self):
        while self.running:
            with self.lock: frame_data = self._build_frame_data()
            self.seq = (self.seq + 1) & 0xFFFF
            if self.seq == 0: self.seq = 1
            
            try:
                p_start = bytearray([0x75, random.randint(0,127), random.randint(0,127), 0, 8, 0x02, 0, 0, 0x33, 0x44, (self.seq >> 8) & 0xFF, self.seq & 0xFF, 0, 0])
                p_start.append(calc_checksum_send(p_start))
                self.sock_send.sendto(bytes(p_start), (self.target_ip, self.send_port))
                time.sleep(0.008)
                
                payload_cfg = bytearray([0x00, 0x0B] * 4)
                p_cfg = self._build_command_packet(0x8877, 0xFFF0, payload_cfg)
                self.sock_send.sendto(p_cfg, (self.target_ip, self.send_port))
                time.sleep(0.008)
                
                p_data = self._build_command_packet(0x8877, 0x0000, frame_data)
                self.sock_send.sendto(p_data, (self.target_ip, self.send_port))
                time.sleep(0.008)
                
                p_end = bytearray([0x75, random.randint(0,127), random.randint(0,127), 0, 8, 0x02, 0, 0, 0x55, 0x66, (self.seq >> 8) & 0xFF, self.seq & 0xFF, 0, 0])
                p_end.append(calc_checksum_send(p_end))
                self.sock_send.sendto(bytes(p_end), (self.target_ip, self.send_port))
                
            except: pass
            time.sleep(0.04) 

    def _recv_loop(self):
        while self.running:
            try:
                data, _ = self.sock_recv.recvfrom(2048)
                if len(data) >= 687 and data[0] == 0x88:
                    touches = set()
                    for wall in range(4):
                        base = 2 + wall * 171
                        for led in range(1, 11): 
                            if data[base + 1 + led] == 0xCC:
                                touches.add((wall, led))
                    with self.lock: 
                        self.active_touches.update(touches)
            except: pass
            
    def stop(self): self.running = False


# ==============================================================================
# 5. LOGICA JOCULUI (EVIL EYE MASTER)
# ==============================================================================

class EvilEyeGame:
    def __init__(self, hardware_ip):
        self.engine = EvilEyeEngine(hardware_ip)
        self.lock = threading.RLock()
        self.running = True
        self.state = 'LOBBY'
        self.gameover_text = ""
        self.hw_ip = hardware_ip
        
        self.TEAM_A_WALLS = [0, 1] 
        self.TEAM_B_WALLS = [2, 3] 
        
        self.team_a_score = 0
        self.team_b_score = 0
        self.team_a_lives = 5
        self.team_b_lives = 5
        self.starting_lives = 5
        self.difficulty = "hard"
        
        self.start_time = 0
        self.state_timer = 0
        self.MAX_TIME = 300 
        
        self.eye_wall = -1
        self.next_eye_wall = -1
        self.eye_time_elapsed = 0.0 
        self.last_tick_time = 0.0
        
        self.eye_locked_timer = 0
        self.freeze_a_timer = 0
        self.freeze_b_timer = 0
        
        self.invuln_a_timer = 0
        self.invuln_b_timer = 0
        
        self.init_round_data()

    def init_round_data(self):
        self.team_a_score = 0
        self.team_b_score = 0
        self.team_a_lives = self.starting_lives
        self.team_b_lives = self.starting_lives
        
        if self.difficulty == "easy":
            powerups_list = ['LOCK', 'LOCK', 'LOCK']
        else:
            powerups_list = ['FREEZE', 'FREEZE', 'SWITCH', 'SWITCH', 'LOCK']
            
        self.team_pools = {
            'A': {'points_left': 7, 'powerups': list(powerups_list)},
            'B': {'points_left': 7, 'powerups': list(powerups_list)}
        }
        random.shuffle(self.team_pools['A']['powerups'])
        random.shuffle(self.team_pools['B']['powerups'])
            
        self.active_entities = [] 
        
        self.eye_wall = -1
        self.next_eye_wall = -1
        self.eye_time_elapsed = 0.0
        self.last_tick_time = time.time()
        self.freeze_a_timer = 0
        self.freeze_b_timer = 0
        self.invuln_a_timer = 0
        self.invuln_b_timer = 0

    def start_game(self, lives=5, difficulty="hard"):
        with self.lock:
            self.starting_lives = lives
            self.difficulty = difficulty
            self.init_round_data()
            self.state = 'STARTUP'
            self.state_timer = time.time()
            self.last_tick_time = time.time()
            
            self.eye_wall = random.randint(0, 3)
            self.next_eye_wall = random.choice([w for w in range(4) if w != self.eye_wall])
            print(f"[!] PREGATIRE RUNDA (5 SEC) - VIETI: {lives} | DIFICULTATE: {difficulty.upper()}")

    def spawn_entities(self):
        occupied = [(e['wall'], e['index']) for e in self.active_entities]
        
        for team, walls in [('A', self.TEAM_A_WALLS), ('B', self.TEAM_B_WALLS)]:
            pts_active = sum(1 for e in self.active_entities if e['team'] == team and e['type'] == 'POINT')
            pwr_active = sum(1 for e in self.active_entities if e['team'] == team and e['type'] == 'POWERUP')
            
            while pts_active < 2 and self.team_pools[team]['points_left'] > 0:
                w = random.choice(walls)
                idx = random.randint(1, 10)
                if (w, idx) not in occupied:
                    self.active_entities.append({'team': team, 'type': 'POINT', 'wall': w, 'index': idx, 'data': None})
                    occupied.append((w, idx))
                    self.team_pools[team]['points_left'] -= 1
                    pts_active += 1
                    
            while pwr_active < 1 and len(self.team_pools[team]['powerups']) > 0:
                w = random.choice(walls)
                idx = random.randint(1, 10)
                if (w, idx) not in occupied:
                    pwr_type = self.team_pools[team]['powerups'].pop()
                    self.active_entities.append({'team': team, 'type': 'POWERUP', 'wall': w, 'index': idx, 'data': pwr_type})
                    occupied.append((w, idx))
                    pwr_active += 1

    def trigger_gameover(self, reason):
        self.state = 'GAMEOVER'
        self.gameover_text = reason
        play_sound("gameover.mp3")
        print(f"JOC TERMINAT! {reason}")

    def handle_touches(self, touches, now):
        for wall, led_idx in touches:
            team_touched = 'A' if wall in self.TEAM_A_WALLS else 'B'
            
            if wall == self.eye_wall:
                if team_touched == 'A' and now > self.invuln_a_timer:
                    self.team_a_lives -= 1
                    self.invuln_a_timer = now + 1.5
                    play_sound("damage_heart.mp3")
                elif team_touched == 'B' and now > self.invuln_b_timer:
                    self.team_b_lives -= 1
                    self.invuln_b_timer = now + 1.5
                    play_sound("damage_heart.mp3")
                continue 
                
            if team_touched == 'A' and now < self.freeze_a_timer: continue
            if team_touched == 'B' and now < self.freeze_b_timer: continue
            
            for ent in list(self.active_entities):
                if ent['wall'] == wall and ent['index'] == led_idx:
                    self.active_entities.remove(ent)
                    
                    if ent['type'] == 'POINT':
                        if team_touched == 'A': self.team_a_score += 1
                        else: self.team_b_score += 1
                        play_sound("coin.mp3")
                    
                    elif ent['type'] == 'POWERUP':
                        pt = ent['data']
                        play_sound("powerup.mp3")
                        if pt == 'FREEZE':
                            if team_touched == 'A': self.freeze_b_timer = now + 5.0
                            else: self.freeze_a_timer = now + 5.0
                        elif pt == 'SWITCH':
                            if team_touched == 'A': self.eye_wall = random.choice(self.TEAM_B_WALLS)
                            else: self.eye_wall = random.choice(self.TEAM_A_WALLS)
                            self.next_eye_wall = random.choice([w for w in range(4) if w != self.eye_wall])
                            self.eye_time_elapsed = 0.0 
                        elif pt == 'LOCK':
                            self.eye_locked_timer = now + 5.0 
                    break 

    def check_win_condition(self, now):
        if self.team_a_lives <= 0:
            self.trigger_gameover("MAGENTA A CASTIGAT (CYAN ELIMINAT)")
            return
        if self.team_b_lives <= 0:
            self.trigger_gameover("CYAN A CASTIGAT (MAGENTA ELIMINAT)")
            return
            
        if self.team_a_score >= 7:
            self.trigger_gameover("CYAN A CASTIGAT (7 PUNCTE)")
            return
        if self.team_b_score >= 7:
            self.trigger_gameover("MAGENTA A CASTIGAT (7 PUNCTE)")
            return
            
        if (now - self.start_time) >= self.MAX_TIME:
            if self.team_a_score > self.team_b_score: self.trigger_gameover("CYAN A CASTIGAT (TIMP)")
            elif self.team_b_score > self.team_a_score: self.trigger_gameover("MAGENTA A CASTIGAT (TIMP)")
            else:
                if self.team_a_lives > self.team_b_lives: self.trigger_gameover("CYAN A CASTIGAT (DEPARTAJARE VIETI)")
                elif self.team_b_lives > self.team_a_lives: self.trigger_gameover("MAGENTA A CASTIGAT (DEPARTAJARE VIETI)")
                else: self.trigger_gameover("REMIZA PERFECTA")

    def tick(self):
        self.engine.clear()
        now = time.time()
        touches = self.engine.get_touches()
        
        delta_time = now - self.last_tick_time
        self.last_tick_time = now
        
        with self.lock:
            if self.state == 'LOBBY':
                pass 
                    
            elif self.state == 'STARTUP':
                elapsed = now - self.state_timer
                is_blinking_phase = (elapsed >= 3.0)
                blink_state = (int(elapsed * 8) % 2 == 0) if is_blinking_phase else True
                
                for w in range(4):
                    if w in self.TEAM_A_WALLS:
                        r, g, b = (0, 255, 255) if blink_state else (0, 0, 0)
                    else:
                        r, g, b = (255, 0, 255) if blink_state else (0, 0, 0)
                        
                    for i in range(1, 11):
                        self.engine.set_led(w, i, r, g, b)
                        
                    if is_blinking_phase and w == self.eye_wall:
                        eye_r = 255 if blink_state else 0
                        self.engine.set_led(w, 0, eye_r, 0, 0)
                    else:
                        self.engine.set_led(w, 0, 0, 0, 0)

                if elapsed >= 5.0:
                    self.state = 'PLAYING'
                    self.start_time = now
                    self.eye_time_elapsed = 0.0
                    print("[!] JOCUL A INCEPUT EFECTIV!")
                    play_sound("start.mp3")

            elif self.state == 'PLAYING':
                self.spawn_entities()
                self.handle_touches(touches, now)
                self.check_win_condition(now)

                if self.state != 'PLAYING': return

                is_eye_locked = now <= self.eye_locked_timer
                
                if not is_eye_locked:
                    self.eye_time_elapsed += delta_time
                    if self.eye_time_elapsed >= 5.0:
                        self.eye_wall = self.next_eye_wall
                        self.next_eye_wall = random.choice([w for w in range(4) if w != self.eye_wall])
                        self.eye_time_elapsed = 0.0
                
                for ent in self.active_entities:
                    w, idx = ent['wall'], ent['index']
                    if w == self.eye_wall: 
                        self.engine.set_led(w, idx, 255, 0, 0)
                        continue
                        
                    if ent['type'] == 'POINT':
                        self.engine.set_led(w, idx, 255, 255, 0) 
                    else:
                        pt = ent['data']
                        if pt == 'FREEZE': self.engine.set_led(w, idx, 160, 32, 240) 
                        elif pt == 'SWITCH': self.engine.set_led(w, idx, 0, 255, 0) 
                        elif pt == 'LOCK': self.engine.set_led(w, idx, 255, 0, 0) 

                if self.eye_wall != -1:
                    self.engine.set_led(self.eye_wall, 0, 255, 0, 0) 
                    
                if not is_eye_locked and self.eye_time_elapsed >= 3.0:
                    self.engine.set_led(self.next_eye_wall, 0, 255, 255, 0) 
                    
                for w in range(4):
                    is_frozen = (w in self.TEAM_A_WALLS and now < self.freeze_a_timer) or \
                                (w in self.TEAM_B_WALLS and now < self.freeze_b_timer)
                    if is_frozen:
                        for i in range(1, 11):
                            if not any(e['wall'] == w and e['index'] == i for e in self.active_entities):
                                self.engine.set_led(w, i, 40, 0, 60) 

            elif self.state == 'GAMEOVER':
                w_color = (0, 255, 255) if self.team_a_score > self.team_b_score else (255, 0, 255)
                for w in range(4):
                    for i in range(11):
                        self.engine.set_led(w, i, w_color[0], w_color[1], w_color[2])


# ==============================================================================
# 6. ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    print("=============================================")
    print("👁️ EVIL EYE: THE VAULT (MASTER RUNNER) 👁️")
    print("=============================================\n")
    
    target_ip = run_discovery_flow()
    
    sim_process = None
    if not target_ip:
        print("[!] Trecere automata pe SIMULATOR. Se initializeaza fereastra de Test...")
        sim_process = multiprocessing.Process(target=run_simulator_process)
        sim_process.start()
        
        target_ip = "127.0.0.1"
        time.sleep(2) 

    game = EvilEyeGame(target_ip)
    
    def game_loop():
        while game.running:
            game.tick()
            time.sleep(0.03)
            
    t = threading.Thread(target=game_loop, daemon=True)
    t.start()
    
    try:
        import evil_eye_screens
        evil_eye_screens.launch(game)
    except ImportError:
        print("[!] Eroare: Nu am gasit fisierul evil_eye_screens.py pentru interfata!")
        while game.running:
            time.sleep(1)
            
    print("\n[!] Se inchide sistemul...")
    if sim_process and sim_process.is_alive():
        sim_process.terminate()