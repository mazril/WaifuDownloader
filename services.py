# -*- coding: utf-8 -*-
import time
import random
import requests
import subprocess
import sys
import re
import logging
try:
    import torch
    from transformers import T5Tokenizer, T5ForConditionalGeneration
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

import constants
import config_handler
import os

logger = logging.getLogger(__name__)

# --- AI State ---
ai_tokenizer = None
ai_model = None
ai_device = None
ai_initialized_successfully = False

# --- VPN ---
def rotate_vpn(attempts=3):
    logger.info("Rozpoczynam rotację NordVPN...")
    for attempt in range(1, attempts + 1):
        try:
            logger.info(f"Próba rotacji VPN ({attempt}/{attempts})... Odłączam...")
            use_shell = sys.platform == "win32"

            disconnect_process = subprocess.run(
                [constants.NORDVPN_CLI_EXECUTABLE, "--disconnect"],
                capture_output=True, text=True, timeout=60, shell=use_shell, check=False
            )
            if disconnect_process.returncode != 0 and "You are not connected" not in disconnect_process.stderr:
                logger.warning(f"NordVPN disconnect stderr (kod {disconnect_process.returncode}): {disconnect_process.stderr.strip()}")

            time.sleep(random.uniform(3, 7))

            logger.info("Łączę z NordVPN...")
            connect_process = subprocess.run(
                [constants.NORDVPN_CLI_EXECUTABLE, "--connect"],
                capture_output=True, text=True, timeout=120, shell=use_shell, check=True
            )
            if constants.VERBOSE_VPN_LOGGING and connect_process.stdout:
                logger.debug(f"NordVPN connect stdout: {connect_process.stdout.strip()}")
            if connect_process.stderr:
                 logger.warning(f"NordVPN connect stderr: {connect_process.stderr.strip()}")


            logger.info("Połączono. Czekam na stabilizację połączenia (10-15s)...")
            time.sleep(random.uniform(10, 15))

            logger.info("Weryfikuję nowe IP...")
            r = requests.get("https://api.ipify.org?format=json", timeout=20)
            r.raise_for_status()
            new_ip = r.json().get("ip", "Nie udało się odczytać IP")
            logger.info(f"Rotacja VPN zakończona pomyślnie! Nowe IP: {new_ip}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Błąd polecenia NordVPN (próba {attempt}): {e.stderr.strip() if e.stderr else e.stdout.strip()}", exc_info=False)
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout podczas operacji NordVPN (próba {attempt}).")
        except FileNotFoundError:
            logger.critical(f"BŁĄD: Plik wykonywalny '{constants.NORDVPN_CLI_EXECUTABLE}' nie został znaleziony. Nie można zarządzać VPN.")
            return False
        except requests.RequestException as e:
            logger.error(f"Błąd weryfikacji IP po rotacji VPN (próba {attempt}): {e}", exc_info=False)
        except Exception as e:
            logger.error(f"Nieoczekiwany błąd podczas rotacji VPN (próba {attempt}): {e}", exc_info=True)

        if attempt < attempts:
            logger.info(f"Czekam 15s przed następną próbą rotacji VPN...")
            time.sleep(15)

    logger.error("Nie udało się wykonać rotacji VPN po wszystkich próbach.")
    return False

