<?php
return [
    // Status
    "get_status" => ["controller" => "StatusController", "method" => "getCurrentStatus"],
    "clear_cache" => ["controller" => "StatusController", "method" => "clearCache"],
    
    // Models
    "get_models_list" => ["controller" => "ModelController", "method" => "getModelsList"],
    "add_model" => ["controller" => "ModelController", "method" => "addModel"],
    "get_galleries_for_model" => ["controller" => "ModelController", "method" => "getGalleriesForModel"],
    
    // Galleries
    "get_gallery_files" => ["controller" => "GalleryController", "method" => "getGalleryFiles"],
    "rename_gallery_folder" => ["controller" => "GalleryController", "method" => "renameGalleryFolder"],
    "mark_gallery_completed" => ["controller" => "GalleryController", "method" => "markGalleryCompleted"],
    "toggle_gallery_disabled_status" => ["controller" => "GalleryController", "method" => "toggleGalleryDisabled"],
    "search_galleries" => ["controller" => "GalleryController", "method" => "searchGalleries"],
    
    // Queue
    "get_queue" => ["controller" => "QueueController", "method" => "getQueue"],
    "update_queue" => ["controller" => "QueueController", "method" => "updateQueue"],
    "prioritize" => ["controller" => "QueueController", "method" => "addToQueue"],
    
    // AI
    "get_galleries_for_ai_test" => ["controller" => "AIController", "method" => "getGalleriesForTest"],
    "trigger_ai_test_run" => ["controller" => "AIController", "method" => "triggerTestRun"],
    "trigger_ai_update" => ["controller" => "AIController", "method" => "triggerUpdate"],
    "get_ai_prompt_configs" => ["controller" => "AIController", "method" => "getPromptConfigs"],
    "save_ai_prompt_config" => ["controller" => "AIController", "method" => "savePromptConfig"],
    "get_global_ai_settings" => ["controller" => "AIController", "method" => "getGlobalSettings"],
    "save_global_ai_settings" => ["controller" => "AIController", "method" => "saveGlobalSettings"],
    "promote_test_to_production" => ["controller" => "AIController", "method" => "promoteTestToProd"],
    
    // Refresh
    "refresh_empty_descriptions_all" => ["controller" => "ModelController", "method" => "refreshEmptyDescriptions"],
    "refresh_all_galleries_lists" => ["controller" => "ModelController", "method" => "refreshAllGalleries"]
];