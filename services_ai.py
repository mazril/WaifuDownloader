# services_ai.py
# -*- coding: utf-8 -*-
import requests
import json
import re
import logging
import time

import config_handler
import db_manager

logger = logging.getLogger("ai_worker.services_ai")

ollama_connection_ok = False

def initialize_ai_model():
    """
    Sprawdza połączenie z serwerem Ollama, używając adresu z config.json.
    Opis: Bez zmian w tej funkcji.
    """
    global ollama_connection_ok
    
    config_handler.load_config()
    ollama_base_url = config_handler.current_config['ai_settings']['api_base_url']['value']
    
    logger.info(f"Sprawdzanie połączenia z Ollama ({ollama_base_url})...")
    try:
        response_tags = requests.get(f"{ollama_base_url}/api/tags", timeout=5)
        if response_tags.status_code == 200:
            logger.info(f"Połączenie z serwerem Ollama ({ollama_base_url}) OK (sprawdzono /api/tags).")
            ollama_connection_ok = True
            return True
        else:
            logger.error(f"Serwer Ollama pod adresem {ollama_base_url} zwrócił status {response_tags.status_code} dla /api/tags.")
            ollama_connection_ok = False
            return False
    except requests.exceptions.Timeout:
        logger.error(f"Timeout podczas próby połączenia z Ollama: {ollama_base_url}.")
        ollama_connection_ok = False
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Błąd połączenia z Ollama ({ollama_base_url}): {e}.")
        ollama_connection_ok = False
        return False
    except Exception as e_init:
        logger.error(f"Nieoczekiwany błąd podczas inicjalizacji AI (Ollama): {e_init}", exc_info=True)
        ollama_connection_ok = False
        return False

def get_ai_prompt_config(config_id="production"):
    """
    Pobiera konfigurację promptu AI z bazy danych.
    Opis: Bez zmian w tej funkcji.
    """
    logger.debug(f"Pobieranie konfiguracji promptu AI dla ID: '{config_id}'")
    try:
        config_data = db_manager.get_ai_prompt_config_from_db(config_id)
        if config_data:
            logger.debug(f"Pobrano konfigurację dla '{config_id}'.")
            return config_data
        else:
            logger.error(f"Nie udało się pobrać konfiguracji AI dla ID: '{config_id}' (nawet po fallbacku).")
            return None
    except Exception as e:
        logger.error(f"Błąd podczas pobierania konfiguracji AI '{config_id}' z DB: {e}", exc_info=True)
        return None

