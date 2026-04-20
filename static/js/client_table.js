/**
 * Client Table Management Script
 * Handles filtering, pagination, and rendering
 */

class ClientTableManager {
    constructor(config) {
        // Default configuration for the original module (OCR)
        this.config = Object.assign({
            instanceName: 'clientTableMgr',
            ids: {
                searchInput: 'clientSearchInput',
                selectAll: 'clientSelectAll',
                tableBody: 'clientTableBody',
                pagination: 'clientTablePagination',
                paginationInfo: 'paginationInfo',
                statusInfo: 'clientStatusInfo',
                recordCount: 'clientRecordCount',
                filterInfo: 'clientFilterInfo',
                filteredCount: 'clientFilteredCount',
                loadTime: 'clientLoadTime',
                processEFBtn: 'processEFBtn', // May not exist in OCR module anymore
                efResult: 'efProcessResult',
                efSummary: 'efProcessSummary',
                efDetails: 'efProcessDetails',
                efCloseBtn: 'efProcessCloseBtn',
                queryBtn: 'queryDrakeBtn'
            },
            showActions: true,
            showEF: false,
            showOCR: true,
            showSelectCheckbox: true
        }, config);

        this.allClients = [];
        this.filteredClients = [];
        this.currentPage = 1;
        this.itemsPerPage = 15;
        this.searchTerm = '';
        this.selectedClientIds = new Set();
        this.isProcessing = false;

        // OCR status persistence now comes from Service B DB (queried via Service A proxy).
        // No client-side storage is used for persistence.
        this.ocrStatus = {};
        
        this.lastLoadTime = '';
        
        this.init();
    }