# --- Downloader ---
def download_image(url, dest_filepath):
    if config_handler.current_config is None:
        config_handler.load_config()

    cfg_downloading = config_handler.current_config.get('downloading', {})
    delay_min = cfg_downloading.get('download_delay_min', {}).get('value', 0.5)
    delay_max = cfg_downloading.get('download_delay_max', {}).get('value', 1.5)

    delay = random.uniform(delay_min, delay_max)
    time.sleep(delay)

    if os.path.exists(dest_filepath):
        logger.debug(f"Plik {os.path.basename(dest_filepath)} już istnieje. Pomijam pobieranie.")
        return True

    logger.info(f"Pobieram {os.path.basename(dest_filepath)} z {url} (po {delay:.2f}s)...")
    try:
        headers = {'User-Agent': random.choice(constants.USER_AGENTS)}
        response = requests.get(url, stream=True, headers=headers, timeout=(10, 30))
        response.raise_for_status()
        with open(dest_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.debug(f"Pomyślnie pobrano {os.path.basename(dest_filepath)}.")
        return True
    except requests.exceptions.Timeout:
        logger.error(f"Timeout podczas pobierania {os.path.basename(dest_filepath)} z {url}.")
    except requests.exceptions.RequestException as ex:
        logger.error(f"Błąd żądania podczas pobierania {os.path.basename(dest_filepath)}: {ex}", exc_info=False)
    except Exception as ex_other:
        logger.error(f"Nieoczekiwany błąd podczas pobierania {os.path.basename(dest_filepath)}: {ex_other}", exc_info=True)

    if os.path.exists(dest_filepath):
        try:
            os.remove(dest_filepath)
            logger.info(f"Usunięto niekompletny plik {os.path.basename(dest_filepath)} po błędzie pobierania.")
        except Exception as e_remove:
            logger.warning(f"Nie udało się usunąć niekompletnego pliku {os.path.basename(dest_filepath)}: {e_remove}")
    return False

# --- AI ---
def initialize_ai_model(model_name=None):
    global ai_tokenizer, ai_model, ai_device, ai_initialized_successfully

    if ai_initialized_successfully:
        logger.debug("Model AI jest już zainicjalizowany.")
        return True

    if not TRANSFORMERS_AVAILABLE:
        logger.warning("Biblioteki torch/transformers nie są dostępne. Inicjalizacja modelu AI pominięta.")
        ai_initialized_successfully = False
        return False

    if config_handler.current_config is None: config_handler.load_config()
    
    model_to_load = model_name if model_name else constants.AI_MODEL_TO_USE # Z constants

    logger.info(f"Rozpoczynam ładowanie modelu AI: {model_to_load}...")
    try:
        ai_tokenizer = T5Tokenizer.from_pretrained(model_to_load)
        ai_device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"AI będzie używać urządzenia: {ai_device}")
        
        if ai_device == "cuda":
            ai_model = T5ForConditionalGeneration.from_pretrained(model_to_load).to(ai_device)
        else: # Dla CPU, można spróbować załadować w trybie float16 dla mniejszego zużycia RAM, jeśli model to wspiera
            try:
                ai_model = T5ForConditionalGeneration.from_pretrained(model_to_load, torch_dtype=torch.float16).to(ai_device)
                logger.info("Model AI (CPU) załadowany z torch_dtype=torch.float16.")
            except Exception:
                logger.warning("Nie udało się załadować modelu AI (CPU) z float16, próbuję standardowo.")
                ai_model = T5ForConditionalGeneration.from_pretrained(model_to_load).to(ai_device)

        ai_model.eval()
        ai_initialized_successfully = True
        logger.info(f"Model AI '{model_to_load}' załadowany pomyślnie na urządzeniu '{ai_device}'.")
        return True
    except Exception as e:
        logger.error(f"Krytyczny błąd podczas inicjalizacji modelu AI ({model_to_load}): {e}", exc_info=True)
        logger.warning("Funkcjonalność AI będzie niedostępna.")
        ai_tokenizer, ai_model, ai_device, ai_initialized_successfully = None, None, None, False
        return False

def extract_gallery_name_t5(text_to_process, negative_prompts_list=None, positive_hints_list=None): # Dodano positive_hints_list
    global ai_tokenizer, ai_model, ai_device, ai_initialized_successfully

    if not ai_initialized_successfully or not ai_model or not ai_tokenizer:
        logger.warning("Próba użycia AI, ale model nie jest (lub nie został pomyślnie) zainicjalizowany.")
        return "Błąd: Model AI niedostępny"

    # Podstawowy prompt
    base_prompt = f"""Extract 'Character' and 'Series' from the text. If 'Series' is not obvious or too generic like 'Original', output only 'Character'.
Example 1: Text: "Victoria Lirell - Princess Zelda - The Legend Of Zelda - 37 photos" Title: Princess Zelda - The Legend Of Zelda
Example 2: Text: "Shinano by Kokura Chiyo from Azur Lane" Title: Shinano - Azur Lane
Example 3: Text: "Some Artist - Just A Character - 50 photos" Title: Just A Character
Example 4: Text: "Cute Girl - Original Character by ArtistX - 22 images" Title: Cute Girl
Example 5: Text: "My OC Lily - 12 pics" Title: My OC Lily
"""
    # Instrukcja negatywna
    negative_instruction = ""
    if negative_prompts_list and isinstance(negative_prompts_list, list) and len(negative_prompts_list) > 0:
        terms_to_avoid = ", ".join([f"'{term.strip()}'" for term in negative_prompts_list if term.strip()])
        if terms_to_avoid:
            negative_instruction = f"The generated title MUST NOT include any of these specific names or terms: {terms_to_avoid}.\n"

    # Instrukcja pozytywna (wskazówki)
    positive_instruction = ""
    if positive_hints_list and isinstance(positive_hints_list, list) and len(positive_hints_list) > 0:
        preferred_terms = ", ".join([f"'{term.strip()}'" for term in positive_hints_list if term.strip()])
        if preferred_terms:
            positive_instruction = f"If possible and relevant, try to include terms like: {preferred_terms} in the title.\n"

    # Składanie finalnego promptu
    # Ważne: text_to_process powinien być ostatnim elementem przed "Title:"
    final_prompt = base_prompt + positive_instruction + negative_instruction + f'Text: "{text_to_process}"\nTitle:'


    if positive_instruction: logger.debug(f"Używam pozytywnych wskazówek: {positive_instruction.strip()}")
    if negative_instruction: logger.debug(f"Używam instrukcji negatywnej: {negative_instruction.strip()}")
    logger.debug(f"Pełny prompt dla AI:\n{final_prompt}")

    try:
        input_ids = ai_tokenizer(final_prompt, return_tensors="pt", max_length=512, truncation=True).input_ids.to(ai_device)
        outputs = ai_model.generate(
            input_ids,
            max_length=60,          # Maksymalna długość generowanego tekstu
            num_beams=5,            # Zwiększenie liczby wiązek może dać lepsze wyniki, ale jest wolniejsze
            early_stopping=True,
            no_repeat_ngram_size=2, # Unikanie powtarzania tych samych n-gramów
            temperature=0.7,        # Można eksperymentować, niższa = bardziej deterministyczne
            top_k=50,               # Ograniczenie do top_k tokenów przy próbkowaniu
            top_p=0.95              # Ograniczenie do top_p przy próbkowaniu (nucleus sampling)
        )
        decoded_output = ai_tokenizer.decode(outputs[0], skip_special_tokens=True)
        logger.debug(f"AI zwróciło surowy tytuł: '{decoded_output}'")
        return decoded_output.strip()
    except Exception as e:
        logger.error(f"Błąd podczas generowania tytułu przez AI: {e}", exc_info=True)
        return "Błąd generowania AI"

