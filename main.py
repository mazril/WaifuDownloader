# -*- coding: utf-8 -*-
import os
import sys
import time
import traceback
import signal
import atexit
import logging
import logging.handlers

import constants
import config_handler
import utils
# import data_manager # Usunięto, funkcje stanu są teraz w db_manager
import reporting
import processing
import services
import driver_utils
import db_manager # Dodano import

# --- Globalny słownik do przechowywania zebranych linków do obrazów ---
# Klucz: gallery_id, Wartość: lista URL-i obrazów
collected_gallery_image_links = {}

# --- Konfiguracja loggingu ---
def setup_logging():
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)-8s] [%(name)-20s:%(lineno)4d] %(message)s')
    log_file_name = "script.txt"
    log_file_path = os.path.join(constants.SCRIPT_DIR, log_file_name)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(console_handler)

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8', delay=True
        )
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        logging.info(f"Logowanie do pliku skonfigurowane: {log_file_path}")
    except Exception as e_file_log:
        logging.error(f"KRYTYCZNY BŁĄD: Nie udało się skonfigurować logowania do pliku '{log_file_path}': {e_file_log}", exc_info=True)
        logging.error("Logowanie do pliku będzie niedostępne.")

    logging.info("Poprawnie zainicjowano system logowania.")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("undetected_chromedriver").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("mysql.connector").setLevel(logging.WARNING) # Wyciszenie logów MySQL

shutdown_requested = False
logger = logging.getLogger(__name__)

def graceful_shutdown(signum, frame):
    global shutdown_requested
    signal_name = signal.Signals(signum).name if isinstance(signum, int) else str(signum)
    if not shutdown_requested:
        logger.critical(f"Otrzymano sygnał {signal_name} ({signum}). Inicjuję zamknięcie...")
        shutdown_requested = True
        if hasattr(db_manager, 'set_shutdown_requested_flag'): 
            db_manager.set_shutdown_requested_flag(True)
        elif hasattr(processing, 'data_manager') and hasattr(processing.data_manager, 'set_shutdown_requested_flag'): 
            processing.data_manager.set_shutdown_requested_flag(True)
    else:
        logger.warning(f"Ponownie otrzymano sygnał {signal_name} ({signum}). Proces zamykania już trwa.")


def setup_signal_handlers():
    logger.info("Ustawiam obsługę sygnałów (SIGINT, SIGTERM)...")
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, graceful_shutdown)

def final_cleanup():
    logger.info("Wykonywanie czyszczenia przy wyjściu (atexit)...")
    if shutdown_requested:
        logger.info("Atexit: Wykonywanie kill_chrome_processes jako ostateczność...")
        driver_utils.kill_chrome_processes()
    reporting.update_current_status("Skrypt zatrzymany (atexit).")
    logger.info("--- Koniec działania (atexit) ---")
    logging.shutdown()

def main_menu():
    """
    Wyświetla menu główne i zwraca wybraną operację.
    
    Opis modyfikacji:
    Menu zostało uproszczone. Główna opcja "Uruchom pełny cykl" teraz obejmuje
    przetwarzanie nowych galerii, a następnie automatyczne przejście do
    uzupełniania niekompletnych. To odzwierciedla nową, dwuetapową logikę przetwarzania.
    
    Wpływ na inne funkcje:
    - Wybór opcji '1' inicjuje nową, dwuetapową logikę w `main_loop`.
    """
    print("\n" + "=" * 50)
    print(" " * 19 + "MENU GŁÓWNE")
    print("=" * 50)
    print(" ℹ️  Strona statusu PHP jest dostępna pod adresem: ")
    print("     http://localhost/TWOJA_SCIEZKA_DO_PROJEKTU/status.php ")
    print("     (Dostosuj URL do konfiguracji swojego serwera WWW)")
    print("-" * 50)
    print(" 1. Uruchom pełny cykl (Nowe galerie, potem uzupełnianie)")
    print(" 2. Sprawdź tylko nowe/zaktualizowane galerie (szybkie skanowanie)")
    print(" 3. Wyjdź")
    print("=" * 50)
    choice = input(" Wybierz opcję (1-3): ")
    logger.info(f"Wybrano opcję menu: {choice}")

    if choice == '1':
        return "full_run", {}
    elif choice == '2':
        params = {"start_model_index": 0, "check_mode": "only_new_or_count_changed"}
        return "process_models", params
    elif choice == '3':
        return "exit_app", None
    else:
        logger.warning(f"Nieprawidłowy wybór: '{choice}'.")
        print("Nieprawidłowy wybór.")
        return None, None

