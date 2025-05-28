# -*- coding: utf-8 -*-
import re
import sys
import time
import selectors
from urllib.parse import urlparse, unquote
import logging # <-- Dodano

logger = logging.getLogger(__name__) # <-- Dodano

def sanitize_foldername(name):
    if not name: 
        logger.debug("sanitize_foldername otrzymał pustą nazwę, zwracam 'Nienazwana_Galeria'")
        return "Nienazwana_Galeria"
    
    name = str(name).strip()
    # Zastąp znaki specjalne, które są problematyczne w nazwach folderów/plików
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F\t\n\r\f\v]', '_', name) 
    name = re.sub(r'\s+', ' ', name) 
    name = name.strip() # Usuń białe znaki z początku i końca po zamianach
    
    # Zastąp wielokrotne wystąpienia _ lub - pojedynczymi, ale tylko jeśli nie są jedynymi znakami
    if len(name) > 1:
        name = re.sub(r'_+', '_', name) 
        name = re.sub(r'-+', '-', name) 
    
    name = name.strip(' _-.') # Usuń znaki z początku/końca, które mogły powstać

    # Skróć, jeśli zbyt długie, ale upewnij się, że nie jest puste
    max_len = 150 # Maksymalna długość nazwy folderu (można dostosować)
    if len(name) > max_len:
        logger.debug(f"Nazwa folderu '{name}' skrócona do {max_len} znaków.")
        name = name[:max_len].strip(' _-.') # Ponownie usuń znaki z końca po skróceniu
        
    final_name = name if name else "Nienazwana_Galeria"
    # logger.debug(f"Sanitize foldername: original='{original_name_for_log}', sanitized='{final_name}'") # original_name_for_log nie jest przekazywane
    return final_name


def get_gallery_id(url):
    if not url or not isinstance(url, str):
        logger.warning(f"Nieprawidłowy URL przekazany do get_gallery_id: {url}")
        return f"error_invalid_url_{int(time.time())}"
    try:
        path = urlparse(url).path
        # Pobierz ostatni segment ścieżki i odkoduj go
        gallery_id_str = unquote(path.strip('/').split('/')[-1])
        # Dodatkowe czyszczenie, jeśli ID zawiera np. rozszerzenie pliku (choć nie powinno z URL galerii)
        gallery_id_str = gallery_id_str.split('.')[0] if '.' in gallery_id_str else gallery_id_str
        if not gallery_id_str: # Jeśli po czyszczeniu ID jest puste
            logger.warning(f"Nie udało się wyekstrahować ID galerii z URL '{url}', ostatni segment pusty.")
            return f"error_empty_id_{int(time.time())}"
        return gallery_id_str
    except Exception as e:
        logger.error(f"Nie można pobrać ID galerii z URL '{url}': {e}", exc_info=False)
        return f"error_parsing_id_{int(time.time())}"

def wait_for_key_press_or_timeout(timeout_seconds=5):
    # Ten print jest bezpośrednią interakcją z użytkownikiem, może zostać
    print(f"\nNaciśnij ENTER w ciągu {timeout_seconds}s, aby wyświetlić MENU GŁÓWNE.")
    print("W przeciwnym razie skrypt spróbuje automatycznie wznowić ostatnią operację.")
    logger.info(f"Oczekiwanie na klawisz (timeout: {timeout_seconds}s)...")
    
    start_time = time.monotonic()
    if sys.platform != "win32": 
        sel = selectors.DefaultSelector()
        sel.register(sys.stdin, selectors.EVENT_READ)
        
        while time.monotonic() - start_time < timeout_seconds:
            remaining_time = timeout_seconds - (time.monotonic() - start_time)
            sys.stdout.write(f"\rAutomatyczne wznowienie za: {int(round(remaining_time))}s... ")
            sys.stdout.flush()
            
            # Sprawdź, czy są dane do odczytania, z timeoutem 0.1s, aby pętla mogła iterować
            events = sel.select(timeout=0.1) 
            if events:
                try:
                    _ = sys.stdin.readline() 
                    sys.stdout.write("\rKlawisz naciśnięty. Wyświetlam menu...        \n")
                    sys.stdout.flush()
                    logger.info("Klawisz naciśnięty przez użytkownika.")
                    return True
                except Exception as e_read: 
                    logger.warning(f"Problem z odczytem klawisza: {e_read}. Wyświetlam menu.")
                    sys.stdout.write("\rProblem z odczytem klawisza. Wyświetlam menu...\n")
                    return True # Traktuj błąd odczytu jak naciśnięcie klawisza (bezpieczniej)
            if remaining_time <= 0.1: break # Wyjdź jeśli czas prawie minął
        
        # Po pętli (timeout)
        sys.stdout.write("\rCzas minął. Próbuję wznowić operację...       \n")
        sys.stdout.flush()
        logger.info("Czas na naciśnięcie klawisza minął.")
        return False
    else: # Prostsze, blokujące odliczanie dla Windows (selectors może tu gorzej działać)
        for i in range(timeout_seconds, 0, -1):
            # Ten print jest dynamiczny, nie ma sensu go logować w tej formie
            print(f"\rAutomatyczne wznowienie za: {i}s (Naciśnij Ctrl+C aby przerwać i wymusić menu)... ", end="")
            try:
                time.sleep(1)
                # Sprawdzenie, czy coś jest w buforze wejścia (bardzo uproszczone dla Windows)
                # To nie jest idealne, ale może złapać szybkie naciśnięcie Enter
                # import msvcrt
                # if msvcrt.kbhit() and msvcrt.getwche() == '\r':
                #     sys.stdout.write("\rKlawisz Enter naciśnięty (Windows). Wyświetlam menu...\n")
                #     logger.info("Klawisz Enter naciśnięty przez użytkownika (Windows).")
                #     return True
            except KeyboardInterrupt: # Ctrl+C przechwycone przez główny handler, ale też tutaj
                 sys.stdout.write("\rCtrl+C naciśnięte. Wyświetlam menu...\n")
                 logger.info("Ctrl+C naciśnięte podczas odliczania (Windows).")
                 return True # Wymuś menu
        print("\rCzas minął. Próbuję wznowić operację...                     ")
        logger.info("Czas na naciśnięcie klawisza minął (Windows).")
        return False