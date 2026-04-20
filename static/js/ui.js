/**
 * UI components and interactions
 */

/**
 * Update file info display
 * @param {string|null} filename - Filename to display
 * @param {string} status - Status text
 */
function updateFileInfo(filename, status) {
    const fileInfo = document.getElementById('fileInfo');
    const fileNameEl = document.getElementById('fileName');
    const fileStatusEl = document.getElementById('fileStatus');
    
    if (filename) {
        fileNameEl.textContent = filename;
        fileStatusEl.textContent = status;
        fileInfo.classList.remove('hidden');
    } else {
        fileInfo.classList.add('hidden');
    }
}

/**
 * Display page groups in the UI
 * @param {Object} detectedPageGroups - Optional automatically detected page groups from OCR (0-based page numbers)
 */
function displayPageGroups(detectedPageGroups = null) {
    const container = document.getElementById('pageGroupsList');
    container.innerHTML = '';
    selectedGroups = {};

    // Check if availablePageGroups is defined and is an array
    if (!availablePageGroups || !Array.isArray(availablePageGroups)) {
        console.error('availablePageGroups is not defined or is not an array:', availablePageGroups);
        container.innerHTML = '<div class="error-message">Error: Page groups data is not available. Please try again.</div>';
        return;
    }

    // Show automated detection status message if detection was attempted
    if (detectedPageGroups !== null) {
        const hasDetections = Object.keys(detectedPageGroups).length > 0;
        const statusDiv = document.createElement('div');
        statusDiv.className = hasDetections ? 'status-message status-success' : 'status-message status-info';
        statusDiv.style.marginBottom = '15px';
        statusDiv.innerHTML = hasDetections 
            ? '<strong>✓ Automated Detection Complete:</strong> Page numbers have been automatically detected from OCR data and filled in. Please review and adjust if needed.'
            : '<strong>ℹ Automated Detection:</strong> Could not automatically detect page numbers from OCR data. Please enter them manually below.';
        container.appendChild(statusDiv);
    }

    // Get max page number from job status (1-based)
    const maxPage = parseInt(document.getElementById('maxPage')?.textContent || '0');

    availablePageGroups.forEach(group => {
        const card = document.createElement('div');
        card.className = 'page-group-input-card';
        card.dataset.groupName = group.name;
        
        // Check if pages were automatically detected for this group (0-based)
        const detectedPages = detectedPageGroups && detectedPageGroups[group.name] 
            ? detectedPageGroups[group.name] 
            : null;
        
        // Use detected pages if available, otherwise fall back to config defaults
        // Both are 0-based, convert to 1-based for display
        const pagesToUse = detectedPages || group.pages;
        const displayPages = pagesToUse.map(p => p + 1);
        const isAutoDetected = detectedPages !== null && detectedPages.length > 0;
        
        // Determine input type based on group name and form type
        // For Form 1120: Both Form 1120 and Schedule L, M-1, M-2 need single page
        // For Form 1065: Both Form 1065 and Schedule L, M-1, M-2 need single page
        // For Form 1120S: Form 1120S needs range, Schedule L and Schedule M need single page
        // For other forms: check if default pages length > 1 for range
        let needsRange = false;
        
        if (selectedFormType === '1120' || selectedFormType === '1065') {
            // Form 1120 and Form 1065: Always use single page for both groups
            needsRange = false;
        } else if (selectedFormType === '1120s') {
            // Form 1120S: Form 1120S uses range, others use single page
            needsRange = group.display_name === 'Form 1120S';
        } else {
            // Other forms: Use range if multiple pages, unless it's Schedule L or Schedule M
            needsRange = group.pages.length > 1 && 
                        group.display_name !== 'Schedule L' && 
                        group.display_name !== 'Schedule M';
        }
        
        // Auto-detected badge HTML
        const autoDetectedBadge = isAutoDetected 
            ? '<span class="auto-detected-badge" style="background: #28a745; color: white; font-size: 0.7em; padding: 2px 8px; border-radius: 3px; margin-left: 8px; font-weight: 600;">✓ Auto-Detected</span>' 
            : '';
        
        let inputHTML = '';
        if (needsRange) {
            // Range input: Start Page and End Page (1-based)
            inputHTML = `
                <div class="page-input-group">
                    <label class="page-input-label">Start Page</label>
                    <input type="number" class="page-input-field" 
                           data-group="${group.name}" data-type="start"
                           min="1" max="${maxPage}" 
                           placeholder="1" 
                           value="${displayPages.length > 0 ? displayPages[0] : ''}">
                </div>
                <div class="page-input-group">
                    <label class="page-input-label">End Page</label>
                    <input type="number" class="page-input-field" 
                           data-group="${group.name}" data-type="end"
                           min="1" max="${maxPage}" 
                           placeholder="1" 
                           value="${displayPages.length > 0 ? displayPages[displayPages.length - 1] : ''}">
                </div>
            `;
        } else {
            // Single page input (1-based)
            const defaultValue = displayPages.length > 0 ? displayPages[0] : '';
            inputHTML = `
                <div class="page-input-group">
                    <label class="page-input-label">Page Number</label>
                    <input type="number" class="page-input-field" 
                           data-group="${group.name}" data-type="single"
                           min="1" max="${maxPage}" 
                           placeholder="1" 
                           value="${defaultValue}">
                </div>
            `;
        }
        
        card.innerHTML = `
            <div class="page-group-input-header">
                <div>
                    <div class="page-group-input-title">${group.display_name}${autoDetectedBadge}</div>
                    <div class="page-group-input-description">
                        ${isAutoDetected 
                            ? (needsRange ? 'Automatically detected from OCR data - review and adjust if needed' : 'Automatically detected from OCR data - review and adjust if needed')
                            : (needsRange ? 'Enter start and end page numbers' : 'Enter page number')}
                    </div>
                </div>
            </div>
            <div class="page-group-input-fields">
                ${inputHTML}
            </div>
            <div class="page-group-preview-container" data-preview-group="${group.name}" style="display: none; margin-top: 15px;">
                <div class="page-group-preview-loading" style="text-align: center; padding: 20px; color: #666;">
                    <div class="spinner" style="margin: 0 auto 10px;"></div>
                    <p style="margin: 0;">Loading preview...</p>
                </div>
                <div class="page-group-preview-content" style="display: none;">
                    <!-- Preview will be inserted here -->
                </div>
            </div>
        `;
        
        // Add event listeners to inputs
        card.querySelectorAll('.page-input-field').forEach(input => {
            input.addEventListener('input', () => handlePageInputChange(group, card));
            input.addEventListener('change', () => handlePageInputChange(group, card));
        });
        
        container.appendChild(card);
        
        // Initialize with values (detected or default)
        if (pagesToUse.length > 0) {
            handlePageInputChange(group, card);
        }
    });
    
    updateProcessButton();
}

