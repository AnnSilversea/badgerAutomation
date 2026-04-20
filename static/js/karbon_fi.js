/**
 * Logic for Drake Filing Instructions to Karbon Module
 */

// State variables for pagination
let allKarbonFIItems = [];
let filteredKarbonFIItems = [];
let currentKarbonFIPage = 1;
const karbonFIItemsPerPage = 10;
let selectedFIKeys = new Set();
let fiStatusPollInterval = null;
const FI_POLL_INTERVAL_MS = 4000;
const FI_MAX_POLL_DURATION_MS = 8 * 60 * 1000; // safety cutoff
const FI_NO_PROGRESS_TIMEOUT_MS = 3 * 60 * 1000; // stop if statuses never change
let fiActiveBatchKeys = [];
let fiProcessBtnOriginalHtml = null;
let fiIsProcessingBatch = false;

document.addEventListener('DOMContentLoaded', function() {
    // Attach event listener to the Query button
    const queryBtn = document.getElementById('queryKarbonFIBtn');
    if (queryBtn) {
        queryBtn.addEventListener('click', function() {
            loadKarbonFIItems();
        });
    }

    // Handle "Select All" checkbox
    const selectAllCheckbox = document.getElementById('karbonFISelectAll');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const isChecked = this.checked;
            filteredKarbonFIItems.forEach(item => {
                const hasTaxId = item.registrationNumber && String(item.registrationNumber).trim() !== '';
                if (item.workItemKey && hasTaxId) {
                    if (isChecked) selectedFIKeys.add(item.workItemKey);
                    else selectedFIKeys.delete(item.workItemKey);
                } else if (item.workItemKey) {
                    selectedFIKeys.delete(item.workItemKey); // Ensure non-selectable are always deselected
                }
            });
            renderKarbonFITable();
        });
    }

    // Handle individual checkbox changes
    const tableBody = document.getElementById('karbonFITableBody');
    if (tableBody) {
        tableBody.addEventListener('change', function(e) {
            if (e.target.classList.contains('item-checkbox')) {
                const key = e.target.value;
                if (e.target.checked) selectedFIKeys.add(key);
                else selectedFIKeys.delete(key);
                
                updateSelectAllCheckboxState();
                updateProcessButtonState();
            }
        });
    }

    // Handle Process button
    const processBtn = document.getElementById('processKarbonFIBtn');
    if (processBtn) {
        processBtn.addEventListener('click', processSelectedFIItems);
    }

    // Handle Search Input
    const searchInput = document.getElementById('karbonFISearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            filterKarbonFIItems(e.target.value);
        });
    }
});

function fiStatusToUiLabel(dbStatus) {
    const s = String(dbStatus || '').toUpperCase();
    if (s === 'QUEUE') return 'Queue';
    if (s === 'START') return 'Start';
    if (s === 'SUCCESS') return 'Success';
    if (s === 'FAIL') return 'Fail';
    if (s === 'ERROR') return 'Error';
    if (s === 'MISSING_TAX_ID') return 'Missing Tax ID/SSN';
    return 'Not Checked';
}

