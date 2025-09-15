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
<?php $basePath = rtrim(dirname($_SERVER['SCRIPT_NAME'] ?? ''), '/\\'); ?>

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




<script src="<?=$basePath?>/assets/js/runtime.js"></script>
<script src="<?=$basePath?>/assets/js/app.js"></script>
</body>
</html>