/**
 * Handle page input change
 * @param {Object} group - Page group object
 * @param {HTMLElement} card - Card element
 */
function handlePageInputChange(group, card) {
    const inputs = card.querySelectorAll('.page-input-field');
    const groupName = group.name;
    const needsRange = inputs.length === 2;
    
    let pages = []; // Will store 0-based page numbers for backend
    
    if (needsRange) {
        const startInput = card.querySelector('[data-type="start"]');
        const endInput = card.querySelector('[data-type="end"]');
        const startPage = parseInt(startInput.value); // 1-based from UI
        const endPage = parseInt(endInput.value); // 1-based from UI
        
        if (!isNaN(startPage) && !isNaN(endPage) && startPage <= endPage && startPage >= 1) {
            // Convert 1-based to 0-based and generate page array from start to end (inclusive)
            for (let i = startPage; i <= endPage; i++) {
                pages.push(i - 1); // Convert to 0-based for backend
            }
        }
    } else {
        const singleInput = card.querySelector('[data-type="single"]');
        const pageNum = parseInt(singleInput.value); // 1-based from UI
        
        if (!isNaN(pageNum) && pageNum >= 1) {
            pages = [pageNum - 1]; // Convert to 0-based for backend
        }
    }
    
    if (pages.length > 0) {
        selectedGroups[groupName] = pages; // Store 0-based for backend
        card.classList.add('has-value');
        // Show preview for this specific group (convert back to 1-based for display)
        const displayPages = pages.map(p => p + 1);
        updateGroupPreview(groupName, pages, card, displayPages);
    } else {
        delete selectedGroups[groupName];
        card.classList.remove('has-value');
        // Hide preview for this group
        hideGroupPreview(card);
    }
    
    updateProcessButton();
}

