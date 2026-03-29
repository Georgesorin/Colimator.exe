import subprocess
import time
import sys
import os

def start_system():
    print("🚀 INITIALIZARE SISTEM LABIRINT E-SPORTS 🚀")
    print("---------------------------------------------")

    # Aflăm folderul EXACT în care se află launch.py (adică folderul Labirinth)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    procese = []

    try:
        # Folosim parametrul cwd=BASE_DIR pentru a forța deschiderea în folderul corect
        print("[1/3] Pornire Motor Principal (fog_run.py)...")
        p_main = subprocess.Popen([sys.executable, "fog_run.py"], cwd=BASE_DIR)
        procese.append(p_main)
        
        time.sleep(1)

        print("[2/3] Pornire Live Scoreboard (live_monitor.py)...")
        p_score = subprocess.Popen([sys.executable, "live_monitor.py"], cwd=BASE_DIR)
        procese.append(p_score)

        print("[3/3] Pornire Terminal Configurare (entry_terminal.py)...")
        p_term = subprocess.Popen([sys.executable, "entry_terminal.py"], cwd=BASE_DIR)
        procese.append(p_term)

        print("\n✅ TOATE SISTEMELE SUNT ONLINE!")
        print("Apasă CTRL+C în această consolă pentru a închide tot.")

        for p in procese:
            p.wait()

    except KeyboardInterrupt:
        print("\n🛑 Se închid toate sistemele...")
        for p in procese:
            p.terminate()
        print("Sistem oprit cu succes.")

if __name__ == "__main__":
    start_system()