    init() {
        const searchInput = document.getElementById(this.config.ids.searchInput);
        if (searchInput) {
            searchInput.addEventListener('input', (e) => this.handleSearch(e.target.value));
            searchInput.addEventListener('keyup', (e) => {
                if (e.key === 'Enter') this.handleSearch(e.target.value);
            });
        }

        const selectAllCheckbox = document.getElementById(this.config.ids.selectAll);
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => this.handleSelectAll(e.target.checked));
        }

        const tbody = document.getElementById(this.config.ids.tableBody);
        if (tbody) {
            tbody.addEventListener('change', (e) => {
                if (e.target.classList.contains('client-item-checkbox')) {
                    this.handleItemSelect(e.target.value, e.target.checked);
                }
            });
        }
        
        // Auto-load on page load
        this.autoLoad();

        const goToPageBtn = document.getElementById('goToPageBtn');
        const goToPageInput = document.getElementById('goToPageInput');

        if (goToPageBtn && goToPageInput) {
            const goToHandler = () => {
                const page = parseInt(goToPageInput.value, 10);
                if (!isNaN(page)) {
                    this.goToPage(page);
                }
                goToPageInput.value = ''; // Clear input after use
            };

            goToPageBtn.addEventListener('click', goToHandler);
            goToPageInput.addEventListener('keyup', (e) => {
                if (e.key === 'Enter') goToHandler();
            });
        }

        // Query Button
        const queryBtn = document.getElementById(this.config.ids.queryBtn);
        if (queryBtn) {
            queryBtn.addEventListener('click', () => this.manualQuery());
        }
    }

    async autoLoad() {
        console.log('[ClientTable] Auto-loading data from latest CSV...');
        
        try {
            // First get metadata
            const metaResponse = await fetch('/api/drake/file-metadata');
            const metadata = await metaResponse.json();
            
            if (metadata.exists) {
                this.lastLoadTime = metadata.timestamp;
                const timeEl = document.getElementById(this.config.ids.loadTime);
                if (timeEl) {
                    timeEl.textContent = `Loaded: ${metadata.timestamp}`;
                    timeEl.style.display = 'inline';
                }
                console.log(`[ClientTable] Latest file: ${metadata.filename} (${metadata.timestamp})`);
            } else {
                console.log('[ClientTable] No export files found, requesting manual Query Drake');
                return;
            }
            
            // Then fetch client data
            const response = await fetch('/api/drake/latest-clients');
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const clients = await response.json();
            this.setClients(clients);
            console.log(`[ClientTable] ✓ Auto-loaded ${clients.length} clients`);
            
        } catch (error) {
            console.warn('[ClientTable] Auto-load failed:', error.message);
            // Auto-load failed, show message to user
            const infoEl = document.getElementById(this.config.ids.statusInfo);
            if (infoEl) {
                infoEl.innerHTML = `<strong style="color: #dc3545;">❌ No data available</strong> - Click "Query Drake" to load client list`;
            }
        }
    }

    async manualQuery() {
        const queryBtn = document.getElementById(this.config.ids.queryBtn);

        const originalText = queryBtn ? queryBtn.innerHTML : '';
        const loadingHtml = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Querying...';

        if (queryBtn) {
            queryBtn.innerHTML = loadingHtml;
            queryBtn.disabled = true;
        }

        const infoEl = document.getElementById(this.config.ids.statusInfo);
        if (infoEl) { infoEl.innerHTML = ''; infoEl.style.display = 'none'; }

        try {
            const response = await fetch('/api/drake/query-clients', { method: 'POST' });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to query Drake clients.');
            }
            const clients = await response.json();

            this.setClients(clients);
            this.updateLoadTime();

        } catch (error) {
            console.error('Error querying Drake:', error);
            const errorHtml = `<strong style="color: #dc3545;">❌ Error:</strong> ${this.escapeHtml(error.message)}`;
            if (infoEl) { infoEl.innerHTML = errorHtml; infoEl.style.display = 'block'; }
        } finally {
            if (queryBtn) { queryBtn.innerHTML = originalText; queryBtn.disabled = false; }
        }
    }

    setClients(clients) {
        this.allClients = clients || [];
        this.allClients.forEach(client => {
            client.ocrStatus = ''; // filled by refreshOcrStatuses()
        });
        this.filteredClients = [...this.allClients];
        this.currentPage = 1;
        this.selectedClientIds.clear();
        this.updateRecordCount();
        this.render();
        this.refreshOcrStatuses();
    }

    handleSearch(term) {
        this.searchTerm = term.toLowerCase().trim();
        this.currentPage = 1;

        if (!this.searchTerm) {
            this.filteredClients = [...this.allClients];
            document.getElementById(this.config.ids.filterInfo).style.display = 'none';
        } else {
            this.filteredClients = this.allClients.filter(client => {
                const id = (client['Taxpayer ID'] || '').toString().toLowerCase();
                const name = (client['Taxpayer Name'] || '').toLowerCase();
                const type = (client['Return Type'] || '').toLowerCase();
                
                return id.includes(this.searchTerm) || 
                       name.includes(this.searchTerm) || 
                       type.includes(this.searchTerm);
            });
            
            // Show filter info
            const filterInfo = document.getElementById(this.config.ids.filterInfo);
            if (filterInfo) {
                filterInfo.style.display = 'inline';
                document.getElementById(this.config.ids.filteredCount).textContent = this.filteredClients.length;
            }
        }

        this.render();
    }

    updateRecordCount() {
        const countEl = document.getElementById(this.config.ids.recordCount);
        if (countEl) {
            countEl.textContent = this.allClients.length;
        }
    }

    getPagedClients() {
        const start = (this.currentPage - 1) * this.itemsPerPage;
        const end = start + this.itemsPerPage;
        return this.filteredClients.slice(start, end);
    }

    getTotalPages() {
        return Math.ceil(this.filteredClients.length / this.itemsPerPage);
    }

    render() {
        this.renderTable();
        this.renderPagination();
    }

    renderTable() {
        const tbody = document.getElementById(this.config.ids.tableBody);
        if (!tbody) return;

        const pagedClients = this.getPagedClients();
        // Calculate colspan dynamically based on visible columns
        let colspan = 3; // ID, Name, Type
        if (this.config.showSelectCheckbox) colspan++;
        if (this.config.showOCR) colspan++;
        if (this.config.showActions) colspan++;

        if (pagedClients.length === 0) {
            tbody.innerHTML = `
                <tr class="empty-state">
                    <td colspan="${colspan}">
                        <div style="padding: 40px 20px; text-align: center; color: #6c757d;">
                            <i class="bi bi-inbox" style="font-size: 2.5em; opacity: 0.5; display: block; margin-bottom: 12px;"></i>
                            ${this.searchTerm ? 
                                `<div>No results found for "<strong>${this.escapeHtml(this.searchTerm)}</strong>"</div>` 
                                : `<div>Click <strong>"Query Drake"</strong> to load client data</div>`
                            }
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = pagedClients.map(client => {
            let ocrStatusHtmlCell = '';
            if (this.config.showOCR) {
                const ocrStatus = client.ocrStatus || '';
                let ocrStatusHtml = '';
                if (ocrStatus === 'Extracted') {
                    ocrStatusHtml = `<span class="status-extracted">Extracted</span>`;
                } else if (ocrStatus === 'Extracted Fail') {
                    ocrStatusHtml = `<span class="status-error">Extracted Fail</span>`;
                } else {
                    ocrStatusHtml = '';
                }
                ocrStatusHtmlCell = `<td style="text-align: center;">${ocrStatusHtml}</td>`;
            }

            const clientId = client['Taxpayer ID'] || '';
            const isChecked = this.selectedClientIds.has(clientId);

            let actionsHtml = '';
            if (this.config.showActions) {
                actionsHtml = `
                    <td class="text-center">
                        <button 
                            type="button"
                            class="btn btn-primary ocr-extract-btn btn-sm"
                            onclick="${this.config.instanceName}.handleOCR(
                                event,
                                '${this.escapeHtml(client['Taxpayer ID'] || '')}',
                                '${this.escapeHtml(client['Return Type'] || 'N/A')}'
                            )">
                            <span class="btn-text">Extract Final Tax Return Data</span>
                            <span class="spinner-border spinner-border-sm hidden" role="status" aria-hidden="true"></span>
                        </button>
                    </td>`;
            }

            let checkboxHtml = '';
            if (this.config.showSelectCheckbox) {
                checkboxHtml = `
                    <td class="text-center">
                        <input class="form-check-input client-item-checkbox" type="checkbox" value="${this.escapeHtml(clientId)}" ${isChecked ? 'checked' : ''}>
                    </td>`;
            }

            return `
                <tr>
                    ${checkboxHtml}
                    <td class="text-center">${this.escapeHtml(client['Taxpayer ID'] || '')}</td>
                    <td class="text-start">${this.escapeHtml(client['Taxpayer Name'] || '')}</td>
                    <td>${this.escapeHtml(client['Return Type'] || 'N/A')}</td>
                    ${ocrStatusHtmlCell}
                    ${actionsHtml}
                </tr>
            `;
        }).join('');
        this.updateSelectAllCheckboxState();
    }

    renderPagination() {

        const totalPages = this.getTotalPages();
        const paginationEl = document.getElementById(this.config.ids.pagination);
        const paginationInfo = document.getElementById(this.config.ids.paginationInfo);
        const goToPageContainer = document.getElementById('goToPageContainer');

        if (!paginationEl) return;

        // Update pagination info
        if (paginationInfo) {
            if (this.filteredClients.length === 0) {
                paginationInfo.textContent = '';
            } else {
                const start = (this.currentPage - 1) * this.itemsPerPage + 1;
                const end = Math.min(this.currentPage * this.itemsPerPage, this.filteredClients.length);
                paginationInfo.textContent = `Showing ${start} to ${end} of ${this.filteredClients.length}`;
            }
        }

        if (totalPages <= 1) {
            paginationEl.innerHTML = '';
            if (goToPageContainer) goToPageContainer.style.display = 'none';
            return;
        }

        if (goToPageContainer) {
            goToPageContainer.style.display = 'flex';
            const goToPageInput = document.getElementById('goToPageInput');
            goToPageInput.max = totalPages;
            goToPageInput.placeholder = `1-${totalPages}`;
        }

        let html = '';

        // Previous button
        html += `            
            <li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="${this.config.instanceName}.goToPage(${this.currentPage - 1}); return false;">
                    ← Previous
                </a>
            </li>
        `;

        // Page numbers
        const maxVisible = 5;
        const halfVisible = Math.floor(maxVisible / 2);
        let startPage = Math.max(1, this.currentPage - halfVisible);
        let endPage = Math.min(totalPages, startPage + maxVisible - 1);

        if (endPage - startPage + 1 < maxVisible) {
            startPage = Math.max(1, endPage - maxVisible + 1);
        }

        if (startPage > 1) {
            html += `<li class="page-item"><a class="page-link" href="#" onclick="${this.config.instanceName}.goToPage(1); return false;">1</a></li>`;
            if (startPage > 2) {
                html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }
        }

        for (let i = startPage; i <= endPage; i++) {
            html += `
                <li class="page-item ${i === this.currentPage ? 'active' : ''}">
                    <a class="page-link" href="#" onclick="${this.config.instanceName}.goToPage(${i}); return false;">
                        ${i}
                    </a>
                </li>
            `;
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }
            html += `<li class="page-item"><a class="page-link" href="#" onclick="${this.config.instanceName}.goToPage(${totalPages}); return false;">${totalPages}</a></li>`;
        }

        // Next button
        html += `
            <li class="page-item ${this.currentPage === totalPages ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="${this.config.instanceName}.goToPage(${this.currentPage + 1}); return false;">
                    Next →
                </a>
            </li>
        `;

        paginationEl.innerHTML = html;
    }

    updateStatus(clientId, statusType, text) {
        if (!clientId) return;
        const normalizedId = String(clientId).trim();
        
        let statusObject;
        let storageKey;
        let clientField;

        if (statusType === 'ocr') {
            statusObject = this.ocrStatus;
            clientField = 'ocrStatus';
        } else {
            console.warn(`[ClientTable] Unknown status type: ${statusType}. Must be 'ocr'.`);
            return;
        }

        console.log(`[ClientTable] Updating ${statusType} status for ${normalizedId}: ${text}`);
        statusObject[normalizedId] = text;

        // Update in allClients
        const client = this.allClients.find(c => String(c['Taxpayer ID']).trim() === normalizedId);
        if (client) {
            client[clientField] = text;
        }

        this.render();
    }

    async refreshOcrStatuses() {
        const taxIds = (this.allClients || [])
            .map(c => String(c['Taxpayer ID'] || '').trim())
            .filter(Boolean);
        if (taxIds.length === 0) return;

        try {
            const response = await fetch(`/api/ocr-results?tax_ids=${encodeURIComponent(taxIds.join(','))}`);
            if (!response.ok) return;
            const rows = await response.json();
            const map = {};
            (rows || []).forEach(r => {
                const taxId = String(r.tax_id || '').trim();
                if (!taxId) return;
                if (r.ocr_status === 'EXTRACTED') map[taxId] = 'Extracted';
                else if (r.ocr_status === 'EXTRACTED_FAIL') map[taxId] = 'Extracted Fail';
            });

            this.allClients.forEach(client => {
                const id = String(client['Taxpayer ID'] || '').trim();
                client.ocrStatus = map[id] || '';
            });
            this.filteredClients.forEach(client => {
                const id = String(client['Taxpayer ID'] || '').trim();
                client.ocrStatus = map[id] || '';
            });
            this.render();
        } catch (e) {
            console.warn('[ClientTable] Failed to refresh OCR statuses', e);
        }
    }

    async handleOCR(event, clientId, returnType) {
        console.log('OCR clicked for:', clientId, returnType);
        
        // if (!confirm(`Start OCR extraction process for Client ${clientId} (${returnType})?`)) {
        //     return;
        // }

        const button = event.currentTarget;
        const originalText = button.querySelector('.btn-text');

        const spinner = button.querySelector('.spinner-border');
        const allButtons = document.querySelectorAll('.ocr-extract-btn');

        if (button.disabled) {
            return; // Already processing
        }

        // Disable all buttons to prevent concurrent requests

        allButtons.forEach(btn => btn.disabled = true);
        originalText.textContent = 'Processing...';
        spinner.classList.remove('hidden');


        try {
            const response = await fetch('/api/drake/print-return', {

                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ client_id: clientId, return_type: returnType })
            });
            const result = await response.json();
            
            if (result.job_id) {

                // New logic: switch tab and auto-start the flow
                console.log(`Switching to OCR Tax Return module with Job ID: ${result.job_id}`);
                
                // 1. Switch the active module
                if (typeof setActiveModule === 'function') {
                    setActiveModule('ocrTaxReturnModule');
                } else {
                    console.error('setActiveModule function is not available globally.');
                    alert('Could not switch to OCR Tax Return module automatically.');
                    return;
                }

                // 2. Get job details to find filename and form type
                const jobDetailsResponse = await fetch(`/api/jobs/${result.job_id}`);
                if (!jobDetailsResponse.ok) throw new Error('Failed to fetch job details for auto-start.');
                const jobData = await jobDetailsResponse.json();
                const fileName = jobData.filename;
                const formType = jobData.form_type;

                // 2.5. Automatically run page detection
                console.log(`[ClientTable] Auto-detecting pages for Job ID: ${result.job_id}`);
                
                if (typeof showDetectionModal === 'function') {
                    showDetectionModal('Analyzing PDF document with OCR to automatically detect page numbers...');
                }

                const detectFormData = new FormData();
                detectFormData.append('form_type', formType);
                const detectResponse = await fetch(`/api/jobs/${result.job_id}/detect-pages`, {
                    method: 'POST',
                    body: detectFormData
                });

                if (!detectResponse.ok) {
                    console.warn('Auto-detection of pages failed, the user will need to do it manually.');
                }

                if (typeof hideDetectionModal === 'function') {
                    hideDetectionModal();
                }

                // 3. Start the OCR flow with the new job
                if (window.ocrTaxReturnMgr && typeof window.ocrTaxReturnMgr.startJobWithId === 'function') {
                    await window.ocrTaxReturnMgr.startJobWithId(result.job_id, formType, fileName);
                } else {
                    console.error('ocrTaxReturnMgr or startJobWithId method not found.');
                    alert('Could not start the OCR flow automatically.');
                }
            } else {
                alert(result.message || 'Process started but no job ID was returned.');
            }
        } catch (error) {
            console.error('Error triggering OCR:', error);
            if (typeof hideDetectionModal === 'function') {
                hideDetectionModal();

            }
            alert('Failed to trigger process: ' + error.message);
        } finally {
            // Re-enable all buttons
            allButtons.forEach(btn => btn.disabled = false);
            
            if (button) {
                originalText.textContent = 'Extract Final Tax Return Data';
                spinner.classList.add('hidden');
            }
        }
    }

    handleSelectAll(isChecked) {
        // Select/deselect all visible (filtered) clients
        this.filteredClients.forEach(client => {
            const id = client['Taxpayer ID'] || '';
            if (id) {
                if (isChecked) {
                    this.selectedClientIds.add(id);
                } else {
                    this.selectedClientIds.delete(id);
                }
            }
        });
        this.renderTable(); // Re-render table to show checked state
    }

    handleItemSelect(clientId, isChecked) {
        if (isChecked) {
            this.selectedClientIds.add(clientId);
        } else {
            this.selectedClientIds.delete(clientId);
        }
        this.updateSelectAllCheckboxState();
    }

    updateSelectAllCheckboxState() {
        const selectAllCheckbox = document.getElementById(this.config.ids.selectAll);
        if (!selectAllCheckbox) return;

        if (this.filteredClients.length === 0) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
            return;
        }

        let selectedCountInFilter = 0;
        this.filteredClients.forEach(client => {
            const id = client['Taxpayer ID'] || '';
            if (id && this.selectedClientIds.has(id)) {
                selectedCountInFilter++;
            }
        });

        selectAllCheckbox.checked = selectedCountInFilter > 0 && selectedCountInFilter === this.filteredClients.length;
        selectAllCheckbox.indeterminate = selectedCountInFilter > 0 && selectedCountInFilter < this.filteredClients.length;

    }

    goToPage(page) {
        const totalPages = this.getTotalPages();
        if (page >= 1 && page <= totalPages) {
            this.currentPage = page;
            this.render();
            // Scroll to table
            document.getElementById(this.config.ids.tableBody)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }


    getReturnTypeClass(type) {
        if (!type) return '1099';
        const t = type.toString().toLowerCase();
        if (t.includes('1040')) return '1040';
        if (t.includes('1065')) return '1065';
        if (t.includes('1120s')) return '1120s';
        if (t.includes('1120')) return '1120';
        if (t.includes('w2')) return 'w2';
        if (t.includes('1099') || t.includes('1099-')) return '1099';
        return '1099';
    }

    updateLocalStatus(clientId, field, value) {
        const client = this.allClients.find(c => String(c['Taxpayer ID']).trim() === clientId);
        if (client) {
            client[field] = value;
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async updateLoadTime() {
        try {
            const metaResponse = await fetch('/api/drake/file-metadata');
            const metadata = await metaResponse.json();

            if (metadata.exists) {
                this.lastLoadTime = metadata.timestamp;

                const timeEl = document.getElementById(this.config.ids.loadTime);
                if (timeEl) {
                    timeEl.innerHTML = `
                        <i class="bi bi-clock me-1"></i>
                        Loaded: ${metadata.timestamp}
                    `;
                    timeEl.style.display = 'inline';
                }
            }
        } catch (err) {
            console.warn('[ClientTable] Failed to update load time', err);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Assign to window explicitly so other modules (like OCR) can access it
    // 1. Original Module (OCR)
    window.clientTableMgr = new ClientTableManager({
        instanceName: 'clientTableMgr',
        showActions: true,
        showEF: false,
        showOCR: true,
        showSelectCheckbox: false
    });
});