/**
 * Update group preview
 * @param {string} groupName - Group name
 * @param {Array<number>} pages - Page numbers (0-based)
 * @param {HTMLElement} card - Card element
 * @param {Array<number>} displayPages - Display page numbers (1-based)
 */
function updateGroupPreview(groupName, pages, card, displayPages = null) {
    const previewContainer = card.querySelector(`[data-preview-group="${groupName}"]`);
    const previewLoading = previewContainer?.querySelector('.page-group-preview-loading');
    const previewContent = previewContainer?.querySelector('.page-group-preview-content');
    
    if (!previewContainer) return;
    
    // Show preview container
    previewContainer.style.display = 'block';
    if (previewLoading) previewLoading.style.display = 'block';
    if (previewContent) previewContent.style.display = 'none';
    
    const groupInfo = availablePageGroups.find(g => g.name === groupName);
    const displayName = groupInfo?.display_name || groupName;
    const previewUrl = `${API_BASE}/jobs/${currentJobId}/preview-group/${groupName}?pages=${encodeURIComponent(JSON.stringify(pages))}`;
    
    // Convert 0-based pages to 1-based for display
    const displayPagesList = displayPages || pages.map(p => p + 1);
    
    // Create preview iframe
    if (previewContent) {
        previewContent.innerHTML = `
            <div style="margin-bottom: 10px; font-size: 0.9em; color: #666;">
                Preview: Pages ${displayPagesList.join(', ')}
            </div>
            <object data="${previewUrl}" type="application/pdf" class="preview-iframe" style="width: 100%; height: 400px; border: 1px solid #e0e0e0; border-radius: 4px;">
                <iframe src="${previewUrl}" class="preview-iframe" style="width: 100%; height: 400px; border: 1px solid #e0e0e0; border-radius: 4px;"></iframe>
            </object>
        `;
        
        // Hide loading and show preview after a short delay
        setTimeout(() => {
            if (previewLoading) previewLoading.style.display = 'none';
            if (previewContent) previewContent.style.display = 'block';
        }, 500);
    }
}

/**
 * Hide group preview
 * @param {HTMLElement} card - Card element
 */
function hideGroupPreview(card) {
    const previewContainer = card.querySelector('.page-group-preview-container');
    if (previewContainer) {
        previewContainer.style.display = 'none';
    }
}

/**
 * Update process button state
 */
function updateProcessButton() {
    const hasValidGroups = Object.keys(selectedGroups).length > 0 && 
        Object.values(selectedGroups).every(pages => pages.length > 0);
    document.getElementById('processBtn').disabled = !hasValidGroups;
}

/**
 * Show detection modal with loading spinner
 * @param {string} message - Main message to display
 * @param {string} title - Title to display (optional, default: 'Detecting Page Numbers')
 */
function showDetectionModal(message, title = 'Detecting Page Numbers') {
    const modal = document.getElementById('detectionModal');
    const messageEl = document.getElementById('detectionMessage');
    const titleEl = document.getElementById('detectionTitle');
    const submessageEl = modal?.querySelector('.modal-submessage');
    
    if (modal && messageEl) {
        messageEl.textContent = message;
        if (titleEl) {
            titleEl.textContent = title;
        }
        if (submessageEl) {
            submessageEl.textContent = 'This may take 10-30 seconds depending on document size.';
        }
        modal.classList.remove('hidden');
    }
}

/**
 * Update detection modal message
 * @param {string} message - Main message to display
 * @param {string} submessage - Submessage to display
 */
function updateDetectionModalMessage(message, submessage = '') {
    const modal = document.getElementById('detectionModal');
    const messageEl = document.getElementById('detectionMessage');
    const submessageEl = modal?.querySelector('.modal-submessage');
    
    if (messageEl) {
        messageEl.textContent = message;
    }
    
    if (submessageEl && submessage) {
        submessageEl.innerHTML = submessage;
    }
}

/**
 * Hide detection modal
 */
function hideDetectionModal() {
    const modal = document.getElementById('detectionModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}
