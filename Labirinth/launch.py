import subprocess
import time
import sys

def start_system():
    print("🚀 INITIALIZARE SISTEM LABIRINT E-SPORTS 🚀")
    print("---------------------------------------------")

    procese = []

    try:
        # 1. Pornim motorul jocului (trebuie să pornească primul pentru a deschide porturile)
        print("[1/3] Pornire Motor Principal (fog_run.py)...")
        p_main = subprocess.Popen([sys.executable, "fog_run.py"])
        procese.append(p_main)
        
        # Așteptăm 1 secundă să fim siguri că s-au deschis socket-urile UDP
        time.sleep(1)

        # 2. Pornim Scoreboard-ul
        print("[2/3] Pornire Live Scoreboard (live_monitor.py)...")
        p_score = subprocess.Popen([sys.executable, "live_monitor.py"])
        procese.append(p_score)

        # 3. Pornim Terminalul de Comandă
        print("[3/3] Pornire Terminal Configurare (entry_terminal.py)...")
        p_term = subprocess.Popen([sys.executable, "entry_terminal.py"])
        procese.append(p_term)

        print("\n✅ TOATE SISTEMELE SUNT ONLINE!")
        print("Apasă CTRL+C în această consolă pentru a închide tot.")

        # Menținem launcher-ul deschis până când închizi programele
        for p in procese:
            p.wait()

    except KeyboardInterrupt:
        print("\n🛑 Se închid toate sistemele...")
        for p in procese:
            p.terminate()
        print("Sistem oprit cu succes.")

if __name__ == "__main__":
    start_system()