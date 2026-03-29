import customtkinter as ctk
import socket
import json
import time

# Setări globale pentru aspect modern
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ModernScoreboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LIVE SCOREBOARD - E-SPORTS EDITION")
        self.attributes('-fullscreen', True)
        
        # Fundal albastru-închis rafinat
        self.configure(fg_color="#0D0D14") 
        
        # Culori vibrante (Neon Flat)
        self.C_CYAN = "#00FFFF"  # CYAN
        self.C_MAGENTA = "#FF00FF" # ROȘU (Înainte era Magenta)
        self.C_RED = "#FF1744"
        self.C_GREEN = "#00E676"
        self.C_YELLOW = "#FFEA00" 
        self.C_ORANGE = "#FF9800" # Culoare pentru Anti-Cheat
        self.C_PANEL = "#1A1A24" 
        
        # Socket setup
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 5005))
        self.sock.setblocking(False)
        
        self.game_data = {
            "p1_score": 0, "p1_lives": 5, "p1_status": "ACTIVE",
            "p2_score": 0, "p2_lives": 5, "p2_status": "ACTIVE"
        }
        
        self.max_lives = 5 
        self.flash_state = False
        
        self.setup_ui()
        self.update_data()
        self.animate_alerts()

    def setup_ui(self):
        # --- HEADER ---
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(pady=(40, 20), fill="x")
        
        self.lbl_sys = ctk.CTkLabel(self.header_frame, text="TRANSMISIE LIVE // LABIRINT", text_color="#555", font=("Helvetica", 20, "bold"))
        self.lbl_sys.pack()
        
        self.lbl_round = ctk.CTkLabel(self.header_frame, text="ÎN AȘTEPTARE...", text_color=self.C_YELLOW, font=("Helvetica", 45, "bold"))
        self.lbl_round.pack(pady=(10, 0))

        # --- CONTAINER PRINCIPAL ---
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(expand=True, fill="both", padx=50, pady=20)

        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(1, weight=0, minsize=100) 
        self.main_container.grid_columnconfigure(2, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)

        # ==========================================
        # PANOU JUCĂTOR 1 (STÂNGA)
        # ==========================================
        self.p1_card = ctk.CTkFrame(self.main_container, fg_color=self.C_PANEL, corner_radius=30, border_width=4, border_color=self.C_CYAN)
        self.p1_card.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        ctk.CTkLabel(self.p1_card, text="JUCĂTORUL 1 (CYAN)", text_color=self.C_CYAN, font=("Helvetica", 35, "bold")).pack(pady=(40, 10))
        
        self.p1_score_lbl = ctk.CTkLabel(self.p1_card, text="0", text_color=self.C_CYAN, font=("Helvetica", 280, "bold"))
        self.p1_score_lbl.pack(expand=True)
        
        # Container pentru vieți individuale (până la 10)
        self.p1_lives_container = ctk.CTkFrame(self.p1_card, fg_color="transparent")
        self.p1_lives_container.pack(pady=(10, 10))
        self.p1_life_boxes = []
        for _ in range(10):
            box = ctk.CTkFrame(self.p1_lives_container, width=35, height=35, corner_radius=20, fg_color="#222", border_width=2, border_color="#111")
            self.p1_life_boxes.append(box)
        
        self.p1_hp_text = ctk.CTkLabel(self.p1_card, text="INTEGRITATE: 5/5", text_color="#AAA", font=("Helvetica", 22, "bold"))
        self.p1_hp_text.pack(pady=(0, 20))

        self.p1_status_badge = ctk.CTkLabel(self.p1_card, text=" STATUS: OPTIM ", text_color="black", fg_color=self.C_CYAN, font=("Helvetica", 25, "bold"), corner_radius=15, width=350, height=60)
        self.p1_status_badge.pack(pady=(0, 40))


        # ==========================================
        # PANOU JUCĂTOR 2 (DREAPTA)
        # ==========================================
        self.p2_card = ctk.CTkFrame(self.main_container, fg_color=self.C_PANEL, corner_radius=30, border_width=4, border_color=self.C_MAGENTA)
        self.p2_card.grid(row=0, column=2, sticky="nsew", padx=20, pady=20)
        
        ctk.CTkLabel(self.p2_card, text="JUCĂTORUL 2 (ROZ)", text_color=self.C_MAGENTA, font=("Helvetica", 35, "bold")).pack(pady=(40, 10))
        
        self.p2_score_lbl = ctk.CTkLabel(self.p2_card, text="0", text_color=self.C_MAGENTA, font=("Helvetica", 280, "bold"))
        self.p2_score_lbl.pack(expand=True)
        
        # Container pentru vieți individuale (până la 10)
        self.p2_lives_container = ctk.CTkFrame(self.p2_card, fg_color="transparent")
        self.p2_lives_container.pack(pady=(10, 10))
        self.p2_life_boxes = []
        for _ in range(10):
            box = ctk.CTkFrame(self.p2_lives_container, width=35, height=35, corner_radius=20, fg_color="#222", border_width=2, border_color="#111")
            self.p2_life_boxes.append(box)
        
        self.p2_hp_text = ctk.CTkLabel(self.p2_card, text="INTEGRITATE: 5/5", text_color="#AAA", font=("Helvetica", 22, "bold"))
        self.p2_hp_text.pack(pady=(0, 20))

        self.p2_status_badge = ctk.CTkLabel(self.p2_card, text=" STATUS: OPTIM ", text_color="white", fg_color=self.C_MAGENTA, font=("Helvetica", 25, "bold"), corner_radius=15, width=350, height=60)
        self.p2_status_badge.pack(pady=(0, 40))

    def update_data(self):
        try:
            data, _ = self.sock.recvfrom(2048)
            new_info = json.loads(data.decode())
            self.game_data.update(new_info)
            
            if self.game_data["p1_lives"] > self.max_lives or self.game_data["p2_lives"] > self.max_lives:
                self.max_lives = max(self.game_data["p1_lives"], self.game_data["p2_lives"])
                if self.max_lives == 0: self.max_lives = 1
        except:
            pass

        # --- UPDATE RUNDA ---
        p1_s = self.game_data["p1_score"]
        p2_s = self.game_data["p2_score"]
        if p1_s == 0 and p2_s == 0:
            self.lbl_round.configure(text="ÎN AȘTEPTARE...", text_color=self.C_YELLOW)
        else:
            self.lbl_round.configure(text=f"RUNDA {(p1_s + p2_s + 1):02d}", text_color="white")

        # --- UPDATE JUCĂTOR 1 VIEȚI ---
        l1 = max(0, self.game_data["p1_lives"])
        self.p1_hp_text.configure(text=f"VIEȚI: {l1} / {self.max_lives}")
        for i in range(10):
            if i < self.max_lives:
                self.p1_life_boxes[i].pack(side="left", padx=8)
                if i < l1:
                    self.p1_life_boxes[i].configure(fg_color=self.C_CYAN, border_color="#FFF")
                else:
                    self.p1_life_boxes[i].configure(fg_color="#111", border_color="#333")
            else:
                self.p1_life_boxes[i].pack_forget()

        # --- UPDATE JUCĂTOR 2 VIEȚI ---
        l2 = max(0, self.game_data["p2_lives"])
        self.p2_hp_text.configure(text=f"VIEȚI: {l2} / {self.max_lives}")
        for i in range(10):
            if i < self.max_lives:
                self.p2_life_boxes[i].pack(side="left", padx=8)
                if i < l2:
                    self.p2_life_boxes[i].configure(fg_color=self.C_MAGENTA, border_color="#FFF")
                else:
                    self.p2_life_boxes[i].configure(fg_color="#111", border_color="#333")
            else:
                self.p2_life_boxes[i].pack_forget()

        self.after(20, self.update_data)

    def animate_alerts(self):
        """Gestionează animațiile de Stun și Anti-Cheat (Resetting)"""
        self.flash_state = not self.flash_state

        for p_num, c_base in [(1, self.C_CYAN), (2, self.C_MAGENTA)]:
            status = self.game_data[f"p{p_num}_status"]
            card = getattr(self, f"p{p_num}_card")
            lbl = getattr(self, f"p{p_num}_score_lbl")
            badge = getattr(self, f"p{p_num}_status_badge")
            score = self.game_data[f"p{p_num}_score"]

            if status == "RESETTING":
                # ANIMAȚIE TRIȘAT (Culoare Portocalie de Alertă)
                color = self.C_ORANGE if self.flash_state else "#8A5000"
                card.configure(border_color=color)
                lbl.configure(text="⚠️", text_color=color) # Înlocuiește scorul cu warning
                badge.configure(text=" ANTI-CHEAT ACTIVAT ", fg_color=color, text_color="white")
                
            elif status == "STUNNED":
                # ANIMAȚIE LOVITURĂ PERETE (Culoare Roșie)
                color = self.C_RED if self.flash_state else "#4A0000"
                card.configure(border_color=color)
                lbl.configure(text=str(score), text_color=color)
                badge.configure(text=" CRITIC: STUNNED ", fg_color=color, text_color="white")
                
            else:
                # STARE NORMALĂ
                card.configure(border_color=c_base)
                lbl.configure(text=str(score), text_color=c_base)
                badge.configure(text=" STATUS: OPTIM ", fg_color=c_base, text_color="black" if p_num == 1 else "white")

        self.after(250, self.animate_alerts)


if __name__ == "__main__":
    app = ModernScoreboard()
    app.mainloop()