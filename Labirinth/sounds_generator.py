import asyncio
import edge_tts
import os

# Definim frazele și numele fișierelor
# Vocea "ro-RO-AlinaNeural" este una dintre cele mai bune voci feminine în română
VOICE = "ro-RO-EmilNeural" 

dialoguri = {
    "start": "Jocul începe, pregătește-te, dar hai mai întâi să ne uităm la un tutorial",
    "scope": "Scopul jocului este să ajungi la finalul labirintului primul, dar să nu rămâi fără vieți",
    "tutorial_wrong_step": "Dacă atingi un pătrat verde pierzi o viață și trebuie să stai pe loc să nu te miști",
    "tutorial_blue_step": "Dacă atingi un pătrat albastru, o să vezi tot labirintul pentru câteva secunde",
    "how_to_win": "Primul jucător care câștigă 5 runde, va câștiga jocul",
    "blue_wins": "Bravo, jucatorul albastru a ajuns primul la finalul labirintului",
    "red_wins": "Bravo, jucatorul roșu a ajuns primul la finalul labirintului",
    "blue_jumps_to_end": "HaaaHaaaHaaa, ai vrut să trișezi jucătorule albastru, pentru asta, jucătorul roșu a câștigat",
    "red_jumps_to_end": "HaaaHaaaHaaa, ai vrut să trișezi jucătorule roșu, pentru asta, jucătorul albastru a câștigat",
    "blue_jumps": "Eeeeeheee, ai vrut să păcălești jocul, jucătorule albastru, acum trebuie să o iei de la început pe un nou labirint",
    "red_jumps": "Eeeeheeee, ai vrut să păcălești jocul, jucătorule roșu, acum trebuie să o iei de la început pe un nou labirint",
    "pause": "Este timpul pentru o mică pauză",
    "get_ready": "Atenție, jocul începe în 3, 2,1 și",
    "blue_won": "Felicitări, jucătorul albastru a căștigat, bravo amândurora",
    "red_won": "Felicitări, jucătorul roșu a căștigat, bravo amândurora",
    "choose_color": "Alege o culoare și apoi mergi la pătratul colorat pentru a începe jocul",
    "lovitura": "Atenție! Ai lovit un perete."
}

async def genereaza_tot():
    if not os.path.exists("sounds"):
        os.mkdir("sounds")

    # 1. Generează dialogurile fixe
    for nume, text in dialoguri.items():
        print(f"Generez: {nume}.mp3")
        await edge_tts.Communicate(text, VOICE).save(f"sounds/{nume}.mp3")

    # 2. Generează toate combinațiile de scor (până la 5)
    print("\nGenerare combinații scor...")
    for s1 in range(6): # De la 0 la 5
        for s2 in range(6):
            nume_fisier = f"scor_{s1}_{s2}"
            text_scor = f"Noul scor este: {s1} la {s2}"
            print(f"Generez: {nume_fisier}.mp3")
            await edge_tts.Communicate(text_scor, VOICE).save(f"sounds/{nume_fisier}.mp3")

    print("\nGATA!")

if __name__ == "__main__":
    asyncio.run(genereaza_tot())