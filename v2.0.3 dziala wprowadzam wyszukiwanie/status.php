<?php
// status.php
require_once 'php_config.php'; 
require_once 'php_utils.php';  

$aggregate_last_modified_timestamp = "Ładowanie..."; 

?>
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Status Pobierania (PHP/MySQL)</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.5; padding: 15px; background-color: #f9f9f9; color: #333; }
        ul { list-style-type: none; padding-left: 0; }
        .model-li > ul.nested { padding-left: 20px; }
        .toggle { cursor: pointer; margin-right: 8px; font-weight: bold; user-select: none; width: 15px; display: inline-block; text-align: center; color: #333; }
        .model-li { margin-bottom: 8px; background-color: #fff; border: 1px solid #ddd; padding: 0; border-radius: 5px; box-shadow: 0 1px 2px rgba(0, 0, 0, .05); overflow: hidden; }
        .model-header { display: flex; align-items: center; padding: 8px 12px; background-color: #e9ecef; border-bottom: 1px solid #ddd; transition: background-color 0.3s; }
        .model-li.model-partial > .model-header { background-color: #FFE0B2; } 
        .model-li.model-complete > .model-header { background-color: #A5D6A7; } 
        .model-li.model-processing > .model-header { background-color: #B3E5FC; } 
        .model-header .model-name { flex-grow: 1; font-weight: bold; }
        ul.nested { display: none; padding-left: 25px; border-left: 2px solid #dee2e6; margin-left: 7px; background-color: #fff; margin-top: 5px; border-radius: 4px; padding: 10px; }
        ul.nested.active { display: block; }
        .gallery-li { margin-bottom: 4px; border-bottom: 1px solid #f1f3f5; padding: 6px 0; display: flex; justify-content: space-between; align-items: center; transition: background-color 0.3s; }
        .gallery-li.processing { background-color: #e0f7fa !important; } 
        .gallery-link { flex-grow: 1; margin-right: 10px; font-size: 0.95em; display: flex; align-items: center; }
        .gallery-controls { display: flex; align-items: center; flex-shrink: 0; }
        .newly-found-count { font-size: 0.8em; color: #007bff; margin-right: 8px; display: none; }
        .gallery-status { font-size: .9em; padding: 2px 6px; border-radius: 3px; color: #fff; min-width: 75px; text-align: center; margin-left: 5px; }
        .green { background-color: #28a745; } .orange { background-color: #fd7e14; } .red { background-color: #dc3545; } .blue { background-color: #007bff }
        h1 { font-size: 1.6em; color: #343a40; border-bottom: 2px solid #adb5bd; padding-bottom: 5px; display: flex; justify-content: space-between; align-items: center; }
        h1 small#last-aggregate-update-time { color: #6c757d; font-size: .7em; }
        a { text-decoration: none; color: #007bff; } a:hover { text-decoration: underline; }
        #current-status { font-size: 0.9em; font-weight: bold; color: #555; background-color: #fff; padding: 10px; border-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,.05); margin-bottom: 15px; border: 1px solid #ddd; min-height: 1.2em; transition: background-color 0.5s; }
        .progress-bar-container { width: 80px; height: 12px; background-color: #e9ecef; border-radius: 5px; overflow: hidden; display: inline-block; margin-left: 10px; vertical-align: middle; border: 1px solid #ced4da; }
        .progress-bar { height: 100%; background-color: #28a745; width: 0%; transition: width 0.3s ease-in-out; text-align: center; color: white; font-size: 0.7em; line-height: 12px; }
        .progress-bar.orange { background-color: #fd7e14; } .progress-bar.red { background-color: #dc3545; }
        .btn-action { font-size: 0.8em; padding: 3px 7px; margin-left: 5px; cursor: pointer; border: 1px solid #ccc; background-color: #f8f9fa; border-radius: 3px; color: #212529; text-decoration: none; display: inline-block; }
        .btn-action:hover { background-color: #e2e6ea; text-decoration: none; color: #212529; }
        #toast { position: fixed; bottom: 20px; right: 20px; background-color: #212529; color: white; padding: 15px; border-radius: 5px; z-index: 1000; opacity: 0; visibility: hidden; transition: opacity 0.5s, visibility 0.5s; font-size: 0.9em; box-shadow: 0 2px 10px rgba(0,0,0,0.2); }
        #toast.show { opacity: 1; visibility: visible; }
        .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(0, 0, 0, 0.1); border-left-color: #007bff; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 8px; vertical-align: middle; visibility: hidden; }
        .gallery-li.processing .spinner { visibility: visible; }
        #add-model-section { margin-bottom: 15px; padding: 10px; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; display: flex; align-items: center; gap: 10px; }
        #add-model-section input[type="text"] { padding: 6px; border: 1px solid #ced4da; border-radius: 3px; flex-grow: 1; }
        #add-model-status { font-size: 0.9em; color: #495057; }
        
        /* Styl dla modala przeglądarki obrazków */
        .image-viewer-modal { display: none; position: fixed; z-index: 1001; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.6); padding-top: 50px; }
        .image-viewer-modal-content { background-color: #fefefe; margin: auto; padding: 20px; border: 1px solid #888; width: 90%; max-width: 1000px; border-radius: 5px; box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2),0 6px 20px 0 rgba(0,0,0,0.19); position: relative; }
        .image-viewer-close-button { color: #aaa; float: right; font-size: 28px; font-weight: bold; cursor: pointer; line-height: 1; position: absolute; top: 10px; right: 20px; }
        .image-viewer-close-button:hover, .image-viewer-close-button:focus { color: black; text-decoration: none; }
        #image-viewer-title { margin-top: 0; margin-bottom: 15px; font-size: 1.3em; }
        .image-grid { display: flex; flex-wrap: wrap; gap: 10px; max-height: 70vh; overflow-y: auto; justify-content: center; padding: 5px; background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 4px;}
        .image-grid img { width: 100px; height: 100px; object-fit: cover; border: 1px solid #ddd; border-radius: 3px; cursor: pointer; transition: transform 0.2s; }
        .image-grid img:hover { transform: scale(1.05); }
        #image-viewer-status { margin-top: 15px; font-size: 0.9em; color: #555; text-align: center; }


        .modal { display: none; position: fixed; z-index: 1001; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.4); }
        .modal-content { background-color: #fefefe; margin: 10% auto; padding: 20px; border: 1px solid #888; width: 80%; max-width: 700px; border-radius: 5px; box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2),0 6px 20px 0 rgba(0,0,0,0.19); }
        .close-button { color: #aaa; float: right; font-size: 28px; font-weight: bold; cursor: pointer; line-height: 1; }
        .close-button:hover, .close-button:focus { color: black; text-decoration: none; }
        #priority-queue-list { list-style: none; padding: 0; margin-top: 15px; border: 1px solid #eee; min-height: 100px; max-height: 400px; overflow-y: auto; background-color: #fff; }
        .queue-item { display: flex; align-items: center; padding: 8px 12px; border-bottom: 1px solid #eee; background-color: #fff; transition: background-color 0.2s; }
        .queue-item:last-child { border-bottom: none; }
        .queue-item .drag-handle { cursor: grab; margin-right: 12px; font-size: 1.3em; color: #ccc; user-select: none; }
        .queue-item .drag-handle:hover { color: #888; }
        .queue-item-info { flex-grow: 1; font-size: 0.9em; }
        .queue-item-controls button { font-size: 0.8em; padding: 2px 6px; margin-left: 4px; cursor: pointer; border: 1px solid #ddd; background-color: #f8f8f8; }
        .queue-item-controls button:hover { background-color: #eee; }
        .queue-item.dragging { opacity: 0.6; background: #d0eaff; border: 1px dashed #99caff; }
        .queue-item.over { border-top: 2px solid #007bff; }
        #queue-status { margin-left: 15px; font-size: 0.9em; font-weight: bold; }
        #manage-queue-btn { margin-left: 15px; background-color: #6c757d; color: white; }
        #manage-queue-btn:hover { background-color: #5a6268; }
        .modal-content h2 { margin-top: 0; }
        .modal-content p { font-size: 0.85em; color: #555; }
        .modal-content button { margin-top: 10px; }
        .loader { text-align: center; padding: 20px; font-size: 1.2em; color: #6c757d; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>

<div id="toast">Wiadomość toast!</div>
<div id="current-status">Ładowanie statusu...</div>

<h1>Status Pobierania <small id="last-aggregate-update-time">(<?php echo htmlspecialchars($aggregate_last_modified_timestamp); ?>)</small>
    <button id="manage-queue-btn" class="btn-action" onclick="openQueueModal()">
        Zarządzaj Kolejką (<span id="queue-count">?</span>)
    </button>
</h1>

<div id="add-model-section">
    <input type="text" id="new-model-name" placeholder="Wpisz nazwę nowej modelki...">
    <button onclick="addModelToList()" class="btn-action">Dodaj do lista.txt</button>
    <span id="add-model-status"></span>
</div>

<ul id="model-tree">
    <li class="loader">Ładowanie listy modeli...</li>
</ul>

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
        <div id="image-viewer-files" class="image-grid">
            </div>
    </div>
</div>


<script>
    const API_URL = '<?php echo API_URL; ?>';
    const toastDiv = document.getElementById('toast');
    const modelTreeUl = document.getElementById('model-tree');
    const statusDiv = document.getElementById('current-status'); 
    const imageViewerModal = document.getElementById('image-viewer-modal');
    const imageViewerTitle = document.getElementById('image-viewer-title');
    const imageViewerFilesDiv = document.getElementById('image-viewer-files');
    const imageViewerStatusDiv = document.getElementById('image-viewer-status');
    let currentlyViewedGalleryId = null; // ID galerii aktualnie otwartej w modalu

    let activeGalleryIdForUI = null;
    let activeModelNameSanitizedForUI = null;
    let aggregateRefreshTimeout = null;

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
        toastDiv.textContent = message;
        toastDiv.style.backgroundColor = isError ? '#dc3545' : '#212529';
        toastDiv.classList.add('show');
        setTimeout(() => { toastDiv.classList.remove('show'); }, 3500);
    }

    function prioritizeItem(type, id) {
        console.log(`Wysłano żądanie priorytetu: typ=${type}, id=${id}`);
        showToast(`Wysyłanie żądania priorytetu dla ${type}: ${id}...`);

        fetch(`${API_URL}?action=prioritize&type=${encodeURIComponent(type)}&id=${encodeURIComponent(id)}&_=${new Date().getTime()}`)
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errData => {
                        throw new Error(`Błąd HTTP ${response.status}: ${errData.message || response.statusText}`);
                    }).catch(() => {
                        throw new Error(`Błąd HTTP ${response.status}: ${response.statusText}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log("Odpowiedź API (prioritize):", data);
                if (data.success) {
                    showToast(`${data.message || 'Dodano do kolejki priorytetowej.'}`);
                    fetchAndDisplayQueue(); 
                } else {
                    showToast(`Błąd: ${data.message || 'Nie udało się dodać do kolejki.'}`, true);
                }
            })
            .catch(error => {
                console.error('Błąd funkcji prioritizeItem:', error);
                showToast(`Błąd sieciowy lub serwera: ${error.message}`, true);
            });
    }
    
    function addModelToList() {
        const modelNameInput = document.getElementById('new-model-name');
        const statusSpan = document.getElementById('add-model-status');
        const modelName = modelNameInput.value.trim();

        if (!modelName) {
            showToast('Wpisz nazwę modelki.', true);
            return;
        }

        statusSpan.textContent = 'Dodawanie...';
        fetch(`${API_URL}?action=add_model&model_name=${encodeURIComponent(modelName)}&_=${new Date().getTime()}`)
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
                console.error("Błąd dodawania modelki:", error);
                showToast('Błąd sieciowy podczas dodawania modelki.', true);
                statusSpan.textContent = '';
            });
    }

    function updateGalleryUI(galleryId, downloaded, expected, scanSessionFound, titleFromServer = null, urlFromServer = null, folderFromServer = null) {
        const galleryLi = document.getElementById('gallery_li_' + galleryId);
        if (!galleryLi) { 
            console.warn("updateGalleryUI: Nie znaleziono LI dla galerii", galleryId); 
            return; 
        }

        const statusSpan = galleryLi.querySelector('.gallery-status');
        const progressBar = galleryLi.querySelector('.progress-bar');
        const progressContainer = galleryLi.querySelector('.progress-bar-container');
        const newlyFoundSpan = galleryLi.querySelector('.newly-found-count');
        const linkA = galleryLi.querySelector('.gallery-link a');

        if (!statusSpan || !progressBar || !progressContainer || !newlyFoundSpan || !linkA) {
            console.warn("updateGalleryUI: Brak jednego z elementów UI dla galerii", galleryId); 
            return;
        }

        const expectedVal = (expected !== null && expected !== undefined) ? parseInt(expected, 10) : (galleryLi.dataset.expected !== '?' ? parseInt(galleryLi.dataset.expected, 10) : '?');
        const expectedText = (expectedVal === '?' || isNaN(expectedVal)) ? '?' : expectedVal;
        
        let currentDownloadedVal = (downloaded !== null && downloaded !== undefined && !isNaN(parseInt(downloaded, 10))) ? parseInt(downloaded, 10) : (parseInt(galleryLi.dataset.downloaded, 10) || 0);
        
        galleryLi.dataset.downloaded = currentDownloadedVal;
        if (expectedText !== '?') galleryLi.dataset.expected = expectedText;


        if (titleFromServer && linkA.textContent !== titleFromServer) {
            linkA.textContent = titleFromServer;
        }
        if (urlFromServer && linkA.href !== urlFromServer) {
            linkA.href = urlFromServer;
        }
        if (folderFromServer && linkA.title !== `Folder: ${folderFromServer}`) {
             linkA.title = `Folder: ${folderFromServer}`;
        }


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
            if (expectedVal > 0) {
                 progress = (currentDownloadedVal / expectedVal * 100);
            } else if (expectedVal === 0 && currentDownloadedVal === 0) { 
                progress = 100;
            }
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
        if (!statusDiv) { 
            console.error("updateStatus: statusDiv nie jest zdefiniowany!");
            return;
        }

        fetch(`${API_URL}?action=get_status&_=${new Date().getTime()}`)
            .then(response => {
                if (!response.ok) throw new Error('HTTP error! status: ' + response.status);
                return response.json();
            })
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
                    } else {
                        console.warn(`updateStatus: Próba aktualizacji nieistniejącej galerii ${activeGalleryIdForUI} jako przetwarzanej.`);
                    }
                    updateGalleryUI(activeGalleryIdForUI, data.current_download_count, data.current_expected_count, data.scan_session_found_count);
                    
                    // Jeśli modal przeglądarki obrazków jest otwarty dla tej galerii, odśwież go
                    if (imageViewerModal.style.display === 'block' && currentlyViewedGalleryId === activeGalleryIdForUI) {
                        // Można dodać mały delay, aby dać czas plikom na pojawienie się
                        setTimeout(() => {
                            fetchGalleryFilesForModal(currentlyViewedGalleryId, imageViewerTitle.textContent.replace("Pliki dla: ",""));
                        }, 1000); 
                    }
                
                } else if (!data.is_processing && galleryThatWasProcessing) { 
                    console.log(`Galeria ${galleryThatWasProcessing} zakończyła przetwarzanie. Finalna aktualizacja UI.`);
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
                console.error("Błąd odświeżania statusu (catch):", error); 
                if (statusDiv) { 
                    statusDiv.textContent = 'Błąd odświeżania statusu: ' + error.message; 
                    statusDiv.style.backgroundColor = '#ffcdd2'; 
                }
            }); 
    }

    function triggerDelayedAggregateRefresh(delay = 2500) { 
        if (aggregateRefreshTimeout) clearTimeout(aggregateRefreshTimeout);
        console.log(`Planuję odświeżenie agregatu za ${delay}ms.`);
        aggregateRefreshTimeout = setTimeout(() => {
            console.log("Uruchamiam odświeżanie danych agregatu modeli...");
            fetchAggregateDataAndUpdateModels(false); 
        }, delay);
    }

    function fetchAggregateDataAndUpdateModels(forceFullRender = false) {
        console.log(`fetchAggregateDataAndUpdateModels wywołane. forceFullRender: ${forceFullRender}`);
        fetch(`${API_URL}?action=get_aggregate&_=${new Date().getTime()}`)
            .then(response => {
                if (!response.ok) {
                    console.error(`Błąd HTTP w get_aggregate: ${response.status} ${response.statusText}`);
                    return response.text().then(text => { 
                        throw new Error(`HTTP error! status: ${response.status} ${response.statusText}, body: ${text.substring(0,500)}`);
                    });
                }
                return response.json();
            })
            .then(aggregateData => {
                console.log("Odpowiedź z get_aggregate (surowa):", aggregateData); 
                if (aggregateData && aggregateData.models && typeof aggregateData.models === 'object') { 
                    console.log("Otrzymano dane agregatu. Liczba modeli:", Object.keys(aggregateData.models).length); 
                    const modelsData = aggregateData.models;
                    const modelNamesSorted = Object.keys(modelsData).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));

                    if(forceFullRender) { 
                        modelTreeUl.innerHTML = ''; 
                        console.log("Wyczyszczono modelTreeUl z powodu forceFullRender."); 
                    }
                    
                    if (modelNamesSorted.length === 0 && forceFullRender) { 
                         modelTreeUl.innerHTML = '<li>Brak modeli na liście lub w bazie danych. Dodaj modelki do pliku `lista.txt`, uruchom skrypt Python, następnie odśwież.</li>';
                         console.log("Wyświetlono komunikat o braku modeli."); 
                         return; 
                    } else if (forceFullRender && modelTreeUl.querySelector('.loader')) { 
                         modelTreeUl.querySelector('.loader').remove();
                         console.log("Usunięto loader."); 
                    }


                    modelNamesSorted.forEach(modelNameOriginal => {
                        const modelData = modelsData[modelNameOriginal];
                        if (typeof modelData !== 'object' || modelData === null) { 
                            console.warn(`Nieprawidłowe dane dla modelu ${modelNameOriginal}, pomijam.`);
                            return; 
                        }
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
                                <button class="btn-action" onclick="prioritizeItem('scan_model_refresh_only', '${escapedModelName}')" title="Tylko skanuj i aktualizuj opisy/liczniki (bez dodawania do kolejki pobierania)">Odśwież Opisy</button>
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
                                    console.log(`Rozwinięto model ${modelNameOriginal}. Ładuję galerie (pierwszy raz)...`); 
                                    fetchAggregateDataAndUpdateModels(false); 
                                } else if (nestedUl.classList.contains('active')) {
                                     console.log(`Model ${modelNameOriginal} już był rozwinięty i galerie załadowane.`);
                                }
                            });
                            console.log("Utworzono nowy LI dla modelu:", modelNameOriginal); 
                        } else {
                            nestedUl = modelLiElement.querySelector('ul.nested');
                            console.log("Znaleziono istniejący LI dla modelu:", modelNameOriginal); 
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
                             console.log(`Aktualizuję galerie dla ${modelNameOriginal} (aktywny: ${nestedUl.classList.contains('active')}, force: ${forceFullRender})`); 
                            if(forceFullRender || (nestedUl.classList.contains('active') && !nestedUl.dataset.galleriesLoadedOnce)) {
                                nestedUl.innerHTML = ''; 
                                console.log(`Wyczyszczono galerie dla ${modelNameOriginal}.`); 
                            }
                            
                            const galleriesFromServer = modelData.galleries || {};
                            const galleryIdsSorted = Object.keys(galleriesFromServer).sort((a,b) => {
                                const titleA = (galleriesFromServer[a] && galleriesFromServer[a].title) ? galleriesFromServer[a].title : a;
                                const titleB = (galleriesFromServer[b] && galleriesFromServer[b].title) ? galleriesFromServer[b].title : b;
                                return titleA.toLowerCase().localeCompare(titleB.toLowerCase());
                            });

                            galleryIdsSorted.forEach(galleryId => {
                                const gData = galleriesFromServer[galleryId];
                                if (typeof gData !== 'object' || gData === null) {
                                     console.warn(`Nieprawidłowe dane dla galerii ${galleryId} w modelu ${modelNameOriginal}, pomijam.`);
                                     return;
                                }
                                let galleryLi = document.getElementById('gallery_li_' + galleryId);
                                const escapedGalleryIdForJS = galleryId.replace(/'/g, "\\'");
                                const escapedGalleryTitleForJS = (gData.title || galleryId).replace(/'/g, "\\'");
                                // const escapedModelSanitizedNameForJS = sanitizedModelName.replace(/'/g, "\\'"); // Już jest sanitizowane

                                if (!galleryLi) {
                                    galleryLi = document.createElement('li');
                                    galleryLi.className = 'gallery-li';
                                    galleryLi.id = 'gallery_li_' + galleryId;
                                    galleryLi.innerHTML = `
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
                                            <button class="btn-action" onclick="showGalleryFiles('${escapedGalleryIdForJS}', '${escapedGalleryTitleForJS}')" title="Pokaż pliki galerii">Galeria</button>
                                            <button class="btn-action" onclick="prioritizeItem('gallery', '${escapedGalleryIdForJS}')" title="Uzupełnij tę galerię priorytetowo">Uzupełnij</button>
                                            <a href="${gData.url || '#'}" target="_blank" class="btn-action" title="Otwórz stronę źródłową galerii">Źródło</a>
                                        </div>
                                    `;
                                    nestedUl.appendChild(galleryLi);
                                } else { // Aktualizuj istniejący przycisk "Galeria", jeśli tytuł się zmienił
                                    const galleryButton = galleryLi.querySelector('button[onclick^="showGalleryFiles"]');
                                    if(galleryButton) {
                                        galleryButton.setAttribute('onclick', `showGalleryFiles('${escapedGalleryIdForJS}', '${escapedGalleryTitleForJS}')`);
                                    }
                                }
                                updateGalleryUI(galleryId, gData.downloaded, gData.expected, null, gData.title, gData.url, gData.folder);
                                if (galleryId === activeGalleryIdForUI && statusDiv && statusDiv.style.backgroundColor.includes('e0f7fa')) { 
                                     galleryLi.classList.add('processing');
                                } else {
                                     galleryLi.classList.remove('processing');
                                }
                            });
                             nestedUl.dataset.galleriesLoadedOnce = "true"; 
                        }
                    });
                    
                    const loaderLiFinal = modelTreeUl.querySelector('.loader');
                    if (loaderLiFinal) {
                        loaderLiFinal.remove();
                        console.log("Usunięto loader (finalnie)."); 
                    }

                    console.log("Dane agregatu modeli zaktualizowane na stronie."); 
                    const lastUpdateSpan = document.getElementById("last-aggregate-update-time");
                    if(lastUpdateSpan) {
                        const now = new Date();
                        lastUpdateSpan.textContent = `(Dane z DB: ${now.toLocaleTimeString()})`;
                    }
                } else {
                     console.error("Brak obiektu 'models' w odpowiedzi z get_aggregate lub aggregateData jest niepoprawne. Odpowiedź:", aggregateData);
                     if(forceFullRender) modelTreeUl.innerHTML = '<li>Brak danych modeli lub nieprawidłowa odpowiedź z API. (force render)</li>'; 
                }
            })
            .catch(error => {
                 console.error("Błąd odświeżania agregatu modeli (catch):", error); 
                 if(forceFullRender) modelTreeUl.innerHTML = '<li>Wystąpił błąd podczas ładowania danych modeli. Sprawdź konsolę. (catch)</li>';
                 if (statusDiv) { 
                    statusDiv.textContent = 'Błąd ładowania danych modeli: ' + error.message;
                    statusDiv.style.backgroundColor = '#ffcdd2';
                 }
            });
    }

    // --- Funkcje dla modala przeglądarki obrazków ---
    function openImageViewerModal(galleryId, galleryTitle) {
        currentlyViewedGalleryId = galleryId;
        imageViewerTitle.textContent = "Pliki dla: " + galleryTitle;
        imageViewerFilesDiv.innerHTML = ''; // Wyczyść poprzednie pliki
        imageViewerStatusDiv.textContent = 'Ładowanie plików...';
        imageViewerModal.style.display = 'block';
        fetchGalleryFilesForModal(galleryId, galleryTitle);
    }

    function closeImageViewerModal() {
        imageViewerModal.style.display = 'none';
        imageViewerFilesDiv.innerHTML = '';
        currentlyViewedGalleryId = null;
    }

    function fetchGalleryFilesForModal(galleryId, galleryTitle) { // galleryTitle dodane dla spójności
        console.log(`Pobieranie plików dla galerii ${galleryId} (${galleryTitle}) do modala.`);
        imageViewerStatusDiv.textContent = 'Pobieranie listy plików...';
        fetch(`${API_URL}?action=get_gallery_files&gallery_id=${encodeURIComponent(galleryId)}&_=${new Date().getTime()}`)
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        throw new Error(`Błąd HTTP ${response.status} ${response.statusText}: ${text.substring(0,200)}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log("Odpowiedź z get_gallery_files:", data);
                if (data.success) {
                    imageViewerFilesDiv.innerHTML = ''; // Wyczyść ponownie na wypadek wielokrotnego wywołania
                    if (data.files && data.files.length > 0) {
                        imageViewerStatusDiv.textContent = `Znaleziono ${data.files.length} plików.`;
                        // Zakładamy, że `Modelki` jest w tym samym katalogu co `status.php` na serwerze WWW
                        // Jeśli jest inaczej, trzeba dostosować tę ścieżkę.
                        const baseWebPathToModelki = "Modelki"; // Dostosuj, jeśli Modelki są gdzie indziej
                        
                        data.files.forEach(filename => {
                            const img = document.createElement('img');
                            // web_path_segment to np. ModelNameSanitized/GalleryFolderName
                            // Pełna ścieżka do pliku będzie: Modelki/ModelNameSanitized/GalleryFolderName/filename.jpg
                            // Jeśli folder Modelki nie jest w katalogu głównym projektu, trzeba dostosować
                            img.src = `${data.web_path_segment}/${filename}`; 
                            img.alt = filename;
                            img.title = filename;
                            img.onerror = function() { this.alt='Błąd ładowania'; this.style.border='1px solid red'; console.error("Błąd ładowania obrazka:", this.src);};
                            // Proste otwieranie w nowej karcie po kliknięciu
                            img.onclick = () => window.open(img.src, '_blank');
                            imageViewerFilesDiv.appendChild(img);
                        });
                    } else {
                        imageViewerStatusDiv.textContent = 'Brak plików w tej galerii lub folder nie istnieje.';
                    }
                } else {
                    imageViewerStatusDiv.textContent = `Błąd: ${data.message || 'Nie udało się pobrać listy plików.'}`;
                    showToast(`Błąd pobierania plików galerii: ${data.message || 'Nieznany błąd.'}`, true);
                }
            })
            .catch(error => {
                console.error('Błąd fetchGalleryFilesForModal:', error);
                imageViewerStatusDiv.textContent = `Błąd sieciowy: ${error.message}`;
                showToast(`Błąd sieciowy przy pobieraniu plików galerii: ${error.message}`, true);
            });
    }
    
    // Funkcja wywoływana przez przycisk "Galeria"
    function showGalleryFiles(galleryId, galleryTitle) {
        openImageViewerModal(galleryId, galleryTitle);
    }
    // --- Koniec funkcji dla modala ---


    document.addEventListener('DOMContentLoaded', function() {
        updateStatus(); 
        fetchAggregateDataAndUpdateModels(true); 
        fetchAndDisplayQueue(); 

        setInterval(updateStatus, 2800); 
        setInterval(() => fetchAggregateDataAndUpdateModels(false), 25000); 
        setInterval(fetchAndDisplayQueue, 30000); 
    });

    // --- Zarządzanie Kolejką (bez zmian) ---
    let draggedItem = null;
    let queueDataCache = []; 

    function getQueueItemDisplay(item) {
        let display = `Typ: ${item.type}`;
        if ((item.type === 'scan_model' || item.type === 'scan_model_refresh_only') && typeof item.data === 'string') {
            display += ` | Model: ${item.data}`;
        } else if (item.type === 'gallery' && typeof item.data === 'object' && item.data !== null) {
            const galleryTitle = item.data.title || item.data.id || 'Nieznana galeria';
            const modelName = item.data.model_name || '?';
            display += ` | Galeria: ${galleryTitle} (Model: ${modelName})`;
        } else {
            display += ` | Dane: ${JSON.stringify(item.data).substring(0, 50)}...`;
        }
        return display;
    }

    function populateQueueList(queue) {
        queueDataCache = queue; 
        const list = document.getElementById('priority-queue-list');
        list.innerHTML = ''; 
        if (queue.length === 0) {
            list.innerHTML = '<li>Kolejka jest pusta.</li>';
        } else {
            queue.forEach((item, index) => {
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
                removeBtn.onclick = () => {
                    queueDataCache.splice(index, 1); 
                    populateQueueList(queueDataCache); 
                    updateQueueCount();
                };
                controls.appendChild(removeBtn);
                li.appendChild(controls);
                list.appendChild(li);
            });
        }
        updateQueueCount();
    }

    function updateQueueCount() {
        document.getElementById('queue-count').textContent = queueDataCache.length;
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
        fetch(`${API_URL}?action=get_queue&_=${new Date().getTime()}`)
            .then(response => response.json())
            .then(data => {
                populateQueueList(data || []);
            })
            .catch(error => {
                console.error("Błąd pobierania kolejki:", error);
                document.getElementById('priority-queue-list').innerHTML = '<li>Błąd ładowania kolejki.</li>';
                updateQueueCount(); 
            });
    }

    function openQueueModal() {
        document.getElementById('queue-modal').style.display = 'block';
        fetchAndDisplayQueue(); 
    }

    function closeQueueModal() {
        document.getElementById('queue-modal').style.display = 'none';
        document.getElementById('queue-status').textContent = ''; 
    }

    function saveQueueOrder() {
        const statusSpan = document.getElementById('queue-status');
        statusSpan.textContent = 'Zapisywanie...';
        statusSpan.style.color = '#555';

        fetch(`${API_URL}?action=update_queue`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(queueDataCache) 
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                statusSpan.textContent = 'Kolejka zapisana!';
                statusSpan.style.color = 'green';
                showToast('Kolejka priorytetowa została zaktualizowana.');
            } else {
                statusSpan.textContent = `Błąd: ${data.message || 'Nieznany błąd serwera.'}`;
                statusSpan.style.color = 'red';
                showToast(`Błąd zapisu kolejki: ${data.message || 'Nieznany błąd.'}`, true);
            }
            setTimeout(() => { statusSpan.textContent = ''; }, 3000);
            updateQueueCount(); 
        })
        .catch(error => {
            console.error('Błąd zapisu kolejki:', error);
            statusSpan.textContent = 'Błąd sieciowy!';
            statusSpan.style.color = 'red';
            showToast('Błąd sieciowy podczas zapisu kolejki.', true);
        });
    }

    window.onclick = function(event) {
        const modal = document.getElementById('queue-modal');
        if (event.target == modal) {
            closeQueueModal();
        }
        // Zamknij modal przeglądarki obrazków, jeśli kliknięto poza nim
        if (event.target == imageViewerModal) {
            closeImageViewerModal();
        }
    };
</script>

</body>
</html>