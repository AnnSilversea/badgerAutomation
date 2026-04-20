/**
 * Main application logic and initialization
 */

// Global state variables
let currentJobId = null;
let currentFileName = null;
let selectedFormType = null;
let selectedGroups = {};
let availablePageGroups = [];
let detectedPageGroups = null; // Automatically detected page groups from OCR (null = not attempted, {} = attempted but nothing found)
let currentStep = 1;
let filingInstructionsDownloadUrl = null;

/**
 * Sets the currently active module in the UI.
 * @param {string} moduleId The ID of the module to activate.
 */
function setActiveModule(moduleId) {
    if (!moduleId) {
        return;
    }

    const buttons = document.querySelectorAll('.module-nav-button');
    const modules = document.querySelectorAll('.module-section');

    modules.forEach((module) => {
        const isActive = module.id === moduleId;
        module.classList.toggle('module-hidden', !isActive);
    });

    // Update button states
    buttons.forEach((button) => {
        const isActive = button.dataset.module === moduleId;
        button.classList.toggle('active', isActive);
        button.setAttribute('aria-pressed', String(isActive));
    });

    // Collapse any group that is not the parent of the active module
    const allGroups = document.querySelectorAll('.module-nav-group');
    const activeModuleButton = document.querySelector(`.module-nav-button[data-module="${moduleId}"]`);
    const activeParentGroup = activeModuleButton ? activeModuleButton.closest('.module-nav-group') : null;

    allGroups.forEach(group => {
        if (group !== activeParentGroup) {
            group.classList.remove('expanded');
        }
    });

    // Expand parent if a child is active
    if (activeParentGroup && activeModuleButton.classList.contains('module-nav-child')) {
        activeParentGroup.classList.add('expanded');
    }

    // Save active module to sessionStorage
    try {
        sessionStorage.setItem('activeModuleId', moduleId);
    } catch (e) {
        console.warn('Cannot save module state:', e);
    }
}

/**
 * Setup module navigation for the navbar
 */
function setupModuleNav() {
    const navContainer = document.querySelector('.module-nav');
    if (!navContainer) return;

    navContainer.addEventListener('click', (e) => {
        const button = e.target.closest('.module-nav-button');
        if (!button) return;

        // If it's a parent button, decide whether to toggle or navigate
        if (button.classList.contains('module-nav-parent')) {
            // If the click was on the chevron icon itself, toggle.
            if (e.target.classList.contains('nav-chevron')) {
                const group = button.closest('.module-nav-group');
                if (group) {
                    group.classList.toggle('expanded');
                }
            } else {
                // Otherwise, navigate and also toggle the expansion.
                setActiveModule(button.dataset.module);
                const group = button.closest('.module-nav-group');
                if (group) {
                    // This will now open/close the children when the parent is clicked
                    group.classList.toggle('expanded');
                }
            }
        } else {
            // For child or regular buttons, just navigate.
            const moduleId = button.dataset.module;
            if (moduleId) setActiveModule(moduleId);
        }
    });
}

// Ensure these exist somewhere (global or before calling this function):
// const API_BASE = '/api';
// let filingInstructionsDownloadUrl = null;

function setupFilingInstructionsModule() {
  const fileInput = document.getElementById('fiFileInput');
  const searchTextInput = document.getElementById('fiSearchText');
  const maxItemsInput = document.getElementById('fiMaxItems');
  const processBtn = document.getElementById('fiProcessBtn');
  const downloadBtn = document.getElementById('fiDownloadBtn');
  const statusEl = document.getElementById('fiStatus');

  if (!fileInput || !searchTextInput || !maxItemsInput || !processBtn || !downloadBtn || !statusEl) return;

  const setStatus = (message, variant = 'info') => {
    statusEl.classList.remove('hidden', 'status-info', 'status-success', 'status-error');
    statusEl.classList.add(`status-${variant}`);
    statusEl.textContent = message;
  };

  const clearStatus = () => {
    statusEl.classList.add('hidden');
    statusEl.textContent = '';
    statusEl.classList.remove('status-info', 'status-success', 'status-error');
  };

  const resetDownload = () => {
    filingInstructionsDownloadUrl = null;
    downloadBtn.disabled = true;
  };

  const setInputsDisabled = (disabled) => {
    fileInput.disabled = disabled;
    searchTextInput.disabled = disabled;
    maxItemsInput.disabled = disabled;
  };

  fileInput.addEventListener('change', () => {
    const hasFile = fileInput.files && fileInput.files.length > 0;
    processBtn.disabled = !hasFile;
    resetDownload();
    clearStatus();
  });

  processBtn.addEventListener('click', async () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      setStatus('Please choose a PDF file first.', 'error');
      return;
    }

    // Validate inputs
    const searchText = (searchTextInput.value || 'FI').trim() || 'FI';
    const maxItems = Math.max(1, Math.min(200, parseInt(maxItemsInput.value, 10) || 5));

    processBtn.disabled = true;
    resetDownload();
    setInputsDisabled(true);
    setStatus('Processing file...', 'info');

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('search_text', searchText);
      formData.append('max_items', String(maxItems));

      const response = await fetch(`${API_BASE}/filing-instructions/extract`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const message = errorData?.detail ? errorData.detail : `Request failed (${response.status})`;
        throw new Error(message);
      }

      const data = await response.json();

      filingInstructionsDownloadUrl = data.download_url || null;
      downloadBtn.disabled = !filingInstructionsDownloadUrl;

      const count = data.extracted_count ?? 0;
      setStatus(`Extracted ${count} page(s). Ready to download.`, 'success');
    } catch (error) {
      setStatus(`Error: ${error.message}`, 'error');
    } finally {
      processBtn.disabled = false;
      setInputsDisabled(false);
    }
  });

  downloadBtn.addEventListener('click', () => {
    if (!filingInstructionsDownloadUrl) {
      setStatus('No output file available yet.', 'error');
      return;
    }
    // You can use window.open if you prefer a new tab:
    window.location.href = filingInstructionsDownloadUrl;
  });
}

/**
 * Setup functionality for the Karbon E-file Status module
 */