def extract_gallery_name_ollama(text_to_process, negative_prompts_list=None, structured_hints_input=None, prompt_config_id="production", context_description=None):
    """
    Wysyła zapytanie do modelu Ollama, używając konfiguracji z DB i config.json.
    Opis: Funkcja została zaktualizowana, aby przyjmować dodatkowy parametr 'context_description'.
          Jeśli ten parametr jest dostępny, jego zawartość jest dodawana do promptu dla AI.
    Wpływ na inne funkcje: Umożliwia przekazanie dodatkowego kontekstu (opisu galerii)
                           do modelu językowego, co powinno poprawić jakość generowanych tytułów.
    """
    global ollama_connection_ok
    if not ollama_connection_ok:
        logger.warning("Próba użycia AI (Ollama), ale flaga ollama_connection_ok jest False.")
        return f"Błąd: Brak połączenia z AI (Ollama - flaga: {ollama_connection_ok})"

    config_handler.load_config()
    ai_settings = config_handler.current_config['ai_settings']
    ollama_api_base_url = ai_settings['api_base_url']['value']
    default_model_name_from_config = ai_settings['default_model_name']['value']

    prompt_config = get_ai_prompt_config(prompt_config_id)
    if not prompt_config:
        logger.error(f"Nie można załadować konfiguracji promptu AI '{prompt_config_id}' dla tekstu: '{text_to_process[:50]}...'")
        return f"Błąd: Brak konfiguracji promptu AI '{prompt_config_id}'"

    system_prompt_content = prompt_config.get("system_prompt", "Please provide a concise and relevant gallery title.")
    ollama_model_to_use = prompt_config.get("ollama_model_name") or default_model_name_from_config
    if not ollama_model_to_use:
        logger.error(f"Nie zdefiniowano modelu Ollama ani w konfiguracji promptu '{prompt_config_id}', ani w config.json.")
        return f"Błąd: Model Ollama nie jest zdefiniowany dla promptu '{prompt_config_id}'"

    temperature = prompt_config.get("ollama_temperature", 0.2)
    num_predict = prompt_config.get("ollama_num_predict", 60)
    top_p = prompt_config.get("ollama_top_p", 0.8)

    logger.info(f"Używam konfiguracji promptu AI: '{prompt_config_id}' (Model: {ollama_model_to_use}, Temp: {temperature}, NumPredict: {num_predict}, TopP: {top_p})")

    model_name_to_avoid = ""
    if negative_prompts_list and isinstance(negative_prompts_list, list) and len(negative_prompts_list) > 0:
        model_name_to_avoid = negative_prompts_list[0].strip() if negative_prompts_list[0] else ""

    character_hint_val = structured_hints_input.get("character_hint") if structured_hints_input else None
    series_hint_val = structured_hints_input.get("series_hint") if structured_hints_input else None
    
    # Budowanie promptu użytkownika
    user_prompt_content = f"Text: \"{text_to_process}\"\n"
    if context_description:
        user_prompt_content += f"Contextual Description: {context_description}\n"
    if model_name_to_avoid:
        user_prompt_content += f"Forbidden Model Name: {model_name_to_avoid}\n"
    if character_hint_val:
        user_prompt_content += f"Character Hint: {character_hint_val}\n"
    if series_hint_val:
        user_prompt_content += f"Series Hint: {series_hint_val}\n"
    user_prompt_content += "Desired Gallery Title:"

    final_prompt_for_ollama = f"{system_prompt_content}\n\n{user_prompt_content}"
    logger.debug(f"Pełny prompt dla Ollama (Config: {prompt_config_id}):\n{final_prompt_for_ollama}")

    payload = {
        "model": ollama_model_to_use,
        "prompt": final_prompt_for_ollama,
        "stream": False,
        "options": {
            "temperature": float(temperature),
            "num_predict": int(num_predict),
            "top_p": float(top_p),
            "stop": ["\n", "User:", "System:"]
        }
    }

    try:
        logger.debug(f"Wysyłanie żądania do Ollama API: {ollama_api_base_url}/api/generate z modelem '{ollama_model_to_use}'")
        response = requests.post(f"{ollama_api_base_url}/api/generate", json=payload, timeout=90)
        
        logger.debug(f"Ollama API ({ollama_model_to_use}) status odpowiedzi: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"Ollama API ({ollama_model_to_use}) zwróciło błąd {response.status_code}. Odpowiedź: {response.text[:500]}")
            return f"Błąd: Ollama API error {response.status_code} (model: {ollama_model_to_use})"
        
        result = response.json()
        ai_title = result.get("response", "").strip()
        
        logger.info(f"Surowa odpowiedź z Ollama ({ollama_model_to_use}, cfg: {prompt_config_id}): '{ai_title}'")
        
        if not ai_title:
             logger.warning(f"Ollama ({ollama_model_to_use}, cfg: {prompt_config_id}) zwróciło pusty tytuł dla tekstu: '{text_to_process[:50]}...'")
             return f"Błąd: AI (cfg: {prompt_config_id}) pusty tytuł"

        return ai_title

    except requests.exceptions.Timeout:
        logger.error(f"Timeout ({payload.get('timeout', 90)}s) podczas komunikacji z Ollama API dla modelu '{ollama_model_to_use}'.")
        return f"Błąd: Timeout AI (Ollama, cfg: {prompt_config_id})"
    except requests.exceptions.RequestException as e:
        logger.error(f"Błąd komunikacji z Ollama API (model: {ollama_model_to_use}): {e}", exc_info=False)
        return f"Błąd: Komunikacja AI (Ollama, cfg: {prompt_config_id}, err: {str(e)[:50]})"
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd podczas generowania tytułu przez Ollama (model: {ollama_model_to_use}): {e}", exc_info=True)
        return f"Błąd: Generowanie AI (Ollama, cfg: {prompt_config_id})"

def post_process_ai_title(raw_title_from_ai, model_name_to_avoid_in_title=None):
    """
    Przetwarza surowy tekst odpowiedzi AI, aby uzyskać czysty tytuł galerii.
    Opis: Bez zmian w tej funkcji.
    """
    if not raw_title_from_ai or "Błąd:" in raw_title_from_ai:
        logger.warning(f"Otrzymano pusty lub błędny surowy tytuł od AI do post-processingu: '{raw_title_from_ai}'. Zwracam pusty string.")
        return ""
    
    cleaned_title = re.sub(r"^\s*(here is a possible title|a good title could be|title suggestion|gallery title|title|tytuł|Desired Gallery Title)\s*[:\-]\s*", "", raw_title_from_ai, flags=re.IGNORECASE).strip()
    cleaned_title = cleaned_title.strip('"').strip("'")

    cleaned_title = re.sub(r"\s*[-\u2013\u2014]\s*\d+\s*(photos|images|pics|pictures|zdjęć|obrazków|fotografii|sets|vids|videos|файлов|枚|枚の写真)\s*$", "", cleaned_title, flags=re.IGNORECASE).strip()
    cleaned_title = re.sub(r"\s+by\s+[\w\s.'-]+$", "", cleaned_title, flags=re.IGNORECASE).strip()
    cleaned_title = re.sub(r"\s*\(\s*\d+\s*(photos|images|pics|pictures|zdjęć|obrazków|fotografii|sets|vids|videos)\s*\)\s*$", "", cleaned_title, flags=re.IGNORECASE).strip()

    stop_phrases = [
        "N/A", "Exclusive Set", "Onlyfans", "Patreon", "Fansly", "Leaks", "Leaked", "Cosplay",
        "Model:", "Character:", "Series:", "Original Character", "Original", "OC",
        "Photo Set", "Image Set", "Gallery", "Photoshoot", "Video", "Videos", "Set",
        "AI Generated Title", "Suggested Title"
    ]
    for phrase in stop_phrases:
        cleaned_title = re.sub(r"(^|\s|[\-_(])\s*" + re.escape(phrase) + r"\s*($|\s|[\-_):])", r"\1\2", cleaned_title, flags=re.IGNORECASE).strip()
        cleaned_title = re.sub(r"^\s*" + re.escape(phrase) + r"\s*[:\-]?\s*", "", cleaned_title, flags=re.IGNORECASE).strip()
        cleaned_title = re.sub(r"\s*[:\-]?\s*" + re.escape(phrase) + r"\s*$", "", cleaned_title, flags=re.IGNORECASE).strip()

    cleaned_title = cleaned_title.strip().strip(' -.:,;!?()[]{}<>').strip()
    cleaned_title = re.sub(r'\s*-\s*', ' - ', cleaned_title) 
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip() 

    if model_name_to_avoid_in_title and model_name_to_avoid_in_title.strip():
        pattern = r"\b" + re.escape(model_name_to_avoid_in_title.strip()) + r"\b"
        if re.search(pattern, cleaned_title, re.IGNORECASE):
            logger.warning(f"Tytuł po post-processingu ('{cleaned_title}') zawiera nazwę modelki ('{model_name_to_avoid_in_title}'). Odrzucam tytuł.")
            return ""

    generic_or_prompt_remains = [
        "based on the text", "from the text provided", "a fitting title", "a good title",
        "gallery title for", "title for the gallery", "here's a title", "text analysis",
        "untitled", "no title", "image gallery"
    ]
    for generic_phrase in generic_or_prompt_remains:
        if generic_phrase.lower() in cleaned_title.lower():
            logger.warning(f"Tytuł po post-processingu ('{cleaned_title}') wygląda na zbyt ogólny lub pozostałość promptu. Odrzucam. Surowy: '{raw_title_from_ai}'")
            return ""

    if len(cleaned_title) < 3:
        logger.warning(f"Tytuł po post-processingu ('{cleaned_title}') jest zbyt krótki (oryginalny AI: '{raw_title_from_ai}'). Zwracam pusty string.")
        return ""

    logger.info(f"Tytuł po post-processingu AI: '{cleaned_title}' (oryginalny surowy AI: '{raw_title_from_ai}')")
    return cleaned_title