# -*- coding: utf-8 -*-
import os
import sys
import time
import traceback
import webbrowser
import signal
import atexit

import constants
import config_handler
import utils
import data_manager
import reporting
import http_server
import processing
import services

# --- Zmienna globalna do obsługi sygnałów ---
shutdown_requested = False

def graceful_shutdown(signum, frame):
    """Obsługuje sygnały, ustawia flagę i próbuje przerwać."""
    global shutdown_requested
    if not shutdown_requested:
        print(f"\n🛑 Otrzymano sygnał {signum}. Inicjuję zamknięcie...")
        shutdown_requested = True
        # Wywołanie KeyboardInterrupt jest jednym ze sposobów przerwania pętli,
        # ale może nie zadziałać, jeśli skrypt jest "głęboko" w innej operacji.
        # Ustawienie flagi jest bezpieczniejsze, ale pętla musi ją sprawdzać.
        # Dodatkowo, rzucenie KI tutaj.
        raise KeyboardInterrupt("Signal received")

def setup_signal_handlers():
    """Ustawia obsługę sygnałów SIGINT i SIGTERM."""
    print("INFO: Ustawiam obsługę sygnałów (SIGINT, SIGTERM)...")
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    # Obsługa SIGBREAK na Windows (jeśli pywin32 nie jest używane/dostępne)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, graceful_shutdown)

    # Próba użycia SetConsoleCtrlHandler dla Windows 'X'
    if sys.platform == "win32":
        try:
            import win32api

            def console_ctrl_handler(ctrl_type):
                # CTRL_C_EVENT = 0
                # CTRL_BREAK_EVENT = 1
                CTRL_CLOSE_EVENT = 2
                # CTRL_LOGOFF_EVENT = 5
                # CTRL_SHUTDOWN_EVENT = 6
                if ctrl_type == CTRL_CLOSE_EVENT:
                    print("INFO: Wykryto zamknięcie konsoli (X).")
                    graceful_shutdown("CTRL_CLOSE", None)
                    # Dajemy chwilę, ale Windows może i tak zabić proces.
                    time.sleep(2)
                    return True # Próbujemy wskazać, że obsłużyliśmy.
                return False # Przekaż dalej inne sygnały.

            win32api.SetConsoleCtrlHandler(console_ctrl_handler, True)
            print("INFO: Zarejestrowano handler konsoli Windows.")
        except ImportError:
            print("INFO: pywin32 nie jest zainstalowany. Obsługa 'X' w konsoli Windows ograniczona.")
        except Exception as e:
            print(f"WARN: Nie udało się ustawić handlera konsoli Windows: {e}")

def final_cleanup():
    """Funkcja czyszcząca wywoływana przez atexit."""
    print("INFO: Wykonywanie czyszczenia przy wyjściu (atexit)...")
    http_server.stop_http_server()
    reporting.update_current_status("Skrypt zatrzymany.")
    print("--- Koniec działania ---")

def main_menu():
    # ... (bez zmian) ...
    if not hasattr(main_menu, "browser_opened"):
        try: webbrowser.open(f"http://localhost:{constants.HTTP_SERVER_PORT}/status.html")
        except Exception as e_wb: print(f"⚠️ Nie udało się otworzyć status.html: {e_wb}")
        main_menu.browser_opened = True

    print("\nMENU GŁÓWNE:")
    print("1. Kontynuuj / Przetwórz listę modelek")
    print("2. Uzupełnij niepełne galerie (douzupelnienia.json)")
    print("3. Sprawdź tylko nowe/zaktualizowane galerie")
    print("4. Wygeneruj ponownie status.html")
    print("5. Wyjdź")
    choice = input("Wybierz opcję (1-5): ")

    if choice == '1':
        state = data_manager.load_script_state()
        start_idx = state.get("last_model_index_processed", -1)
        start_idx = start_idx + 1 if start_idx >= -1 else 0

        models_list = data_manager.read_model_list()
        if start_idx >= len(models_list) and len(models_list) > 0:
            print("🏁 Lista przetworzona.")
            if input("   Zacząć od początku? (t/N): ").lower() == 't':
                start_idx = 0
                data_manager.update_last_model_index(-1)
            else: return None, None
        params = {"start_model_index": start_idx, "check_mode": "all_or_incomplete"}
        return "process_models", params
    elif choice == '2': return "fill_incomplete", {}
    elif choice == '3':
        params = {"start_model_index": 0, "check_mode": "only_new_or_count_changed"}
        return "process_models", params
    elif choice == '4':
        print("INFO: Ręczne generowanie status.html...")
        reporting.generate_global_html_status()
        return None, None
    elif choice == '5': return "exit_app", None
    else:
        print("Nieprawidłowy wybór.")
        return None, None

