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
    
    # Docelowo: model_name powinien być pobierany z config_handler.current_config
    # config_ai_model_name = config_handler.current_config.get('ai', {}).get('model_to_use', {}).get('value', constants.AI_MODEL_TO_USE)
    # model_to_load = model_name if model_name else config_ai_model_name
    model_to_load = model_name if model_name else constants.AI_MODEL_TO_USE


    logger.info(f"Rozpoczynam ładowanie modelu AI: {model_to_load}...")
    try:
        ai_tokenizer = T5Tokenizer.from_pretrained(model_to_load)
        ai_device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"AI będzie używać urządzenia: {ai_device}")
        ai_model = T5ForConditionalGeneration.from_pretrained(model_to_load).to(ai_device)
        ai_model.eval()
        ai_initialized_successfully = True
        logger.info("Model AI załadowany pomyślnie.")
        return True
    except Exception as e:
        logger.error(f"Krytyczny błąd podczas inicjalizacji modelu AI ({model_to_load}): {e}", exc_info=True)
        logger.warning("Funkcjonalność AI będzie niedostępna.")
        ai_tokenizer, ai_model, ai_device, ai_initialized_successfully = None, None, None, False
        return False

def extract_gallery_name_t5(text_to_process, negative_prompts_list=None): # Dodano parametr
    global ai_tokenizer, ai_model, ai_device, ai_initialized_successfully

    if not ai_initialized_successfully or not ai_model or not ai_tokenizer:
        logger.warning("Próba użycia AI, ale model nie jest (lub nie został pomyślnie) zainicjalizowany.")
        return "Błąd: Model AI niedostępny"

    base_prompt = f"""Extract 'Character' and 'Series' from the title. If Series is not obvious or too generic like 'Original', output only 'Character'.
    Example 1: Text: "Victoria Lirell - Princess Zelda - The Legend Of Zelda - 37 photos" Title: Princess Zelda - The Legend Of Zelda
    Example 2: Text: "Shinano by Kokura Chiyo from Azur Lane" Title: Shinano - Azur Lane
    Example 3: Text: "Some Artist - Just A Character - 50 photos" Title: Just A Character
    Example 4: Text: "Cute Girl - Original Character by ArtistX - 22 images" Title: Cute Girl
    Example 5: Text: "My OC Lily - 12 pics" Title: My OC Lily
    Text: "{text_to_process}"
"""
    negative_instruction = ""
    if negative_prompts_list and isinstance(negative_prompts_list, list) and len(negative_prompts_list) > 0:
        terms_to_avoid = ", ".join([f"'{term.strip()}'" for term in negative_prompts_list if term.strip()])
        if terms_to_avoid:
            negative_instruction = f"Important: The generated title MUST NOT include any of these specific names or terms: {terms_to_avoid}.\n"

    final_prompt = base_prompt + negative_instruction + "Title:"

    if negative_instruction:
        logger.debug(f"Używam instrukcji negatywnej: {negative_instruction.strip()}")
    # logger.debug(f"Pełny prompt dla AI (z instrukcją negatywną jeśli jest): {final_prompt}") # Może być zbyt długi do logowania

    try:
        input_ids = ai_tokenizer(final_prompt, return_tensors="pt", max_length=512, truncation=True).input_ids.to(ai_device)
        outputs = ai_model.generate(
            input_ids,
            max_length=60,
            num_beams=4,
            early_stopping=True,
            no_repeat_ngram_size=2
        )
        decoded_output = ai_tokenizer.decode(outputs[0], skip_special_tokens=True)
        logger.debug(f"AI zwróciło surowy tytuł: '{decoded_output}'")
        return decoded_output.strip()
    except Exception as e:
        logger.error(f"Błąd podczas generowania tytułu przez AI: {e}", exc_info=True)
        return "Błąd generowania AI"

def post_process_ai_title(raw_title_from_ai):
    if "Błąd" in raw_title_from_ai:
        return ""

    stop_patterns_regex = [
        r"\s*-\s*\d+\s*(photos|images|pics|zdjęć|obrazków|fotografii).*",
        r"\s*by\s+.*",
        r"\s*from\s+.*",
        r"^\s*(title|Title|tytuł|Tytuł):\s*",
        r"N/A",
        r"^\s*-\s*",
        r"\s*-\s*$",
        r"Exclusive Set",
        r"Onlyfans", r"Patreon", r"Fansly",
        r"Leaks?", r"Leaked",
        r"Cosplay",
    ]

    cleaned_title = raw_title_from_ai
    for pattern in stop_patterns_regex:
        cleaned_title = re.sub(pattern, "", cleaned_title, flags=re.IGNORECASE)

    cleaned_title = cleaned_title.strip().rstrip(' -').strip()

    if len(cleaned_title) < 3:
        logger.debug(f"Tytuł po post-processingu ('{cleaned_title}') jest zbyt krótki. Oryginalny AI: '{raw_title_from_ai}'")
        return ""

    logger.info(f"Tytuł po post-processingu AI: '{cleaned_title}' (oryginalny AI: '{raw_title_from_ai}')")
    return cleaned_title