# -*- coding: utf-8 -*-
import re
import sys
import time
import selectors
from urllib.parse import urlparse, unquote

def sanitize_foldername(name):
    if not name: return "Nienazwana_Galeria"
    name = str(name).strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', name) # Usuń niedozwolone znaki
    name = re.sub(r'\s+', ' ', name) # Zastąp wielokrotne spacje pojedynczą
    name = re.sub(r'_+', '_', name) # Zastąp wielokrotne _ pojedynczym
    name = re.sub(r'-+', '-', name) # Zastąp wielokrotne - pojedynczym
    name = name.strip(' _-.') # Usuń znaki z początku/końca
    # Skróć, jeśli zbyt długie, ale upewnij się, że nie jest puste
    return name[:150] if len(name) > 150 else (name if name else "Nienazwana_Galeria")

def get_gallery_id(url):
    try:
        path = urlparse(url).path
        # Pobierz ostatni segment ścieżki i odkoduj go
        return unquote(path.strip('/').split('/')[-1])
    except Exception as e:
        print(f"⚠️ Nie można pobrać ID galerii z URL '{url}': {e}")
        # Jako fallback, spróbuj użyć hasha lub losowej wartości? Lepiej zwrócić coś identyfikowalnego.
        return f"error_id_{int(time.time())}"

def wait_for_key_press_or_timeout(timeout_seconds=5):
    print(f"\nNaciśnij ENTER w ciągu {timeout_seconds}s, aby wyświetlić MENU GŁÓWNE.")
    print("W przeciwnym razie skrypt spróbuje automatycznie wznowić ostatnią operację.")
    
    if sys.platform != "win32": # selectors działa lepiej na Linux/macOS
        sel = selectors.DefaultSelector()
        sel.register(sys.stdin, selectors.EVENT_READ)
        
        for i in range(timeout_seconds, 0, -1):
            sys.stdout.write(f"\rAutomatyczne wznowienie za: {i}s... ")
            sys.stdout.flush()
            events = sel.select(timeout=1) 
            if events:
                try:
                    _ = sys.stdin.readline() 
                    sys.stdout.write("\rKlawisz naciśnięty. Wyświetlam menu...        \n")
                    sys.stdout.flush()
                    return True
                except Exception: # Na wypadek problemów ze stdin
                    sys.stdout.write("\rProblem z odczytem klawisza. Wyświetlam menu...\n")
                    return True
        sys.stdout.write("\rCzas minął. Próbuję wznowić operację...       \n")
        sys.stdout.flush()
        return False
    else: # Prostsze, blokujące odliczanie dla Windows
        for i in range(timeout_seconds, 0, -1):
            print(f"\rAutomatyczne wznowienie za: {i}s (Naciśnij Ctrl+C aby przerwać i wymusić menu)... ", end="")
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                 sys.stdout.write("\rCtrl+C naciśnięte. Wyświetlam menu...\n")
                 return True
        print("\rCzas minął. Próbuję wznowić operację...                     ")
        return False