# -*- coding: utf-8 -*-
import time
import random
import requests
import subprocess
import sys
import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration
import constants
import config_handler
import os # Potrzebne do os.path.exists i os.path.basename

# --- AI State ---
ai_tokenizer = None
ai_model = None
ai_device = None

# --- VPN ---
def rotate_vpn(attempts=3):
    print("\n🔄 Rozpoczynam rotację NordVPN...")
    for attempt in range(attempts):
        try:
            print("   Odłączam..."); 
            subprocess.run([constants.NORDVPN_CLI_EXECUTABLE, "--disconnect"], check=False, capture_output=True, text=True, timeout=60, shell=True)
            time.sleep(random.uniform(3, 7))
            print("   Łączę..."); 
            subprocess.run([constants.NORDVPN_CLI_EXECUTABLE, "--connect"], check=True, capture_output=True, text=True, timeout=120, shell=True)
            time.sleep(random.uniform(10, 15))
            r = requests.get("https://api.ipify.org", timeout=20); r.raise_for_status()
            print(f"✅ Rotacja VPN OK! IP: {r.text}"); return True
        except subprocess.CalledProcessError as e: print(f"   ❌ Błąd NordVPN ({attempt+1}): {e.stderr.strip()}")
        except subprocess.TimeoutExpired: print(f"   ❌ Timeout NordVPN ({attempt+1}).")
        except FileNotFoundError: print(f"   ❌ BŁĄD: '{constants.NORDVPN_CLI_EXECUTABLE}' nie znaleziono."); return False
        except Exception as e: print(f"   ❌ Nieoczekiwany błąd VPN: {e}")
        time.sleep(15)
    print("🛑 Nie udało się wykonać rotacji VPN."); return False

# --- Downloader ---
def download_image(url, dest):
    cfg = config_handler.current_config['downloading']
    delay = random.uniform(cfg['download_delay_min']['value'], cfg['download_delay_max']['value'])
    time.sleep(delay)

    if os.path.exists(dest):
        print(f"  ✅ Plik {os.path.basename(dest)} już istnieje. Pomijam.")
        return True

    print(f"📥 Pobieram {os.path.basename(dest)} (po {delay:.2f}s)...")
    try:
        headers = {'User-Agent': random.choice(constants.USER_AGENTS)}
        r = requests.get(url, stream=True, headers=headers, timeout=30)
        r.raise_for_status()
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(1024): f.write(chunk)
        return True
    except Exception as ex: 
        print(f"   ⚠️ Błąd pobierania {os.path.basename(dest)}: {ex}")
        return False

# --- AI ---
def initialize_ai_model(model_name=constants.AI_MODEL_TO_USE):
    global ai_tokenizer, ai_model, ai_device
    if ai_model: return True # Już zainicjalizowany

    print(f"INFO: Ładowanie modelu AI: {model_name}...", file=sys.stderr)
    try:
        ai_tokenizer = T5Tokenizer.from_pretrained(model_name)
        ai_device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"INFO: AI używa urządzenia: {ai_device}", file=sys.stderr)
        ai_model = T5ForConditionalGeneration.from_pretrained(model_name).to(ai_device)
        print("INFO: Model AI załadowany.", file=sys.stderr)
        return True
    except Exception as e: 
        print(f"BŁĄD: Inicjalizacja modelu AI: {e}", file=sys.stderr)
        ai_tokenizer, ai_model, ai_device = None, None, None
        return False

def extract_gallery_name_t5(text):
    global ai_tokenizer, ai_model, ai_device
    if not ai_model: return "Błąd: Model AI nie zainicjalizowany."
    
    prompt = f"""Extract 'Character' and 'Series' from the title. Output: 'Character - Series' or 'Character'.
    Example 1: Text: "Victoria Lirell - Princess Zelda - The Legend Of Zelda - 37 photos" Title: Princess Zelda - The Legend Of Zelda
    Example 2: Text: "Shinano by Kokura Chiyo from Azur Lane" Title: Shinano - Azur Lane
    Example 3: Text: "Some Artist - Just A Character - 50 photos" Title: Just A Character
    Text: "{text}"
    Title:"""
    try:
        input_ids = ai_tokenizer(prompt, return_tensors="pt", max_length=512, truncation=True).input_ids.to(ai_device)
        outputs = ai_model.generate(input_ids, max_length=100, num_beams=4, early_stopping=True)
        decoded_output = ai_tokenizer.decode(outputs[0], skip_special_tokens=True)
        return decoded_output.strip()
    except Exception as e: 
        print(f"BŁĄD GENEROWANIA AI: {e}", file=sys.stderr)
        return "Błąd generowania AI"

def post_process_ai_title(title):
    stop_patterns = [
        r"\s-\s\d+\sphotos.*", r"\s-\sExclusive\sSet.*", r"\s-\sLeaks.*", r"\s-\sleaked.*",
        r"\s-\sOnlyfans.*", r"\s-\sPatreon.*", r"\s-\sFansly.*", r"^\s*Title:\s*", r"N/A"
    ]
    cleaned_title = title
    if "Błąd" in title: return ""
    for pattern in stop_patterns:
        cleaned_title = re.sub(pattern, "", cleaned_title, flags=re.IGNORECASE)
    return cleaned_title.strip().rstrip(' -').strip()