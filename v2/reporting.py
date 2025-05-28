# -*- coding: utf-8 -*-
import time
import constants
import data_manager
import utils
import config_handler # <-- Dodano import

def update_current_status(message, model="", gallery="", gallery_id=None,
                          downloaded_count=None,
                          scan_session_found_count=None,
                          expected_count=None, is_processing=False):
    status_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "current_model": model,
        "current_gallery_title": gallery,
        "current_gallery_id": gallery_id,
        "current_download_count": downloaded_count,
        "scan_session_found_count": scan_session_found_count,
        "current_expected_count": expected_count,
        "is_processing": is_processing
    }
    if not data_manager.save_json_file_generic(constants.CURRENT_STATUS_FILE_PATH, status_data, indent=None):
        print(f"KRYTYCZNY BŁĄD: Nie udało się zapisać pliku statusu: {constants.CURRENT_STATUS_FILE_PATH}")


def build_global_status_data(): # ... (bez zmian) ...
    global_data = {"models": {}}
    models_in_list = data_manager.read_model_list(constants.LIST_FILE_PATH)
    if not models_in_list: return global_data

    for model_name_original in models_in_list:
        model_name_sanitized = utils.sanitize_foldername(model_name_original)
        model_galleries_data = data_manager.load_model_galleries_data(model_name_sanitized)
        global_data["models"][model_name_original] = {"galleries": {}}

        for gallery_id, gallery_info in model_galleries_data.items():
            is_complete = gallery_info.get("status") in ["completed", "completed_with_tolerance"]
            dl_count = gallery_info.get("downloaded_count", 0)
            expected = gallery_info.get("expected_count", None)
            status_color = "green" if is_complete else ("orange" if dl_count > 0 else "red")

            global_data["models"][model_name_original]["galleries"][gallery_id] = {
                "title": gallery_info.get("determined_title", gallery_info.get("original_title_from_list", gallery_id)),
                "folder": gallery_info.get("folder_path_on_disk", "Brak"),
                "expected": expected,
                "downloaded": dl_count,
                "url": gallery_info.get("url", "#"),
                "status_color": status_color,
                "completed": is_complete,
                "model_name": model_name_original,
                "gallery_id": gallery_id
            }
    return global_data

