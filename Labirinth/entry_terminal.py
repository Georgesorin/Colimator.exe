import customtkinter as ctk
import tkinter as tk
import socket
import json
import random

# GLOBAL - UI
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class TouchTerm(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Configurare Labirint - E-Sports Edition")
        self.attributes('-fullscreen', True)
        self.configure(fg_color="#0A0A12")

        # NETWORK
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.game_addr = ("127.0.0.1", 6767)

        self.selected_category = None
        self.selected_difficulty = None

        # MORE UI
        self.canvas = tk.Canvas(self, bg="#0A0A12", highlightthickness=0)
        self.canvas.place(relwidth=1, relheight=1)
        self.init_animated_bg()

        self.setup_frames()
        self.show_category_screen()

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

    def setup_frames(self):
        # FONTS
        f_super = ("Helvetica", 87, "bold")
        f_title = ("Helvetica", 50, "bold")
        f_btn = ("Helvetica", 40, "bold")
        f_btn_small = ("Helvetica", 25, "bold")
        f_desc = ("Helvetica", 32)
        f_info = ("Helvetica", 50, "bold")

        # CONTROLLER - UI (FIRST WINDOW)
        self.cat_frame = ctk.CTkFrame(self, fg_color="transparent")
        
        ctk.CTkLabel(self.cat_frame, text="RĂZBOIUL DE CEAȚĂ", font=f_super, text_color="#00E5FF").pack(pady=(30, 10), ipady=15)
        ctk.CTkLabel(self.cat_frame, text="SELECTEAZĂ UN MOD DE JOC", text_color="white", font=f_info).pack(pady=(0, 60))
        
        btn_width, btn_height = 650, 130
        
        ctk.CTkButton(self.cat_frame, text="COPIL", fg_color="#00BFFF", hover_color="#0088CC", font=f_btn, 
                      text_color="black", width=btn_width, height=btn_height, corner_radius=30, 
                      border_width=4, border_color="#00E5FF",
                      command=lambda: self.select_category("CHILD")).pack(pady=15)
                      
        ctk.CTkButton(self.cat_frame, text="ADULT", fg_color="#FF0055", hover_color="#CC0044", font=f_btn, 
                      text_color="black", width=btn_width, height=btn_height, corner_radius=30, 
                      border_width=4, border_color="#FF3377",
                      command=lambda: self.select_category("ADULT")).pack(pady=15)
                      
        ctk.CTkButton(self.cat_frame, text="COPIL + ADULT", fg_color="#00E676", hover_color="#00B259", font=f_btn, 
                      text_color="black", width=btn_width, height=btn_height, corner_radius=30, 
                      border_width=4, border_color="#69FF9E",
                      command=lambda: self.select_category("MIXED")).pack(pady=15)

        ctk.CTkButton(self.cat_frame, text="INCHIDERE LABIRINT", font=f_btn_small, text_color="#666", 
                      fg_color="transparent", hover_color="#111", width=200, height=60, 
                      command=self.quit).pack(pady=(60, 0))

        # SECOND WINDOW - DIFICULTY
    
        self.diff_frame = ctk.CTkFrame(self, fg_color="transparent")
        
        self.lbl_diff_subtitle = ctk.CTkLabel(self.diff_frame, text="ALEGE MODUL DE JOC", font=f_info, text_color="#00E5FF")
        self.lbl_diff_subtitle.pack(pady=(0, 5))
        
        self.lbl_diff_title = ctk.CTkLabel(self.diff_frame, text="NIVEL DE DIFICULTATE", text_color="white", font=f_super)
        self.lbl_diff_title.pack(pady=(0, 60))

        diff_kw = {"font": f_btn, "width": btn_width, "height": btn_height, "corner_radius": 20, "border_width": 3}
        
        self.btn_easy = ctk.CTkButton(self.diff_frame, text="UȘOR", **diff_kw, command=lambda: self.show_details("EASY"))
        self.btn_medium = ctk.CTkButton(self.diff_frame, text="MEDIU", **diff_kw, command=lambda: self.show_details("MEDIUM"))
        self.btn_hard = ctk.CTkButton(self.diff_frame, text="GREU", **diff_kw, command=lambda: self.show_details("HARD"))

        ctk.CTkButton(self.diff_frame, text="< INAPOI LA PROFIL", font=f_btn_small, text_color="#AAA", 
                      fg_color="#1A1A24", hover_color="#2A2A35", corner_radius=20, width=300, height=50, 
                      command=self.show_category_screen).pack(pady=(60, 0))

        # DETAILS / CONFIRMATIONS
        self.details_frame = ctk.CTkFrame(self, fg_color="#12121A", corner_radius=40, border_width=3, border_color="#00E5FF")
        self.details_frame.configure(width=1200, height=800)
        self.details_frame.pack_propagate(False) 
        
        self.lbl_det_title = ctk.CTkLabel(self.details_frame, text="CONFIRMARE DIFICULTATE", font=f_title, text_color="white")
        self.lbl_det_title.pack(pady=(60, 40))
        
        desc_container = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        desc_container.pack(expand=True, fill="both", padx=80)
        
        self.lbl_det_desc = ctk.CTkLabel(desc_container, text="", font=f_desc, justify="center", text_color="#E0E0E0")
        self.lbl_det_desc.pack(expand=True)
        
        b_box = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        b_box.pack(side="bottom", pady=(0, 60))
        
        ctk.CTkButton(b_box, text="ANULEAZĂ", font=f_btn, text_color="#FFF", fg_color="#444", hover_color="#555", 
                      corner_radius=20, width=300, height=90, command=self.show_diff_screen).pack(side="left", padx=20)
                      
        self.btn_start = ctk.CTkButton(b_box, text="START MISIUNE >", font=f_btn, text_color="#000", 
                                       fg_color="#00E676", hover_color="#00C853", corner_radius=20, width=450, height=90, 
                                       command=self.start_game)
        self.btn_start.pack(side="left", padx=20)

        # TRANSITION TO GAME
        self.load_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.load_frame, text="SE PREGĂTEȘTE LABIRINTUL...", font=f_super, text_color="#00E5FF").pack(pady=20)
        
        self.progress_bar = ctk.CTkProgressBar(self.load_frame, width=600, height=25, corner_radius=12, progress_color="#00E5FF", fg_color="#222")
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=20)

    # NAVIGATION

    def hide_all(self):
        for f in [self.cat_frame, self.diff_frame, self.details_frame, self.load_frame]: 
            f.place_forget()

    def show_category_screen(self):
        self.hide_all()
        self.cat_frame.place(relx=0.5, rely=0.5, anchor="center")

    def show_diff_screen(self):
        self.hide_all()
        self.btn_easy.pack(pady=20)
        self.btn_medium.pack(pady=20)
        self.btn_hard.pack(pady=20)
        
        if self.selected_category == "MIXED":
            self.btn_medium.pack_forget()
            self.btn_easy.configure(text="VÂNĂTOARE DE COMORI (UȘOR)", fg_color="transparent", text_color="#00E676", border_color="#00E676", hover_color="#004422")
            self.btn_hard.configure(text="LUMINA PARTAJATĂ (GREU)", fg_color="transparent", text_color="#FF00FF", border_color="#FF00FF", hover_color="#440044")
        else:
            self.btn_easy.configure(text="MOD: UȘOR", fg_color="transparent", text_color="#00E676", border_color="#00E676", hover_color="#004422")
            self.btn_medium.configure(text="MOD: MEDIU", fg_color="transparent", text_color="#00BFFF", border_color="#00BFFF", hover_color="#003344")
            self.btn_hard.configure(text="MOD: GREU", fg_color="transparent", text_color="#FF00FF", border_color="#FF00FF", hover_color="#440044")
        
        self.diff_frame.place(relx=0.5, rely=0.5, anchor="center")

    def select_category(self, cat):
        self.selected_category = cat
        nume_profil = "COPIL" if cat == "CHILD" else "ADULT" if cat == "ADULT" else "COPIL + ADULT"
        self.lbl_diff_subtitle.configure(text=f"PROFIL SELECTAT: {nume_profil}")
        self.show_diff_screen()

    def show_details(self, diff):
        self.selected_difficulty = diff
        self.hide_all()
        
        desc = ""
        title = ""
        
        if self.selected_category == "CHILD":
            if diff == "EASY":
                title = "EXPLORATOR (UȘOR)"
                desc = "• Vizibilitate extinsă (5x5)\n• Integrite la maximum (10 vieți)\n• Traseul luminos rămâne vizibil permanent"
            elif diff == "MEDIUM":
                title = "AVENTURIER (MEDIU)"
                desc = "• Vizibilitate normală (3x3)\n• Integritate medie (5 vieți)\n• Urma luminoasă dispare după 20 de secunde"
            else:
                title = "EROU (GREU)"
                desc = "• Vizibilitate normală (3x3)\n• Integritate critică (3 vieți)\n• Urma luminoasă se șterge rapid (10 secunde)"
        
        elif self.selected_category == "ADULT":
            if diff == "EASY":
                title = "RECRUT (UȘOR)"
                desc = "• Vizibilitate extinsă (5x5)\n• 5 vieți disponibile\n• Urma luminoasă dispare după 25 de secunde"
            elif diff == "MEDIUM":
                title = "VETERAN (MEDIU)"
                desc = "• Vizibilitate normală (3x3)\n• 3 vieți disponibile\n• Urma luminoasă dispare după 15 secunde"
            else:
                title = "FANTOMĂ (GREU)"
                desc = "• Vizibilitate normală (3x3)\n• O SINGURĂ VIAȚĂ. Orice greșeală e fatală.\n• Mod Furișare: Nu rămâne nicio urmă în spate."

        elif self.selected_category == "MIXED":
            if diff == "EASY":
                title = "VÂNĂTOAREA DE COMORI"
                desc = "COPILUL ARE O HARTĂ A LABIRINTULUI!\nCOPILUL VA JUCA CU CULOAREA CYAN!\n\n• Copilul vede pereții slab luminați și are 10 vieți.\n• Părintele are 5 vieți și trebuie să urmeze traseul copilului."
            else:
                self.selected_difficulty = "HARD"
                title = "LUMINA PARTAJATĂ"
                desc = "PĂRINTELE ESTE LANTERNA!\nCOPILUL VA JUCA PE CULOAREA CYAN! \n\n• Când părintele lovește un zid, harta copilului se aprinde 3s.\n• Părintele are 3 vieți și nu lasă urme.\n• Copilul are 5 vieți."

        self.lbl_det_title.configure(text=title)
        self.lbl_det_desc.configure(text=desc)
        self.details_frame.place(relx=0.5, rely=0.5, anchor="center")

    def animate_loading(self, value):
        """Umple bara de progres și revine"""
        self.progress_bar.set(value)
        if value < 1.0:
            self.after(40, self.animate_loading, value + 0.05)
        else:
            self.show_category_screen()
            self.progress_bar.set(0)

    def start_game(self):
        msg = {"cmd": "START_GAME", "difficulty": self.selected_difficulty, "category": self.selected_category}
        try:
            self.sock.sendto(json.dumps(msg).encode(), self.game_addr)
        except:
            pass
            
        self.hide_all()
        self.load_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.animate_loading(0.0)

if __name__ == "__main__":
    app = TouchTerm()
    app.mainloop()