def main_loop():
    global shutdown_requested
    config_handler.load_config(force_reload=True)
    if not http_server.start_http_server():
        print("🛑 Nie można uruchomić serwera HTTP. Kończę.")
        return

    print("INFO: Generowanie początkowego status.html...", flush=True)
    reporting.generate_global_html_status()
    reporting.update_current_status("Skrypt uruchomiony, inicjalizacja...")

    key_pressed = utils.wait_for_key_press_or_timeout(5) if 'SKIP_MENU_PROMPT' not in os.environ else False
    show_menu = key_pressed

    if show_menu:
        print("   Klawisz naciśnięty. Czyszczę stan i wyświetlam menu.")
        data_manager.clear_active_operation()
    else:
        state = data_manager.load_script_state()
        if not state.get("current_operation", {}).get("name"):
             print("   ℹ️ Czas minął i brak aktywnej operacji. Wyświetlam menu.")
             show_menu = True
        else:
             print("   ℹ️ Czas minął. Wznawiam ostatnią operację...")
             show_menu = False

    try: # --- Dodano blok try...finally ---
        while not shutdown_requested: # Sprawdzaj flagę
            try:
                config_handler.load_config()
                print("--- Pętla: Sprawdzam kolejkę...", flush=True)

                queue = data_manager.load_priority_queue()
                if queue:
                    print(f"--- Pętla: Znaleziono {len(queue)} w kolejce. Przetwarzam pierwszy.", flush=True)
                    item = queue.pop(0)
                    data_manager.save_priority_queue(queue)
                    processing.handle_priority_item(item)
                    show_menu = False
                    continue

                print("--- Pętla: Kolejka pusta. Sprawdzam stan.", flush=True)
                state = data_manager.load_script_state()
                op_name = state["current_operation"]["name"]
                op_params = state["current_operation"]["params"]

                if show_menu or not op_name:
                    print("--- Pętla: Wyświetlam menu.", flush=True)
                    reporting.update_current_status("Wyświetlanie menu...")
                    op_name_new, op_params_new = main_menu()
                    if op_name_new and op_name_new != "exit_app":
                        data_manager.update_active_operation(op_name_new, op_params_new)
                        op_name, op_params = op_name_new, op_params_new
                        show_menu = False
                    elif op_name_new == "exit_app":
                        op_name = "exit_app"
                    else:
                        show_menu = True; continue

                if op_name == "exit_app": break

                print(f"--- Pętla: Mam operację '{op_name}'. Show_menu={show_menu}", flush=True)
                show_menu_next_iter = True

                if op_name:
                    print(f"--- Pętla: Uruchamiam '{op_name}'...", flush=True)
                    if op_name == "process_models":
                        processing.handle_process_models(**op_params)
                    elif op_name == "fill_incomplete":
                        processing.handle_fill_incomplete()

                    if not data_manager.load_priority_queue():
                        print(f"--- Pętla: Operacja '{op_name}' zakończona, czyszczę stan.", flush=True)
                        data_manager.clear_active_operation()
                        op_name = None
                        show_menu_next_iter = True
                    else:
                        print(f"--- Pętla: Operacja '{op_name}' przerwana/zakończona, kolejka niepusta.", flush=True)
                        show_menu_next_iter = False

                show_menu = show_menu_next_iter
                if shutdown_requested: break # Sprawdź ponownie po operacji

            except constants.RestartRequiredError as e:
                reporting.update_current_status(f"Restart ({e})")
                print(f"\n🚨🚨🚨 RESTART: {e} 🚨🚨🚨")
                if hasattr(e, 'no_vpn') and e.no_vpn:
                    print("   ℹ️ Restart bez VPN. Czekam 5s...")
                    time.sleep(5)
                elif services.rotate_vpn():
                    print("✅ IP zmienione. Wznawiam za 10s..."); time.sleep(10)
                else: print("❌ Nie udało się zmienić IP. Zatrzymuję."); break
                show_menu = False

            except KeyboardInterrupt: # Przechwyć KI z sygnałów
                print("\n🛑 Przerwanie przez użytkownika lub sygnał.")
                reporting.update_current_status("Przerwano przez użytkownika.")
                shutdown_requested = True # Ustaw flagę, aby wyjść z pętli
                break # Wyjdź z pętli

            except Exception as e:
                print(f"💥💥💥 KRYTYCZNY BŁĄD: {e} 💥💥💥"); traceback.print_exc()
                reporting.update_current_status(f"Błąd krytyczny: {e}")
                data_manager.clear_active_operation()
                time.sleep(15)
                show_menu = True

    finally: # --- Blok finally ---
        print("\nINFO: Rozpoczynam czyszczenie przed wyjściem...")
        http_server.stop_http_server()
        reporting.update_current_status("Skrypt zatrzymany.")
        print("Program zakończył działanie.")


if __name__ == '__main__':
    atexit.register(final_cleanup) # Zarejestruj funkcję atexit
    setup_signal_handlers() # Ustaw obsługę sygnałów
    main_loop()