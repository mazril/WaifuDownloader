# -*- coding: utf-8 -*-
import http.server
import socketserver
import urllib.parse
import json
import threading
import time
import constants
import data_manager
import utils
import os
import config_handler # <-- Dodano import

priority_queue_lock = threading.Lock()
httpd_thread = None
httpd = None

class PriorityRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=constants.SCRIPT_DIR, **kwargs)

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)

        if parsed_path.path == '/prioritize':
            query_components = urllib.parse.parse_qs(parsed_path.query)
            gallery_id = query_components.get("gallery", [None])[0]
            model_name = query_components.get("model", [None])[0]

            added = False
            message = "OK"

            with priority_queue_lock:
                if gallery_id:
                    added = data_manager.add_to_priority_queue("gallery", gallery_id)
                    message = f"Galeria {gallery_id} {'dodana' if added else 'już była'} do kolejki."
                elif model_name:
                    model_name_sanitized = utils.sanitize_foldername(model_name)
                    model_profile_path = data_manager.get_model_galleries_filepath(model_name_sanitized)

                    if not os.path.exists(model_profile_path):
                        print(f"ℹ️ Model '{model_name}' jest nowy. Dodaję zadanie skanowania.")
                        added = data_manager.add_to_priority_queue("scan_model", model_name)
                        message = f"Model '{model_name}' jest nowy. Dodano zadanie skanowania do kolejki."
                    else:
                        model_galleries = data_manager.load_model_galleries_data(model_name_sanitized)
                        added_count = 0
                        for gid, ginfo in model_galleries.items():
                             if ginfo.get("status") not in ["completed", "completed_with_tolerance"]:
                                if data_manager.add_to_priority_queue("gallery", gid):
                                    added_count += 1
                        added = added_count > 0
                        message = f"Dodano {added_count} galerii dla {model_name}." if added_count > 0 else f"Brak nowych galerii do dodania dla {model_name}."

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_message = {"status": "ok", "message": message, "added": added}
            self.wfile.write(json.dumps(response_message).encode('utf-8'))
        else:
            super().do_GET()

    def log_message(self, format, *args):
        pass # Wycisza standardowe logi

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

def start_http_server():
    global httpd, httpd_thread
    if httpd_thread and httpd_thread.is_alive():
        print("ℹ️ Serwer HTTP już działa.")
        return True

    def run_server():
        global httpd
        # --- ZMIANA: Wczytanie hosta i portu z config_handler ---
        config_handler.load_config() # Upewnij się, że config jest aktualny
        server_cfg = config_handler.get_http_server_config()
        host = server_cfg['bind_host']['value']
        port = server_cfg['port']['value']
        status_host = server_cfg['status_page_host']['value']
        address = (host, port)
        # --- KONIEC ZMIANY ---
        try:
            socketserver.TCPServer.allow_reuse_address = True
            httpd = socketserver.TCPServer(address, PriorityRequestHandler)
            # --- ZMIANA: Użycie status_host w komunikacie ---
            print(f"🌐 Serwer HTTP nasłuchuje na {host}:{port}. Status dostępny pod http://{status_host}:{port}/status.html")
            httpd.serve_forever()
        except OSError as e:
             print(f"❌ BŁĄD: Nie można uruchomić serwera HTTP na {host}:{port}: {e}")
             print(f"   ℹ️ Sprawdź, czy adres IP '{host}' jest poprawny dla tej maszyny i czy port {port} nie jest zajęty.")
             httpd = None
        except Exception as e:
            print(f"❌ Nieoczekiwany błąd serwera HTTP: {e}")
            httpd = None

    httpd_thread = threading.Thread(target=run_server)
    httpd_thread.daemon = True
    httpd_thread.start()
    time.sleep(1)
    return httpd is not None

def stop_http_server():
    global httpd, httpd_thread
    if httpd:
        print("🛑 Zatrzymuję serwer HTTP...")
        httpd.shutdown()
        httpd.server_close()
        httpd = None
    if httpd_thread:
        httpd_thread.join(timeout=2)
        httpd_thread = None
    print("🛑 Serwer HTTP zatrzymany.")