function setupKarbonEfileModule() {
  const queryBtn = document.getElementById('queryKarbonBtn');
  if (!queryBtn) return;

  let statusPollInterval = null;

  const tbody = document.getElementById('karbonTableBody');
  const recordCountEl = document.getElementById('karbonRecordCount');
  const processBtn = document.getElementById('processKarbonBtn');
  const selectAllCheckbox = document.getElementById('karbonSelectAll');

  // Search + filter UI elements
  const searchInput = document.getElementById('karbonSearchInput');
  const filterInfoEl = document.getElementById('karbonFilterInfo');
  const filteredCountEl = document.getElementById('karbonFilteredCount');

  // Result panel elements (above table)
  const resultBox = document.getElementById('karbonProcessResult');
  const resultSummary = document.getElementById('karbonProcessSummary');
  const resultDetails = document.getElementById('karbonProcessDetails');
  const resultCloseBtn = document.getElementById('karbonProcessCloseBtn');

  // Cache all items after querying Karbon
  let allWorkItems = [];

  // -----------------------------
  // Helpers
  // -----------------------------
  function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
  }

  function debounce(fn, delay = 200) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), delay);
    };
  }

  function showProcessResult({ type = "info", summaryHtml = null, detailsHtml = null }) {
    if (!resultBox) return;

    resultBox.hidden = false;
    resultBox.style.display = '';
    resultBox.classList.remove('alert-success', 'alert-warning', 'alert-danger', 'alert-info');
    resultBox.classList.add(`alert-${type}`);

    if (resultSummary && summaryHtml !== null) resultSummary.innerHTML = summaryHtml;
    if (resultDetails && detailsHtml !== null) resultDetails.innerHTML = detailsHtml;
  }

  function hideProcessResult({ clear = true } = {}) {
    if (!resultBox) return;

    if (clear) {
      if (resultSummary) resultSummary.innerHTML = '';
      if (resultDetails) resultDetails.innerHTML = '';
    }

    resultBox.hidden = true;
    resultBox.style.display = 'none';
  }

  hideProcessResult(); // hide on initial load

  if (resultCloseBtn) {
    resultCloseBtn.addEventListener('click', () => hideProcessResult({ clear: false }));
  }

  function updateProcessButtonState() {
    if (!processBtn) return;
    const selected = tbody.querySelectorAll('.karbon-item-checkbox:checked:not(:disabled)');
    processBtn.disabled = selected.length === 0;
  }

  function badgeClassForStatus(status, result) {
    const s = String(status || '').toLowerCase();

    if (status === 'EF Accepted') return 'bg-success';
    if (status === 'EF Rejected') return 'bg-danger';
    if (status === 'Skipped') return 'bg-secondary';
    if (status === 'Queue') return 'bg-warning text-dark';
    if (status === 'Started') return 'bg-primary';

    if (s.includes('missing') || s.includes('not found') || s.includes('invalid')) return 'bg-warning text-dark';
    if (result === 'failed' || s.includes('error') || s.includes('failed')) return 'bg-danger';

    return 'bg-secondary';
  }

  /**
   * Get the display label for an item's Drake Efile Status (for search).
   * Mirrors the logic in renderStatusBadge.
   */
  function getStatusDisplayLabel(item) {
    const reg = String(item.registrationNumber || '').trim();
    if (!reg) return 'missing tax id/ssn';
    const s = String(item.automationStatus || 'NOT_STARTED').toUpperCase();
    switch (s) {
      case 'IN_QUEUE': return 'in queue';
      case 'PROCESSING':
      case 'IN_PROCESSING': return 'in processing';
      case 'CLIENT_NOT_FOUND': return 'client not found in drake';
      case 'AGENCY_ACCEPTED': return 'ef accepted';
      case 'AGENCY_REJECTED': return 'ef rejected';
      case 'SUCCESS':
        return (item.automationMessage || '').toLowerCase().includes('ef accepted')
          ? 'ef accepted'
          : (item.automationMessage || '').toLowerCase().includes('ef rejected')
          ? 'ef rejected'
          : 'completed';
      case 'FAIL':
      case 'FAILED':
      case 'ERROR': return 'error';
      case 'MISSING_TAX_ID': return 'missing tax id/ssn';
      case 'NOT_CHECKED':
      default: return 'not checked';
    }
  }

  function getStatusDisplayMeta(rawStatus, rawTaxId, rawMessage) {
    const taxId = String(rawTaxId ?? '').trim();
    const message = String(rawMessage ?? '').trim();

    // Rule 1: Missing Tax ID / SSN overrides everything
    if (!taxId) {
      return {
        label: 'Missing Tax ID/SSN',
        cssClass: 'status-missingtax',
        is_disabled: true,
      };
    }

    const status = String(rawStatus || 'NOT_STARTED').toUpperCase();
    let label = 'Not Checked';
    let cssClass = 'status-notchecked';
    let is_disabled = false;

    switch (status) {
      case 'IN_QUEUE':
        label = 'Queue';
        cssClass = 'status-inqueue';
        is_disabled = true;
        break;
      case 'PROCESSING':
      case 'IN_PROCESSING':
        label = 'Start';
        cssClass = 'status-processing';
        is_disabled = true;
        break;
      
      case 'SKIPPED':
            label = 'Skipped';
            cssClass = 'bg-secondary';
            is_disabled = false;
            break;

      case 'CLIENT_NOT_FOUND':
        label = 'Client Not Found in Drake';
        cssClass = 'status-clientnotfound';
        is_disabled = false;
        break;
      case 'AGENCY_ACCEPTED':
        label = 'EF Accepted';
        cssClass = 'status-success';
        is_disabled = false;
        break;
      case 'AGENCY_REJECTED':
        label = 'EF Rejected';
        cssClass = 'status-error';
        is_disabled = false;
        break;
      case 'SUCCESS':
        if (message.toLowerCase().includes('ef accepted')) {
          label = 'EF Accepted';
          cssClass = 'status-success';
          is_disabled = false;
        } else if (message.toLowerCase().includes('ef rejected')) {
          label = 'EF Rejected';
          cssClass = 'status-error';
          is_disabled = false;
        } else {
          label = message || 'Completed';
          cssClass = 'status-success';
          is_disabled = false;
        }
        break;
      case 'FAIL':
      case 'FAILED':
      case 'ERROR':
        label = 'Failed';
        cssClass = 'status-error';
        is_disabled = false;
        break;
      case 'MISSING_TAX_ID':
        label = 'Missing Tax ID/SSN';
        cssClass = 'status-missingtax';
        is_disabled = true;
        break;
      case 'NOT_STARTED':
      case 'NOT_CHECKED':
      default:
        label = 'Not Checked';
        cssClass = 'status-notchecked';
        is_disabled = false;
        break;
    }

    return { label, cssClass, is_disabled };
  }

  /**
   * Render a Drake Efile Status badge based on automation status, Tax ID, and message.
   * - If Tax ID is blank, always show "Missing Tax ID/SSN" (overrides status).
   * - SUCCESS + message "EF Accepted"/"EF Rejected" → Agency Accepted/Rejected
   * - Map backend status → UI label + CSS class (status-inqueue, status-processing, etc.)
   */
  function renderStatusBadge(rawStatus, rawTaxId, rawMessage) {
    const meta = getStatusDisplayMeta(rawStatus, rawTaxId, rawMessage);
    const label = meta.label;
    const cssClass = meta.cssClass;
    return `<span class="status-badge ${cssClass} karbon-efile-status">${escapeHtml(label)}</span>`;
  }

  function applyWorkStatusStyle(cell, workStatusText) {
    if (!cell) return;
    const span = cell.querySelector('span');
    if (!span) return;

    const s = String(workStatusText || '').toLowerCase().trim();
    span.classList.remove('karbon-status-accepted', 'karbon-status-rejected', 'text-success', 'text-danger', 'fw-bold');

    // Match your actual values like: "Drake Efile Accepted/Rejected"
    if (s.includes('ef accepted') || s.includes('agency accepted')) {
      span.classList.add('text-success', 'fw-bold');
    } else if (s.includes('ef rejected') || s.includes('agency rejected')) {
      span.classList.add('text-danger', 'fw-bold');
    }
  }

  function markItemState(workItemKey, patch = {}) {
    const idx = allWorkItems.findIndex(x => String(x.workItemKey) === String(workItemKey));
    if (idx === -1) return;
    allWorkItems[idx] = { ...allWorkItems[idx], ...patch };
  }

  // Derive initial efile status after Query (no backend change needed)
  function deriveInitialEfileStatus(item) {
    const reg = String(item.registrationNumber || '').trim();
    const ws = String(item.workStatus || '').toLowerCase();

    if (!reg) {
      return { efileStatus: 'Missing SSN/EIN', badgeClass: badgeClassForStatus('Missing SSN/EIN') };
    }

    // If workStatus already indicates accepted/rejected (because you updated Karbon before)
    if (ws.includes('agency accepted')) {
      return { efileStatus: 'EF Accepted', badgeClass: badgeClassForStatus('EF Accepted') };
    }
    if (ws.includes('agency rejected')) {
      return { efileStatus: 'EF Rejected', badgeClass: badgeClassForStatus('EF Rejected') };
    }

    // default
    const current = item.efileStatus || 'Not Checked';
    return { efileStatus: current, badgeClass: badgeClassForStatus(current) };
  }

  // Map Drake detail -> what to display on badge (covers missing/none/error)
  function mapDetailToEfileDisplay(d) {
    const drakeStatus = d?.drake_status; // may be null
    const reason = d?.reason;
    const result = d?.result;
    const error = d?.error;

    if (drakeStatus) {
      return { text: drakeStatus, result, cls: badgeClassForStatus(drakeStatus, result) };
    }

    // No drake_status -> derive from reason/result
    let text = 'Not Checked';
    if (reason === 'missing_registration_number') text = 'Missing SSN/EIN';
    else if (reason === 'no_drake_status') text = 'Client not found / No status';
    else if (reason === 'normalize_id_failed') text = 'Invalid ID';
    else if (reason === 'drake_lookup_error') text = 'Drake error';
    else if (result === 'failed') text = 'Failed';
    else if (error) text = 'Error';

    return { text, result, cls: badgeClassForStatus(text, result) };
  }

  // -----------------------------
  // Rendering
  // -----------------------------
  function renderEmpty(messageHtml) {
    tbody.innerHTML = `
      <tr class="empty-state">
        <td colspan="9">
          <div style="padding: 40px 20px; text-align: center; color: #6c757d;">
            <i class="bi bi-inbox" style="font-size: 2.5em; opacity: 0.5; display: block; margin-bottom: 12px;"></i>
            <div>${messageHtml}</div>
          </div>
        </td>
      </tr>
    `;
  }

  function renderTable(items) {
    if (!Array.isArray(items) || items.length === 0) {
      renderEmpty('No matching results.');
      return;
    }

    tbody.innerHTML = items.map(item => {
      const processed = !!item._processed;

      const statusMeta = getStatusDisplayMeta(
        item.automationStatus,
        item.registrationNumber,
        item.automationMessage
      );
      const disabled = statusMeta.is_disabled;

      const automationBadgeHtml = renderStatusBadge(
        item.automationStatus,
        item.registrationNumber,
        item.automationMessage
      );
      const karbonLink = `https://app2.karbonhq.com/#/work/${escapeHtml(item.workItemKey)}`;
      
      const ts = item.automationCompletedAt || item.automationStartedAt || item._lastUpdated;
      const lastUpdated = ts ? new Date(ts).toLocaleString() : '';

      return `
        <tr data-workitem-key="${escapeHtml(item.workItemKey)}" class="${processed ? 'karbon-row-processed' : ''}" style="${disabled ? 'opacity:0.65;' : ''}">
          <td>
            <input class="form-check-input karbon-item-checkbox"
                   type="checkbox"
                   value="${escapeHtml(item.workItemKey)}"
                   ${disabled ? 'disabled' : ''}
                   ${disabled ? 'title="Task already in queue"' : ''}>
          </td>
          <td>${escapeHtml(item.registrationNumber || '')}</td>
          <td>${escapeHtml(item.clientName || '')}</td>
          <td style="text-align:center; vertical-align:middle;">${escapeHtml(item.clientType || '')}</td>
          <td style="text-align:center; vertical-align:middle;">${escapeHtml(item.assigneeName || '')}</td>

          <td class="karbon-work-status" style="text-align:center; vertical-align:middle;">
            <span>${escapeHtml(item.workStatus || '')}</span>
          </td>

          <td style="text-align:center; vertical-align:middle;">
            <a href="${karbonLink}" target="_blank" rel="noopener noreferrer" title="View work item in Karbon">Link</a>
          </td>

          <td style="text-align:center; vertical-align:middle;">
            ${automationBadgeHtml}
          </td>

          <td class="karbon-last-updated" style="text-align:center; vertical-align:middle;">
            ${escapeHtml(lastUpdated)}
          </td>
        </tr>
      `;
    }).join('');

    // Apply Work Status colors AFTER rendering
    tbody.querySelectorAll('.karbon-work-status').forEach(cell => {
      applyWorkStatusStyle(cell, cell.textContent);
    });
  }

  // -----------------------------
  // Search / filter
  // -----------------------------
  function applySearchFilter() {
    const q = (searchInput?.value || '').trim().toLowerCase();

    let filtered = allWorkItems;
    if (q) {
      filtered = allWorkItems.filter(item => {
        const reg = String(item.registrationNumber || '').toLowerCase();
        const name = String(item.clientName || '').toLowerCase();

        const type = String(item.clientType || '').toLowerCase();
        const assignee = String(item.assigneeName || '').toLowerCase();
        const workStatus = String(item.workStatus || '').toLowerCase();
        const efileStatus = String(item.efileStatus || '').toLowerCase();
        const statusLabel = getStatusDisplayLabel(item);

        return (
          reg.includes(q) ||
          name.includes(q) ||
          type.includes(q) ||
          assignee.includes(q) ||
          workStatus.includes(q) ||
          efileStatus.includes(q) ||
          statusLabel.includes(q)
        );
      });
    }

    // Update "Filtered to X results"
    if (filterInfoEl && filteredCountEl) {
      if (q) {
        filterInfoEl.style.display = '';
        filteredCountEl.textContent = filtered.length;
      } else {
        filterInfoEl.style.display = 'none';
        filteredCountEl.textContent = '0';
      }
    }

    renderTable(filtered);
    updateProcessButtonState();
  }

  if (searchInput) {
    searchInput.addEventListener('input', debounce(applySearchFilter, 200));
  }

  // -----------------------------
  // Select All (ignore disabled)
  // -----------------------------
  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener('change', (e) => {
      const checkboxes = tbody.querySelectorAll('.karbon-item-checkbox:not(:disabled)');
      checkboxes.forEach(cb => (cb.checked = e.target.checked));
      updateProcessButtonState();
    });
  }

  // Event delegation on tbody for checkbox changes
  tbody.addEventListener('change', (e) => {
    if (e.target.classList.contains('karbon-item-checkbox')) {
      updateProcessButtonState();
      if (selectAllCheckbox && !e.target.checked) selectAllCheckbox.checked = false;
    }
  });

  // -----------------------------
  // Process
  // -----------------------------
  function updateItemStatusUI(key, statusText) {
      // Map human-friendly text coming from the processing loop to
      // our canonical automation status values where possible.
      let newStatus = statusText;
      let newMessage = null;
      const t = String(statusText || '').toLowerCase();

      if (t === 'queue' || t === 'in queue' || t === 'queued') {
        newStatus = 'IN_QUEUE';
      } else if (t === 'started' || t === 'in processing' || t === 'processing') {
        newStatus = 'PROCESSING';
      } else if (t === 'error' || t === 'failed') {
        newStatus = 'FAIL';
        newMessage = statusText;
      } else if (t.includes('ef accepted') || t.includes('ef rejected')) {
        newStatus = 'SUCCESS';
        newMessage = statusText; // e.g., "EF Accepted"
      } else if (t.includes('client not found')) {
        newStatus = 'CLIENT_NOT_FOUND';
        newMessage = statusText;
      } else if (t.includes('karbon skipped') || t.includes('not valid')) {
        newStatus = 'FAIL';
        newMessage = statusText;
      }
      else {
          newStatus = 'SKIPPED';
          newMessage = statusText;
        }


      // Update model
      markItemState(key, {
        automationStatus: newStatus,
        automationMessage: newMessage,
      });

      // Update DOM (Drake Efile Status column now reflects automation state)
      const row = tbody.querySelector(`tr[data-workitem-key="${CSS.escape(String(key))}"]`);
      if (row) {
        const badge = row.querySelector('.karbon-efile-status');
        const taxCell = row.querySelector('td:nth-child(2)');
        const taxId = taxCell ? taxCell.textContent : '';
        
        if (badge) {
          badge.outerHTML = renderStatusBadge(newStatus, taxId, newMessage);
        }

        // If status becomes queued, prevent selection immediately; otherwise re-enable
        const cb = row.querySelector('.karbon-item-checkbox');
        if (cb) {
          if (isNonSelectableAutomationStatus(newStatus)) {
            cb.disabled = true;
            cb.checked = false;
            cb.title = 'Task already in queue';
            row.style.opacity = '0.65';
          } else {
            cb.disabled = false;
            cb.title = '';
            row.style.opacity = '';
          }
        }
      }
  }

  if (processBtn) {
    processBtn.addEventListener('click', async () => {
      const selectedKeys = Array.from(
        tbody.querySelectorAll('.karbon-item-checkbox:checked:not(:disabled)')
      ).map(cb => cb.value);

      if (selectedKeys.length === 0) return;

      const originalText = processBtn.innerHTML;
      processBtn.disabled = true;
      
      // 1. Set Initial Status and ensure polling runs for active items
      selectedKeys.forEach((key, index) => {
        const initialStatus = index === 0 ? 'Started' : 'Queue';
        updateItemStatusUI(key, initialStatus);
      });
      
      // Database
      // startStatusPolling(selectedKeys);
      stopStatusPolling();

      let successCount = 0;
      let failedCount = 0;
      let updatedCount = 0;
      let skippedCount = 0;
      let batchDetails = [];
      let accumulatedTotals = {
          processed: 0,
          updated: 0,
          failed: 0,
          skipped: 0,
          failed_drake: 0,
          failed_karbon: 0
      };
      const startTime = performance.now();

      // Show result panel initially
      showProcessResult({ 
          type: "info", 
          summaryHtml: `Starting processing for ${selectedKeys.length} items...`, 
          detailsHtml: '' // Clear previous details
      });

      try {
        // 2. OPEN DRAKE
        processBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status"></span> Opening Drake...`;
        const openResp = await fetch('/api/karbon/efile-status/open', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ work_item_keys: selectedKeys })
        });
        if (!openResp.ok) throw new Error("Failed to open Drake session");

        // 3. PROCESS LOOP
        for (let i = 0; i < selectedKeys.length; i++) {
            const key = selectedKeys[i];
            const item = allWorkItems.find(x => String(x.workItemKey) === String(key));
            
            processBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status"></span> Processing ${i + 1}/${selectedKeys.length}...`;
            
            if (selectedKeys.length > 1) {
                updateItemStatusUI(key, 'Started');
            }

            if (!item) {
                skippedCount++;
                continue;
            }

            try {
                // A. Check Drake Status
                const checkResp = await fetch('/api/karbon/efile-status/check-client', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        client_id: item.registrationNumber,
                        client_name: item.clientName,
                        work_item_key: key
                    })
                });

                const checkData = await checkResp.json();
                if (!checkResp.ok) throw new Error(checkData.detail || "Check failed");

                if (checkData.status === 'blocked' || checkData.status === 'skipped') {
                    const skipMsg = checkData.message || checkData.automation_status || 'Skipped';
                    updateItemStatusUI(key, skipMsg);
                    batchDetails.push({
                        workItemKey: key,
                        client: item.clientName,
                        registrationNumber: item.registrationNumber,
                        drake_status: skipMsg,
                        result: 'skipped',
                        error: null
                    });
                    continue;
                }

                const drakeStatus = checkData.drake_status;
                let finalStatus = "Client not found in Drake";
                let badgeClass = "bg-secondary";
                let isUpdated = false;
                let karbonUpdateFailed = false;

                if (drakeStatus) {
                    finalStatus = drakeStatus;

                    // B. If Accepted/Rejected, Update Karbon
                    if (drakeStatus === "EF Accepted" || drakeStatus === "EF Rejected") {
                        badgeClass = drakeStatus === "EF Accepted" ? "bg-success" : "bg-danger";
                        
                        const updateResp = await fetch('/api/karbon/update-workitem-status', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                work_item_key: key,
                                efile_status: drakeStatus
                            })
                        });
                        
                        const updateData = await updateResp.json();

                        if (updateResp.ok && updateData.updated > 0) {
                            isUpdated = true;
                            updatedCount++;
                            
                            // Update local model and UI for Work Status
                            const newWorkStatus = drakeStatus === "EF Accepted" ? "Agency Accepted" : "Agency Rejected";
                            markItemState(key, {
                                workStatus: newWorkStatus,
                                _processed: true,
                                _lastUpdated: new Date().toISOString()
                            });
                            
                            // Update Work Status Cell UI
                            const row = tbody.querySelector(`tr[data-workitem-key="${CSS.escape(String(key))}"]`);
                            if (row) {
                                const workStatusCell = row.querySelector('.karbon-work-status');
                                if (workStatusCell) {
                                    const span = workStatusCell.querySelector('span');
                                    if (span) span.textContent = newWorkStatus;
                                    applyWorkStatusStyle(workStatusCell, newWorkStatus);
                                }
                                const timeCell = row.querySelector('.karbon-last-updated');
                                if (timeCell) timeCell.textContent = new Date().toLocaleString();
                                
                                const cb = row.querySelector('.karbon-item-checkbox');
                                if (cb) { cb.checked = false; }
                                row.classList.add('karbon-row-processed');
                            }
                        } else {
                            karbonUpdateFailed = true;
                            finalStatus = "Failed";
                            badgeClass = "bg-danger";
                            // Extract detailed error message from backend response if available
                            if (updateData.details) {
                                const errDetail = updateData.details.find(d => String(d.workItemKey) === String(key));
                                if (errDetail && (errDetail.reason || errDetail.error)) {
                                    // Will be picked up by detailResult logic below if we store it
                                    // However, currently detailResult logic is generic. 
                                    // We'll rely on the batchDetails push below which uses generic error text, 
                                    // OR we can modify the error variable below.
                                }
                            }
                        }
                    }
                    if (karbonUpdateFailed) {
                        failedCount++;
                    } else {
                        successCount++;
                    }
                } else {
                    failedCount++; // Considered a "miss" if not found
                    badgeClass = "bg-warning text-dark";
                }

                // Update Status Badge
                updateItemStatusUI(key, finalStatus);
                
                // Log details (result: updated | skipped | failed_karbon)
                let detailResult = isUpdated ? "updated" : (karbonUpdateFailed ? "failed_karbon" : "skipped");
                batchDetails.push({
                    workItemKey: key,
                    client: item.clientName,
                    registrationNumber: item.registrationNumber,
                    drake_status: finalStatus,
                    result: detailResult,
                    error: karbonUpdateFailed ? "Fail updating Karbon (Status invalid or API error)" : null
                });
                
                // Append to result panel
                if (resultDetails) {
                    const div = document.createElement('div');
                    div.className = 'd-flex justify-content-between border-bottom py-1';
                    div.innerHTML = `
                      <div class="me-2">
                        <span class="text-muted">${escapeHtml(item.registrationNumber)}</span> - <b>${escapeHtml(item.clientName)}</b>
                      </div>
                      <div>
                        <span class="badge ${badgeClass}">${escapeHtml(finalStatus)}</span>
                      </div>
                    `;
                    resultDetails.appendChild(div);
                    resultDetails.scrollTop = resultDetails.scrollHeight;
                }

            } catch (err) {
                console.error(`Error processing ${item.clientName}:`, err);
                failedCount++;
                updateItemStatusUI(key, 'Error');
                
                batchDetails.push({
                    workItemKey: key,
                    client: item.clientName,
                    registrationNumber: item.registrationNumber,
                    drake_status: "Error",
                    result: "failed",
                    error: err.message
                });

                if (resultDetails) {
                    const div = document.createElement('div');
                    div.className = 'd-flex justify-content-between border-bottom py-1';
                    div.innerHTML = `
                      <div class="me-2"><span class="text-muted">${escapeHtml(item.registrationNumber || '')}</span> - <b>${escapeHtml(item.clientName || 'N/A')}</b></div>
                      <div>
                          <span class="badge bg-danger">Failed</span>
                          <span class="text-danger ms-2">- ${escapeHtml(err.message)}</span>
                      </div>
                    `;
                    resultDetails.appendChild(div);
                    resultDetails.scrollTop = resultDetails.scrollHeight;
                }
            }
        }

      } catch (error) {
          console.error("Batch Error:", error);
          if (resultSummary) resultSummary.innerHTML += `<br><span class="text-danger">Batch stopped: ${error.message}</span>`;
      } finally {
          // 4. CLOSE DRAKE
          processBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status"></span> Closing Drake...`;
          try {
              await fetch('/api/karbon/efile-status/close', { method: 'POST' });
          } catch (e) {
              console.warn("Failed to close Drake session:", e);
          }

          // 5. SEND SUMMARY EMAIL (compute totals from per-record batchDetails)
          try {
              const processed = batchDetails.length;
              const updated = batchDetails.filter(d => d.result === 'updated').length;
              const failed_drake = batchDetails.filter(d => d.result === 'failed').length;
              const skipped = batchDetails.filter(d => d.result === 'skipped').length;
              const failed_karbon = batchDetails.filter(d => d.result === 'failed_karbon').length;
              await fetch('/api/karbon/send-efile-summary', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                      totals: {
                          processed,
                          updated,
                          failed_drake,
                          failed_karbon,
                          skipped
                      },
                      processed_count: processed,
                      updates_found: updated,
                      details: batchDetails,
                      duration_sec: (performance.now() - startTime) / 1000
                  })
              });
          } catch (e) { console.error("Failed to send summary email", e); }
      }

      // 3. Finalize
      processBtn.innerHTML = originalText;
      processBtn.disabled = false;
      
      // Cleanup selection states
      tbody.querySelectorAll('.karbon-item-checkbox:checked').forEach(cb => (cb.checked = false));
      if (selectAllCheckbox) selectAllCheckbox.checked = false;
      
      updateProcessButtonState();

      // Update Result Panel
      let panelType = "info";
      if (failedCount > 0) panelType = "warning";
      if (failedCount === selectedKeys.length) panelType = "danger";
      else if (successCount > 0 && failedCount === 0) panelType = "success";

      const summaryHtml = `
          <div>
            <span class="me-3"><b>Processed:</b> ${selectedKeys.length}</span>
            <span class="me-3"><b>Success:</b> ${successCount}</span>
            <span class="me-3"><b>Updated:</b> ${updatedCount}</span>
            <span class="me-3"><b>Failed:</b> ${failedCount}</span>
          </div>
        `;

      // Update summary and status color, but keep the incrementally built details
      showProcessResult({ type: panelType, summaryHtml });
    });
  }

  // -----------------------------
  // Auto-refresh status: poll only for IN_QUEUE/IN_PROCESSING items
  // Stop when all items reach terminal state (SUCCESS, FAIL, CLIENT_NOT_FOUND, etc.)
  // -----------------------------
  const POLL_INTERVAL_MS = 4000;
  const MAX_POLL_DURATION_MS = 8 * 60 * 1000; // safety cutoff
  const NO_PROGRESS_TIMEOUT_MS = 3 * 60 * 1000; // stop if statuses never change
  const NON_SELECTABLE_STATUSES = new Set([
    'IN_QUEUE',
    'IN_PROGRESS',
    'MISSING_TAX_ID',
    'PROCESSING',
    'IN_PROCESSING',
  ]);

  function isNonSelectableAutomationStatus(s) {
    return NON_SELECTABLE_STATUSES.has(String(s || '').toUpperCase());
  }

  function isActiveStatus(s) {
    const status = String(s || '').toUpperCase();
    return (
      status === 'IN_QUEUE' ||
      status === 'IN_PROCESSING' ||
      status === 'PROCESSING' ||
      status === 'IN_PROGRESS'
    );
  }

  function startStatusPolling(trackedKeys = []) {
    stopStatusPolling();

    const normalizedTrackedKeys = Array.from(new Set(
      (Array.isArray(trackedKeys) ? trackedKeys : [])
        .map(k => String(k || '').trim())
        .filter(Boolean)
    ));

    const pollStartedAt = Date.now();
    let lastProgressAt = pollStartedAt;
    const lastStatusByKey = new Map(); // key -> "STATUS|message"

    const hasActiveItems = () =>
      allWorkItems.some(w => isActiveStatus(w.automationStatus)) || normalizedTrackedKeys.length > 0;
    if (!hasActiveItems()) return;

    function applyDbStatusToRow(permaKey, st) {
      if (!permaKey || !st) return false;
      const key = String(permaKey);

      const idx = allWorkItems.findIndex(x => String(x.workItemKey) === key);
      if (idx === -1) return false;

      const nextStatus = st.status;
      const nextMessage = st.message || null;
      const nextStartedAt = st.started_at || null;
      const nextCompletedAt = st.completed_at || null;

      const prev = allWorkItems[idx] || {};
      const changed =
        prev.automationStatus !== nextStatus ||
        (prev.automationMessage || null) !== nextMessage ||
        (prev.automationStartedAt || null) !== nextStartedAt ||
        (prev.automationCompletedAt || null) !== nextCompletedAt;

      allWorkItems[idx] = {
        ...prev,
        automationStatus: nextStatus,
        automationMessage: nextMessage,
        automationStartedAt: nextStartedAt,
        automationCompletedAt: nextCompletedAt,
      };

      const row = tbody.querySelector(`tr[data-workitem-key="${CSS.escape(key)}"]`);
      if (row) {
        const badge = row.querySelector('.karbon-efile-status');
        const taxCell = row.querySelector('td:nth-child(2)');
        const taxId = taxCell ? taxCell.textContent : '';
        if (badge) {
          badge.outerHTML = renderStatusBadge(nextStatus, taxId, nextMessage);
        }

        const cb = row.querySelector('.karbon-item-checkbox');
        if (cb) {
          if (isNonSelectableAutomationStatus(nextStatus)) {
            cb.disabled = true;
            cb.checked = false;
            cb.title = 'Task already in queue';
            row.style.opacity = '0.65';
          } else {
            cb.disabled = false;
            cb.title = '';
            row.style.opacity = '';
          }
        }

        const tsIso = nextCompletedAt || nextStartedAt || null;
        const tsCell = row.querySelector('.karbon-last-updated');
        if (tsCell && tsIso) {
          tsCell.textContent = new Date(tsIso).toLocaleString();
        }
      }

      return changed;
    }

    const tick = async () => {
      if (allWorkItems.length === 0) return;

      const now = Date.now();
      if (now - pollStartedAt > MAX_POLL_DURATION_MS) {
        stopStatusPolling();
        try {
          showProcessResult?.({
            type: "warning",
            summaryHtml: "Processing is taking longer than expected. Please refresh later.",
          });
        } catch (e) { /* ignore */ }
        return;
      }
      if (now - lastProgressAt > NO_PROGRESS_TIMEOUT_MS) {
        stopStatusPolling();
        try {
          showProcessResult?.({
            type: "warning",
            summaryHtml: "Processing appears stuck (no status changes). Please retry later.",
          });
        } catch (e) { /* ignore */ }
        return;
      }

      // Query both currently active records and explicit batch keys so polling
      // starts immediately after trigger even if local status is stale.
      const activeItems = allWorkItems.filter(w => isActiveStatus(w.automationStatus));
      const trackedItems = allWorkItems.filter(w =>
        normalizedTrackedKeys.includes(String(w.workItemKey || ''))
      );
      const itemsToQuery = [...activeItems];
      for (const wi of trackedItems) {
        if (!itemsToQuery.some(x => String(x.workItemKey) === String(wi.workItemKey))) {
          itemsToQuery.push(wi);
        }
      }

      if (itemsToQuery.length === 0) {
        stopStatusPolling();
        return;
      }

      const keys = itemsToQuery.map(w => String(w.workItemKey)).filter(Boolean);
      if (keys.length === 0) return;
      try {
        const resp = await fetch(`/api/workitems/status?perma_keys=${encodeURIComponent(keys.join(','))}`);
        if (!resp.ok) return;
        const data = await resp.json();
        const statuses = data.statuses || {};
        let changed = false;
        for (const [permaKey, st] of Object.entries(statuses)) {
          if (applyDbStatusToRow(permaKey, st)) changed = true;
          lastStatusByKey.set(String(permaKey), `${String(st?.status || '')}|${String(st?.message || '')}`);
        }
        // Consider "progress" any time we observe a status/message change from backend.
        if (changed) lastProgressAt = Date.now();
        if (changed) applySearchFilter();
        const stillActive = allWorkItems.some(w => {
          const key = String(w.workItemKey || '');
          return isActiveStatus(w.automationStatus) && (normalizedTrackedKeys.length === 0 || normalizedTrackedKeys.includes(key));
        });
        if (!stillActive) stopStatusPolling();
      } catch (e) { /* ignore */ }
    };

    // Run one poll immediately, then continue with interval.
    tick();
    statusPollInterval = setInterval(tick, POLL_INTERVAL_MS);
  }

  function stopStatusPolling() {
    if (statusPollInterval) {
      clearInterval(statusPollInterval);
      statusPollInterval = null;
    }
  }

  // -----------------------------
  // Query Karbon
  // -----------------------------
  queryBtn.addEventListener('click', async () => {
    hideProcessResult({ clear: true });

    const originalText = queryBtn.innerHTML;
    queryBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Querying...';
    queryBtn.disabled = true;

    if (processBtn) processBtn.disabled = true;
    if (selectAllCheckbox) selectAllCheckbox.checked = false;
    if (recordCountEl) recordCountEl.textContent = '0';

    tbody.innerHTML = `
      <tr class="empty-state">
        <td colspan="9">
          <div style="padding: 40px 20px; text-align: center; color: #6c757d;">
            <div class="spinner-border text-primary" role="status">
              <span class="visually-hidden">Loading Karbon data...</span>
            </div>
          </div>
        </td>
      </tr>
    `;

    try {
      const response = await fetch('/api/karbon/efile-status-work-items?top=100&skip=0');
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to query Karbon.' }));
        throw new Error(errorData.detail);
      }

      const workItems = await response.json();
      allWorkItems = Array.isArray(workItems) ? workItems : [];

      // Derive initial statuses (Missing SSN/EIN, or map workStatus -> EF Accepted/Rejected)
      // automationStatus is merged by backend on Query Karbon so badges show immediately
      allWorkItems = allWorkItems.map(it => {
        const derived = deriveInitialEfileStatus(it);
        return {
          ...it,
          efileStatus: derived.efileStatus,
          _badgeClass: derived.badgeClass,
          automationStatus: it.automationStatus || 'NOT_STARTED',
        };
      });

      hideProcessResult();

      if (recordCountEl) recordCountEl.textContent = allWorkItems.length;

      // Reset search/filter UI
      if (searchInput) searchInput.value = '';
      if (filterInfoEl) filterInfoEl.style.display = 'none';
      if (filteredCountEl) filteredCountEl.textContent = '0';

      if (allWorkItems.length === 0) {
        renderEmpty('Click <strong>"Query Karbon"</strong> to load the item list from Karbon.');
        stopStatusPolling();
      } else {
        renderTable(allWorkItems);
        // Do not auto-start polling on list load; only poll after explicit processing action.
        stopStatusPolling();
      }
    } catch (error) {
      console.error('Error querying Karbon:', error);
      tbody.innerHTML = `
        <tr class="empty-state">
          <td colspan="10">
            <div style="padding: 40px 20px; text-align: center; color: #dc3545;">
              <i class="bi bi-exclamation-triangle" style="font-size: 2.5em; display: block; margin-bottom: 12px;"></i>
              <div><strong>Error:</strong> ${escapeHtml(error.message)}</div>
            </div>
          </td>
        </tr>
      `;
      if (recordCountEl) recordCountEl.textContent = '0';
    } finally {
      queryBtn.innerHTML = originalText;
      queryBtn.disabled = false;
      updateProcessButtonState();
    }
  });
}
/**
 * Reset Step 1 selection and disable upload UI
 */