def post_process_ai_title(raw_title_from_ai):
    if "Błąd" in raw_title_from_ai or not raw_title_from_ai:
        return ""

    # Usuń początkowe "Title: " jeśli model to zwrócił
    cleaned_title = re.sub(r"^\s*(title|Title|tytuł|Tytuł)\s*:\s*", "", raw_title_from_ai, flags=re.IGNORECASE)
    
    # Usuń frazy typu "- X photos", "by Artist", "from Series" na końcu
    # To jest trudniejsze do zrobienia idealnie uniwersalnie, ale spróbujmy kilka wzorców
    # Najpierw usuń część z liczbą zdjęć/obrazków itp.
    cleaned_title = re.sub(r"\s*-\s*\d+\s*(photos|images|pics|zdjęć|obrazków|fotografii|sets|vids|videos|файлов)\s*$", "", cleaned_title, flags=re.IGNORECASE)
    # Usuń "by [Nazwa Artysty]" na końcu
    cleaned_title = re.sub(r"\s+by\s+[\w\s.-]+$", "", cleaned_title, flags=re.IGNORECASE)
    # Usuń "from [Nazwa Serii]" na końcu, jeśli seria nie jest częścią nazwy postaci (trudne)
    # Na razie zostawmy to, bo seria jest często ważna.
    # Można dodać bardziej specyficzne reguły, jeśli zauważysz powtarzające się niechciane wzorce.

    # Ogólne czyszczenie
    stop_phrases = [
        "N/A", "Exclusive Set", "Onlyfans", "Patreon", "Fansly", "Leaks", "Leaked", "Cosplay",
        "Model:", "Character:", "Series:", "Original Character", "Original", "OC" # Usuwamy te ogólniki, jeśli AI je dodało
    ]
    for phrase in stop_phrases:
        cleaned_title = re.sub(r"(^|\s|-)" + re.escape(phrase) + r"($|\s|-)", r"\1\2", cleaned_title, flags=re.IGNORECASE)


    # Usuń nadmiarowe białe znaki i myślniki
    cleaned_title = cleaned_title.strip().strip(' -').strip()
    cleaned_title = re.sub(r'\s*-\s*', ' - ', cleaned_title) # Ujednolić spacje wokół myślników
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()


    # Jeśli tytuł stał się zbyt krótki lub pusty po czyszczeniu
    if len(cleaned_title) < 3:
        logger.debug(f"Tytuł po post-processingu ('{cleaned_title}') jest zbyt krótki. Oryginalny AI: '{raw_title_from_ai}' -> Używam oryginalnego przed post-processingiem, jeśli jest dłuższy.")
        # Wróć do wersji przed agresywnym czyszczeniem jeśli była lepsza
        if len(raw_title_from_ai.replace("Title:","").strip()) >= 3:
            # Mniej agresywne czyszczenie dla raw_title
            raw_cleaned = re.sub(r"^\s*(title|Title|tytuł|Tytuł)\s*:\s*", "", raw_title_from_ai, flags=re.IGNORECASE).strip()
            raw_cleaned = re.sub(r"\s*-\s*\d+\s*(photos|images|pics|zdjęć|obrazków|fotografii|sets|vids|videos|файлов)\s*$", "", raw_cleaned, flags=re.IGNORECASE).strip()
            if len(raw_cleaned) >=3 : return raw_cleaned

        return "" # Jeśli nawet surowy był zły

    logger.info(f"Tytuł po post-processingu AI: '{cleaned_title}' (oryginalny AI: '{raw_title_from_ai}')")
    return cleaned_title