def main_loop():
    """
    Główna pętla programu zarządzająca operacjami.
    
    Opis modyfikacji:
    Logika została rozbudowana, aby obsłużyć dwuetapowe przetwarzanie.
    Po wybraniu opcji "Uruchom pełny cykl", pętla najpierw wykonuje przetwarzanie
    podstawowe (`check_mode="all_or_incomplete"`), a po jego zakończeniu
    automatycznie rozpoczyna etap uzupełniania niekompletnych galerii
    (`check_mode="fill_incomplete_only"`).
    
    Wpływ na inne funkcje:
    - Wywołuje `processing.handle_process_models` z nowym `check_mode`.
    - Współpracuje ze zmienionym `main_menu` i logiką w `db_manager`.
    """
    global shutdown_requested
    global collected_gallery_image_links

    try:
        config_handler.load_config(force_reload=True)
        db_manager.initialize_connection_pool()
        reporting.update_current_status("Skrypt uruchomiony, inicjalizacja DB...")

        state_on_startup = db_manager.get_app_state('script_state') or {}
        operation_to_resume = state_on_startup.get("current_operation", {}).get("name")

        show_menu_on_start_flag = True
        if operation_to_resume and operation_to_resume != 'full_run_fill_incomplete':
            if 'SKIP_MENU_PROMPT' in os.environ:
                logger.info(f"SKIP_MENU_PROMPT: Wznawiam '{operation_to_resume}' bez pytania.")
                show_menu_on_start_flag = False
            else:
                logger.info(f"Wykryto operację ('{operation_to_resume}') do wznowienia. Kontynuuję automatycznie.")
                show_menu_on_start_flag = False
        else:
            logger.info("Brak zapisanej operacji lub operacja uzupełniania. Czekam na ewentualne przerwanie (5s) lub wyświetlam menu.")
            if utils.wait_for_key_press_or_timeout(5):
                logger.info("Klawisz naciśnięty. Czyszczę stan (jeśli był) i wyświetlam menu.")
                current_state = db_manager.get_app_state('script_state') or {}
                current_state["current_operation"] = {"name": None, "params": {}}
                db_manager.update_app_state('script_state', current_state)
                show_menu_on_start_flag = True
            else:
                logger.info("Czas minął, brak operacji. Wyświetlam menu.")
                show_menu_on_start_flag = True

        active_op_name = None
        active_op_params = {}
        if not show_menu_on_start_flag and operation_to_resume:
            active_op_name = operation_to_resume
            active_op_params = state_on_startup.get("current_operation", {}).get("params", {})
            logger.info(f"Wznawiam operację: {active_op_name} z parametrami: {active_op_params}")

        force_menu_next_iteration = show_menu_on_start_flag

        while not shutdown_requested:
            try:
                if config_handler.load_config():
                    logger.info("Konfiguracja przeładowana dynamicznie.")
                logger.debug("ML: Sprawdzam kolejkę priorytetową (DB)...")
                priority_queue = db_manager.get_priority_queue()

                if priority_queue:
                    logger.info(f"ML: Znaleziono {len(priority_queue)} zadań w kolejce DB. Przetwarzam pierwszy.")
                    item = priority_queue.pop(0)
                    db_manager.save_priority_queue(priority_queue)
                    try:
                        processing.handle_priority_item(
                            item,
                            shutdown_flag_func=lambda: shutdown_requested,
                            collected_gallery_image_links_ref=collected_gallery_image_links
                        )
                    except constants.RestartRequiredError as rre_priority:
                        logger.error(f"ML: RESTART WYMAGANY w zadaniu priorytetowym: {rre_priority}", exc_info=False)
                        reporting.update_current_status(f"Restart (priorytet: {str(rre_priority)[:50]})")
                        if hasattr(rre_priority, 'no_vpn') and rre_priority.no_vpn:
                            time.sleep(5)
                        elif services.rotate_vpn():
                            time.sleep(10)
                        else:
                            logger.critical("ML: Błąd rotacji VPN po RRE z priorytetu. Zatrzymuję.")
                            shutdown_requested = True
                        force_menu_next_iteration = False
                        continue
                    logger.info("ML: Zakończono element priorytetowy. Kontynuuję pętlę.")
                    force_menu_next_iteration = False
                    continue

                if force_menu_next_iteration or not active_op_name:
                    logger.info("ML: Wyświetlam menu.")
                    reporting.update_current_status("Oczekiwanie na wybór z menu...")
                    if active_op_name:
                        current_state = db_manager.get_app_state('script_state') or {}
                        current_state["current_operation"] = {"name": None, "params": {}}
                        db_manager.update_app_state('script_state', current_state)
                        active_op_name = None
                        active_op_params = {}
                    op_choice, params_choice = main_menu()
                    if op_choice == "exit_app":
                        shutdown_requested = True
                        break
                    elif op_choice:
                        active_op_name = op_choice
                        active_op_params = params_choice if params_choice is not None else {}
                        current_state = db_manager.get_app_state('script_state') or {}
                        current_state["current_operation"]["name"] = active_op_name
                        current_state["current_operation"]["params"] = active_op_params
                        db_manager.update_app_state('script_state', current_state)
                        force_menu_next_iteration = False
                    else:
                        force_menu_next_iteration = True
                        active_op_name = None
                        continue

                if active_op_name and not shutdown_requested:
                    logger.info(f"ML: Uruchamiam operację '{active_op_name}' param: {active_op_params}")
                    operation_completed_normally = False
                    try:
                        if active_op_name == "full_run":
                            # Etap 1: Przetwarzanie nowych i błędnych
                            state = db_manager.get_app_state('script_state') or {"last_model_index_processed": -1}
                            start_idx = state.get("last_model_index_processed", -1) + 1
                            
                            reporting.update_current_status("Rozpoczynanie pełnego cyklu (Etap 1: Nowe galerie)...")
                            processing.handle_process_models(
                                start_model_index=start_idx,
                                check_mode="all_or_incomplete",
                                shutdown_flag_func=lambda: shutdown_requested,
                                collected_gallery_image_links_ref=collected_gallery_image_links
                            )
                            # Po zakończeniu etapu 1, płynnie przejdź do etapu 2
                            active_op_name = "full_run_fill_incomplete"
                            active_op_params = {} # Resetuj parametry dla nowego etapu
                            current_state = db_manager.get_app_state('script_state') or {}
                            current_state["current_operation"]["name"] = active_op_name
                            current_state["current_operation"]["params"] = active_op_params
                            current_state["last_model_index_processed"] = -1 # Zacznij od początku dla uzupełniania
                            db_manager.update_app_state('script_state', current_state)
                            logger.info("ML: Zakończono etap 1 (Nowe). Rozpoczynam etap 2 (Uzupełnianie).")
                            continue # Przejdź do następnej iteracji pętli, aby rozpocząć etap 2

                        elif active_op_name == "full_run_fill_incomplete":
                            # Etap 2: Uzupełnianie niekompletnych
                            state = db_manager.get_app_state('script_state') or {"last_model_index_processed": -1}
                            start_idx = state.get("last_model_index_processed", -1) + 1
                            
                            reporting.update_current_status("Kontynuacja pełnego cyklu (Etap 2: Uzupełnianie niekompletnych)...")
                            processing.handle_process_models(
                                start_model_index=start_idx,
                                check_mode="fill_incomplete_only",
                                shutdown_flag_func=lambda: shutdown_requested,
                                collected_gallery_image_links_ref=collected_gallery_image_links
                            )
                            operation_completed_normally = True

                        elif active_op_name == "process_models":
                            processing.handle_process_models(
                                **active_op_params,
                                shutdown_flag_func=lambda: shutdown_requested,
                                collected_gallery_image_links_ref=collected_gallery_image_links
                            )
                            operation_completed_normally = True

                        elif active_op_name == "fill_incomplete":
                            processing.handle_fill_incomplete(
                                shutdown_flag_func=lambda: shutdown_requested,
                                collected_gallery_image_links_ref=collected_gallery_image_links
                            )
                            operation_completed_normally = True

                    except constants.RestartRequiredError as e_restart_op:
                        logger.info(f"ML: Operacja '{active_op_name}' zgłosiła RRE. Przekazuję.")
                        raise

                    if operation_completed_normally:
                        if not db_manager.get_priority_queue() and not shutdown_requested:
                            logger.info(f"ML: Operacja '{active_op_name}' zakończona, kolejka pusta. Czyszczę stan.")
                            current_state = db_manager.get_app_state('script_state') or {}
                            current_state["current_operation"] = {"name": None, "params": {}}
                            db_manager.update_app_state('script_state', current_state)
                            active_op_name = None
                            force_menu_next_iteration = True
                        elif not shutdown_requested:
                            logger.info(f"ML: Operacja '{active_op_name}' zakończona, ale kolejka niepusta. Przejdę do kolejki.")
                            force_menu_next_iteration = False

            except constants.RestartRequiredError as e_restart:
                logger.error(f"ML: RESTART WYMAGANY: {e_restart}", exc_info=False)
                reporting.update_current_status(f"Restart ({str(e_restart)[:100]})")
                if hasattr(e_restart, 'no_vpn') and e_restart.no_vpn:
                    logger.info("ML: Restart bez VPN. Czekam 5s...")
                    time.sleep(5)
                elif services.rotate_vpn():
                    logger.info("ML: Rotacja VPN OK. Wznawiam za 10s...")
                    time.sleep(10)
                else:
                    logger.critical("ML: Błąd rotacji VPN. Zatrzymuję.")
                    shutdown_requested = True
                force_menu_next_iteration = False

            except KeyboardInterrupt:
                if not shutdown_requested:
                    logger.warning("ML: Przerwanie przez użytkownika (Ctrl+C).")
                    reporting.update_current_status("Przerwano.")
                shutdown_requested = True

            except Exception as e_main_loop:
                logger.exception(f"ML: KRYTYCZNY BŁĄD: {e_main_loop}")
                reporting.update_current_status(f"Błąd krytyczny: {str(e_main_loop)[:100]}")
                current_state = db_manager.get_app_state('script_state') or {}
                current_state["current_operation"] = {"name": None, "params": {}}
                db_manager.update_app_state('script_state', current_state)
                active_op_name = None
                logger.info("ML: Czekam 15s po błędzie krytycznym...")
                time.sleep(15)
                force_menu_next_iteration = True

            if shutdown_requested:
                logger.info("ML: Żądanie zamknięcia. Wychodzę.")
                break
            if force_menu_next_iteration and not active_op_name and not db_manager.get_priority_queue():
                time.sleep(0.1)
    finally:
        logger.info("ML: Rozpoczynam czyszczenie w bloku finally...")
        if shutdown_requested:
            reporting.update_current_status("Skrypt zatrzymany (przez żądanie zamknięcia).")
        logger.info("ML: Pętla główna zakończona.")

if __name__ == '__main__':
    setup_logging()
    atexit.register(final_cleanup)
    setup_signal_handlers()
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Program zakończony przez KeyboardInterrupt na najwyższym poziomie.")
    except SystemExit as e:
        logger.info(f"Program zakończony przez SystemExit: {e}")
    except Exception as e_top:
        logger.critical(f"Nieobsłużony wyjątek na najwyższym poziomie: {e_top}", exc_info=True)
    finally:
        logger.info("Główny blok skryptu (__name__ == '__main__') zakończył działanie.")