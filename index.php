<?php
// index.php

require_once 'php_config.php'; 
require_once 'php_utils.php';  

// --- Global Initializations ---
$pdo = get_db_connection();
$active_tab = $_GET['tab'] ?? 'status_galleries';

// --- Zmienne dla Zakładki 1: "Przegląd Galerii" ---
$aggregate_last_modified_timestamp = "Ładowanie...";

// --- Zmienne dla Zakładki 2: "Testowanie Tytułów AI" ---
$models_for_filter_tab2 = []; 
$statuses_for_filter_tab2 = ['pending_check', 'pending_ai', 'pending_ai_test', 'partially_downloaded', 'downloaded_unknown_total', 'completed', 'completed_with_tolerance', 'error', 'error_ai', 'error_ai_test', 'test_completed', 'pending_initial_fetch_prod_ai', 'pending_initial_fetch_test_ai', 'error_ai_prod', 'disabled_bad_links']; 

if ($pdo) { 
    try {
        $stmt_models_filter_tab2 = $pdo->query("SELECT model_name FROM models ORDER BY model_name ASC");
        if ($stmt_models_filter_tab2) {
            $models_for_filter_tab2 = $stmt_models_filter_tab2->fetchAll(PDO::FETCH_COLUMN);
        } else {
            error_log("Failed to fetch models for filter in Tab 2 (index.php)");
        }
    } catch (PDOException $e) {
        error_log("PDOException fetching models for Tab 2 (index.php): " . $e->getMessage());
    }
}

