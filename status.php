<?php
// status.php
require_once 'php_config.php';
require_once 'php_utils.php';

$global_data = load_json_file(STATUS_JSON_AGGREGATE_PATH, ["models" => []]);
$models = $global_data['models'] ?? [];
$sorted_models = $models;
uksort($sorted_models, function ($a, $b) {
    return strcasecmp($a, $b);
});

$aggregate_last_modified_timestamp = "N/A";
if (file_exists(STATUS_JSON_AGGREGATE_PATH)) {
    $aggregate_last_modified_timestamp = date("Y-m-d H:i:s", filemtime(STATUS_JSON_AGGREGATE_PATH));
}

?>
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Status Pobierania (PHP)</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.5; padding: 15px; background-color: #f9f9f9; }
        ul { list-style-type: none; padding-left: 0; }
        .model-li > ul.nested { padding-left: 20px; }
        .toggle { cursor: pointer; margin-right: 8px; font-weight: bold; user-select: none; width: 15px; display: inline-block; text-align: center; color: #333; }
        .model-li { margin-bottom: 8px; background-color: #fff; border: 1px solid #ddd; padding: 0; border-radius: 5px; box-shadow: 0 1px 2px rgba(0, 0, 0, .05); overflow: hidden; }
        .model-header { display: flex; align-items: center; padding: 8px 12px; background-color: #e9ecef; border-bottom: 1px solid #ddd; transition: background-color 0.3s; }
        .model-li.model-partial > .model-header { background-color: #FFE0B2; } 
        .model-li.model-complete > .model-header { background-color: #A5D6A7; }
        .model-li.model-processing > .model-header { background-color: #ADD8E6; }
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
        h1 small#last-aggregate-update-time { color: #6c757d; font-size: .7em; }
        a { text-decoration: none; color: #007bff; } a:hover { text-decoration: underline; }
        #current-status { font-size: 0.9em; font-weight: bold; color: #555; background-color: #fff; padding: 10px; border-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,.05); margin-bottom: 15px; border: 1px solid #ddd; min-height: 1.2em; transition: background-color 0.5s; }
        .progress-bar-container { width: 80px; height: 12px; background-color: #e0e0e0; border-radius: 5px; overflow: hidden; display: inline-block; margin-left: 10px; vertical-align: middle; border: 1px solid #c5c5c5; }
        .progress-bar { height: 100%; background-color: #4CAF50; width: 0%; transition: width 0.3s ease-in-out; text-align: center; color: white; font-size: 0.7em; line-height: 12px; }
        .progress-bar.orange { background-color: #fd7e14; } .progress-bar.red { background-color: #dc3545; }
        .btn-action { font-size: 0.8em; padding: 3px 7px; margin-left: 5px; cursor: pointer; border: 1px solid #ccc; background-color: #f0f0f0; border-radius: 3px; color: #333; text-decoration: none; display: inline-block; }
        .btn-action:hover { background-color: #e0e0e0; text-decoration: none; color: #333; }
        #toast { position: fixed; bottom: 20px; right: 20px; background-color: #333; color: white; padding: 15px; border-radius: 5px; z-index: 1000; opacity: 0; visibility: hidden; transition: opacity 0.5s, visibility 0.5s; font-size: 0.9em; }
        #toast.show { opacity: 1; visibility: visible; }
        .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(0, 0, 0, 0.1); border-left-color: #007bff; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 8px; vertical-align: middle; visibility: hidden; }
        .gallery-li.processing .spinner { visibility: visible; }
        #add-model-section { margin-bottom: 15px; padding: 10px; background-color: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; display: flex; align-items: center; gap: 10px; }
        #add-model-section input[type="text"] { padding: 6px; border: 1px solid #ccc; border-radius: 3px; flex-grow: 1; }
        #add-model-section button { padding: 6px 12px; }
        #add-model-status { font-size: 0.9em; color: #555; }
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
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>

<div id="toast">Wiadomość toast!</div>
<div id="current-status">Ładowanie statusu...</div>

<h1>Status Pobierania <small id="last-aggregate-update-time">(Dane zbiorcze: <?php echo htmlspecialchars($aggregate_last_modified_timestamp); ?>)</small>
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
    <?php foreach ($sorted_models as $model_name => $model_data): ?>
        <?php
            $model_name_sanitized = $model_data['sanitized_name'] ?? sanitize_foldername($model_name);
            $galleries = $model_data['galleries'] ?? [];
            $total_galleries = count($galleries);
            $completed_galleries = 0;
            foreach ($galleries as $g_info) {
                if (is_array($g_info) && ($g_info['completed'] ?? false)) {
                    $completed_galleries++;
                }
            }
            $model_progress = ($total_galleries > 0) ? ($completed_galleries / $total_galleries * 100) : 0;
            
            $model_li_class = "model-li";
            if ($total_galleries > 0 && $completed_galleries === $total_galleries) {
                $model_li_class .= " model-complete";
            } elseif ($completed_galleries > 0 && $completed_galleries < $total_galleries) {
                $model_li_class .= " model-partial";
            }
        ?>
        <li class="<?php echo htmlspecialchars($model_li_class); ?>" data-model-name="<?php echo htmlspecialchars($model_name_sanitized); ?>">
            <div class="model-header">
                <span class="toggle">+</span>
                <span class="model-name"><?php echo htmlspecialchars($model_name); ?> (<?php echo $completed_galleries; ?>/<?php echo $total_galleries; ?>)</span>
                <div class="progress-bar-container" title="<?php echo number_format($model_progress, 1); ?>% ukończonych galerii">
                    <div class="progress-bar" style="width:<?php echo number_format($model_progress, 1); ?>%;"><?php echo number_format($model_progress, 0); ?>%</div>
                </div>
                <button class="btn-action" onclick="prioritizeItem('scan_model', '<?php echo htmlspecialchars($model_name, ENT_QUOTES); ?>')" title="Uzupełnij lub rozpocznij przetwarzanie tej modelki">Uzupełnij Model</button>
            </div>
            <ul class="nested">
                <?php
                    $sorted_galleries = $galleries;
                    uasort($sorted_galleries, function ($a, $b) {
                        return strcasecmp($a['title'] ?? '', $b['title'] ?? '');
                    });
                ?>
                <?php foreach ($sorted_galleries as $gallery_id => $gallery_info): ?>
                    <?php
                        if (!is_array($gallery_info)) continue;
                        $title_html = htmlspecialchars($gallery_info['title'] ?? $gallery_id);
                        $expected = $gallery_info['expected'] ?? null;
                        $downloaded = $gallery_info['downloaded'] ?? 0;
                        $url = $gallery_info['url'] ?? '#';
                        $color = $gallery_info['status_color'] ?? 'red';
                        $folder = htmlspecialchars($gallery_info['folder'] ?? 'Brak');
                        $gallery_progress = 0;
                        if ($expected !== null && $expected > 0) {
                            $gallery_progress = ($downloaded / $expected * 100);
                        } elseif (($gallery_info['completed'] ?? false) && ($expected === 0 || $expected === null) && $downloaded === 0) {
                             // Dla galerii pustych (0/0), ale oznaczonych jako completed
                            $gallery_progress = 100;
                        } elseif (($gallery_info['completed'] ?? false)) {
                            $gallery_progress = 100;
                        }

                        $progress_bar_color_class = ($gallery_progress >= 100) ? 'green' : ($downloaded > 0 ? 'orange' : 'red');
                        $expected_text = $expected !== null ? $expected : '?';
                    ?>
                    <li class="gallery-li" id="gallery_li_<?php echo htmlspecialchars($gallery_id); ?>" data-expected="<?php echo $expected_text; ?>" data-downloaded="<?php echo $downloaded; ?>">
                        <span class="gallery-link">
                            <span class="spinner" id="spinner_<?php echo htmlspecialchars($gallery_id); ?>"></span>
                            <a href="<?php echo htmlspecialchars($url); ?>" target="_blank" title="Folder: <?php echo $folder; ?>"><?php echo $title_html; ?></a>
                        </span>
                        <div class="gallery-controls">
                            <span class="newly-found-count" id="newly_found_<?php echo htmlspecialchars($gallery_id); ?>"></span>
                            <div class="progress-bar-container" id="progress_container_<?php echo htmlspecialchars($gallery_id); ?>" title="D: <?php echo $downloaded; ?>/<?php echo $expected_text; ?> (<?php echo number_format($gallery_progress, 1); ?>%)">
                                <div class="progress-bar <?php echo $progress_bar_color_class; ?>" id="progress_bar_<?php echo htmlspecialchars($gallery_id); ?>" style="width:<?php echo number_format($gallery_progress, 1); ?>%;"><?php echo number_format($gallery_progress, 0); ?>%</div>
                            </div>
                            <span class="gallery-status <?php echo $color; ?>" id="status_<?php echo htmlspecialchars($gallery_id); ?>">D: <?php echo $downloaded; ?>/<?php echo $expected_text; ?></span>
                            <button class="btn-action" onclick="prioritizeItem('gallery', '<?php echo htmlspecialchars($gallery_id, ENT_QUOTES); ?>')" title="Uzupełnij tę galerię priorytetowo">Uzupełnij</button>
                            <a href="<?php echo htmlspecialchars($url); ?>" target="_blank" class="btn-action" title="Otwórz stronę źródłową galerii">Źródło</a>
                        </div>
                    </li>
                <?php endforeach; ?>
            </ul>
        </li>
    <?php endforeach; ?>
    <?php if (empty($sorted_models)): ?>
        <li>Brak modeli na liście lub plik statusu nie został jeszcze wygenerowany. Uruchom skrypt Python.</li>
    <?php endif; ?>
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

<script>
    const API_URL = '<?php echo API_URL; ?>';
    const toastDiv = document.getElementById('toast');
    
    let activeGalleryIdForUI = null; 
    let activeModelNameSanitizedForUI = null;
    let aggregateRefreshTimeout = null;

    function pySanitizeForQuerySelector(name) {
        if (typeof name !== 'string') name = String(name);
        let sanitized = name.trim();
        sanitized = sanitized.replace(/[<>:"\/\\|?*\x00-\x1F\t\n\r\f\v]/g, '_');
        sanitized = sanitized.replace(/\s+/g, ' ');
        sanitized = sanitized.trim();
        if (sanitized.length > 1) {
            sanitized = sanitized.replace(/_+/g, '_');
            sanitized = sanitized.replace(/-+/g, '-');
        }
        sanitized = sanitized.replace(/^[\s._-]+|[\s._-]+$/g, '');
        if (sanitized.length > 150) sanitized = sanitized.substring(0, 150);
        sanitized = sanitized.replace(/^[\s._-]+|[\s._-]+$/g, '');
        sanitized = sanitized.replace(/\s+/g, '_');
        return sanitized ? sanitized : "_fallback_sanitized_name_";
    }

    function showToast(message, isError = false) { /* ... bez zmian ... */ }
    function prioritizeItem(type, id) { /* ... bez zmian ... */ }
    function addModelToList() { /* ... bez zmian ... */ }
    
    function updateGalleryUI(galleryId, downloaded, expected, scanSessionFound) {
        // === DODANO LOGOWANIE PARAMETRÓW ===
        console.log(`updateGalleryUI CALLED for ${galleryId}: downloaded=${downloaded} (type: ${typeof downloaded}), expected=${expected} (type: ${typeof expected}), scanSessionFound=${scanSessionFound}`);
        // =====================================

        const galleryLi = document.getElementById('gallery_li_' + galleryId);
        if (!galleryLi) { console.warn("updateGalleryUI: Nie znaleziono LI dla galerii", galleryId); return; }
        
        const statusSpan = document.getElementById('status_' + galleryId);
        const progressBar = document.getElementById('progress_bar_' + galleryId);
        const progressContainer = document.getElementById('progress_container_' + galleryId);
        const newlyFoundSpan = document.getElementById('newly_found_' + galleryId);

        if (!statusSpan || !progressBar || !progressContainer || !newlyFoundSpan) {
            console.warn("updateGalleryUI: Brak jednego z elementów UI dla galerii", galleryId);
            return;
        }

        const expectedValFromParam = (expected !== null && expected !== undefined) ? expected : galleryLi.dataset.expected;
        const expectedText = (expectedValFromParam === '?' || expectedValFromParam === null || expectedValFromParam === undefined || isNaN(parseInt(expectedValFromParam,10))) ? '?' : parseInt(expectedValFromParam, 10);
        
        // Używaj wartości z parametru 'downloaded', jeśli jest dostępna i jest liczbą.
        // W przeciwnym razie spróbuj z dataset, ale upewnij się, że to liczba.
        let currentDownloadedVal;
        if (downloaded !== null && downloaded !== undefined && !isNaN(parseInt(downloaded, 10))) {
            currentDownloadedVal = parseInt(downloaded, 10);
        } else {
            currentDownloadedVal = parseInt(galleryLi.dataset.downloaded, 10);
            if (isNaN(currentDownloadedVal)) currentDownloadedVal = 0; // Fallback na 0, jeśli dataset też jest zły
        }
        galleryLi.dataset.downloaded = currentDownloadedVal; // Zawsze aktualizuj dataset poprawną liczbą

        if (scanSessionFound !== null && scanSessionFound !== undefined && scanSessionFound > 0) {
            newlyFoundSpan.textContent = 'Nowych: ' + scanSessionFound;
            newlyFoundSpan.style.display = 'inline';
        } else {
            newlyFoundSpan.style.display = 'none';
        }

        let statusText = 'D: ' + currentDownloadedVal + '/' + expectedText;
        let progress = 0;
        let color = 'red';

        if (expectedText !== '?') {
            const numExpected = parseInt(expectedText, 10); // expectedText jest już liczbą lub '?'
            if (numExpected > 0) {
                 progress = (currentDownloadedVal / numExpected * 100);
            } else if (numExpected === 0 && currentDownloadedVal === 0) {
                progress = 100; // Pusta, ale kompletna
            }
             // Kolor na podstawie progresu lub jeśli galeria pusta ale kompletna
            color = (progress >= 100 || (numExpected === 0 && currentDownloadedVal === 0)) ? 'green' : (currentDownloadedVal > 0 ? 'orange' : 'red');
        } else { // expectedText jest '?'
            color = currentDownloadedVal > 0 ? 'orange' : 'red';
        }
        
        statusSpan.textContent = statusText;
        statusSpan.className = 'gallery-status ' + color;

        const progressPercent = Math.min(100, Math.max(0, progress)); // Upewnij się, że progres jest w zakresie 0-100
        progressBar.style.width = progressPercent.toFixed(1) + '%';
        progressBar.textContent = progressPercent.toFixed(0) + '%';
        progressBar.className = 'progress-bar ' + color;
        progressContainer.title = `Pobrano: ${currentDownloadedVal}/${expectedText} (${progressPercent.toFixed(1)}%)`;
    }

    function updateStatus() {
        const statusDiv = document.getElementById('current-status');
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
                    if (currentGalleryLi) currentGalleryLi.classList.add('processing');
                    updateGalleryUI(activeGalleryIdForUI, data.current_download_count, data.current_expected_count, data.scan_session_found_count);
                
                } else if (!data.is_processing && galleryThatWasProcessing) {
                    console.log(`Galeria ${galleryThatWasProcessing} zakończyła. Finalna aktualizacja UI z current_status.json.`);
                    const finishedGalleryLi = document.getElementById('gallery_li_' + galleryThatWasProcessing);
                    if (finishedGalleryLi) finishedGalleryLi.classList.remove('processing');
                    
                    updateGalleryUI(galleryThatWasProcessing, data.current_download_count, data.current_expected_count, null);
                    activeGalleryIdForUI = null; 
                    
                    if(modelSanitizedThatWasProcessing && !currentProcessingModelSanitized){
                        const oldModelLi = document.querySelector(`.model-li[data-model-name="${modelSanitizedThatWasProcessing}"]`);
                        if (oldModelLi) oldModelLi.classList.remove('model-processing');
                    }
                    triggerDelayedAggregateRefresh();
                } else {
                     activeGalleryIdForUI = null;
                     if (modelSanitizedThatWasProcessing && !currentProcessingModelSanitized) {
                         const oldModelLi = document.querySelector(`.model-li[data-model-name="${modelSanitizedThatWasProcessing}"]`);
                         if (oldModelLi) {
                             oldModelLi.classList.remove('model-processing');
                             triggerDelayedAggregateRefresh();
                         }
                     }
                }
            })
            .catch(error => { console.error("Błąd odświeżania statusu:", error); /* ... reszta bez zmian ... */ });
    }

    function triggerDelayedAggregateRefresh(delay = 2000) { /* Zmieniono domyślne opóźnienie na 2s */
        if (aggregateRefreshTimeout) clearTimeout(aggregateRefreshTimeout);
        console.log(`Planuję odświeżenie agregatu za ${delay}ms.`);
        aggregateRefreshTimeout = setTimeout(() => {
            console.log("Uruchamiam odświeżanie danych agregatu modeli...");
            fetchAggregateDataAndUpdateModels();
        }, delay);
    }

    function fetchAggregateDataAndUpdateModels() {
        fetch(`${API_URL}?action=get_aggregate&_=${new Date().getTime()}`)
            .then(response => {
                if (!response.ok) throw new Error('HTTP error! status: ' + response.status);
                return response.json();
            })
            .then(aggregateData => {
                if (aggregateData && aggregateData.models) {
                    console.log("Otrzymano dane agregatu, aktualizuję modele.");
                    let anyChangeRequiringUIToggleUpdate = false;
                    for (const modelNameOriginal in aggregateData.models) {
                        if (aggregateData.models.hasOwnProperty(modelNameOriginal)) {
                            const modelDataFromServer = aggregateData.models[modelNameOriginal];
                            const sanitizedModelName = modelDataFromServer.sanitized_name || pySanitizeForQuerySelector(modelNameOriginal);
                            const modelLiElement = document.querySelector(`.model-li[data-model-name="${sanitizedModelName}"]`);

                            if (modelLiElement) {
                                const galleriesFromServer = modelDataFromServer.galleries || {};
                                let completedInModel = 0;
                                const totalInModel = Object.keys(galleriesFromServer).length;

                                for (const galleryId in galleriesFromServer) {
                                    if (galleriesFromServer[galleryId].completed) {
                                        completedInModel++;
                                    }
                                    const galleryLi = document.getElementById('gallery_li_' + galleryId);
                                    // Aktualizuj galerie tylko jeśli model jest rozwinięty, aby nie robić za dużo pracy
                                    const nestedUl = modelLiElement.querySelector('ul.nested');
                                    if(galleryLi && nestedUl && nestedUl.classList.contains('active')){
                                        const gData = galleriesFromServer[galleryId];
                                        // Przekazuj explicite null dla scanSessionFound, bo nie jest tu relevantne
                                        updateGalleryUI(galleryId, gData.downloaded, gData.expected, null);
                                    }
                                }
                                
                                // Aktualizacja klas CSS modelu (tylko jeśli nie jest aktualnie przetwarzany)
                                if (!modelLiElement.classList.contains('model-processing')) {
                                    let appliedClass = "";
                                    if (totalInModel > 0 && completedInModel === totalInModel) appliedClass = "model-complete";
                                    else if (completedInModel > 0 && completedInModel < totalInModel) appliedClass = "model-partial";
                                    
                                    modelLiElement.classList.remove('model-complete', 'model-partial'); // Usuń stare
                                    if(appliedClass) modelLiElement.classList.add(appliedClass); // Dodaj nową, jeśli jest
                                }

                                const modelNameSpan = modelLiElement.querySelector('.model-header .model-name');
                                const modelProgressBar = modelLiElement.querySelector('.model-header .progress-bar');
                                const modelProgressContainer = modelLiElement.querySelector('.model-header .progress-bar-container');

                                const newModelText = `${modelNameOriginal} (${completedInModel}/${totalInModel})`;
                                if (modelNameSpan && modelNameSpan.textContent !== newModelText) modelNameSpan.textContent = newModelText;
                                
                                const modelProgressPercent = totalInModel > 0 ? (completedInModel / totalInModel * 100) : 0;
                                if (modelProgressBar) {
                                    modelProgressBar.style.width = `${modelProgressPercent.toFixed(1)}%`;
                                    modelProgressBar.textContent = `${modelProgressPercent.toFixed(0)}%`;
                                }
                                if (modelProgressContainer) modelProgressContainer.title = `${modelProgressPercent.toFixed(1)}% ukończonych galerii`;
                                anyChangeRequiringUIToggleUpdate = true;
                            }
                        }
                    }
                    if(anyChangeRequiringUIToggleUpdate) console.log("Podsumowania modeli zaktualizowane przez dane agregatu.");

                    const lastAggregateUpdateSpan = document.getElementById("last-aggregate-update-time");
                    if(lastAggregateUpdateSpan) {
                        const date = new Date();
                        const timeString = date.getHours().toString().padStart(2, '0') + ':' +
                                           date.getMinutes().toString().padStart(2, '0') + ':' +
                                           date.getSeconds().toString().padStart(2, '0');
                        lastAggregateUpdateSpan.textContent = `(Dane zbiorcze: ${timeString})`;
                    }
                }
            })
            .catch(error => { console.error("Błąd odświeżania agregatu modeli:", error); });
    }
        
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('.toggle').forEach(span => {
            span.addEventListener('click', function() {
                const nestedUl = this.closest('li.model-li').querySelector('ul.nested');
                nestedUl.classList.toggle('active');
                this.textContent = nestedUl.classList.contains('active') ? '−' : '+';
                if (nestedUl.classList.contains('active')) {
                    fetchAggregateDataAndUpdateModels(); 
                }
            });
        });
        updateStatus(); 
        fetchAndDisplayQueue();
        setInterval(updateStatus, 2800); 
        setInterval(fetchAggregateDataAndUpdateModels, 15000); // Zmniejszone do 15 sekund
    });

    function getQueueItemDisplay(item) { /* ... bez zmian ... */ }
    function populateQueueList(queue) { /* ... bez zmian ... */ }
    function updateQueueCount() { /* ... bez zmian ... */ }
    function handleDragStart(e) { /* ... bez zmian ... */ }
    function handleDragOver(e) { /* ... bez zmian ... */ }
    function handleDrop(e) { /* ... bez zmian ... */ }
    function handleDragEnd(e) { /* ... bez zmian ... */ }
    function fetchAndDisplayQueue() { /* ... bez zmian ... */ }
    function openQueueModal() { /* ... bez zmian ... */ }
    function closeQueueModal() { /* ... bez zmian ... */ }
    function saveQueueOrder() { /* ... bez zmian ... */ }
    window.onclick = function(event) { /* ... bez zmian ... */ };
</script>

</body>
</html>