function resetStep1Selection() {
    const uploadArea = document.getElementById('uploadArea');
    const uploadPrompt = document.getElementById('uploadPrompt');

    selectedFormType = null;
    detectedPageGroups = null; // Reset automated detection
    
    const radios = document.querySelectorAll('input[name="taxFormType"]');
    radios.forEach(r => r.checked = false);

    if (uploadArea) {
        uploadArea.style.opacity = '0.5';
        uploadArea.style.pointerEvents = 'none';
    }
    if (uploadPrompt) {
        uploadPrompt.classList.remove('hidden');
        uploadPrompt.textContent = 'Please select a form type in Step 1 first.';
    }
}

/**
 * Navigate to a specific step
 * @param {number} stepNumber - Step number (1-5)
 */
function goToStep(stepNumber) {
    currentStep = stepNumber;
    
    for (let i = 1; i <= 5; i++) {
        const step = document.getElementById(`step${i}`);
        const content = document.getElementById(`step${i}Content`);
        
        if (!step || !content) continue;

        if (i < stepNumber) {
            step.classList.add('completed');
            step.classList.remove('active');
            content.classList.remove('active');
        } else if (i === stepNumber) {
            step.classList.add('active');
            step.classList.remove('completed');
            content.classList.add('active');
        } else {
            step.classList.remove('active', 'completed');
            content.classList.remove('active');
        }
    }
    
    // Update back button visibility
    updateBackButton();
}

