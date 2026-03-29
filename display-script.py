import tkinter as tk
from tkinter import ttk, messagebox
import screeninfo

class MonitorApp:
    def _init_(self, root):
        self.root = root
        self.root.title("Monitor Configurator")
       
        try:
            self.monitors = screeninfo.get_monitors()
        except Exception as e:
            messagebox.showerror("Error", f"Could not detect monitors: {e}")
            self.monitors = []
           
        self.monitor_entries = []
       
        row = 0
        ttk.Label(root, text="Step 1: Assign a letter or number to your monitors").grid(row=row, column=0, columnspan=2, pady=(10, 5), padx=10)
        row += 1
       
        for i, m in enumerate(self.monitors):
            monitor_name = getattr(m, 'name', f'Monitor {i}')
            text = f"{monitor_name} ({m.width}x{m.height}): "
            ttk.Label(root, text=text).grid(row=row, column=0, padx=10, pady=2, sticky="e")
            entry = ttk.Entry(root, width=8)
            entry.grid(row=row, column=1, padx=10, pady=2, sticky="w")
            self.monitor_entries.append((m, entry))
            row += 1
           
        ttk.Separator(root, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=10)
        row += 1
       
        ttk.Label(root, text="Step 2: Start 2 Windows").grid(row=row, column=0, columnspan=2, pady=(0, 5))
        row += 1
       
        ttk.Label(root, text="Target Monitor ID for Window 1:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        self.target_entry_1 = ttk.Entry(root, width=8)
        self.target_entry_1.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1

        ttk.Label(root, text="Target Monitor ID for Window 2:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        self.target_entry_2 = ttk.Entry(root, width=8)
        self.target_entry_2.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1
       
        ttk.Button(root, text="Start", command=self.start_windows).grid(row=row, column=0, columnspan=2, pady=15)
       
    def get_monitor_by_id(self, target_id):
        if not target_id: return None
        for m, entry in self.monitor_entries:
            if entry.get().strip() == target_id:
                return m
        return None

    def start_windows(self):
        id1 = self.target_entry_1.get().strip()
        id2 = self.target_entry_2.get().strip()
       
        m1 = self.get_monitor_by_id(id1) if id1 else None
        m2 = self.get_monitor_by_id(id2) if id2 else None

        if id1 and not m1:
            messagebox.showerror("Error", f"No monitor found with ID '{id1}'.")
            return
        if id2 and not m2:
            messagebox.showerror("Error", f"No monitor found with ID '{id2}'.")
            return
           
        if not m1 and not m2:
            messagebox.showinfo("Info", "Please enter at least one target ID.")
            return
           
        if m1:
            self.open_fullscreen_window(m1, "Window 1", "#2c3e50")
        if m2:
            self.open_fullscreen_window(m2, "Window 2", "#2980b9")

    def open_fullscreen_window(self, monitor, title, bg_color):
        top = tk.Toplevel(self.root)
        top.title(title)
       
        top.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")
        top.configure(bg=bg_color)
        top.overrideredirect(True)
        top.lift()
       
        top.bind("<Escape>", lambda e: top.destroy())
       
        lbl = tk.Label(top, text=f"{title}\nPress Escape to close", font=("Arial", 36), bg=bg_color, fg="white")
        lbl.pack(expand=True)

if _name_ == "_main_":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
       
    root = tk.Tk()
    app = MonitorApp(root)
    root.mainloop()