def generate_global_html_status():
    data = build_global_status_data()
    data_manager.save_json_file_generic(constants.STATUS_JSON_AGGREGATE_PATH, data)

    # --- ZMIANA: Wczytanie hosta i portu z config_handler ---
    config_handler.load_config()
    server_cfg = config_handler.get_http_server_config()
    status_host_js = server_cfg['status_page_host']['value']
    status_port_js = server_cfg['port']['value']
    status_file_js = constants.CURRENT_STATUS_FILENAME
    # --- KONIEC ZMIANY ---

    html_content = """<!DOCTYPE html><html lang="pl"><head><meta charset="UTF-8"><title>Status Pobierania</title>
<style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.5; padding: 15px; background-color: #f9f9f9; }
    ul { list-style-type: none; padding-left: 0; }
    .model-li > ul.nested { padding-left: 20px; }
    .toggle { cursor: pointer; margin-right: 8px; font-weight: bold; user-select: none; width: 15px; display: inline-block; text-align: center; color: #333; }
    .model-li { margin-bottom: 8px; background-color: #fff; border: 1px solid #ddd; padding: 0; border-radius: 5px; box-shadow: 0 1px 2px rgba(0, 0, 0, .05); overflow: hidden; }
    .model-header { display: flex; align-items: center; padding: 8px 12px; background-color: #e9ecef; border-bottom: 1px solid #ddd; }
    .model-header .toggle { margin-right: 8px; }
    .model-header .model-name { flex-grow: 1; font-weight: bold; }
    ul.nested { display: none; padding-left: 25px; border-left: 2px solid #dee2e6; margin-left: 7px; background-color: #fff; margin-top: 5px; border-radius: 4px; padding: 10px; }
    ul.nested.active { display: block; }
    .gallery-li { margin-bottom: 4px; border-bottom: 1px solid #f1f3f5; padding: 6px 0; display: flex; justify-content: space-between; align-items: center; transition: background-color 0.3s; }
    .gallery-li.processing { background-color: #e0f7fa; }
    .gallery-link { flex-grow: 1; margin-right: 10px; font-size: 0.95em; display: flex; align-items: center; }
    .gallery-controls { display: flex; align-items: center; flex-shrink: 0; }
    .newly-found-count { font-size: 0.8em; color: #007bff; margin-right: 8px; display: none; }
    .gallery-status { font-size: .9em; padding: 2px 6px; border-radius: 3px; color: #fff; min-width: 65px; text-align: center; margin-left: 5px; }
    .green { background-color: #28a745; } .orange { background-color: #fd7e14; } .red { background-color: #dc3545; }
    h1 { font-size: 1.6em; color: #343a40; border-bottom: 2px solid #adb5bd; padding-bottom: 5px; display: flex; justify-content: space-between; align-items: center; }
    small { color: #6c757d; font-size: .7em; } a { text-decoration: none; color: #007bff; } a:hover { text-decoration: underline; }
    #current-status { font-size: 0.9em; font-weight: bold; color: #555; background-color: #fff; padding: 10px; border-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,.05); margin-bottom: 15px; border: 1px solid #ddd; min-height: 1.2em; transition: background-color 0.5s; }
    .progress-bar-container { width: 80px; height: 12px; background-color: #e0e0e0; border-radius: 5px; overflow: hidden; display: inline-block; margin-left: 10px; vertical-align: middle; border: 1px solid #c5c5c5; }
    .progress-bar { height: 100%; background-color: #4CAF50; width: 0%; transition: width 0.3s ease-in-out; text-align: center; color: white; font-size: 0.7em; line-height: 12px; }
    .progress-bar.orange { background-color: #fd7e14; } .progress-bar.red { background-color: #dc3545; }
    .btn-action { font-size: 0.8em; padding: 3px 7px; margin-left: 5px; cursor: pointer; border: 1px solid #ccc; background-color: #f0f0f0; border-radius: 3px; color: #333; text-decoration: none; display: inline-block; }
    .btn-action:hover { background-color: #e0e0e0; text-decoration: none; color: #333; }
    .toast { position: fixed; bottom: 20px; right: 20px; background-color: #333; color: white; padding: 15px; border-radius: 5px; z-index: 1000; opacity: 0; visibility: hidden; transition: opacity 0.5s, visibility 0.5s; font-size: 0.9em; }
    .toast.show { opacity: 1; visibility: visible; }
    .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(0, 0, 0, 0.1); border-left-color: #007bff; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 8px; vertical-align: middle; visibility: hidden; }
    .gallery-li.processing .spinner { visibility: visible; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
</style>
</head><body>
<div id="current-status">Ładowanie statusu...</div>
<h1>Status Pobierania <small>(Ostatnia aktualizacja: """ + time.strftime("%Y-%m-%d %H:%M:%S") + """)</small></h1><ul id="model-tree">"""

    sorted_models = sorted(data.get("models", {}).items())
    for model_name, model_data_html in sorted_models:
        galleries = model_data_html.get("galleries", {}); total_galleries = len(galleries)
        completed_galleries = sum(1 for g in galleries.values() if g.get("completed", False))
        model_progress = (completed_galleries / total_galleries * 100) if total_galleries > 0 else 0

        html_content += f"""<li class="model-li">
            <div class="model-header">
                <span class="toggle">+</span>
                <span class="model-name">{model_name} ({completed_galleries}/{total_galleries})</span>
                <div class="progress-bar-container" title="{model_progress:.1f}% ukończonych galerii">
                    <div class="progress-bar" style="width:{model_progress:.1f}%;">{model_progress:.0f}%</div>
                </div>
                <button class="btn-action" onclick="prioritizeItem('model', '{model_name}')" title="Uzupełnij lub rozpocznij przetwarzanie tej modelki">Uzupełnij Model</button>
            </div>
            <ul class="nested">"""

        sorted_galleries = sorted(galleries.items(), key=lambda item: item[1].get("title", item[0]))
        for gallery_id, gallery_info in sorted_galleries:
            title = gallery_info.get("title", gallery_id);
            expected = gallery_info.get("expected")
            downloaded = gallery_info.get("downloaded", 0)
            url = gallery_info.get("url", "#"); color = gallery_info.get("status_color", "red"); folder = gallery_info.get("folder", "Brak")
            gallery_progress = (downloaded / expected * 100) if expected and expected > 0 else (100 if gallery_info.get("completed") else 0)
            progress_bar_color_class = "green" if gallery_progress >= 100 else ("orange" if gallery_progress > 0 else "red")
            expected_text = expected if expected is not None else '?'

            html_content += f"""<li class="gallery-li" id="gallery_li_{gallery_id}" data-expected="{expected_text}" data-downloaded="{downloaded}">
                <span class="gallery-link">
                    <span class="spinner" id="spinner_{gallery_id}"></span>
                    <a href="{url}" target="_blank" title="Folder: {folder}">{title}</a>
                </span>
                <div class="gallery-controls">
                    <span class="newly-found-count" id="newly_found_{gallery_id}"></span>
                    <div class="progress-bar-container" id="progress_container_{gallery_id}" title="D: {downloaded}/{expected_text} ({gallery_progress:.1f}%)">
                        <div class="progress-bar {progress_bar_color_class}" id="progress_bar_{gallery_id}" style="width:{gallery_progress:.1f}%;">{gallery_progress:.0f}%</div>
                    </div>
                    <span class="gallery-status {color}" id="status_{gallery_id}">D: {downloaded}/{expected_text}</span>
                    <button class="btn-action" onclick="prioritizeItem('gallery', '{gallery_id}')" title="Uzupełnij tę galerię priorytetowo">Uzupełnij</button>
                    <a href="{url}" target="_blank" class="btn-action" title="Otwórz stronę źródłową galerii">Źródło</a>
                </div>
            </li>"""
        html_content += "</ul></li>"


    html_content += f"""</ul><div id="toast" class="toast"></div>
<script>
    // --- ZMIANA: Dodano hosta i port z Pythona ---
    const STATUS_HOST = '{status_host_js}';
    const STATUS_PORT = {status_port_js};
    const STATUS_FILE = '{status_file_js}';
    const toastDiv = document.getElementById('toast');
    let currentProcessingId = null;

    function showToast(message, isError = false) {{
        toastDiv.textContent = message;
        toastDiv.style.backgroundColor = isError ? '#dc3545' : '#333';
        toastDiv.classList.add('show');
        setTimeout(() => {{ toastDiv.classList.remove('show'); }}, 3500);
    }}

    document.addEventListener('DOMContentLoaded', function() {{
        // ... (bez zmian w logice toggle) ...
        const toggles = document.querySelectorAll('.toggle');
        toggles.forEach(spanToggle => {{
            spanToggle.addEventListener('click', function(event) {{
                const modelLiElement = this.closest('li.model-li');
                if (modelLiElement) {{
                    const nestedUl = modelLiElement.querySelector('ul.nested');
                    if (nestedUl) {{
                        nestedUl.classList.toggle('active');
                        this.textContent = nestedUl.classList.contains('active') ? '−' : '+';
                    }}
                }}
            }});
        }});
        updateStatus();
        setInterval(updateStatus, 3000);
    }});

    function prioritizeItem(type, id) {{
        console.log(`prioritizeItem called with type: ${{type}}, id: ${{id}}`);
        // --- ZMIANA: Użycie pełnego adresu z hostem i portem ---
        const url = `http://${{STATUS_HOST}}:${{STATUS_PORT}}/prioritize?${{type}}=${{encodeURIComponent(id)}}`;
        fetch(url)
            .then(response => {{
                if (!response.ok) {{ throw new Error(`HTTP error! status: ${{response.status}}`); }}
                return response.json();
            }})
            .then(data => {{ showToast(data.message || `Żądanie wysłane.`); }})
            .catch(error => {{
                console.error('Error in prioritizeItem fetch:', error);
                showToast(`Błąd wysyłania żądania. Czy skrypt Python działa i jest dostępny pod http://${{STATUS_HOST}}:${{STATUS_PORT}}?`, true);
            }});
    }}

    function updateGalleryUI(galleryId, downloaded, expected, scanSessionFound) {{
        // ... (bez zmian) ...
        const galleryLi = document.getElementById(`gallery_li_${{galleryId}}`);
        if (!galleryLi) return;
        const statusSpan = document.getElementById(`status_${{galleryId}}`);
        const progressBar = document.getElementById(`progress_bar_${{galleryId}}`);
        const progressContainer = document.getElementById(`progress_container_${{galleryId}}`);
        const newlyFoundSpan = document.getElementById(`newly_found_${{galleryId}}`);
        if (!statusSpan || !progressBar || !progressContainer || !newlyFoundSpan) return;
        const expectedValFromData = (expected !== null && expected !== undefined) ? expected : parseInt(galleryLi.dataset.expected, 10);
        const expectedText = isNaN(expectedValFromData) ? '?' : expectedValFromData;
        const currentDownloaded = (downloaded !== null && downloaded !== undefined) ? downloaded : parseInt(galleryLi.dataset.downloaded, 10);
        galleryLi.dataset.downloaded = currentDownloaded;
        if (scanSessionFound !== null && scanSessionFound !== undefined) {{
            newlyFoundSpan.textContent = `Nowych: ${{scanSessionFound}}`;
            newlyFoundSpan.style.display = 'inline';
        }} else {{
            newlyFoundSpan.style.display = 'none';
        }}
        let statusText = `D: ${{currentDownloaded}}/${{expectedText}}`;
        let progress = (expectedValFromData && expectedValFromData > 0) ? (currentDownloaded / expectedValFromData * 100) : 0;
        const color = progress >= 100 ? 'green' : (currentDownloaded > 0 ? 'orange' : 'red');
        statusSpan.textContent = statusText;
        statusSpan.className = `gallery-status ${{color}}`;
        progressBar.style.width = `${{Math.min(100, progress).toFixed(1)}}%`;
        progressBar.textContent = `${{Math.min(100, progress).toFixed(0)}}%`;
        progressBar.className = `progress-bar ${{color}}`;
        progressContainer.title = `${{statusText}} (${{progress.toFixed(1)}}%)`;
    }}

    function updateStatus() {{
        const statusDiv = document.getElementById('current-status');
        if (!statusDiv) return;

        // --- ZMIANA: Użycie pełnego adresu z hostem i portem ---
        fetch(`http://${{STATUS_HOST}}:${{STATUS_PORT}}/${{STATUS_FILE}}?_=${{new Date().getTime()}}`)
            .then(response => {{
                if (!response.ok) {{ throw new Error(`HTTP error! status: ${{response.status}}`); }}
                return response.text().then(text => {{
                    if (!text) {{ throw new Error("Empty response from server for status JSON."); }}
                    try {{ return JSON.parse(text); }}
                    catch (e) {{ console.error("Failed to parse JSON:", e, "Raw text:", text); throw new Error("Failed to parse status JSON."); }}
                }});
            }})
            .then(data => {{
                // ... (bez zmian w logice przetwarzania danych) ...
                if (!data || typeof data.timestamp === 'undefined' || typeof data.message === 'undefined') {{
                     statusDiv.textContent = "Błąd: Nieprawidłowe dane statusu z serwera.";
                     statusDiv.style.backgroundColor = '#fff8dc';
                     return;
                }}
                statusDiv.textContent = `[${{data.timestamp}}] ${{data.message}}` +
                                        (data.current_model ? ` | Model: ${{data.current_model}}` : '') +
                                        (data.current_gallery_title ? ` | Galeria: ${{data.current_gallery_title}}` : '');
                statusDiv.style.backgroundColor = '#fff';
                const newProcessingId = data.is_processing ? data.current_gallery_id : null;
                if (currentProcessingId && currentProcessingId !== newProcessingId) {{
                    const oldLi = document.getElementById(`gallery_li_${{currentProcessingId}}`);
                    if (oldLi) {{ oldLi.classList.remove('processing'); const oldNewlyFoundSpan = document.getElementById(`newly_found_${{currentProcessingId}}`); if (oldNewlyFoundSpan) oldNewlyFoundSpan.style.display = 'none'; }}
                }}
                if (newProcessingId) {{
                    const newLi = document.getElementById(`gallery_li_${{newProcessingId}}`);
                    if (newLi) newLi.classList.add('processing');
                    updateGalleryUI(newProcessingId, data.current_download_count, data.current_expected_count, data.scan_session_found_count);
                }}
                currentProcessingId = newProcessingId;
            }})
            .catch(error => {{
                console.error("Error in updateStatus fetch:", error);
                if (statusDiv) {{
                    statusDiv.textContent = `Błąd odświeżania: ${{error.message}}. Sprawdź adres http://${{STATUS_HOST}}:${{STATUS_PORT}} i firewall. Status nieaktualny.`;
                    statusDiv.style.backgroundColor = '#f8d7da';
                }}
                if (currentProcessingId) {{
                    const oldLi = document.getElementById(`gallery_li_${{currentProcessingId}}`);
                    if (oldLi) {{ oldLi.classList.remove('processing'); const oldNewlyFoundSpan = document.getElementById(`newly_found_${{currentProcessingId}}`); if (oldNewlyFoundSpan) oldNewlyFoundSpan.style.display = 'none'; }}
                    currentProcessingId = null;
                }}
            }});
    }}
</script></body></html>"""

    try:
        with open(constants.STATUS_HTML_FILE_PATH, 'w', encoding='utf-8') as f: f.write(html_content)
        print(f"📊 Wygenerowano globalny plik statusu: {constants.STATUS_HTML_FILE_PATH}")
    except Exception as e:
         print(f"❌ Błąd zapisu pliku status.html: {e}")