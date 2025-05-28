# -*- coding: utf-8 -*-
# testai.py
import re
import logging
import sys
import os

# --- Globalny Stan AI i Stałe ---
AI_MODEL_TO_USE = "google/flan-t5-large"
ai_tokenizer = None
ai_model = None
ai_device = None
ai_initialized_successfully = False
TRANSFORMERS_AVAILABLE = False

try:
    import torch
    from transformers import T5Tokenizer, T5ForConditionalGeneration
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    print("UWAGA: Biblioteki 'torch' lub 'transformers' nie są zainstalowane.")
    print("Funkcjonalność AI będzie niedostępna.")
    print("Zainstaluj je używając: pip install torch torchvision torchaudio transformers sentencepiece")
    print("(biblioteka 'sentencepiece' jest często wymagana przez tokenizery T5)")

# --- Konfiguracja Logowania ---
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-8s] [%(name)-10s:%(lineno)4d] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
if TRANSFORMERS_AVAILABLE:
    logging.getLogger("transformers.modeling_utils").setLevel(logging.WARN)
    logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.WARN)

# --- Funkcje AI ---

def initialize_ai_model(model_name_to_load=None):
    """Inicjalizuje model AI i tokenizer."""
    global ai_tokenizer, ai_model, ai_device, ai_initialized_successfully

    if ai_initialized_successfully:
        logger.debug("Model AI jest już zainicjalizowany.")
        return True

    if not TRANSFORMERS_AVAILABLE:
        logger.error("Biblioteki torch/transformers nie są dostępne. Nie można zainicjalizować modelu AI.")
        ai_initialized_successfully = False
        return False

    model_to_load = model_name_to_load if model_name_to_load else AI_MODEL_TO_USE

    logger.info(f"Rozpoczynam ładowanie modelu AI: {model_to_load}...")
    try:
        ai_tokenizer = T5Tokenizer.from_pretrained(model_to_load)
        ai_device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"AI będzie używać urządzenia: {ai_device}")
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

def extract_gallery_name_t5(text_to_process, current_negative_prompts=None):
    """Ekstrahuje nazwę galerii z tekstu, uwzględniając bieżące negatywne prompty."""
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
    if current_negative_prompts and isinstance(current_negative_prompts, list) and len(current_negative_prompts) > 0:
        terms_to_avoid = ", ".join([f"'{term.strip()}'" for term in current_negative_prompts if term.strip()])
        if terms_to_avoid:
            negative_instruction = f"Important: The generated title MUST NOT include any of these terms or names: {terms_to_avoid}.\n"

    final_prompt = base_prompt + negative_instruction + "Title:"

    if negative_instruction:
        logger.debug(f"Używam instrukcji negatywnej dla tego zapytania: {negative_instruction.strip()}")
    logger.debug(f"Pełny prompt dla AI:\n{final_prompt}")

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
    """Czyści surowy tytuł zwrócony przez AI."""
    if "Błąd" in raw_title_from_ai:
        return ""
    stop_patterns_regex = [
        r"\s*-\s*\d+\s*(photos|images|pics|zdjęć|obrazków|fotografii).*",
        r"\s*by\s+.*", r"\s*from\s+.*", r"^\s*(title|Title|tytuł|Tytuł):\s*",
        r"N/A", r"^\s*-\s*", r"\s*-\s*$", r"Exclusive Set",
        r"Onlyfans", r"Patreon", r"Fansly", r"Leaks?", r"Leaked", r"Cosplay",
    ]
    cleaned_title = raw_title_from_ai
    for pattern in stop_patterns_regex:
        cleaned_title = re.sub(pattern, "", cleaned_title, flags=re.IGNORECASE)
    cleaned_title = cleaned_title.strip().rstrip(' -').strip()
    if len(cleaned_title) < 3:
        logger.debug(f"Tytuł po post-processingu ('{cleaned_title}') jest zbyt krótki. Oryginalny AI: '{raw_title_from_ai}'")
        return ""
    logger.debug(f"Tytuł po post-processingu AI: '{cleaned_title}' (oryginalny AI: '{raw_title_from_ai}')")
    return cleaned_title

# --- Główna Pętla Testująca ---
if __name__ == "__main__":
    if not TRANSFORMERS_AVAILABLE:
        logger.error("Nie można uruchomić testu AI bez bibliotek torch i transformers.")
        logger.error("Upewnij się, że są zainstalowane (np. przez: pip install torch torchvision torchaudio transformers sentencepiece)")
        sys.exit(1)

    if not initialize_ai_model():
        logger.error("Nie udało się zainicjalizować modelu AI. Program testowy zostanie zamknięty.")
        sys.exit(1)

    logger.info("Model AI jest gotowy.")
    logger.info("Wpisz tekst do przetworzenia. Następnie zostaniesz zapytany o negatywne prompty dla tego tekstu.")
    logger.info("Wpisz 'quit' lub 'exit' jako tekst źródłowy, aby zakończyć.")
    print("-" * 50)

    while True:
        try:
            input_text = input("Podaj tekst źródłowy (lub 'quit'/'exit'): ")
            if input_text.strip().lower() in ['quit', 'exit']:
                logger.info("Zakończono działanie na żądanie użytkownika.")
                break
            if not input_text.strip():
                continue

            # Pytanie o negatywne prompty dla bieżącego zapytania
            negative_prompts_str = input("Podaj negatywne prompty (oddzielone przecinkami, np. ModelkaX, SeriaY; zostaw puste jeśli brak): ")
            current_negative_prompts_list = []
            if negative_prompts_str.strip():
                current_negative_prompts_list = [term.strip() for term in negative_prompts_str.split(',') if term.strip()]

            if current_negative_prompts_list:
                logger.info(f"Dla bieżącego zapytania używam negatywnych promptów: {current_negative_prompts_list}")


            raw_ai_output = extract_gallery_name_t5(input_text, current_negative_prompts=current_negative_prompts_list)
            processed_output = post_process_ai_title(raw_ai_output)

            print(f"  > Surowy wynik z AI:   '{raw_ai_output}'")
            print(f"  > Przetworzony wynik:  '{processed_output}'")
            print("-" * 50)

        except KeyboardInterrupt:
            logger.info("\nPrzerwano przez użytkownika (Ctrl+C). Zamykanie.")
            break
        except Exception as e:
            logger.exception(f"Wystąpił nieoczekiwany błąd w pętli testującej: {e}")
            break