?>
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Panel Główny WaifuDownloader</title>
    <link rel="stylesheet" href="styles.css?v=<?php echo time(); ?>">
    <style>
        .global-ai-settings { border: 1px solid #ddd; border-radius: 5px; padding: 15px; margin-top: 25px; background-color: #f9f9f9; }
        .global-ai-settings h3 { margin-top: 0; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        .global-ai-settings .form-group { margin-bottom: 15px; }
        .global-ai-settings label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
        .global-ai-settings input[type="text"] { width: 100%; padding: 8px; border-radius: 4px; border: 1px solid #ccc; box-sizing: border-box; }
    </style>
</head>
<body>

<div class="global-container">
    <div class="tabs-navigation">
        <button class="tab-button <?php echo ($active_tab === 'status_galleries') ? 'active' : ''; ?>" onclick="openTab(event, 'status_galleries')">Przegląd Galerii</button>
        <button class="tab-button <?php echo ($active_tab === 'test_ai_titles') ? 'active' : ''; ?>" onclick="openTab(event, 'test_ai_titles')">Testowanie Tytułów AI</button>
        <button class="tab-button <?php echo ($active_tab === 'ollama_prompts_settings') ? 'active' : ''; ?>" onclick="openTab(event, 'ollama_prompts_settings')">Ustawienia AI</button>
    </div>

    <div class="tab-content-wrapper">
        <div id="status_galleries" class="tab-content <?php echo ($active_tab === 'status_galleries') ? 'active' : ''; ?>">
            <div id="toast-status">Wiadomość toast!</div>
            <div id="current-status">Ładowanie statusu...</div>

            <h1>
                Status Pobierania <small id="last-aggregate-update-time">(<?php echo htmlspecialchars($aggregate_last_modified_timestamp); ?>)</small>
                <div class="main-controls">
                    <button id="refresh-empty-btn" class="btn-action" onclick="refreshAllEmptyDescriptions()" title="Dodaje wszystkie modelki do kolejki odświeżania opisów/liczników (dla galerii 0/0 lub ?/0)">Odśwież Puste Opisy</button>
                    <button id="refresh-all-galleries-btn" class="btn-action" onclick="refreshAllGalleriesLists()" title="Dodaje wszystkie modelki do kolejki skanowania galerii. Najpierw puste modele, potem istniejące w poszukiwaniu nowych linków.">Odśwież Listę Galerii</button>
                    <button id="search-galleries-btn" class="btn-action" onclick="openSearchModal()">Szukaj Galerii</button>
                    <button id="manage-queue-btn" class="btn-action" onclick="openQueueModal()">
                        Zarządzaj Kolejką (<span id="queue-count">?</span>)
                    </button>
                </div>
            </h1>

            <div id="add-model-section">
                <input type="text" id="new-model-name" placeholder="Wpisz nazwę nowej modelki...">
                <button onclick="addModelToDb()" class="btn-action">Dodaj Modelkę do Bazy</button>
                <span id="add-model-status"></span>
            </div>

            <ul id="model-tree">
                <li class="loader">Ładowanie listy modeli...</li>
            </ul>
        </div>

        <div id="test_ai_titles" class="tab-content <?php echo ($active_tab === 'test_ai_titles') ? 'active' : ''; ?>">
             <h1>Testowanie i Porównywanie Tytułów AI</h1>
            <div class="filters">
                <label for="model-filter-test-ai">Modelka:</label>
                <select id="model-filter-test-ai">
                    <option value="">-- Wszystkie --</option>
                    <?php foreach ($models_for_filter_tab2 as $model_filter_item): ?>
                        <option value="<?php echo htmlspecialchars($model_filter_item); ?>"><?php echo htmlspecialchars($model_filter_item); ?></option>
                    <?php endforeach; ?>
                </select>
                <label for="status-filter-test-ai">Status:</label>
                <select id="status-filter-test-ai">
                    <option value="">-- Wszystkie --</option>
                    <?php foreach ($statuses_for_filter_tab2 as $status_filter_item): ?>
                        <option value="<?php echo htmlspecialchars($status_filter_item); ?>"><?php echo htmlspecialchars(str_replace('_', ' ', $status_filter_item)); ?></option>
                    <?php endforeach; ?>
                </select>
                <label for="items-per-page-test-ai">Na stronę:</label>
                <select id="items-per-page-test-ai">
                    <option value="100">100</option>
                    <option value="200" selected>200</option>
                    <option value="300">300</option>
                    <option value="400">400</option>
                </select>
                <button id="load-data-btn-test-ai">Załaduj Dane</button>
                <div class="sort-controls">
                    <label for="sort-by-filter-test-ai">Sortuj wg:</label>
                    <select id="sort-by-filter-test-ai">
                        <option value="model_gallery">Modelka, Galeria</option>
                        <option value="original_title">Tytuł Oryginalny</option>
                        <option value="determined_title">Tytuł AI (Prod.)</option>
                        <option value="test_ai_title">Tytuł AI (Test)</option>
                        <option value="status">Status</option>
                    </select>
                    <select id="sort-order-filter-test-ai">
                        <option value="ASC">Rosnąco</option>
                        <option value="DESC">Malejąco</option>
                    </select>
                </div>
                <span id="polling-indicator-test-ai" class="polling-indicator" title="Sprawdzanie statusu AI"></span>
            </div>

            <div class="actions">
                <button id="select-all-btn-test-ai">Zaznacz/Odznacz Wszystkie</button>
                <button id="run-test-ai-selected-btn-test-ai" class="ai-btn" disabled>Uruchom Test AI dla Zaznaczonych</button>
                <button id="rename-selected-btn-test-ai" class="action-btn" disabled>Zapisz Tytuł Prod. i Zmień Nazwę Zaznaczonych</button>
                <span id="selection-status-test-ai" style="margin-left: auto;">Zaznaczono: 0</span>
            </div>

            <div id="table-container-test-ai">
                <table>
                    <thead>
                        <tr>
                            <th><input type="checkbox" id="select-all-header-test-ai"></th>
                            <th>ID Galerii</th>
                            <th>Modelka</th>
                            <th>Oryginalny Tytuł</th>
                            <th>Tytuł AI (Prod.)</th>
                            <th>Tytuł AI (Test)</th>
                            <th>Folder</th>
                            <th>Status</th>
                            <th>Akcje</th>
                        </tr>
                    </thead>
                    <tbody id="galleries-test-ai-tbody">
                        <tr><td colspan="9" class="loader">Wybierz filtry i kliknij 'Załaduj Dane'.</td></tr>
                    </tbody>
                </table>
            </div>
            
            <div class="pagination">
                <button id="prev-page-btn-test-ai" class="neutral-btn" disabled>Poprzednia</button>
                <span id="page-info-test-ai">Strona - z -</span>
                <button id="next-page-btn-test-ai" class="neutral-btn" disabled>Następna</button>
            </div>
        </div>

        <div id="ollama_prompts_settings" class="tab-content <?php echo ($active_tab === 'ollama_prompts_settings') ? 'active' : ''; ?>">
             <h1>Ustawienia AI</h1>
            <div class="global-ai-settings">
                <h3>Ustawienia Globalne AI</h3>
                <div class="form-group">
                    <label for="ollama-url">URL Serwera Ollama:</label>
                    <input type="text" id="ollama-url" placeholder="http://localhost:11434" title="Pełny adres URL serwera Ollama, np. http://192.168.1.100:11434">
                </div>
                <div class="form-group">
                    <label for="ollama-default-model">Domyślna Nazwa Modelu:</label>
                    <input type="text" id="ollama-default-model" placeholder="llama3:latest" title="Model używany, gdy nie jest określony w konfiguracji promptu, np. llama3:latest">
                </div>
                <button onclick="saveGlobalAiSettings()" class="neutral-btn">Zapisz Ustawienia Globalne</button>
            </div>
            
            <h2>Ustawienia Promptów AI (Ollama)</h2>
            <div id="prompt-configs-container-ollama">
                <p class="loader">Ładowanie konfiguracji promptów...</p>
            </div>
            <div class="actions" style="justify-content: flex-end; margin-top: 20px;">
                <button id="promote-test-btn-ollama" class="action-btn">Promuj Konfigurację Testową na Produkcyjną</button>
            </div>
        </div>
    </div>
</div>

<div id="queue-modal" class="modal">
    <div class="modal-content">
        <span class="close-button" onclick="closeQueueModal()">&times;</span>
        <h2>Zarządzaj Kolejką Priorytetową</h2>
        <p>Przeciągnij i upuść elementy, aby zmienić ich kolejność. Zmiany zostaną zapisane po kliknięciu przycisku 'Zapisz'.</p>
        <ul id="priority-queue-list">
            <li>Ładowanie kolejki...</li>
        </ul>
        <button onclick="saveQueueOrder()" class="btn-action">Zapisz Kolejność</button>
        <button onclick="fetchAndDisplayQueue()" class="btn-action">Odśwież Listę</button>
        <span id="queue-status"></span>
    </div>
</div>

<div id="image-viewer-modal" class="image-viewer-modal">
    <div class="image-viewer-modal-content">
        <span class="image-viewer-close-button" onclick="closeImageViewerModal()">&times;</span>
        <h3 id="image-viewer-title">Nazwa Galerii</h3>
        <div id="image-viewer-status">Ładowanie plików...</div>
        <div id="image-viewer-files" class="image-grid"></div>
    </div>
</div>

<div id="search-modal" class="modal">
    <div class="modal-content">
        <span class="close-button" onclick="closeSearchModal()">&times;</span>
        <h2>Wyszukaj Galerie</h2>
        <div>
            <input type="text" id="search-input" placeholder="Wpisz frazę...">
            <button onclick="performGallerySearch()" class="btn-action">Szukaj</button>
        </div>
        <div id="search-modal-status" style="margin-top:10px; font-size:0.9em;"></div>
        <ul id="search-modal-results" style="margin-top:15px; max-height: 60vh; overflow-y:auto;">
        </ul>
    </div>
</div>

<div id="lightbox-overlay" style="display:none;">
    <span class="lightbox-close" onclick="closeLightbox()">&times;</span>
    <div class="lightbox-nav prev" onclick="changeLightboxImage(-1)">&#10094;</div>
    <img id="lightbox-image" src="" alt="Lightbox Image">
    <div class="lightbox-nav next" onclick="changeLightboxImage(1)">&#10095;</div>
    <div id="lightbox-caption"></div>
</div>

<div id="toast">Wiadomość</div>

<script>
    // --- Global JS ---
    const API_URL_INDEX = 'api.php'; 
    const toastDivGlobal = document.getElementById('toast');

    // --- Zmienne dla Lightbox ---
    let lightboxVisible = false;
    let lightboxImages = [];
    let currentLightboxIndex = 0;

    function showGlobalToast(message, isError = false, duration = 3500) {
        if (!toastDivGlobal) return;
        toastDivGlobal.textContent = message;
        toastDivGlobal.style.backgroundColor = isError ? '#d9534f' : '#5cb85c';
        toastDivGlobal.classList.add('show');
        setTimeout(() => { toastDivGlobal.classList.remove('show'); }, duration);
    }

    function openTab(evt, tabId) {
        let i, tabcontent, tabbuttons;
        tabcontent = document.getElementsByClassName("tab-content");
        for (i = 0; i < tabcontent.length; i++) {
            tabcontent[i].style.display = "none";
        }
        tabbuttons = document.getElementsByClassName("tab-button");
        for (i = 0; i < tabbuttons.length; i++) {
            tabbuttons[i].className = tabbuttons[i].className.replace(" active", "");
        }
        const currentTabElement = document.getElementById(tabId);
        if (currentTabElement) {
            currentTabElement.style.display = "block";
            currentTabElement.classList.add("active");
        }
        
        let clickedButton = null;
        if (evt && evt.currentTarget) { 
            clickedButton = evt.currentTarget;
        } else { 
            const buttons = document.getElementsByClassName('tab-button');
            for (let j = 0; j < buttons.length; j++) {
                if (buttons[j].getAttribute('onclick') && buttons[j].getAttribute('onclick').includes("'" + tabId + "'")) {
                    clickedButton = buttons[j];
                    break;
                }
            }
        }
        if(clickedButton) clickedButton.className += " active";
        
        const url = new URL(window.location);
        url.searchParams.set('tab', tabId);
        if (tabId !== 'status_galleries') url.searchParams.delete('page_status');
        if (tabId !== 'test_ai_titles') url.searchParams.delete('page_test_ai');

        history.pushState({}, '', url);

        if (tabId === 'status_galleries') {
            initStatusTab();
        } else if (tabId === 'test_ai_titles') {
            startPollingTestAi(); 
        } else {
            stopPollingTestAi(); 
            stopStatusPolling();
        }

        if (tabId === 'ollama_prompts_settings') {
            loadPromptConfigsOllama();
            loadGlobalAiSettings();
        }
    }

    // --- JS for Tab 1: Status Galleries ---
    let statusTabInitialized = false;
    let statusPollingInterval = null;
    let aggregateRefreshTimeout = null;
    let activeGalleryIdForUI = null;
    let activeModelNameSanitizedForUI = null;
    let currentlyViewedGalleryId = null;
    let statusDiv, modelTreeUl, imageViewerModal, imageViewerTitle, imageViewerFilesDiv, imageViewerStatusDiv;
    let searchModal, searchInput, searchModalResultsUl, searchModalStatusDiv;
    let draggedItem = null;
    let queueDataCache = [];

    function initStatusTab() {
        if (statusTabInitialized) {
            startStatusPolling();
            return;
        }
        statusDiv = document.getElementById('current-status');
        modelTreeUl = document.getElementById('model-tree');
        imageViewerModal = document.getElementById('image-viewer-modal');
        imageViewerTitle = document.getElementById('image-viewer-title');
        imageViewerFilesDiv = document.getElementById('image-viewer-files');
        imageViewerStatusDiv = document.getElementById('image-viewer-status');
        searchModal = document.getElementById('search-modal');
        searchInput = document.getElementById('search-input');
        searchModalResultsUl = document.getElementById('search-modal-results');
        searchModalStatusDiv = document.getElementById('search-modal-status');
        if (searchInput) {
            searchInput.addEventListener('keypress', function(event) {
                if (event.key === 'Enter') {
                    event.preventDefault(); 
                    performGallerySearch();
                }
            });
        }
        statusTabInitialized = true;
        startStatusPolling();
        fetchAggregateDataAndUpdateModels(true);
        fetchAndDisplayQueue();
    }

    function startStatusPolling() {
        if (statusPollingInterval) clearInterval(statusPollingInterval);
        updateStatus();
        statusPollingInterval = setInterval(updateStatus, 2800);
        setInterval(() => fetchAggregateDataAndUpdateModels(false), 25000);
        setInterval(fetchAndDisplayQueue, 30000);
    }

    function stopStatusPolling() {
        if (statusPollingInterval) {
            clearInterval(statusPollingInterval);
            statusPollingInterval = null;
        }
    }

    function pySanitizeForQuerySelector(name) {
        if (typeof name !== 'string') name = String(name);
        let sanitized = name.trim();
        sanitized = sanitized.replace(/[<>:"\/\\|?*\x00-\x1F\t\n\r\f\v]/g, '_');
        sanitized = sanitized.replace(/\s+/g, '_'); 
        sanitized = sanitized.replace(/[^a-zA-Z0-9_.-]/g, ''); 
        sanitized = sanitized.trim('_.-');
        if (sanitized.length > 100) sanitized = sanitized.substring(0, 100); 
        return sanitized ? sanitized : "fallback_sanitized_name";
    }

    function showToast(message, isError = false) {
        const toastDiv = document.getElementById('toast-status') || toastDivGlobal;
        if (!toastDiv) return;
        toastDiv.textContent = message;
        toastDiv.style.backgroundColor = isError ? '#dc3545' : '#212529';
        toastDiv.classList.add('show');
        setTimeout(() => { toastDiv.classList.remove('show'); }, 3500);
    }

    function prioritizeItem(type, id) {
        showToast(`Wysyłanie żądania priorytetu dla ${type}: ${id}...`);
        fetch(`${API_URL_INDEX}?action=prioritize&type=${encodeURIComponent(type)}&id=${encodeURIComponent(id)}&_=${new Date().getTime()}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showToast(`${data.message || 'Dodano do kolejki priorytetowej.'}`);
                    fetchAndDisplayQueue(); 
                } else {
                    showToast(`Błąd: ${data.message || 'Nie udało się dodać do kolejki.'}`, true);
                }
            })
            .catch(error => {
                showToast(`Błąd sieciowy lub serwera: ${error.message}`, true);
            });
    }
    
    function addModelToDb() { 
        const modelNameInput = document.getElementById('new-model-name');
        const statusSpan = document.getElementById('add-model-status');
        const modelName = modelNameInput.value.trim();
        if (!modelName) { showToast('Wpisz nazwę modelki.', true); return; }
        statusSpan.textContent = 'Dodawanie do bazy...';
        fetch(`${API_URL_INDEX}?action=add_model&model_name=${encodeURIComponent(modelName)}&_=${new Date().getTime()}`)
            .then(response => response.json())
            .then(data => {
                showToast(data.message, !data.success);
                statusSpan.textContent = '';
                if (data.success) {
                    modelNameInput.value = '';
                    fetchAggregateDataAndUpdateModels(true); 
                }
            })
            .catch(error => {
                showToast('Błąd sieciowy podczas dodawania modelki do bazy.', true);
                statusSpan.textContent = '';
            });
    }

    function updateGalleryUI(galleryId, downloaded, expected, scanSessionFound, titleFromServer = null, urlFromServer = null, folderFromServer = null) {
        const galleryLi = document.getElementById('gallery_li_' + galleryId);
        if (!galleryLi) return; 
        const statusSpan = galleryLi.querySelector('.gallery-status');
        const progressBar = galleryLi.querySelector('.progress-bar');
        const progressContainer = galleryLi.querySelector('.progress-bar-container');
        const newlyFoundSpan = galleryLi.querySelector('.newly-found-count');
        const linkA = galleryLi.querySelector('.gallery-link a');
        if (!statusSpan || !progressBar || !progressContainer || !newlyFoundSpan || !linkA) return;
        const expectedVal = (expected !== null && expected !== undefined) ? parseInt(expected, 10) : (galleryLi.dataset.expected !== '?' ? parseInt(galleryLi.dataset.expected, 10) : '?');
        const expectedText = (expectedVal === '?' || isNaN(expectedVal)) ? '?' : expectedVal;
        let currentDownloadedVal = (downloaded !== null && downloaded !== undefined && !isNaN(parseInt(downloaded, 10))) ? parseInt(downloaded, 10) : (parseInt(galleryLi.dataset.downloaded, 10) || 0);
        galleryLi.dataset.downloaded = currentDownloadedVal;
        if (expectedText !== '?') galleryLi.dataset.expected = expectedText;
        if (titleFromServer && linkA.textContent !== titleFromServer) linkA.textContent = titleFromServer;
        if (urlFromServer && linkA.href !== urlFromServer) linkA.href = urlFromServer;
        if (folderFromServer && linkA.title !== `Folder: ${folderFromServer}`) linkA.title = `Folder: ${folderFromServer}`;
        if (scanSessionFound !== null && scanSessionFound !== undefined && scanSessionFound > 0) {
            newlyFoundSpan.textContent = 'Znaleziono: ' + scanSessionFound;
            newlyFoundSpan.style.display = 'inline';
        } else {
            newlyFoundSpan.style.display = 'none';
        }
        let statusText = 'D: ' + currentDownloadedVal + '/' + expectedText;
        let progress = 0;
        let colorClass = 'red';
        if (expectedText !== '?') {
            if (expectedVal > 0) progress = (currentDownloadedVal / expectedVal * 100);
            else if (expectedVal === 0 && currentDownloadedVal === 0) progress = 100;
            colorClass = (progress >= 100 || (expectedVal === 0 && currentDownloadedVal === 0)) ? 'green' : (currentDownloadedVal > 0 ? 'orange' : 'red');
        } else { 
            colorClass = currentDownloadedVal > 0 ? 'orange' : 'red';
            statusText = `D: ${currentDownloadedVal}/?`;
        }
        statusSpan.textContent = statusText;
        statusSpan.className = 'gallery-status ' + colorClass;
        const progressPercent = Math.min(100, Math.max(0, progress));
        progressBar.style.width = progressPercent.toFixed(1) + '%';
        progressBar.textContent = progressPercent.toFixed(0) + '%';
        progressBar.className = 'progress-bar ' + colorClass;
        progressContainer.title = `Pobrano: ${currentDownloadedVal}/${expectedText} (${progressPercent.toFixed(1)}%)`;
    }

    function updateStatus() {
        if (!statusDiv) return;
        fetch(`${API_URL_INDEX}?action=get_status&_=${new Date().getTime()}`)
            .then(response => response.json())
            .then(data => {
                if (!data || typeof data.timestamp === 'undefined') {
                   statusDiv.textContent = 'Oczekiwanie na status ze skryptu Python...';
                   statusDiv.style.backgroundColor = '#fff8dc'; 
                   return;
                }
                statusDiv.textContent = '[' + data.timestamp + '] ' + data.message +
                                        (data.current_model ? ' | Model: ' + data.current_model : '') +
                                        (data.current_gallery_title ? ' | Galeria: ' + data.current_gallery_title : '');
                statusDiv.style.backgroundColor = data.is_processing ? '#e0f7fa' : '#fff'; 
                const galleryThatWasProcessing = activeGalleryIdForUI;
                const modelSanitizedThatWasProcessing = activeModelNameSanitizedForUI;
                const currentProcessingModelOriginal = data.current_model;
                const currentProcessingModelSanitized = currentProcessingModelOriginal ? pySanitizeForQuerySelector(currentProcessingModelOriginal) : null;
                if (modelSanitizedThatWasProcessing && modelSanitizedThatWasProcessing !== currentProcessingModelSanitized) {
                    const oldModelLi = document.querySelector(`.model-li[data-model-name="${modelSanitizedThatWasProcessing}"]`);
                    if (oldModelLi) oldModelLi.classList.remove('model-processing');
                }
                if (currentProcessingModelSanitized) {
                    const currentModelLi = document.querySelector(`.model-li[data-model-name="${currentProcessingModelSanitized}"]`);
                    if (currentModelLi) {
                        currentModelLi.classList.remove('model-complete', 'model-partial'); 
                        currentModelLi.classList.add('model-processing');
                    }
                }
                activeModelNameSanitizedForUI = currentProcessingModelSanitized;
                if (data.is_processing && data.current_gallery_id) {
                    activeGalleryIdForUI = data.current_gallery_id;
                    if (galleryThatWasProcessing && galleryThatWasProcessing !== activeGalleryIdForUI) {
                        const prevGalleryLi = document.getElementById('gallery_li_' + galleryThatWasProcessing);
                        if (prevGalleryLi) prevGalleryLi.classList.remove('processing');
                    }
                    const currentGalleryLi = document.getElementById('gallery_li_' + activeGalleryIdForUI);
                    if (currentGalleryLi) {
                         currentGalleryLi.classList.add('processing');
                         const parentModelLi = currentGalleryLi.closest('li.model-li');
                         if(parentModelLi){
                             const nestedUl = parentModelLi.querySelector('ul.nested');
                             const toggle = parentModelLi.querySelector('.toggle');
                             if(nestedUl && !nestedUl.classList.contains('active')){
                                 nestedUl.classList.add('active');
                                 if(toggle) toggle.textContent = '−';
                             }
                         }
                    }
                    updateGalleryUI(activeGalleryIdForUI, data.current_download_count, data.current_expected_count, data.scan_session_found_count);
                    if (imageViewerModal && imageViewerModal.style.display === 'block' && currentlyViewedGalleryId === activeGalleryIdForUI) {
                        setTimeout(() => {
                            if(imageViewerTitle.textContent.includes(data.current_gallery_title) || imageViewerTitle.textContent.includes(activeGalleryIdForUI)){
                                fetchGalleryFilesForModal(currentlyViewedGalleryId, data.current_gallery_title || activeGalleryIdForUI);
                            }
                        }, 1000); 
                    }
                } else if (!data.is_processing && galleryThatWasProcessing) { 
                    const finishedGalleryLi = document.getElementById('gallery_li_' + galleryThatWasProcessing);
                    if (finishedGalleryLi) finishedGalleryLi.classList.remove('processing');
                    updateGalleryUI(galleryThatWasProcessing, data.current_download_count, data.current_expected_count, null);
                    activeGalleryIdForUI = null; 
                    triggerDelayedAggregateRefresh(); 
                } else if (!data.is_processing && modelSanitizedThatWasProcessing && !currentProcessingModelSanitized) {
                    const oldModelLi = document.querySelector(`.model-li[data-model-name="${modelSanitizedThatWasProcessing}"]`);
                    if (oldModelLi) oldModelLi.classList.remove('model-processing');
                    activeModelNameSanitizedForUI = null;
                    triggerDelayedAggregateRefresh();
                }
            })
            .catch(error => { 
                if (statusDiv) { 
                    statusDiv.textContent = 'Błąd odświeżania statusu: ' + error.message; 
                    statusDiv.style.backgroundColor = '#ffcdd2'; 
                }
            }); 
    }

    function triggerDelayedAggregateRefresh(delay = 2500) { 
        if (aggregateRefreshTimeout) clearTimeout(aggregateRefreshTimeout);
        aggregateRefreshTimeout = setTimeout(() => {
            fetchAggregateDataAndUpdateModels(false); 
        }, delay);
    }

    function fetchAggregateDataAndUpdateModels(forceFullRender = false) {
        if (!modelTreeUl) return;
        fetch(`${API_URL_INDEX}?action=get_aggregate&_=${new Date().getTime()}`)
            .then(response => response.json())
            .then(aggregateData => {
                if (aggregateData && aggregateData.models && typeof aggregateData.models === 'object') { 
                    const modelsData = aggregateData.models;
                    const modelNamesSorted = Object.keys(modelsData).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
                    if(forceFullRender) modelTreeUl.innerHTML = ''; 
                    if (modelNamesSorted.length === 0 && forceFullRender) { 
                         modelTreeUl.innerHTML = '<li>Brak modeli na liście lub w bazie danych.</li>';
                         return; 
                    } else if (forceFullRender && modelTreeUl.querySelector('.loader')) { 
                         modelTreeUl.querySelector('.loader').remove();
                    }
                    modelNamesSorted.forEach(modelNameOriginal => {
                        const modelData = modelsData[modelNameOriginal];
                        if (typeof modelData !== 'object' || modelData === null) return; 
                        const sanitizedModelName = modelData.sanitized_name || pySanitizeForQuerySelector(modelNameOriginal);
                        let modelLiElement = document.querySelector(`.model-li[data-model-name="${sanitizedModelName}"]`);
                        let nestedUl;
                        if (!modelLiElement) { 
                            modelLiElement = document.createElement('li');
                            modelLiElement.className = 'model-li';
                            modelLiElement.dataset.modelName = sanitizedModelName;
                            const modelHeader = document.createElement('div');
                            modelHeader.className = 'model-header';
                            const escapedModelName = modelNameOriginal.replace(/'/g, "\\'");
                            modelHeader.innerHTML = `
                                <span class="toggle">+</span>
                                <span class="model-name">${modelNameOriginal}</span>
                                <div class="progress-bar-container">
                                    <div class="progress-bar"></div>
                                </div>
                                <button class="btn-action" onclick="prioritizeItem('scan_model', '${escapedModelName}')" title="Skanuj, aktualizuj i dodaj brakujące galerie do kolejki pobierania">Uzupełnij Model</button>
                                <button class="btn-action" onclick="prioritizeItem('scan_model_refresh_only', '${escapedModelName}')" title="Tylko skanuj i aktualizuj opisy/liczniki">Odśwież Opisy</button>
                            `;
                            nestedUl = document.createElement('ul');
                            nestedUl.className = 'nested';
                            modelLiElement.appendChild(modelHeader);
                            modelLiElement.appendChild(nestedUl);
                            const loaderLi = modelTreeUl.querySelector('.loader');
                            if(loaderLi) modelTreeUl.insertBefore(modelLiElement, loaderLi);
                            else modelTreeUl.appendChild(modelLiElement);
                            modelHeader.querySelector('.toggle').addEventListener('click', function() {
                                nestedUl.classList.toggle('active');
                                this.textContent = nestedUl.classList.contains('active') ? '−' : '+';
                                if (nestedUl.classList.contains('active') && !nestedUl.dataset.galleriesLoadedOnce) { 
                                    fetchAggregateDataAndUpdateModels(false); 
                                }
                            });
                        } else {
                            nestedUl = modelLiElement.querySelector('ul.nested');
                        }
                        const completedInModel = modelData.completed_galleries || 0;
                        const totalInModel = modelData.total_galleries || 0;
                        const modelProgressPercent = modelData.model_progress || 0;
                        modelLiElement.querySelector('.model-name').textContent = `${modelNameOriginal} (${completedInModel}/${totalInModel})`;
                        const modelProgressBarDiv = modelLiElement.querySelector('.progress-bar');
                        if (modelProgressBarDiv) { 
                            modelProgressBarDiv.style.width = `${modelProgressPercent.toFixed(1)}%`;
                            modelProgressBarDiv.textContent = `${modelProgressPercent.toFixed(0)}%`;
                        }
                        const progressBarContainer = modelLiElement.querySelector('.progress-bar-container');
                        if(progressBarContainer) progressBarContainer.title = `${modelProgressPercent.toFixed(1)}% ukończonych galerii`;
                        modelLiElement.classList.remove('model-complete', 'model-partial', 'model-processing');
                        if (modelLiElement.dataset.modelName === activeModelNameSanitizedForUI) {
                             modelLiElement.classList.add('model-processing');
                        } else if (totalInModel > 0 && completedInModel === totalInModel) {
                            modelLiElement.classList.add('model-complete');
                        } else if (completedInModel > 0 || (totalInModel > 0 && completedInModel < totalInModel)) { 
                            modelLiElement.classList.add('model-partial');
                        }
                        if (nestedUl && (nestedUl.classList.contains('active') || forceFullRender)) {
                            if(forceFullRender || (nestedUl.classList.contains('active') && !nestedUl.dataset.galleriesLoadedOnce)) {
                                nestedUl.innerHTML = ''; 
                            }
                            const galleriesFromServer = modelData.galleries || {};
                            const galleryIdsSorted = Object.keys(galleriesFromServer).sort((a,b) => {
                                const titleA = (galleriesFromServer[a] && galleriesFromServer[a].title) ? galleriesFromServer[a].title : a;
                                const titleB = (galleriesFromServer[b] && galleriesFromServer[b].title) ? galleriesFromServer[b].title : b;
                                return titleA.toLowerCase().localeCompare(titleB.toLowerCase());
                            });
                            galleryIdsSorted.forEach(galleryId => {
                                const gData = galleriesFromServer[galleryId];
                                if (typeof gData !== 'object' || gData === null) return;
                                let galleryLi = document.getElementById('gallery_li_' + galleryId);
                                const escapedGalleryIdForJS = galleryId.replace(/'/g, "\\'");
                                const escapedGalleryTitleForJS = (gData.title || galleryId).replace(/'/g, "\\'");
                                
                                const isDisabled = gData.is_disabled || false;
                                const disabledClass = isDisabled ? 'disabled' : '';
                                const toggleBtnClass = isDisabled ? 'disabled' : 'enabled';
                                const toggleBtnText = isDisabled ? 'Włącz' : 'Wyłącz';

                                if (!galleryLi) {
                                    galleryLi = document.createElement('li');
                                    galleryLi.id = 'gallery_li_' + galleryId;
                                    galleryLi.innerHTML = `
                                        <div class="gallery-main-info">
                                            <span class="gallery-link">
                                                <span class="spinner"></span>
                                                <a href="${gData.url || '#'}" target="_blank" title="Folder: ${gData.folder || 'Brak'}">${gData.title || galleryId}</a>
                                            </span>
                                            <div class="gallery-controls">
                                                <span class="newly-found-count"></span>
                                                <div class="progress-bar-container">
                                                    <div class="progress-bar"></div>
                                                </div>
                                                <span class="gallery-status"></span>
                                                <button class="btn-action btn-toggle-disabled ${toggleBtnClass}" onclick="toggleGalleryDisabledStatus('${escapedGalleryIdForJS}')">${toggleBtnText}</button>
                                                <button class="btn-action btn-view-gallery" onclick="showGalleryFiles('${escapedGalleryIdForJS}', '${escapedGalleryTitleForJS}')">Pliki</button>
                                                <button class="btn-action completed-action" onclick="markGalleryAsCompleted('${escapedGalleryIdForJS}', '${escapedGalleryTitleForJS}')">Ukończ</button>
                                                <button class="btn-action" onclick="prioritizeItem('gallery', '${escapedGalleryIdForJS}')">Uzupełnij</button>
                                                <a href="${gData.url || '#'}" target="_blank" class="btn-action">Źródło</a>
                                            </div>
                                        </div>
                                        <div class="gallery-thumbnails" id="thumbnails-for-${galleryId}"></div>
                                    `;
                                    nestedUl.appendChild(galleryLi);
                                }
                                
                                galleryLi.className = `gallery-li ${disabledClass}`;
                                if (galleryId === activeGalleryIdForUI && statusDiv && statusDiv.style.backgroundColor.includes('e0f7fa')) { 
                                     galleryLi.classList.add('processing');
                                } else {
                                     galleryLi.classList.remove('processing');
                                }
                                updateGalleryUI(galleryId, gData.downloaded, gData.expected, null, gData.title, gData.url, gData.folder);

                                // Renderowanie miniaturek
                                const thumbnailsDiv = galleryLi.querySelector(`#thumbnails-for-${galleryId}`);
                                if (thumbnailsDiv && gData.thumbnails && gData.thumbnails.length > 0 && thumbnailsDiv.childElementCount === 0) {
                                    gData.thumbnails.forEach(filename => {
                                        const img = document.createElement('img');
                                        img.src = `${gData.web_path_segment}/${filename}`;
                                        img.loading = 'lazy';
                                        img.alt = filename;
                                        img.title = filename;
                                        img.addEventListener('click', () => showGalleryFiles(galleryId, escapedGalleryTitleForJS));
                                        thumbnailsDiv.appendChild(img);
                                    });
                                }
                            });
                             nestedUl.dataset.galleriesLoadedOnce = "true"; 
                        }
                    });
                    const loaderLiFinal = modelTreeUl.querySelector('.loader');
                    if (loaderLiFinal) loaderLiFinal.remove();
                    const lastUpdateSpan = document.getElementById("last-aggregate-update-time");
                    if(lastUpdateSpan) lastUpdateSpan.textContent = `(Dane z DB: ${new Date().toLocaleTimeString()})`;
                } else {
                     if(forceFullRender) modelTreeUl.innerHTML = '<li>Brak danych modeli lub nieprawidłowa odpowiedź z API.</li>'; 
                }
            })
            .catch(error => {
                 if(forceFullRender && modelTreeUl) modelTreeUl.innerHTML = '<li>Wystąpił błąd podczas ładowania danych modeli.</li>';
                 if (statusDiv) { 
                    statusDiv.textContent = 'Błąd ładowania danych modeli: ' + error.message;
                    statusDiv.style.backgroundColor = '#ffcdd2';
                 }
            });
    }

    function toggleGalleryDisabledStatus(galleryId) {
        showGlobalToast(`Przełączanie statusu galerii ${galleryId}...`);
        fetch(`${API_URL_INDEX}?action=toggle_gallery_disabled_status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gallery_id: galleryId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showGlobalToast(data.message || 'Status galerii zaktualizowany.');
                fetchAggregateDataAndUpdateModels(false);
            } else {
                showGlobalToast(`Błąd: ${data.message || 'Nie udało się zaktualizować statusu.'}`, true);
            }
        })
        .catch(error => {
            showGlobalToast(`Błąd sieciowy: ${error.message}`, true);
        });
    }

    function markGalleryAsCompleted(galleryId, galleryTitle) {
        if (!confirm(`Czy na pewno chcesz oznaczyć galerię "${galleryTitle}" jako ukończoną?`)) return;
        showToast(`Oznaczanie galerii "${galleryTitle}" jako ukończonej...`);
        fetch(`${API_URL_INDEX}?action=mark_gallery_completed`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gallery_id: galleryId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast(data.message || `Galeria "${galleryTitle}" oznaczona jako ukończona.`);
                fetchAggregateDataAndUpdateModels(false);
            } else {
                showToast(`Błąd: ${data.message || 'Nie udało się oznaczyć galerii jako ukończonej.'}`, true);
            }
        })
        .catch(error => {
            showToast(`Błąd sieciowy lub serwera: ${error.message}`, true);
        });
    }

    function showGalleryFiles(galleryId, galleryTitle) {
        currentlyViewedGalleryId = galleryId;
        imageViewerTitle.textContent = "Pliki dla: " + galleryTitle;
        imageViewerFilesDiv.innerHTML = ''; 
        imageViewerStatusDiv.textContent = 'Ładowanie plików...';
        imageViewerModal.style.display = 'block';
        fetchGalleryFilesForModal(galleryId, galleryTitle);
    }

    function closeImageViewerModal() {
        imageViewerModal.style.display = 'none';
        imageViewerFilesDiv.innerHTML = '';
        currentlyViewedGalleryId = null;
    }

    function fetchGalleryFilesForModal(galleryId, galleryTitle) { 
        imageViewerStatusDiv.textContent = 'Pobieranie listy plików...';
        fetch(`${API_URL_INDEX}?action=get_gallery_files&gallery_id=${encodeURIComponent(galleryId)}&_=${new Date().getTime()}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    imageViewerFilesDiv.innerHTML = ''; 
                    if (data.files && data.files.length > 0) {
                        const allImageUrls = data.files.map(filename => `${data.web_path_segment}/${filename}`);
                        imageViewerStatusDiv.textContent = `Znaleziono ${data.files.length} plików.`;
                        allImageUrls.forEach((url, index) => {
                            const img = document.createElement('img');
                            img.src = url; 
                            img.alt = data.files[index];
                            img.title = data.files[index];
                            img.loading = 'lazy';
                            img.onerror = function() { this.alt='Błąd ładowania'; this.style.border='1px solid red';};
                            img.onclick = () => openLightbox(allImageUrls, index);
                            imageViewerFilesDiv.appendChild(img);
                        });
                    } else {
                        imageViewerStatusDiv.textContent = 'Brak plików w tej galerii lub folder nie istnieje/jest pusty.';
                    }
                } else {
                    imageViewerStatusDiv.textContent = `Błąd: ${data.message || 'Nie udało się pobrać listy plików.'}`;
                }
            })
            .catch(error => {
                imageViewerStatusDiv.textContent = `Błąd sieciowy: ${error.message}`;
            });
    }

    function openSearchModal() {
        searchInput.value = '';
        searchModalResultsUl.innerHTML = '';
        searchModalStatusDiv.textContent = 'Wpisz frazę i kliknij Szukaj.';
        searchModal.style.display = 'block';
        searchInput.focus();
    }

    function closeSearchModal() {
        searchModal.style.display = 'none';
    }

    function performGallerySearch() {
        const searchTerm = searchInput.value.trim();
        if (searchTerm.length < 2) { searchModalStatusDiv.textContent = 'Wpisz przynajmniej 2 znaki.'; return; }
        searchModalStatusDiv.textContent = 'Szukam...';
        searchModalResultsUl.innerHTML = '';
        fetch(`${API_URL_INDEX}?action=search_galleries&term=${encodeURIComponent(searchTerm)}&_=${new Date().getTime()}`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.galleries) {
                    if (data.galleries.length > 0) {
                        searchModalStatusDiv.textContent = `Znaleziono ${data.galleries.length} galerii.`;
                        data.galleries.forEach(gData => {
                            const li = document.createElement('li');
                            li.className = 'gallery-li'; 
                            const escapedGalleryIdForJS = gData.gallery_id.replace(/'/g, "\\'");
                            const escapedGalleryTitleForJS = (gData.title || gData.gallery_id).replace(/'/g, "\\'");
                            li.innerHTML = `
                                <span class="gallery-link" style="flex-direction: column; align-items: flex-start;">
                                    <a href="${gData.url || '#'}" target="_blank" title="Model: ${gData.model_name || '?'}">${gData.title || gData.gallery_id}</a>
                                    <small style="color: #666;">Model: ${gData.model_name || '?'}</small>
                                </span>
                                <div class="gallery-controls">
                                    <span class="gallery-status ${gData.status_color}">${gData.downloaded}/${gData.expected !== null ? gData.expected : '?'}</span>
                                    <button class="btn-action" onclick="showGalleryFiles('${escapedGalleryIdForJS}', '${escapedGalleryTitleForJS}')">Pliki</button>
                                    <button class="btn-action completed-action" onclick="markGalleryAsCompleted('${escapedGalleryIdForJS}', '${escapedGalleryTitleForJS}')">Ukończ</button>
                                    <button class="btn-action" onclick="prioritizeItem('gallery', '${escapedGalleryIdForJS}')">Uzupełnij</button>
                                </div>
                            `;
                            searchModalResultsUl.appendChild(li);
                        });
                    } else {
                        searchModalStatusDiv.textContent = 'Nie znaleziono galerii pasujących do wyszukiwania.';
                    }
                } else {
                    searchModalStatusDiv.textContent = `Błąd wyszukiwania: ${data.message || 'Nieznany błąd.'}`;
                }
            })
            .catch(error => {
                searchModalStatusDiv.textContent = `Błąd sieciowy: ${error.message}`;
            });
    }

    function refreshAllEmptyDescriptions() {
        showToast('Wysyłanie żądania odświeżenia pustych opisów dla wszystkich modeli...');
        fetch(`${API_URL_INDEX}?action=refresh_empty_descriptions_all&_=${new Date().getTime()}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showToast(data.message || 'Zadania odświeżania dodane do kolejki.');
                    fetchAndDisplayQueue(); 
                } else {
                    showToast(`Błąd: ${data.message || 'Nie udało się dodać zadań.'}`, true);
                }
            })
            .catch(error => {
                showToast(`Błąd sieciowy: ${error.message}`, true);
            });
    }

    function refreshAllGalleriesLists() {
        showToast('Wysyłanie żądania odświeżenia list galerii dla wszystkich modeli (najpierw puste, potem istniejące)...');
        fetch(`${API_URL_INDEX}?action=refresh_all_galleries_lists&_=${new Date().getTime()}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showToast(data.message || 'Zadania odświeżania list galerii dodane do kolejki.');
                    fetchAndDisplayQueue(); 
                } else {
                    showToast(`Błąd: ${data.message || 'Nie udało się dodać zadań.'}`, true);
                }
            })
            .catch(error => {
                showToast(`Błąd sieciowy: ${error.message}`, true);
            });
    }

    function getQueueItemDisplay(item) {
        let display = `Typ: ${item.type}`;
        if ((item.type === 'scan_model' || item.type === 'scan_model_refresh_only') && typeof item.payload === 'string') {
            display += ` | Model: ${item.payload}`;
        } else if (item.type === 'gallery' && typeof item.payload === 'object' && item.payload !== null) {
            const galleryTitle = item.payload.title || item.payload.id || 'Nieznana galeria';
            const modelName = item.payload.model_name || '?';
            display += ` | Galeria: ${galleryTitle} (Model: ${modelName})`;
        } else if (item.payload !== undefined) { 
            display += ` | Dane: ${JSON.stringify(item.payload).substring(0, 50)}...`;
        } else {
            display += ' | Dane: (brak)';
        }
        return display;
    }

    function populateQueueList(queueFromServer) {
        queueDataCache = queueFromServer.map(item => ({ type: item.type, payload: item.payload, priority: item.priority }));
        const list = document.getElementById('priority-queue-list');
        list.innerHTML = ''; 
        if (queueDataCache.length === 0) { list.innerHTML = '<li>Kolejka jest pusta.</li>'; } 
        else {
            queueDataCache.forEach((item, index) => {
                const li = document.createElement('li');
                li.className = 'queue-item';
                li.draggable = true;
                li.dataset.index = index;
                li.addEventListener('dragstart', handleDragStart);
                li.addEventListener('dragover', handleDragOver);
                li.addEventListener('drop', handleDrop);
                li.addEventListener('dragend', handleDragEnd);
                const handle = document.createElement('span');
                handle.className = 'drag-handle';
                handle.textContent = '☰';
                li.appendChild(handle);
                const info = document.createElement('span');
                info.className = 'queue-item-info';
                info.textContent = getQueueItemDisplay(item);
                li.appendChild(info);
                const controls = document.createElement('div');
                controls.className = 'queue-item-controls';
                const removeBtn = document.createElement('button');
                removeBtn.textContent = 'Usuń';
                removeBtn.onclick = () => { queueDataCache.splice(index, 1); populateQueueList(queueDataCache); updateQueueCount(); };
                controls.appendChild(removeBtn);
                li.appendChild(controls);
                list.appendChild(li);
            });
        }
        updateQueueCount();
    }

    function updateQueueCount() {
        const queueCountSpan = document.getElementById('queue-count');
        if (queueCountSpan) queueCountSpan.textContent = queueDataCache.length;
    }

    function handleDragStart(e) {
        draggedItem = e.target.closest('.queue-item'); 
        if (!draggedItem) return;
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', draggedItem.dataset.index);
        setTimeout(() => draggedItem.classList.add('dragging'), 0);
    }

    function handleDragOver(e) {
        e.preventDefault();
        const target = e.target.closest('.queue-item');
        if (target && target !== draggedItem) {
            document.querySelectorAll('.queue-item.over').forEach(it => it.classList.remove('over'));
            target.classList.add('over');
        }
    }

    function handleDrop(e) {
        e.preventDefault();
        const target = e.target.closest('.queue-item');
        if (target && target !== draggedItem && draggedItem) {
            const fromIndex = parseInt(draggedItem.dataset.index, 10);
            const toIndex = parseInt(target.dataset.index, 10);
            const [movedItem] = queueDataCache.splice(fromIndex, 1);
            queueDataCache.splice(toIndex, 0, movedItem);
            populateQueueList(queueDataCache);
        }
        document.querySelectorAll('.queue-item.over').forEach(it => it.classList.remove('over'));
    }
    
    function handleDragEnd(e) {
        if(draggedItem) draggedItem.classList.remove('dragging');
        draggedItem = null;
        document.querySelectorAll('.queue-item.over').forEach(it => it.classList.remove('over'));
    }

    function fetchAndDisplayQueue() {
        fetch(`${API_URL_INDEX}?action=get_queue&_=${new Date().getTime()}`)
            .then(response => response.json())
            .then(data => populateQueueList(Array.isArray(data) ? data : []))
            .catch(error => {
                const list = document.getElementById('priority-queue-list');
                if (list) list.innerHTML = '<li>Błąd ładowania kolejki.</li>';
                updateQueueCount(); 
            });
    }

    function openQueueModal() {
        document.getElementById('queue-modal').style.display = 'block';
        fetchAndDisplayQueue(); 
    }

    function closeQueueModal() {
        document.getElementById('queue-modal').style.display = 'none';
        const statusSpan = document.getElementById('queue-status');
        if (statusSpan) statusSpan.textContent = '';
    }

    function saveQueueOrder() {
        const statusSpan = document.getElementById('queue-status');
        statusSpan.textContent = 'Zapisywanie...';
        const dataToSend = queueDataCache.map((item, index) => ({ type: item.type, payload: item.payload, priority: index * 10 }));
        fetch(`${API_URL_INDEX}?action=update_queue`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dataToSend) 
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                statusSpan.textContent = 'Kolejka zapisana!';
                showToast('Kolejka priorytetowa została zaktualizowana.');
            } else {
                statusSpan.textContent = `Błąd: ${data.message || 'Nieznany błąd.'}`;
                showToast(`Błąd zapisu kolejki: ${data.message || 'Nieznany błąd.'}`, true);
            }
            setTimeout(() => { statusSpan.textContent = ''; }, 3000);
            updateQueueCount(); 
        })
        .catch(error => {
            statusSpan.textContent = 'Błąd sieciowy!';
            showToast('Błąd sieciowy podczas zapisu kolejki.', true);
        });
    }

    // --- NOWE FUNKCJE DLA LIGHTBOX ---
    function openLightbox(images, index) {
        if (!images || images.length === 0) return;
        lightboxImages = images;
        currentLightboxIndex = index;
        lightboxVisible = true;
        document.getElementById('lightbox-overlay').style.display = 'flex';
        document.addEventListener('keydown', handleLightboxKeys);
        showLightboxImage();
    }

    function closeLightbox() {
        lightboxVisible = false;
        document.getElementById('lightbox-overlay').style.display = 'none';
        document.removeEventListener('keydown', handleLightboxKeys);
    }

    function changeLightboxImage(direction) {
        currentLightboxIndex += direction;
        if (currentLightboxIndex >= lightboxImages.length) {
            currentLightboxIndex = 0;
        } else if (currentLightboxIndex < 0) {
            currentLightboxIndex = lightboxImages.length - 1;
        }
        showLightboxImage();
    }

    function showLightboxImage() {
        const imageUrl = lightboxImages[currentLightboxIndex];
        document.getElementById('lightbox-image').src = imageUrl;
        document.getElementById('lightbox-caption').textContent = `${currentLightboxIndex + 1} / ${lightboxImages.length}`;
    }

    function handleLightboxKeys(e) {
        if (!lightboxVisible) return;
        if (e.key === 'ArrowRight' || e.key === 'd') {
            changeLightboxImage(1);
        } else if (e.key === 'ArrowLeft' || e.key === 'a') {
            changeLightboxImage(-1);
        } else if (e.key === 'Escape') {
            closeLightbox();
        }
    }

    // --- JS for Tab 2: Testowanie Tytułów AI ---
    let tbodyTestAi, loadBtnTestAi, modelFilterTestAi, statusFilterTestAi, sortByFilterTestAi, sortOrderFilterTestAi;
    let selectAllHeaderTestAi, selectAllBtnTestAi, runTestAiSelectedBtnTestAi, renameSelectedBtnTestAi;
    let selectionStatusTestAi, prevPageBtnTestAi, nextPageBtnTestAi, pageInfoTestAi, pollingIndicatorTestAi;
    let itemsPerPageSelectTestAi;
    let currentPageTestAi = 1;
    let totalItemsTestAi = 0;
    let currentGalleriesDataTestAi = {}; 
    let pollingIntervalTestAi = null;
    let currentSortByTestAi = 'model_gallery';
    let currentSortOrderTestAi = 'ASC';
    const statusMapTestAi = { 
        'pending_ai': 'AI (Prod)...', 'pending_ai_test': 'AI (Test)...',
        'pending_initial_fetch_test_ai': 'Pobieranie (Test AI)...', 'pending_initial_fetch_prod_ai': 'Pobieranie (Prod AI)...',
        'error_ai': 'Błąd AI (Prod)', 'error_ai_prod': 'Błąd AI (Prod)',
        'error_ai_test': 'Błąd AI (Test)', 'test_completed': 'Test OK', 'disabled_bad_links': 'Wyłączona (złe linki)'
    };
    function setLoadingTestAi(isLoading, targetElement = tbodyTestAi, colSpan = 9) {
        if (targetElement) targetElement.innerHTML = isLoading ? `<tr><td colspan="${colSpan}" class="loader">Ładowanie...</td></tr>` : '';
        if (loadBtnTestAi) loadBtnTestAi.disabled = isLoading;
        if (prevPageBtnTestAi) prevPageBtnTestAi.disabled = isLoading;
        if (nextPageBtnTestAi) nextPageBtnTestAi.disabled = isLoading;
    }
    function sanitizeForIdTestAi(text) {
        return String(text).replace(/[^a-zA-Z0-9_-]/g, '_');
    }
    function fetchGalleriesTestAi() {
        if (!tbodyTestAi) return; 
        setLoadingTestAi(true);
        const model = modelFilterTestAi ? modelFilterTestAi.value : '';
        const statusVal = statusFilterTestAi ? statusFilterTestAi.value : ''; 
        const itemsPerPage = itemsPerPageSelectTestAi ? parseInt(itemsPerPageSelectTestAi.value, 10) : 25;
        const offset = (currentPageTestAi - 1) * itemsPerPage;
        currentSortByTestAi = sortByFilterTestAi ? sortByFilterTestAi.value : 'model_gallery';
        currentSortOrderTestAi = sortOrderFilterTestAi ? sortOrderFilterTestAi.value : 'ASC';
        const queryParams = new URLSearchParams({ action: 'get_galleries_for_ai_test', model: model, status_filter: statusVal, limit: itemsPerPage, offset: offset, sort_by: currentSortByTestAi, sort_order: currentSortOrderTestAi, _: new Date().getTime() });
        fetch(`${API_URL_INDEX}?${queryParams.toString()}`)
            .then(res => res.json())
            .then(data => {
                setLoadingTestAi(false);
                if (data.success && data.galleries) {
                    totalItemsTestAi = data.total || 0;
                    currentGalleriesDataTestAi = {}; 
                    renderTableTestAi(data.galleries);
                    updatePaginationTestAi();
                    updateSelectionStatusTestAi();
                    const activeTabElement = document.querySelector('.tab-content.active');
                    if (activeTabElement && activeTabElement.id === 'test_ai_titles') startPollingTestAi(); 
                } else {
                    showGlobalToast(`Błąd ładowania galerii (Test AI): ${data.message || 'Nie udało się pobrać danych.'}`, true);
                    if (tbodyTestAi) tbodyTestAi.innerHTML = `<tr><td colspan="9" class="loader">Wystąpił błąd: ${data.message || 'Nieznany błąd'}</td></tr>`;
                }
            })
            .catch(error => {
                setLoadingTestAi(false);
                showGlobalToast(`Błąd sieciowy (Test AI): ${error.message}`, true);
                 if (tbodyTestAi) tbodyTestAi.innerHTML = '<tr><td colspan="9" class="loader">Błąd sieciowy.</td></tr>';
            });
    }
    function renderTableTestAi(galleries) {
        if (!tbodyTestAi) return;
        tbodyTestAi.innerHTML = '';
        if (galleries.length === 0) {
            tbodyTestAi.innerHTML = '<tr><td colspan="9" class="loader">Brak galerii pasujących do kryteriów.</td></tr>';
            return;
        }
        galleries.forEach(gallery => {
            const galleryIdSafe = sanitizeForIdTestAi(gallery.gallery_id);
            currentGalleriesDataTestAi[gallery.gallery_id] = gallery; 
            const row = document.createElement('tr');
            row.id = `row-test-ai-${galleryIdSafe}`;
            row.dataset.galleryId = gallery.gallery_id;
            const determinedTitle = gallery.determined_title || '';
            const testAiTitle = gallery.test_ai_title || '';
            let statusTextRender = gallery.status || '<i>(Brak)</i>';
            let statusClass = `status-${gallery.status ? gallery.status.replace(/_/g, '-') : 'unknown'}`;
            statusTextRender = statusMapTestAi[gallery.status] || (gallery.status ? gallery.status.replace(/_/g, ' ') : '<i>(Brak)</i>');
            row.innerHTML = `
                <td><input type="checkbox" class="select-row-test-ai" data-id="${galleryIdSafe}"></td>
                <td>${gallery.gallery_id}</td>
                <td>${gallery.model_name || '<i>Brak</i>'}</td>
                <td>${gallery.original_title || '<i>Brak</i>'}</td>
                <td><input type="text" class="title-input prod-title-input-test-ai" value="${determinedTitle}" data-original-value="${determinedTitle}"></td>
                <td><input type="text" class="title-input test-title-input-test-ai" value="${testAiTitle}" readonly></td>
                <td class="folder-cell">${gallery.folder_path || '<i>Brak</i>'}</td>
                <td class="status-cell ${statusClass}">${statusTextRender}</td>
                <td class="actions-cell">
                    <button class="ai-btn btn-run-test-ai-single" onclick="triggerAiTestRunSingle('${gallery.gallery_id}')">Testuj AI</button>
                    <button class="action-btn rename-btn-single" onclick="saveProdTitleAndRenameSingle('${gallery.gallery_id}')">Zapisz i Zmień</button>
                </td>
            `;
            tbodyTestAi.appendChild(row);
        });
        document.querySelectorAll('.prod-title-input-test-ai').forEach(input => {
            input.addEventListener('input', (e) => {
                if (e.target.value !== e.target.dataset.originalValue) e.target.classList.add('changed');
                else e.target.classList.remove('changed');
            });
        });
        document.querySelectorAll('.select-row-test-ai').forEach(cb => { cb.addEventListener('change', updateSelectionStatusTestAi); });
        if (selectAllHeaderTestAi) selectAllHeaderTestAi.checked = false; 
    }
    function triggerAiTestRunSingle(galleryId) { 
        const galleryIdSafe = sanitizeForIdTestAi(galleryId);
        const row = document.getElementById(`row-test-ai-${galleryIdSafe}`);
        if (!row) return; 
        const btn = row.querySelector('.btn-run-test-ai-single');
        const statusCell = row.querySelector('.status-cell');
        const testTitleInput = row.querySelector('.test-title-input-test-ai');
        let originalStatusInCache = null;
        if (currentGalleriesDataTestAi[galleryId]) {
            originalStatusInCache = currentGalleriesDataTestAi[galleryId].status; 
            currentGalleriesDataTestAi[galleryId].status = 'pending_ai_test'; 
            if (testTitleInput) { currentGalleriesDataTestAi[galleryId].test_ai_title = ''; testTitleInput.value = ''; }
        }
        if(btn) { btn.disabled = true; btn.textContent = 'Kolejkuję...';}
        if(statusCell) { statusCell.textContent = 'Kolejkowanie Test AI...'; statusCell.className = 'status-cell status-pending-ai-test'; }
        fetch(`${API_URL_INDEX}?action=trigger_ai_test_run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ gallery_id: galleryId }) })
        .then(res => res.json())
        .then(data => {
            if(btn) {btn.textContent = 'Testuj AI'; btn.disabled = false;}
            if (data.success) {
                showGlobalToast(data.message || `Test AI dla ${galleryId} zakolejkowany.`);
                if(statusCell) { statusCell.textContent = 'AI (Test)...'; statusCell.className = 'status-cell status-pending-ai-test'; }
            } else { 
                showGlobalToast(`Test AI dla ${galleryId}: ${data.message || 'Niepowodzenie.'}`, true);
                if (statusCell && currentGalleriesDataTestAi[galleryId] && originalStatusInCache) { 
                    statusCell.textContent = (statusMapTestAi[originalStatusInCache] || originalStatusInCache.replace(/_/g, ' ')) || '<i>(Brak)</i>';
                    statusCell.className = `status-cell status-${originalStatusInCache ? originalStatusInCache.replace(/_/g, '-') : 'unknown'}`;
                    currentGalleriesDataTestAi[galleryId].status = originalStatusInCache;
                } else if (statusCell) { statusCell.textContent = 'Błąd operacji'; statusCell.className = 'status-cell status-error'; }
            }
        })
        .catch(error => { 
            if(btn) { btn.textContent = 'Testuj AI'; btn.disabled = false; }
            if (statusCell) {
                if (originalStatusInCache && currentGalleriesDataTestAi[galleryId]) { 
                    statusCell.textContent = (statusMapTestAi[originalStatusInCache] || originalStatusInCache.replace(/_/g, ' ')) || '<i>(Brak)</i>';
                    statusCell.className = `status-cell status-${originalStatusInCache ? originalStatusInCache.replace(/_/g, '-') : 'unknown'}`;
                    currentGalleriesDataTestAi[galleryId].status = originalStatusInCache;
                } else { statusCell.textContent = 'Błąd sieci'; statusCell.className = 'status-cell status-error'; }
            }
            showGlobalToast(`Błąd sieciowy (Test AI Single): ${error.message}`, true);
        });
    }
    function saveProdTitleAndRenameSingle(galleryId) {
        const galleryIdSafe = sanitizeForIdTestAi(galleryId);
        const row = document.getElementById(`row-test-ai-${galleryIdSafe}`);
        if (!row) return;

        const prodTitleInput = row.querySelector('.prod-title-input-test-ai');
        const testTitleInput = row.querySelector('.test-title-input-test-ai');
        const btn = row.querySelector('.rename-btn-single');

        const testTitle = testTitleInput.value.trim();
        if (!testTitle) {
            showGlobalToast('Tytuł testowy jest pusty. Nie można wykonać akcji.', true);
            return;
        }

        prodTitleInput.value = testTitle;
        prodTitleInput.classList.add('changed');
        
        if(btn) {btn.disabled = true; btn.textContent = 'Zmieniam...';}

        fetch(`${API_URL_INDEX}?action=rename_gallery_folder`, { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify({ gallery_id: galleryId, new_title: testTitle }) 
        })
        .then(res => res.json())
        .then(data => {
            if(btn) {btn.disabled = false; btn.textContent = 'Zapisz i Zmień';}
            if (data.success) {
                showGlobalToast(`Zapis i zmiana nazwy dla ${galleryId}: ${data.message}`);
                prodTitleInput.dataset.originalValue = testTitle;
                prodTitleInput.classList.remove('changed');
                
                if (data.new_folder_path) {
                    const folderCell = row.querySelector('.folder-cell');
                    if (folderCell) folderCell.textContent = data.new_folder_path;
                }

                if (currentGalleriesDataTestAi[galleryId]) {
                    currentGalleriesDataTestAi[galleryId].determined_title = testTitle;
                    if (data.new_folder_path) {
                        currentGalleriesDataTestAi[galleryId].folder_path = data.new_folder_path;
                    }
                }
            } else {
                showGlobalToast(`Błąd zapisu/zmiany nazwy ${galleryId}: ${data.message}`, true);
                prodTitleInput.value = prodTitleInput.dataset.originalValue;
                prodTitleInput.classList.remove('changed');
            }
        })
        .catch(error => {
            if(btn) { btn.disabled = false; btn.textContent = 'Zapisz i Zmień';}
            showGlobalToast(`Błąd sieciowy (Rename Single): ${error.message}`, true);
            prodTitleInput.value = prodTitleInput.dataset.originalValue;
            prodTitleInput.classList.remove('changed');
        });
    }
    function toggleSelectAllTestAi() {
        if (!selectAllHeaderTestAi) return;
        document.querySelectorAll('.select-row-test-ai').forEach(cb => { cb.checked = selectAllHeaderTestAi.checked; });
        updateSelectionStatusTestAi();
    }
    function updateSelectionStatusTestAi() {
        const count = document.querySelectorAll('.select-row-test-ai:checked').length;
        if(selectionStatusTestAi) selectionStatusTestAi.textContent = `Zaznaczono: ${count}`;
        if(runTestAiSelectedBtnTestAi) runTestAiSelectedBtnTestAi.disabled = count === 0;
        if(renameSelectedBtnTestAi) renameSelectedBtnTestAi.disabled = count === 0;
    }
    function getSelectedIdsTestAi() {
        const ids = [];
        document.querySelectorAll('.select-row-test-ai:checked').forEach(cb => ids.push(cb.closest('tr').dataset.galleryId));
        return ids;
    }
    async function runTestAiForSelectedBulk() { 
        const selectedIds = getSelectedIdsTestAi();
        if (selectedIds.length === 0) { showGlobalToast('Nie zaznaczono żadnych galerii.', true); return; }
        if(runTestAiSelectedBtnTestAi) runTestAiSelectedBtnTestAi.disabled = true;
        let successCount = 0, errorCount = 0;
        for (const galleryId of selectedIds) {
            const galleryIdSafe = sanitizeForIdTestAi(galleryId);
            const row = document.getElementById(`row-test-ai-${galleryIdSafe}`);
            let btn, statusCell; let originalStatusInCacheBulk = null;
            if (row) {
                btn = row.querySelector('.btn-run-test-ai-single'); 
                statusCell = row.querySelector('.status-cell');
                if(statusCell) { statusCell.textContent = 'Kolejkowanie...'; statusCell.className = 'status-cell status-pending-ai-test'; }
                if(btn) btn.disabled = true; 
            }
            if (currentGalleriesDataTestAi[galleryId]) {
                originalStatusInCacheBulk = currentGalleriesDataTestAi[galleryId].status;
                currentGalleriesDataTestAi[galleryId].status = 'pending_ai_test';
                currentGalleriesDataTestAi[galleryId].test_ai_title = '';
            }
            try {
                 const response = await fetch(`${API_URL_INDEX}?action=trigger_ai_test_run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ gallery_id: galleryId }) });
                 const data = await response.json(); 
                 if (!response.ok) throw new Error(data.message || response.statusText);
                 if (data.success) { successCount++; if(statusCell) statusCell.textContent = 'AI (Test)...'; } 
                 else { errorCount++; showGlobalToast(`Błąd ${galleryId}: ${data.message || 'Błąd API'}`, true, 4000);
                    if(statusCell && currentGalleriesDataTestAi[galleryId] && originalStatusInCacheBulk) { 
                        statusCell.textContent = (statusMapTestAi[originalStatusInCacheBulk] || originalStatusInCacheBulk.replace(/_/g,' ')) || '<i>(Brak)</i>';
                        statusCell.className = `status-cell status-${originalStatusInCacheBulk ? originalStatusInCacheBulk.replace(/_/g, '-') : 'unknown'}`;
                        currentGalleriesDataTestAi[galleryId].status = originalStatusInCacheBulk;
                    } else if (statusCell) { statusCell.textContent = 'Błąd'; statusCell.className = 'status-cell status-error'; }
                }
            } catch (error) { errorCount++; showGlobalToast(`Błąd ${galleryId}: ${error.message}`, true, 4000);
                 if(statusCell) { 
                     if(originalStatusInCacheBulk && currentGalleriesDataTestAi[galleryId]) {
                        statusCell.textContent = (statusMapTestAi[originalStatusInCacheBulk] || originalStatusInCacheBulk.replace(/_/g,' ')) || '<i>(Brak)</i>';
                        statusCell.className = `status-cell status-${originalStatusInCacheBulk ? originalStatusInCacheBulk.replace(/_/g, '-') : 'unknown'}`;
                        currentGalleriesDataTestAi[galleryId].status = originalStatusInCacheBulk;
                     } else { statusCell.textContent = 'Błąd sieci'; statusCell.className = 'status-cell status-error'; }
                 }
            } finally { if(btn) btn.disabled = false; }
            await new Promise(resolve => setTimeout(resolve, 100)); 
        }
        showGlobalToast(`Zakończono. Zakolejkowano: ${successCount}, Błędów: ${errorCount}.`, errorCount > 0);
        if(runTestAiSelectedBtnTestAi) runTestAiSelectedBtnTestAi.disabled = false; 
    }
    async function renameSelectedFoldersBulkTestAi() {
        const selectedIds = getSelectedIdsTestAi();
        if (selectedIds.length === 0) { showGlobalToast('Nie zaznaczono żadnych galerii.', true); return; }
        if (!confirm(`Zastosować tytuły testowe i zmienić nazwy folderów dla ${selectedIds.length} galerii?`)) return;

        if (renameSelectedBtnTestAi) renameSelectedBtnTestAi.disabled = true;
        let successCount = 0, errorCount = 0, ignoredCount = 0;

        for (const galleryId of selectedIds) {
            const row = document.getElementById(`row-test-ai-${sanitizeForIdTestAi(galleryId)}`);
            if (!row) {
                errorCount++;
                showGlobalToast(`Błąd ${galleryId}: Nie znaleziono wiersza.`, true, 4000);
                continue;
            }

            const prodTitleInput = row.querySelector('.prod-title-input-test-ai');
            const testTitleInput = row.querySelector('.test-title-input-test-ai');
            const btn = row.querySelector('.rename-btn-single');
            
            const testTitle = testTitleInput.value.trim();
            if (!testTitle) {
                ignoredCount++;
                continue;
            }
            
            prodTitleInput.value = testTitle;
            if (btn) btn.disabled = true;

            try {
                const response = await fetch(`${API_URL_INDEX}?action=rename_gallery_folder`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ gallery_id: galleryId, new_title: testTitle })
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.message || response.statusText);

                if (data.success) {
                    successCount++;
                    prodTitleInput.dataset.originalValue = testTitle;
                    prodTitleInput.classList.remove('changed');
                    
                    if (data.new_folder_path) {
                        const folderCell = row.querySelector('.folder-cell');
                        if (folderCell) folderCell.textContent = data.new_folder_path;
                    }

                    if (currentGalleriesDataTestAi[galleryId]) {
                        currentGalleriesDataTestAi[galleryId].determined_title = testTitle;
                        if (data.new_folder_path) {
                            currentGalleriesDataTestAi[galleryId].folder_path = data.new_folder_path;
                        }
                    }
                } else {
                    errorCount++;
                    showGlobalToast(`Błąd ${galleryId}: ${data.message || 'Błąd API'}`, true, 4000);
                    prodTitleInput.value = prodTitleInput.dataset.originalValue;
                }
            } catch (error) {
                errorCount++;
                showGlobalToast(`Błąd ${galleryId}: ${error.message}`, true, 4000);
                prodTitleInput.value = prodTitleInput.dataset.originalValue;
            } finally {
                if (btn) btn.disabled = false;
            }
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        let summaryMessage = `Zakończono. Sukcesów: ${successCount}, Błędów: ${errorCount}`;
        if (ignoredCount > 0) {
            summaryMessage += `, Pustych/Pominiętych: ${ignoredCount}`;
        }
        showGlobalToast(summaryMessage, errorCount > 0);

        if (renameSelectedBtnTestAi) renameSelectedBtnTestAi.disabled = false;
    }
    function updatePaginationTestAi() {
        const itemsPerPage = itemsPerPageSelectTestAi ? parseInt(itemsPerPageSelectTestAi.value, 10) : 25;
        const totalPages = Math.ceil(totalItemsTestAi / itemsPerPage);
        if(pageInfoTestAi) pageInfoTestAi.textContent = `Strona ${currentPageTestAi} z ${totalPages || 1} (Galerii: ${totalItemsTestAi})`;
        if(prevPageBtnTestAi) prevPageBtnTestAi.disabled = currentPageTestAi === 1;
        if(nextPageBtnTestAi) nextPageBtnTestAi.disabled = currentPageTestAi >= totalPages || totalItemsTestAi === 0;
    }
    function pollForAiUpdatesTestAi() {
        const activeTabElement = document.querySelector('.tab-content.active');
        if (!activeTabElement || activeTabElement.id !== 'test_ai_titles') { stopPollingTestAi(); return; }
        const pendingIds = Object.keys(currentGalleriesDataTestAi).filter(id => currentGalleriesDataTestAi[id] && ['pending_ai_test', 'pending_ai', 'pending_initial_fetch_test_ai', 'pending_initial_fetch_prod_ai'].includes(currentGalleriesDataTestAi[id].status));
        if (pendingIds.length === 0) { if(pollingIndicatorTestAi) pollingIndicatorTestAi.classList.remove('active'); return; }
        if(pollingIndicatorTestAi) pollingIndicatorTestAi.classList.add('active');
        fetchGalleriesTestAi(); 
    }
    function startPollingTestAi() {
        if (pollingIntervalTestAi) clearInterval(pollingIntervalTestAi);
        const activeTabElement = document.querySelector('.tab-content.active');
        if (activeTabElement && activeTabElement.id === 'test_ai_titles') pollForAiUpdatesTestAi(); 
        pollingIntervalTestAi = setInterval(pollForAiUpdatesTestAi, 10000); 
    }
    function stopPollingTestAi() {
        if (pollingIntervalTestAi) clearInterval(pollingIntervalTestAi);
        pollingIntervalTestAi = null;
        if (pollingIndicatorTestAi) pollingIndicatorTestAi.classList.remove('active');
    }

    // --- JS for Tab 3: Ustawienia AI ---
    let promptConfigsContainerOllama, promoteTestBtnOllama;
    function initializeTab3Vars() {
        promptConfigsContainerOllama = document.getElementById('prompt-configs-container-ollama');
        promoteTestBtnOllama = document.getElementById('promote-test-btn-ollama');
        if (promoteTestBtnOllama) {
            promoteTestBtnOllama.addEventListener('click', () => {
                if (!confirm("Czy na pewno chcesz nadpisać konfigurację produkcyjną ustawieniami testowymi?")) return;
                showGlobalToast("Przenoszenie konfiguracji testowej do produkcji...");
                fetch(`${API_URL_INDEX}?action=promote_test_to_production`, { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) { showGlobalToast(data.message || "Konfiguracja promowana."); loadPromptConfigsOllama(); } 
                    else { showGlobalToast(`Błąd promocji: ${data.message || 'Nieznany błąd'}`, true); }
                })
                .catch(err => { showGlobalToast(`Błąd sieciowy (Promocja): ${err.message}`, true); });
            });
        }
    }
    function loadGlobalAiSettings() {
        const urlInput = document.getElementById('ollama-url');
        const modelInput = document.getElementById('ollama-default-model');
        if (!urlInput || !modelInput) return;
        urlInput.disabled = true; modelInput.disabled = true;
        fetch(`${API_URL_INDEX}?action=get_global_ai_settings&_=${new Date().getTime()}`)
        .then(res => res.json())
        .then(data => {
            if (data.success && data.settings) {
                urlInput.value = data.settings.api_base_url.value || '';
                modelInput.value = data.settings.default_model_name.value || '';
            } else {
                showGlobalToast(`Błąd ładowania ustawień globalnych: ${data.message || 'Błąd'}`, true);
            }
        })
        .catch(err => { showGlobalToast(`Błąd sieciowy ładowania ust. globalnych: ${err.message}`, true); })
        .finally(() => { urlInput.disabled = false; modelInput.disabled = false; });
    }
    function saveGlobalAiSettings() {
        const urlInput = document.getElementById('ollama-url');
        const modelInput = document.getElementById('ollama-default-model');
        const newUrl = urlInput.value.trim();
        const newModel = modelInput.value.trim();
        if (!newUrl || !newModel) { showGlobalToast('URL i model nie mogą być puste.', true); return; }
        showGlobalToast('Zapisywanie ustawień globalnych...');
        const payload = { api_base_url: newUrl, default_model_name: newModel };
        fetch(`${API_URL_INDEX}?action=save_global_ai_settings`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) })
        .then(res => res.json())
        .then(data => {
            if (data.success) showGlobalToast(data.message || "Ustawienia zapisane.");
            else showGlobalToast(`Błąd zapisu: ${data.message || 'Błąd'}`, true);
        })
        .catch(err => { showGlobalToast(`Błąd sieciowy zapisu: ${err.message}`, true); });
    }
    function setLoadingOllama(isLoading, targetElement = promptConfigsContainerOllama) {
        if(targetElement) targetElement.innerHTML = isLoading ? `<p class="loader">Ładowanie...</p>` : '';
    }
    function loadPromptConfigsOllama() {
        if (!promptConfigsContainerOllama) return; 
        setLoadingOllama(true);
        fetch(`${API_URL_INDEX}?action=get_ai_prompt_configs&_=${new Date().getTime()}`)
            .then(res => res.json())
            .then(data => {
                setLoadingOllama(false);
                if (data.success && data.configs) renderPromptConfigsOllama(data.configs);
                else if(promptConfigsContainerOllama) promptConfigsContainerOllama.innerHTML = `<p class="loader">Błąd: ${data.message || 'Błąd ładowania.'}</p>`;
            })
            .catch(err => {
                setLoadingOllama(false);
                if(promptConfigsContainerOllama) promptConfigsContainerOllama.innerHTML = `<p class="loader">Błąd sieciowy: ${err.message}</p>`;
            });
    }
    function renderPromptConfigsOllama(configs) {
        if (!promptConfigsContainerOllama) return;
        promptConfigsContainerOllama.innerHTML = '';
        configs.sort((a,b) => { 
            if (a.config_id === 'production') return -1; if (b.config_id === 'production') return 1;
            if (a.config_id === 'test') return -1; if (b.config_id === 'test') return 1;
            return a.config_id.localeCompare(b.config_id);
        });
        configs.forEach(config => {
            const div = document.createElement('div');
            div.className = 'prompt-config-item';
            div.innerHTML = `
                <h3>Konfiguracja: ${config.config_id.toUpperCase()} ${config.config_id === 'production' ? '(Produkcyjna)' : (config.config_id === 'test' ? '(Testowa)' : '')}</h3>
                <form class="prompt-config-form" data-config-id="${config.config_id}" onsubmit="event.preventDefault(); savePromptConfigOllama('${config.config_id}');">
                    <label>Opis:</label><input type="text" id="desc-ollama-${config.config_id}" value="${config.description || ''}">
                    <label>Prompt Systemowy:</label><textarea id="prompt-ollama-${config.config_id}">${config.system_prompt || ''}</textarea>
                    <label>Model Ollama (nadpisuje domyślny):</label><input type="text" id="model-ollama-${config.config_id}" value="${config.ollama_model_name || ''}">
                    <label>Temperatura:</label><input type="number" id="temp-ollama-${config.config_id}" value="${config.ollama_temperature !== null ? config.ollama_temperature : 0.2}" step="0.01" min="0" max="2">
                    <label>Max Tokenów:</label><input type="number" id="numpred-ollama-${config.config_id}" value="${config.ollama_num_predict !== null ? config.ollama_num_predict : 60}" step="1" min="10">
                    <label>Top_p:</label><input type="number" id="topp-ollama-${config.config_id}" value="${config.ollama_top_p !== null ? config.ollama_top_p : 0.8}" step="0.01" min="0" max="1">
                    <button type="submit" class="neutral-btn">Zapisz Konfigurację '${config.config_id.toUpperCase()}'</button>
                </form>
            `;
            promptConfigsContainerOllama.appendChild(div);
        });
    }
    function savePromptConfigOllama(configId) {
        const form = document.querySelector(`.prompt-config-form[data-config-id="${configId}"]`);
        if (!form) { showGlobalToast(`Błąd: Nie znaleziono formularza dla ${configId}`, true); return; }
        const dataToSave = {
            config_id: configId,
            description: form.querySelector(`#desc-ollama-${configId}`).value,
            system_prompt: form.querySelector(`#prompt-ollama-${configId}`).value,
            ollama_model_name: form.querySelector(`#model-ollama-${configId}`).value || null, 
            ollama_temperature: parseFloat(form.querySelector(`#temp-ollama-${configId}`).value),
            ollama_num_predict: parseInt(form.querySelector(`#numpred-ollama-${configId}`).value),
            ollama_top_p: parseFloat(form.querySelector(`#topp-ollama-${configId}`).value)
        };
        showGlobalToast(`Zapisywanie '${configId}'...`);
        fetch(`${API_URL_INDEX}?action=save_ai_prompt_config`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(dataToSave) })
        .then(res => res.json())
        .then(data => {
            if (data.success) showGlobalToast(data.message || "Zapisano.");
            else showGlobalToast(`Błąd zapisu '${configId}': ${data.message || 'Błąd'}`, true);
        })
        .catch(err => { showGlobalToast(`Błąd sieciowy (Zapis Ollama): ${err.message}`, true); });
    }

    // --- Initial Setup ---
    document.addEventListener('DOMContentLoaded', function() {
        tbodyTestAi = document.getElementById('galleries-test-ai-tbody');
        loadBtnTestAi = document.getElementById('load-data-btn-test-ai');
        modelFilterTestAi = document.getElementById('model-filter-test-ai');
        statusFilterTestAi = document.getElementById('status-filter-test-ai');
        sortByFilterTestAi = document.getElementById('sort-by-filter-test-ai');
        sortOrderFilterTestAi = document.getElementById('sort-order-filter-test-ai');
        itemsPerPageSelectTestAi = document.getElementById('items-per-page-test-ai');
        selectAllHeaderTestAi = document.getElementById('select-all-header-test-ai');
        selectAllBtnTestAi = document.getElementById('select-all-btn-test-ai');
        runTestAiSelectedBtnTestAi = document.getElementById('run-test-ai-selected-btn-test-ai');
        renameSelectedBtnTestAi = document.getElementById('rename-selected-btn-test-ai');
        selectionStatusTestAi = document.getElementById('selection-status-test-ai');
        prevPageBtnTestAi = document.getElementById('prev-page-btn-test-ai');
        nextPageBtnTestAi = document.getElementById('next-page-btn-test-ai');
        pageInfoTestAi = document.getElementById('page-info-test-ai');
        pollingIndicatorTestAi = document.getElementById('polling-indicator-test-ai');
        initializeTab3Vars();

        const commonChangeHandler = () => { currentPageTestAi = 1; fetchGalleriesTestAi(); };
        if (loadBtnTestAi) loadBtnTestAi.addEventListener('click', commonChangeHandler);
        if (sortByFilterTestAi) sortByFilterTestAi.addEventListener('change', commonChangeHandler);
        if (sortOrderFilterTestAi) sortOrderFilterTestAi.addEventListener('change', commonChangeHandler);
        if (itemsPerPageSelectTestAi) itemsPerPageSelectTestAi.addEventListener('change', commonChangeHandler);
        
        if (selectAllHeaderTestAi) selectAllHeaderTestAi.addEventListener('change', toggleSelectAllTestAi);
        if (selectAllBtnTestAi) selectAllBtnTestAi.addEventListener('click', () => { if(selectAllHeaderTestAi) selectAllHeaderTestAi.checked = !selectAllHeaderTestAi.checked; toggleSelectAllTestAi(); });
        if (runTestAiSelectedBtnTestAi) runTestAiSelectedBtnTestAi.addEventListener('click', runTestAiForSelectedBulk); 
        if (renameSelectedBtnTestAi) renameSelectedBtnTestAi.addEventListener('click', renameSelectedFoldersBulkTestAi); 
        if (prevPageBtnTestAi) prevPageBtnTestAi.addEventListener('click', () => { if (currentPageTestAi > 1) { currentPageTestAi--; fetchGalleriesTestAi(); } });
        if (nextPageBtnTestAi) nextPageBtnTestAi.addEventListener('click', () => { const totalPages = Math.ceil(totalItemsTestAi / (itemsPerPageSelectTestAi ? parseInt(itemsPerPageSelectTestAi.value, 10) : 25)); if (currentPageTestAi < totalPages && totalItemsTestAi > 0) { currentPageTestAi++; fetchGalleriesTestAi(); } });
        
        window.onclick = function(event) {
            if (event.target == document.getElementById('queue-modal')) closeQueueModal();
            if (event.target == document.getElementById('image-viewer-modal')) closeImageViewerModal();
            if (event.target == document.getElementById('search-modal')) closeSearchModal();
            if (event.target == document.getElementById('lightbox-overlay')) closeLightbox();
        };
        const urlParams = new URLSearchParams(window.location.search);
        let initialTab = urlParams.get('tab') || '<?php echo $active_tab; ?>';
        const validTabIds = ['status_galleries', 'test_ai_titles', 'ollama_prompts_settings'];
        if (!validTabIds.includes(initialTab)) initialTab = 'status_galleries'; 
        const tabButtonToClick = document.querySelector(`.tab-button[onclick*="'${initialTab}'"]`);
        if (tabButtonToClick) openTab({currentTarget: tabButtonToClick}, initialTab); 
        else { 
            const firstTabButton = document.querySelector('.tab-button');
            if (firstTabButton) {
                 const firstTabId = firstTabButton.getAttribute('onclick').match(/'([^']+)'/)[1];
                 if (validTabIds.includes(firstTabId)) openTab({currentTarget: firstTabButton}, firstTabId);
            }
        }
        if (initialTab === 'test_ai_titles') {
            updateSelectionStatusTestAi();
            updatePaginationTestAi();
        }
    });
</script>

</body>
</html>