/**
 * Update back button visibility and behavior
 */
function updateBackButton() {
    const backBtn = document.getElementById('backBtn');
    const backBtnText = backBtn.querySelector('.btn-back-text');
    
    if (currentStep > 1) {
        backBtn.classList.remove('hidden');
        // Update button text based on previous step
        const previousStepLabels = {
            2: 'Select Form Type',
            3: 'Upload Document',
            4: 'Select Page Groups',
            5: 'Process & View'
        };
        const previousLabel = previousStepLabels[currentStep] || 'Previous Step';
        backBtnText.textContent = `Back to ${previousLabel}`;
    } else {
        backBtn.classList.add('hidden');
    }
}

/**
 * Navigate back to previous step
 */
function goBackToPreviousStep() {
    if (currentStep <= 1) return;
    
    const previousStep = currentStep - 1;
    
    // Handle special cases when going back
    if (currentStep === 4) {
        // If going back from results, hide results view
        document.getElementById('resultsView').classList.add('hidden');
        document.getElementById('processingStatus').classList.add('hidden');
    } else if (currentStep === 3) {
        // If going back from page groups, we can keep the uploaded file info
        // No special handling needed
    } else if (currentStep === 2) {
        // If going back to step 1, we can optionally clear the form type selection
        resetStep1Selection();
    }
    
    goToStep(previousStep);
    
    // Scroll to top of page for better UX
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/**
 * Setup step indicator clicks for navigation
 */
function setupStepIndicatorClicks() {
    for (let i = 1; i <= 5; i++) {
        const step = document.getElementById(`step${i}`);
        if (!step) continue;

        step.style.cursor = 'pointer';
        step.setAttribute('tabindex', '0');
        step.setAttribute('role', 'button');
        step.setAttribute('aria-label', `Go to step ${i}`);
        
        step.addEventListener('click', () => {
            // Only allow navigation to completed steps or the current step
            // Don't allow jumping ahead
            if (i <= currentStep || step.classList.contains('completed')) {
                if (i < currentStep) {
                    // Going back - handle cleanup
                    if (currentStep === 4) {
                        document.getElementById('resultsView').classList.add('hidden');
                        document.getElementById('processingStatus').classList.add('hidden');
                    } else if (currentStep === 2 && i === 1) {
                        resetStep1Selection();
                    }
                }
                goToStep(i);
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
        
        // Add keyboard support
        step.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                step.click();
            }
        });
    }
}

/**
 * Initialize the application
 */
function init() {
    // Setup module navigation
    // Restore active module from sessionStorage or use a default.
    const buttons = document.querySelectorAll('.module-nav-button');
    let savedModuleId = null;
    try {
        savedModuleId = sessionStorage.getItem('activeModuleId');
    } catch (e) {
        console.warn('Cannot read module state:', e);
    }

    let initialModuleId = null;

    if (savedModuleId && document.getElementById(savedModuleId)) {
        // A valid module ID was found in storage, use it.
        console.log('Restoring saved module:', savedModuleId);
        initialModuleId = savedModuleId;
    } else if (buttons.length > 0) {
        // Otherwise, fall back to the first module in the list (Introduction).
        initialModuleId = buttons[0].dataset.module;
    }

    setActiveModule(initialModuleId);

    setupModuleNav();
    setupFilingInstructionsModule();
    setupKarbonEfileModule();

    // Setup step indicator clicks
    setupStepIndicatorClicks();

    // Back button click handler
    document.getElementById('backBtn').addEventListener('click', () => {
        goBackToPreviousStep();
    });

    // Step 1: Select Form Type
    const formTypeRadios = document.querySelectorAll('input[name="taxFormType"]');
    const uploadArea = document.getElementById('uploadArea');
    const uploadPrompt = document.getElementById('uploadPrompt');
    
    const handleFormTypeChange = async (e) => {
        selectedFormType = e.target.value;
        if (selectedFormType) {
            // Enable upload area
            uploadArea.style.opacity = '1';
            uploadArea.style.pointerEvents = 'auto';
            uploadPrompt.classList.remove('hidden');
            
            const label = document.querySelector(`label[for="${e.target.id}"]`).textContent;
            uploadPrompt.textContent = `Ready to upload PDF for ${label}`;
            
            // Clear file info if going back to step 2
            if (currentStep === 1) {
                currentFileName = null;
                updateFileInfo(null, '');
            }
            
            setTimeout(() => {
                goToStep(2);
            }, 500);
        } else {
            // Disable upload area
            uploadArea.style.opacity = '0.5';
            uploadArea.style.pointerEvents = 'none';
            uploadPrompt.classList.remove('hidden');
            uploadPrompt.textContent = 'Please select a form type in Step 1 first.';
            
            // Clear file info
            currentFileName = null;
            updateFileInfo(null, '');
        }
    };

    formTypeRadios.forEach(radio => {
        radio.addEventListener('change', handleFormTypeChange);
    });

    // Step 2: Upload Document
    const fileInput = document.getElementById('fileInput');

    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type === 'application/pdf') {
            handleFileUpload(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // Step 3: Process
    const processBtn = document.getElementById('processBtn');
    processBtn.addEventListener('click', async () => {
        if (Object.keys(selectedGroups).length === 0) return;

        // Update file status
        updateFileInfo(currentFileName, 'Processing...');

        goToStep(4);
        document.getElementById('processingStatus').classList.remove('hidden');
        document.getElementById('resultsView').classList.add('hidden');

        try {
            const formData = new FormData();
            formData.append('form_type', selectedFormType);
            formData.append('selected_groups', JSON.stringify(selectedGroups));

            const response = await fetch(`${API_BASE}/jobs/${currentJobId}/process-groups`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Processing failed');
            }

            await pollForResults();
        } catch (error) {
            document.getElementById('processingStatus').innerHTML = 
                `<div class="status-message status-error">Error: ${error.message}</div>`;
            updateFileInfo(currentFileName, 'Processing Failed');
        }
    });

    // Save Changes button
    const saveBtn = document.getElementById('saveChangesBtn');
    if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
            await saveEditedData();
        });
    }

    // Excel Export
    document.getElementById('exportCsvBtn').addEventListener('click', async () => {
        try {
            // Get edited data from both data tables and Excel tables
            const allTables = document.querySelectorAll('.data-table, .excel-data-table');
            const editedFieldsByGroup = {};
            
            for (const table of allTables) {
                const tableId = table.dataset.tableId;
                if (!tableId || !editedData[tableId]) continue;
                
                const accordionSection = table.closest('.accordion-section');
                if (!accordionSection) continue;
                
                const sectionTitle = accordionSection.querySelector('h3')?.textContent || '';
                const groupName = Object.keys(GROUP_DISPLAY_NAMES).find(
                    key => GROUP_DISPLAY_NAMES[key] === sectionTitle
                ) || sectionTitle.toLowerCase().replace(/\s+/g, '_');
                
                if (!editedFieldsByGroup[groupName]) {
                    editedFieldsByGroup[groupName] = {};
                }
                
                const rows = table.querySelectorAll('tbody tr');
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    const fieldKey = cells[2]?.dataset.fieldKey; // Value column (3rd column, index 2)
                    if (fieldKey && editedData[tableId][fieldKey] !== undefined) {
                        editedFieldsByGroup[groupName][fieldKey] = editedData[tableId][fieldKey];
                    }
                });
            }
            
            const url = new URL(`${API_BASE}/jobs/${currentJobId}/export/excel`, window.location.origin);
            if (Object.keys(editedFieldsByGroup).length > 0) {
                url.searchParams.set('edited_fields', JSON.stringify(editedFieldsByGroup));
            }
            
            const response = await fetch(url.toString());
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = `results_${currentJobId}.xlsx`;
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
        } catch (error) {
            alert(`Error exporting Excel: ${error.message}`);
        }
    });

    // JSON Download
    document.getElementById('downloadJsonBtn').addEventListener('click', async () => {
        try {
            const url = `${API_BASE}/jobs/${currentJobId}/export/json`;
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = `results_${currentJobId}.json`;
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
        } catch (error) {
            alert(`Error downloading JSON: ${error.message}`);
        }
    });

    // Clear selection when clicking outside tables
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.data-table')) {
            document.querySelectorAll('.data-table').forEach(table => {
                clearSelection(table);
            });
        }
    });

    // Global keyboard listener for copy (works regardless of focus)
    document.addEventListener('keydown', (e) => {
        // Only handle Ctrl/Cmd+C
        if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
            // Check if user is editing a cell (contenteditable)
            const activeElement = document.activeElement;
            if (activeElement && activeElement.isContentEditable) {
                // Let default copy behavior work for contenteditable elements
                return;
            }

            // Check Excel tables first
            const excelTables = document.querySelectorAll('.excel-data-table');
            for (const table of excelTables) {
                const selectedCells = table.querySelectorAll('td.selected, th.selected');
                if (selectedCells.length > 0) {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('Ctrl/Cmd+C detected, selected cells:', selectedCells.length);
                    if (typeof copySelectedExcelCells === 'function') {
                        copySelectedExcelCells();
                    } else if (typeof window.copySelectedExcelCells === 'function') {
                        window.copySelectedExcelCells();
                    } else {
                        console.error('copySelectedExcelCells function not found');
                    }
                    return;
                }
            }

            // Check regular data tables
            const allTables = document.querySelectorAll('.data-table');
            for (const table of allTables) {
                const selectedCells = table.querySelectorAll('td.selected');
                if (selectedCells.length > 0) {
                    e.preventDefault();
                    copySelectedCells(selectedCells);
                    return;
                }
            }

            // If no cells selected but user pressed Ctrl+C on a table, copy entire table
            if (activeElement && activeElement.closest('.data-table')) {
                const table = activeElement.closest('.data-table');
                e.preventDefault();
                copyTableToClipboard(table);
            }
        }
    });
    // OCR Module Back Button
    const ocrBackBtn = document.getElementById('ocrBackToClientListBtn');
    if (ocrBackBtn) {
        ocrBackBtn.addEventListener('click', () => {
            setActiveModule('clientTaxReturnModule');
        });
    }

    const ocrReturnBtn = document.getElementById('ocrReturnToClientListBtn');
    if (ocrReturnBtn) {
        ocrReturnBtn.addEventListener('click', () => {
            setActiveModule('clientTaxReturnModule');
        });
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