function renderFIStatusBadge(rawStatus, hasTaxId, rawMessage) {
    const message = String(rawMessage ?? '').trim();
    const title = message ? String(message).replace(/"/g, '&quot;') : '';

    if (!hasTaxId) {
        return `<span class="status-badge status-missingtax karbon-fi-status" title="Cannot process without a Tax ID/SSN.">Missing Tax ID/SSN</span>`;
    }

    const status = String(rawStatus || 'NOT_STARTED').toUpperCase();
    const label = fiStatusToUiLabel(status);
    let cssClass = 'status-notchecked';

    switch (status) {
        case 'QUEUE':
            cssClass = 'status-inqueue';
            break;
        case 'START':
            cssClass = 'status-processing';
            break;
        case 'SUCCESS':
            cssClass = 'status-success';
            break;
        case 'FAIL':
        case 'ERROR':
            cssClass = 'status-error';
            break;
        case 'MISSING_TAX_ID': // Fallback
            cssClass = 'status-missingtax';
            break;
        case 'NOT_STARTED':
        case 'NOT_CHECKED':
        default:
            cssClass = 'status-notchecked';
            break;
    }

    return `<span class="status-badge ${cssClass} karbon-fi-status" title="${title}">${label}</span>`;
}

function isTerminalFIStatus(s) {
    const status = String(s || '').toUpperCase();
    return status === 'SUCCESS' || status === 'FAIL' || status === 'ERROR' || status === 'MISSING_TAX_ID';
}

function isActiveFIStatus(s) {
    const status = String(s || '').toUpperCase();
    return status === 'IN_QUEUE' || status === 'IN_PROGRESS' || status === 'IN_PROCESSING' || status === 'PROCESSING';
}

function updateFIProcessingProgressUI() {
    if (!fiIsProcessingBatch) return;
    const processBtn = document.getElementById('processKarbonFIBtn');
    if (!processBtn) return;
    const total = Array.isArray(fiActiveBatchKeys) ? fiActiveBatchKeys.length : 0;
    if (total <= 0) return;

    let done = 0;
    for (const key of fiActiveBatchKeys) {
        const item = allKarbonFIItems.find(i => String(i.workItemKey) === String(key));
        if (item && isTerminalFIStatus(item.automationStatus)) done += 1;
    }

    if (done >= total) {
        // Finished: restore button
        fiIsProcessingBatch = false;
        fiActiveBatchKeys = [];
        processBtn.disabled = false;
        if (fiProcessBtnOriginalHtml !== null) processBtn.innerHTML = fiProcessBtnOriginalHtml;
        fiProcessBtnOriginalHtml = null;
        updateProcessButtonState();
        return;
    }

    // Show "Processing X/Y" like the Efile module, derived from DB completion count.
    const current = Math.min(done + 1, total);
    processBtn.disabled = true;
    processBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status"></span> Processing ${current}/${total}...`;
}

function stopFIStatusPolling() {
    if (fiStatusPollInterval) {
        clearInterval(fiStatusPollInterval);
        fiStatusPollInterval = null;
    }
}

function startFIStatusPolling(trackedKeys = []) {
    stopFIStatusPolling();
    const normalizedTrackedKeys = Array.from(new Set(
        (Array.isArray(trackedKeys) ? trackedKeys : [])
            .map(k => String(k || '').trim())
            .filter(Boolean)
    ));
    const hasActive = () =>
        allKarbonFIItems.some(w => isActiveFIStatus(w.automationStatus)) || normalizedTrackedKeys.length > 0;
    if (!hasActive()) return;

    const pollStartedAt = Date.now();
    let lastProgressAt = pollStartedAt;

    const tick = async () => {
        try {
            if (!allKarbonFIItems || allKarbonFIItems.length === 0) return;

            const now = Date.now();
            if (now - pollStartedAt > FI_MAX_POLL_DURATION_MS) {
                stopFIStatusPolling();
                const resultPanel = document.getElementById('karbonFIProcessResult');
                const resultSummary = document.getElementById('karbonFIProcessSummary');
                if (resultPanel) resultPanel.className = 'alert alert-warning';
                if (resultSummary) resultSummary.textContent = 'Processing is taking longer than expected. Please refresh later.';
                return;
            }
            if (now - lastProgressAt > FI_NO_PROGRESS_TIMEOUT_MS) {
                stopFIStatusPolling();
                const resultPanel = document.getElementById('karbonFIProcessResult');
                const resultSummary = document.getElementById('karbonFIProcessSummary');
                if (resultPanel) resultPanel.className = 'alert alert-warning';
                if (resultSummary) resultSummary.textContent = 'Processing appears stuck (no status changes). Please retry later.';
                return;
            }

            const active = allKarbonFIItems.filter(w => isActiveFIStatus(w.automationStatus));
            const tracked = allKarbonFIItems.filter(w =>
                normalizedTrackedKeys.includes(String(w.workItemKey || ''))
            );
            const itemsToQuery = [...active];
            for (const wi of tracked) {
                if (!itemsToQuery.some(x => String(x.workItemKey) === String(wi.workItemKey))) {
                    itemsToQuery.push(wi);
                }
            }
            if (itemsToQuery.length === 0) {
                stopFIStatusPolling();
                return;
            }
            const keys = itemsToQuery.map(w => String(w.workItemKey)).filter(Boolean);
            if (keys.length === 0) return;

            const resp = await fetch(`/api/workitems/fi/status?perma_keys=${encodeURIComponent(keys.join(','))}`);
            if (!resp.ok) return;
            const data = await resp.json();
            const statuses = data.statuses || {};
            let changed = false;

            for (const item of allKarbonFIItems) {
                const key = String(item.workItemKey || '');
                const st = statuses[key];
                if (!st) continue;
                const nextStatus = st.status || item.automationStatus;
                const nextMessage = st.message || null;
                if (item.automationStatus !== nextStatus || (item.automationMessage || null) !== nextMessage) {
                    item.automationStatus = nextStatus;
                    item.automationMessage = nextMessage;
                    item.automationStartedAt = st.started_at || item.automationStartedAt || null;
                    item.automationCompletedAt = st.completed_at || item.automationCompletedAt || null;
                    changed = true;
                }
            }

            if (changed) lastProgressAt = Date.now();
            if (changed) {
                // Preserve current search filter by reapplying it
                const searchInput = document.getElementById('karbonFISearchInput');
                filterKarbonFIItems(searchInput ? searchInput.value : '', true);
            }

            updateFIProcessingProgressUI();

            const stillActive = allKarbonFIItems.some(w => {
                const key = String(w.workItemKey || '');
                return isActiveFIStatus(w.automationStatus) &&
                    (normalizedTrackedKeys.length === 0 || normalizedTrackedKeys.includes(key));
            });
            if (!stillActive) stopFIStatusPolling();
        } catch (e) {
            // ignore polling failures
        }
    };

    // Run once immediately, then continue interval polling.
    tick();
    fiStatusPollInterval = setInterval(tick, FI_POLL_INTERVAL_MS);
}

/**
 * Fetch work items from the backend and render them in the table.
 */
async function loadKarbonFIItems() {
    const tableBody = document.getElementById('karbonFITableBody');
    const recordCountEl = document.getElementById('karbonFIRecordCount');
    const loadTimeEl = document.getElementById('karbonFILoadTime');
    
    if (!tableBody) return;

    // 1. Show loading state
    tableBody.innerHTML = `
        <tr>
            <td colspan="9" class="text-center py-4">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div class="mt-2 text-muted">Querying Karbon for "Return Assembly" items...</div>
            </td>
        </tr>
    `;

    const startTime = performance.now();

    try {
        // 2. Call API - Request up to 500 items to handle larger datasets
        const response = await fetch('/api/karbon/fi/workitems?top=500&work_status=Return Assembly');
        
        if (!response.ok) {
            throw new Error(`API Error: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();

        // Store data and reset page (items already have DB status merged by backend)
        allKarbonFIItems = Array.isArray(data) ? data : [];
        // Ensure automationStatus fields exist (DB-driven; backend merges on Query Karbon)
        allKarbonFIItems = allKarbonFIItems.map(it => ({
            ...it,
            automationStatus: it.automationStatus || 'NOT_STARTED',
            automationMessage: it.automationMessage || null,
            automationStartedAt: it.automationStartedAt || null,
            automationCompletedAt: it.automationCompletedAt || null,
        }));
        filteredKarbonFIItems = [...allKarbonFIItems];
        currentKarbonFIPage = 1;
        selectedFIKeys.clear();

        // 3. Update stats
        if (recordCountEl) recordCountEl.textContent = allKarbonFIItems.length;
        if (loadTimeEl) {
            loadTimeEl.style.display = 'inline';
            loadTimeEl.innerHTML = `<i class="bi bi-clock me-1"></i> Loaded: ${new Date().toLocaleString()}`;
        }

        // 4. Render Table and Pagination
        renderKarbonFITable();
        renderKarbonFIPagination();
        // Do not auto-start polling on list load; only poll after explicit processing action.
        stopFIStatusPolling();

    } catch (error) {
        console.error('Error loading Karbon FI items:', error);
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center py-4 text-danger">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    Failed to load data: ${error.message}
                </td>
            </tr>
        `;
    }
}

function renderKarbonFITable() {
    const tableBody = document.getElementById('karbonFITableBody');
    tableBody.innerHTML = '';

    if (!filteredKarbonFIItems || filteredKarbonFIItems.length === 0) {
        const searchInput = document.getElementById('karbonFISearchInput');
        const isSearching = searchInput && searchInput.value.trim().length > 0;
        const emptyMessage = isSearching 
            ? `No items found matching "${searchInput.value}"`
            : 'No items found with status "Return Assembly"';
        const emptyIcon = isSearching ? 'bi-search' : 'bi-inbox';

        tableBody.innerHTML = `
            <tr class="empty-state">
                <td colspan="9" class="text-center py-4 text-muted">
                    <i class="bi ${emptyIcon} fs-2 d-block mb-2 opacity-50"></i>
                    ${emptyMessage}
                </td>
            </tr>
        `;
        // Clear pagination if empty
        const paginationEl = document.getElementById('karbonFITablePagination');
        if (paginationEl) paginationEl.innerHTML = '';
        const paginationInfo = document.getElementById('karbonFIPaginationInfo');
        if (paginationInfo) paginationInfo.textContent = '';
        return;
    }

    // Calculate pagination slice
    const startIndex = (currentKarbonFIPage - 1) * karbonFIItemsPerPage;
    const endIndex = Math.min(startIndex + karbonFIItemsPerPage, filteredKarbonFIItems.length);
    const itemsToShow = filteredKarbonFIItems.slice(startIndex, endIndex);

    itemsToShow.forEach(item => {
        const tr = document.createElement('tr');
        
        const hasTaxId = item.registrationNumber && String(item.registrationNumber).trim() !== '';

        // Render the status badge using the unified function
        const statusBadgeHtml = renderFIStatusBadge(item.automationStatus, hasTaxId, item.automationMessage);

        const isChecked = item.workItemKey && selectedFIKeys.has(item.workItemKey);
        const karbonLink = `https://app2.karbonhq.com/#/work/${item.workItemKey}/file-management-documents`;
        const lastUpdatedIso = item.automationCompletedAt || item.automationStartedAt || item._lastUpdated;
        const lastUpdated = lastUpdatedIso ? new Date(lastUpdatedIso).toLocaleString() : '';

        tr.innerHTML = `
            <td class="text-center">
                <input class="form-check-input item-checkbox" type="checkbox" value="${item.workItemKey || ''}" ${isChecked ? 'checked' : ''} ${!hasTaxId ? 'disabled' : ''}>
            </td>
            <td class="text-center font-monospace small">${item.registrationNumber || '-'}</td>
            <td>${item.clientName || '-'}</td>
            <td class="text-center">${item.clientType || '-'}</td>
            <td class="text-center">${item.assigneeName || '-'}</td>
            <td class="text-center"><span class="badge bg-light text-dark border">${item.workStatus || '-'}</span></td>
            <td class="text-center"><a href="${karbonLink}" target="_blank" rel="noopener noreferrer">Link</a></td>
            <td class="text-center">${statusBadgeHtml}</td>
            <td class="text-center small">${lastUpdated}</td>
        `;
        
        tableBody.appendChild(tr);
    });

    updateSelectAllCheckboxState();
    updateProcessButtonState();
}

function renderKarbonFIPagination() {
    const paginationEl = document.getElementById('karbonFITablePagination');
    const paginationInfo = document.getElementById('karbonFIPaginationInfo');
    
    if (!paginationEl) return;

    const totalPages = Math.ceil(filteredKarbonFIItems.length / karbonFIItemsPerPage);
    
    // Update info text
    if (paginationInfo) {
        const start = (currentKarbonFIPage - 1) * karbonFIItemsPerPage + 1;
        const end = Math.min(currentKarbonFIPage * karbonFIItemsPerPage, filteredKarbonFIItems.length);
        paginationInfo.textContent = `Showing ${start} to ${end} of ${filteredKarbonFIItems.length}`;
    }

    if (totalPages <= 1) {
        paginationEl.innerHTML = '';
        return;
    }

    let html = '';

    // Previous
    html += `
        <li class="page-item ${currentKarbonFIPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="changeKarbonFIPage(${currentKarbonFIPage - 1}); return false;">
                ← Previous
            </a>
        </li>
    `;

    // Page numbers logic (max 5 visible)
    const maxVisible = 5;
    let startPage = Math.max(1, currentKarbonFIPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    
    if (endPage - startPage + 1 < maxVisible) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }

    if (startPage > 1) {
        html += `<li class="page-item"><a class="page-link" href="#" onclick="changeKarbonFIPage(1); return false;">1</a></li>`;
        if (startPage > 2) html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `
            <li class="page-item ${i === currentKarbonFIPage ? 'active' : ''}">
                <a class="page-link" href="#" onclick="changeKarbonFIPage(${i}); return false;">${i}</a>
            </li>
        `;
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
        html += `<li class="page-item"><a class="page-link" href="#" onclick="changeKarbonFIPage(${totalPages}); return false;">${totalPages}</a></li>`;
    }

    // Next
    html += `
        <li class="page-item ${currentKarbonFIPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="changeKarbonFIPage(${currentKarbonFIPage + 1}); return false;">
                Next →
            </a>
        </li>
    `;

    paginationEl.innerHTML = html;
}

function changeKarbonFIPage(page) {
    const totalPages = Math.ceil(filteredKarbonFIItems.length / karbonFIItemsPerPage);
    if (page < 1 || page > totalPages) return;
    
    currentKarbonFIPage = page;
    renderKarbonFITable();
    renderKarbonFIPagination();
}

// Expose changeKarbonFIPage to global scope
window.changeKarbonFIPage = changeKarbonFIPage;

function filterKarbonFIItems(searchTerm, preservePage = false) {
    const term = searchTerm ? searchTerm.toLowerCase().trim() : '';
    
    if (!term) {
        filteredKarbonFIItems = [...allKarbonFIItems];
    } else {
        filteredKarbonFIItems = allKarbonFIItems.filter(item => {
            const reg = (item.registrationNumber || '').toString().toLowerCase();
            const name = (item.clientName || '').toString().toLowerCase();
            const type = (item.clientType || '').toString().toLowerCase();
            const assignee = (item.assigneeName || '').toString().toLowerCase();
            
            return reg.includes(term) || 
                   name.includes(term) || 
                   type.includes(term) || 
                   assignee.includes(term);
        });
    }
    
    if (!preservePage) currentKarbonFIPage = 1;
    
    // Update filter info UI
    const filterInfo = document.getElementById('karbonFIFilterInfo');
    const filteredCount = document.getElementById('karbonFIFilteredCount');
    
    if (filterInfo && filteredCount) {
        filterInfo.style.display = term ? 'inline' : 'none';
        if (term) filteredCount.textContent = filteredKarbonFIItems.length;
    }
    
    renderKarbonFITable();
    renderKarbonFIPagination();
}

function updateSelectAllCheckboxState() {
    const selectAllCheckbox = document.getElementById('karbonFISelectAll');
    if (!selectAllCheckbox) return;
    
    const selectableItems = filteredKarbonFIItems.filter(item => 
        item.workItemKey && item.registrationNumber && String(item.registrationNumber).trim() !== ''
    );

    if (selectableItems.length === 0) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
        return;
    }
    
    const numSelected = selectableItems.filter(item => selectedFIKeys.has(item.workItemKey)).length;

    if (numSelected === 0) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
    } else if (numSelected === selectableItems.length) {
        selectAllCheckbox.checked = true;
        selectAllCheckbox.indeterminate = false;
    } else {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = true;
    }
}

function updateProcessButtonState() {
    const processBtn = document.getElementById('processKarbonFIBtn');
    if (!processBtn) return;
    
    processBtn.disabled = selectedFIKeys.size === 0;
}

function updateItemStatus(key, status, message = null) {
    // 1. Update Data Model
    const item = allKarbonFIItems.find(i => i.workItemKey === key);
    if (item) {
        item.automationStatus = status;
        item.automationMessage = message;
        if (isTerminalFIStatus(status)) {
            item.automationCompletedAt = new Date().toISOString();
        } else if (isActiveFIStatus(status)) {
            item.automationStartedAt = new Date().toISOString();
        }
    }

    // 2. Update DOM (if row is rendered)
    const checkbox = document.querySelector(`#karbonFITableBody input.item-checkbox[value="${key}"]`);
    if (checkbox) {
        const row = checkbox.closest('tr');
        if (row) {
            const cells = row.querySelectorAll('td');
            const statusCell = cells[7]; // Status is at index 7 (8th column)
            const badge = statusCell ? statusCell.querySelector('.status-badge') : null;
            if (badge) {
                const hasTaxId = item ? (item.registrationNumber && String(item.registrationNumber).trim() !== '') : false;
                badge.outerHTML = renderFIStatusBadge(status, hasTaxId, message);
            }
            
            // Update Last Updated (index 8)
            const lastUpdatedCell = cells[8];
            if (lastUpdatedCell) {
                const lastUpdatedIso = item.automationCompletedAt || item.automationStartedAt;
                lastUpdatedCell.textContent = lastUpdatedIso ? new Date(lastUpdatedIso).toLocaleString() : '';
            }
        }
    }
}

async function processSelectedFIItems() {
    const processBtn = document.getElementById('processKarbonFIBtn');
    const workItemKeys = Array.from(selectedFIKeys);
    
    if (workItemKeys.length === 0) return;

    // UI Feedback
    const originalText = processBtn.innerHTML;
    fiProcessBtnOriginalHtml = originalText;
    fiActiveBatchKeys = [...workItemKeys];
    fiIsProcessingBatch = true;
    processBtn.disabled = true;
    
    // Show result panel
    const resultPanel = document.getElementById('karbonFIProcessResult');
    const resultSummary = document.getElementById('karbonFIProcessSummary');
    const resultDetails = document.getElementById('karbonFIProcessDetails');
    const closeBtn = document.getElementById('karbonFIProcessCloseBtn');
    
    if (resultPanel) {
        resultPanel.hidden = false;
        resultPanel.className = 'alert alert-info';
        if (resultSummary) resultSummary.innerHTML = `Starting processing for ${workItemKeys.length} items...`;
        if (resultDetails) resultDetails.innerHTML = '';
        if (closeBtn) closeBtn.onclick = () => resultPanel.hidden = true;
    }

    // Define counters and result collectors
    let successCount = 0;
    let failedCount = 0;
    const allDetails = [];
    const accumulatedStats = { updated: 0, failed_drake: 0, failed_karbon: 0, skipped: 0 };

    // 1) Optimistically mark selected items based on batch size (mirrors Efile behavior)
    if (workItemKeys.length === 1) {
        // Single item: show "In Processing" immediately
        updateItemStatus(workItemKeys[0], 'START');
    } else {
        // Multi-item: set all to "In Queue" until worker picks each one up
        workItemKeys.forEach(key => updateItemStatus(key, 'QUEUE'));
    }
    // startFIStatusPolling(workItemKeys);
    stopFIStatusPolling();
    updateFIProcessingProgressUI();

    // 2. Process Loop
    for (let i = 0; i < workItemKeys.length; i++) {
        const key = workItemKeys[i];
        const isLastItem = (i === workItemKeys.length - 1);
        
        // Update progress in button
        processBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status"></span> Processing ${i + 1}/${workItemKeys.length}...`;

        updateItemStatus(key, 'START');

        try {
            const response = await fetch('/api/karbon/process-fi', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    work_item_keys: [key],
                    close_drake: isLastItem,
                    send_email: false
                })
            });

            const data = await response.json();
            
            if (!response.ok) throw new Error(data.detail || 'Processing failed');

            if (data.details && Array.isArray(data.details)) {
                allDetails.push(...data.details);
            }
            
            // Accumulate stats
            if (data.totals) {
                accumulatedStats.updated += (data.totals.updated || 0);
                accumulatedStats.failed_drake += (data.totals.failed_drake || 0);
                accumulatedStats.failed_karbon += (data.totals.failed_karbon || 0);
                accumulatedStats.skipped += (data.totals.skipped || 0);
            }

            // Determine status based on API result
            // API returns details array. Since we sent 1 item, we check details[0]
            const resultDetail = data.details && data.details.length > 0 ? data.details[0] : null;
            const isSuccess = resultDetail && resultDetail.status === 'success';
            
            const finalStatus = isSuccess ? 'SUCCESS' : 'FAIL';
            const message = resultDetail ? resultDetail.message : (isSuccess ? 'Success' : 'Failed');
            updateItemStatus(key, finalStatus, message);

            // Update counts
            if (isSuccess) successCount++;
            else failedCount++;

            // Append to details panel
            if (resultDetails && resultDetail) {
                const msgDiv = document.createElement('div');
                msgDiv.className = isSuccess ? 'text-success border-bottom py-1' : 'text-danger border-bottom py-1';
                msgDiv.innerHTML = `<strong>${resultDetail.client || 'Unknown'}</strong>: ${resultDetail.message}`;
                resultDetails.appendChild(msgDiv);
            }

        } catch (error) {
            console.error(`Error processing item ${key}:`, error);
            updateItemStatus(key, 'ERROR', error.message);
            failedCount++;

            const item = allKarbonFIItems.find(i => i.workItemKey === key);
            allDetails.push({
                client: item ? item.clientName : "Unknown",
                registrationNumber: item ? item.registrationNumber : "",
                workItemKey: key,
                status: "failed",
                message: error.message
            });
            
            if (resultDetails) {
                const msgDiv = document.createElement('div');
                msgDiv.className = 'text-danger border-bottom py-1';
                msgDiv.innerHTML = `<strong>Item Error</strong>: ${error.message}`;
                resultDetails.appendChild(msgDiv);
            }
            
            // Fallback stats update for client-side error
            accumulatedStats.failed_drake += 1; 
        }
    }

    // Send Summary Email
    if (allDetails.length > 0) {
        try {
            await fetch('/api/karbon/send-fi-summary', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    processed_count: workItemKeys.length,
                    totals: accumulatedStats,
                    details: allDetails
                })
            });
        } catch (e) {
            console.error("Failed to send summary email", e);
        }
    }

    // 3. Finalize
    processBtn.disabled = false;
    processBtn.innerHTML = originalText;

    // Clear selections and re-render the table to uncheck boxes
    selectedFIKeys.clear();
    renderKarbonFITable(); // This handles unchecking and updating button states
    // Update Result Panel Summary
    if (resultPanel && resultSummary) {
        resultPanel.className = failedCount === 0 ? 'alert alert-success' : 'alert alert-warning';
        resultSummary.innerHTML = `
            <strong>Processing Complete</strong><br>
            Processed: ${workItemKeys.length} | Success: ${successCount} | Failed: ${failedCount}
        `;
    }
}