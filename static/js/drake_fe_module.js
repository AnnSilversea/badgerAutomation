/**
 * Drake File Extension Module Logic
 * Handles querying Karbon for items needing extension and processing them in Drake.
 */

class DrakeFEManager {
    constructor(config) {
        this.config = Object.assign({
            instanceName: 'drakeFEMgr',
            ids: {
                searchInput: 'drakeFESearchInput',
                selectAll: 'drakeFESelectAll',
                tableBody: 'drakeFETableBody',
                pagination: 'drakeFEPagination',
                paginationInfo: 'drakeFEPaginationInfo',
                statusInfo: 'drakeFEStatusInfo',
                recordCount: 'drakeFERecordCount',
                filterInfo: 'drakeFEFilterInfo',
                filteredCount: 'drakeFEFilteredCount',
                loadTime: 'drakeFELoadTime',
                processBtn: 'drakeFEProcessBtn',
                resultPanel: 'drakeFEResult',
                summaryPanel: 'drakeFESummary',
                detailsPanel: 'drakeFEDetails',
                closeBtn: 'drakeFECloseBtn',
                queryBtn: 'drakeFEQueryBtn'
            }
        }, config);

        this.allWorkItems = [];
        this.filteredWorkItems = [];
        this.currentPage = 1;
        this.itemsPerPage = 15;
        this.searchTerm = '';
        this.selectedClientIds = new Set();
        this.isProcessing = false;
        
        this.init();
    }

    init() {
        const searchInput = document.getElementById(this.config.ids.searchInput);
        if (searchInput) {
            searchInput.addEventListener('input', (e) => this.handleSearch(e.target.value));
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

        const processBtn = document.getElementById(this.config.ids.processBtn);
        if (processBtn) {
            processBtn.addEventListener('click', () => this.handleBatchEF());
        }

        const closeBtn = document.getElementById(this.config.ids.closeBtn);
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                const panel = document.getElementById(this.config.ids.resultPanel);
                if (panel) panel.hidden = true;
            });
        }

        const queryBtn = document.getElementById(this.config.ids.queryBtn);
        if (queryBtn) {
            queryBtn.addEventListener('click', () => this.queryKarbon());
        }
    }

    async queryKarbon() {
        const queryBtn = document.getElementById(this.config.ids.queryBtn);
        if (!queryBtn) return;

        const originalText = queryBtn.innerHTML;
        queryBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Querying...';
        queryBtn.disabled = true;

        const infoEl = document.getElementById(this.config.ids.statusInfo);
        if (infoEl) { infoEl.innerHTML = ''; infoEl.style.display = 'none'; }

        try {
            const response = await fetch('/api/karbon/fi/workitems?work_status=Extension Needed');
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to query Karbon.');
            }
            const workItems = await response.json();
            this.setWorkItems(workItems);
            this.updateLoadTime();

        } catch (error) {
            console.error('Error querying Karbon for EF:', error);
            const errorHtml = `<strong style="color: #dc3545;">❌ Error:</strong> ${this.escapeHtml(error.message)}`;
            if (infoEl) { infoEl.innerHTML = errorHtml; infoEl.style.display = 'block'; }
        } finally {
            if (queryBtn) { queryBtn.innerHTML = originalText; queryBtn.disabled = false; }
        }
    }

    setWorkItems(workItems) {
        this.allWorkItems = (workItems || []).map(item => ({
            ...item,
            efStatus: 'N/A' // Initial status
        }));
        this.filteredWorkItems = [...this.allWorkItems];
        this.currentPage = 1;
        this.selectedClientIds.clear();
        this.updateRecordCount();
        this.render();
    }

    handleSearch(term) {
        this.searchTerm = term.toLowerCase().trim();
        this.currentPage = 1;

        if (!this.searchTerm) {
            this.filteredWorkItems = [...this.allWorkItems];
            document.getElementById(this.config.ids.filterInfo).style.display = 'none';
        } else {
            this.filteredWorkItems = this.allWorkItems.filter(item => {
                const id = (item.registrationNumber || '').toString().toLowerCase();
                const name = (item.clientName || '').toLowerCase();
                const type = (item.clientType || '').toLowerCase();
                
                return id.includes(this.searchTerm) || 
                       name.includes(this.searchTerm) || 
                       type.includes(this.searchTerm);
            });
            
            const filterInfo = document.getElementById(this.config.ids.filterInfo);
            if (filterInfo) {
                filterInfo.style.display = 'inline';
                document.getElementById(this.config.ids.filteredCount).textContent = this.filteredWorkItems.length;
            }
        }

        this.render();
    }

    updateRecordCount() {
        const countEl = document.getElementById(this.config.ids.recordCount);
        if (countEl) {
            countEl.textContent = this.allWorkItems.length;
        }
    }

    getPagedItems() {
        const start = (this.currentPage - 1) * this.itemsPerPage;
        const end = start + this.itemsPerPage;
        return this.filteredWorkItems.slice(start, end);
    }

    getTotalPages() {
        return Math.ceil(this.filteredWorkItems.length / this.itemsPerPage);
    }

    render() {
        this.renderTable();
        this.renderPagination();
    }

    renderTable() {
        const tbody = document.getElementById(this.config.ids.tableBody);
        if (!tbody) return;

        const pagedItems = this.getPagedItems();
        const colspan = 9;

        if (pagedItems.length === 0) {
            tbody.innerHTML = `
                <tr class="empty-state">
                    <td colspan="${colspan}">
                        <div style="padding: 40px 20px; text-align: center; color: #6c757d;">
                            <i class="bi bi-inbox" style="font-size: 2.5em; opacity: 0.5; display: block; margin-bottom: 12px;"></i>
                            ${this.searchTerm ? 
                                `<div>No results found for "<strong>${this.escapeHtml(this.searchTerm)}</strong>"</div>` 
                                : `<div>Click <strong>"Query Karbon"</strong> to load client data</div>`
                            }
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = pagedItems.map(item => {
            const efStatus = item.efStatus || 'N/A';
            const workItemKey= item.workItemKey || 'N/A';
            const lastUpdated = item._lastUpdated || '';

            let statusBadgeClass;

            if (efStatus === 'Success') statusBadgeClass = 'bg-success';
            else if (efStatus === 'Fail') statusBadgeClass = 'bg-danger';

            else if (efStatus === 'Start') statusBadgeClass = 'bg-primary';
            else if (efStatus === 'Queue') statusBadgeClass = 'bg-warning text-dark';
            else statusBadgeClass = 'bg-secondary';

            const statusText = (efStatus === 'Start') ? 'Started' : this.escapeHtml(efStatus);
            const efStatusHtmlCell = `<td style="text-align: center;"><span class="badge ${statusBadgeClass}">${statusText}</span></td>`;

            const clientId = item.registrationNumber || '';
            const isChecked = this.selectedClientIds.has(clientId);
            const isDisabled = !clientId
            

            const checkboxHtml = `
                <td class="text-center" style="vertical-align: middle;">
                    <input class="form-check-input client-item-checkbox" type="checkbox" value="${this.escapeHtml(clientId)}" ${isChecked ? 'checked' : ''} ${isDisabled ? 'disabled' : ''}>
                </td>`;

            return `
                <tr>
                    ${checkboxHtml}
                    <td class="text-center">${this.escapeHtml(clientId)}</td>
                    <td style="vertical-align: middle;">${this.escapeHtml(item.clientName || '')}</td>
                    <td style="text-align:center; vertical-align: middle;">${this.escapeHtml(item.clientType || 'N/A')}</td>
                    <td style="text-align:center; vertical-align: middle;">${this.escapeHtml(item.assigneeName || '')}</td>
                    <td style="text-align:center; vertical-align: middle;">${this.escapeHtml(item.workStatus || '')}</td>
                    <td style="text-align:center; vertical-align: middle;"><a href="https://app2.karbonhq.com/#/work/${this.escapeHtml(item.workItemKey)}" target="_blank">Link</a></td>
                    ${efStatusHtmlCell}
                     <td style="text-align:center; vertical-align: middle;">${lastUpdated}</td>
                </tr>
            `;
        }).join('');
        this.updateSelectAllCheckboxState();
    }

    renderPagination() {
        const totalPages = this.getTotalPages();
        const paginationEl = document.getElementById(this.config.ids.pagination);
        const paginationInfo = document.getElementById(this.config.ids.paginationInfo);

        if (!paginationEl || !paginationInfo) return;

        if (this.filteredWorkItems.length === 0) {
            paginationInfo.textContent = '';
            paginationEl.innerHTML = '';
            return;
        }

        const start = (this.currentPage - 1) * this.itemsPerPage + 1;
        const end = Math.min(this.currentPage * this.itemsPerPage, this.filteredWorkItems.length);
        paginationInfo.textContent = `Showing ${start} to ${end} of ${this.filteredWorkItems.length}`;

        if (totalPages <= 1) {
            paginationEl.innerHTML = '';
            return;
        }

        let html = '';
        html += `<li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}"><a class="page-link" href="#" onclick="${this.config.instanceName}.goToPage(${this.currentPage - 1}); return false;">← Previous</a></li>`;
        
        const maxVisible = 5;
        let startPage = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
        let endPage = Math.min(totalPages, startPage + maxVisible - 1);
        if (endPage - startPage + 1 < maxVisible) {
            startPage = Math.max(1, endPage - maxVisible + 1);
        }
        if (startPage > 1) {
            html += `<li class="page-item"><a class="page-link" href="#" onclick="${this.config.instanceName}.goToPage(1); return false;">1</a></li>`;
            if (startPage > 2) html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
        }
        for (let i = startPage; i <= endPage; i++) {
            html += `<li class="page-item ${i === this.currentPage ? 'active' : ''}"><a class="page-link" href="#" onclick="${this.config.instanceName}.goToPage(${i}); return false;">${i}</a></li>`;
        }
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            html += `<li class="page-item"><a class="page-link" href="#" onclick="${this.config.instanceName}.goToPage(${totalPages}); return false;">${totalPages}</a></li>`;
        }
        
        html += `<li class="page-item ${this.currentPage === totalPages ? 'disabled' : ''}"><a class="page-link" href="#" onclick="${this.config.instanceName}.goToPage(${this.currentPage + 1}); return false;">Next →</a></li>`;
        paginationEl.innerHTML = html;
    }

    async handleBatchEF() {
        const selectedIds = Array.from(this.selectedClientIds);
        if (selectedIds.length === 0 || this.isProcessing) return;
        this.isProcessing = true;

        const btn = document.getElementById(this.config.ids.processBtn);
        const originalText = btn ? btn.innerHTML : '';
        if (btn) {
            btn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Preparing...`;
            btn.disabled = true;
        }

        selectedIds.forEach((id, index) => this.updateLocalStatus(id, 'efStatus', index === 0 ? 'Start' : 'Queue'));
        this.render();
        await new Promise(r => setTimeout(r, 500));

        this.showProcessResult({
            type: 'info',
            summaryHtml: `Starting processing for <b>${selectedIds.length}</b> clients...`,
            detailsHtml: ''
        });

        let successCount = 0;
        let failCount = 0;
        const batchDetails = [];
        let sendSummary = true;

        try {
            for (let i = 0; i < selectedIds.length; i++) {
                const clientId = selectedIds[i];
                if (btn) btn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Processing ${i + 1}/${selectedIds.length}...`;
                
                const clientObj = this.allWorkItems.find(c => String(c.registrationNumber || '').trim() === String(clientId || '').trim());
                const clientName = clientObj ? clientObj.clientName : '';

                this.updateLocalStatus(clientId, 'efStatus', 'Start');
                this.render();
                await new Promise(r => setTimeout(r, 50));

                try {
                    const doOpen = (i === 0);
                    const doClose = (i === selectedIds.length - 1);

                    const selectResponse = await fetch('/api/drake/efile/select-clients', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ 
                            client_ids: [clientId],
                            open: doOpen,
                            close: doClose
                        })
                    });
                    const data = await selectResponse.json();
                    if (!selectResponse.ok) {
                        if (selectResponse.status === 408) sendSummary = false;
                        throw new Error(data.detail || `Failed to select client ${clientId}`);
                    }

                    const clientStatus = data?.client_status || 'Unknown';
                    if (clientStatus === 'Success') {
                        this.updateLocalStatus(clientId, 'efStatus', 'Success');
                        this.updateLocalStatus(clientId, '_lastUpdated', new Date().toLocaleString());
                        successCount++;
                        batchDetails.push({ clientId, clientName, status: 'Success', message: clientStatus });
                        this.appendProcessDetail(clientId, clientName, clientStatus, 'success');
                    } else {
                        this.updateLocalStatus(clientId, 'efStatus', 'Fail');
                        failCount++;
                        batchDetails.push({ clientId, clientName, status: 'Fail', message: clientStatus });
                        this.appendProcessDetail(clientId, clientName, clientStatus, 'danger');
                    }
                } catch (err) {
                    this.updateLocalStatus(clientId, 'efStatus', 'Fail');
                    failCount++;
                    let cleanErrMsg = err.message.replace(/Screenshot saved at:.*$/i, '').trim();
                    batchDetails.push({ clientId, clientName, status: 'Fail', message: cleanErrMsg });
                    this.appendProcessDetail(clientId, clientName, cleanErrMsg, 'danger');

                    if (cleanErrMsg.includes("Prepare Extensions") && cleanErrMsg.includes("Could not activate menu item")) {
                        sendSummary = false;
                        for (let j = i + 1; j < selectedIds.length; j++) {
                            const rId = selectedIds[j];
                            const rClient = this.allWorkItems.find(c => String(c.registrationNumber || '').trim() === String(rId || '').trim());
                            const rName = rClient ? rClient.clientName : '';
                            
                            this.updateLocalStatus(rId, 'efStatus', 'Fail');
                            failCount++;
                            const msg = "Batch stopped: Critical error (Prepare Extensions menu inaccessible)";
                            batchDetails.push({ clientId: rId, clientName: rName, status: 'Fail', message: msg });
                            this.appendProcessDetail(rId, rName, msg, 'danger');
                        }
                        break;
                    }

                    if (!sendSummary) throw err;
                }
                this.render();
                this.showProcessResult({
                    type: 'info',
                    summaryHtml: `Processed: <b>${successCount + failCount}/${selectedIds.length}</b> | Success: <b class="text-success">${successCount}</b> | Failed: <b class="text-danger">${failCount}</b>`
                });
            }
        } catch (error) {
            let cleanMsg = error.message.replace(/Screenshot saved at:.*$/i, '').trim();
            selectedIds.forEach(id => {
                const client = this.allWorkItems.find(c => String(c.registrationNumber || '').trim() === String(id || '').trim());
                if (client && client.efStatus !== 'Success' && client.efStatus !== 'Fail') {
                    this.updateLocalStatus(id, 'efStatus', 'Fail');
                    failCount++;
                    this.appendProcessDetail(id, client.clientName, `Batch stopped: ${cleanMsg}`, 'danger');
                    batchDetails.push({ clientId: id, clientName: client.clientName, status: 'Fail', message: `Batch stopped: ${cleanMsg}` });
                }
            });
            this.showProcessResult({ type: 'danger', summaryHtml: `Batch Process Error: ${cleanMsg}` });
        } finally {
            this.isProcessing = false;
            this.selectedClientIds.clear();
            this.render();
            if (btn) btn.innerHTML = originalText;

            let finalType = 'success';
            if (failCount > 0) finalType = (failCount === selectedIds.length) ? 'danger' : 'warning';
            this.showProcessResult({
                type: finalType,
                summaryHtml: `<b>Completed.</b> Total: ${selectedIds.length} | Success: <b class="text-success">${successCount}</b> | Failed: <b class="text-danger">${failCount}</b>`
            });

            if (sendSummary) {
                try {
                    await fetch('/api/drake/efile/send-summary', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            totals: { success: successCount, failed: failCount, total: selectedIds.length },
                            details: batchDetails
                        })
                    });
                } catch (emailError) { console.warn('Failed to send EF Batch summary email:', emailError); }
            }
        }
    }

    showProcessResult({ type = "info", summaryHtml = null, detailsHtml = null }) {
        const resultBox = document.getElementById(this.config.ids.resultPanel);
        const resultSummary = document.getElementById(this.config.ids.summaryPanel);
        const resultDetails = document.getElementById(this.config.ids.detailsPanel);
        
        if (!resultBox) return;

        resultBox.hidden = false;
        resultBox.classList.remove('alert-success', 'alert-warning', 'alert-danger', 'alert-info');
        resultBox.classList.add(`alert-${type}`);

        if (resultSummary && summaryHtml !== null) resultSummary.innerHTML = summaryHtml;
        if (resultDetails && detailsHtml !== null) resultDetails.innerHTML = detailsHtml;
    }

    appendProcessDetail(clientId, clientName, message, type) {
        const resultDetails = document.getElementById(this.config.ids.detailsPanel);
        if (resultDetails) {
            const div = document.createElement('div');
            div.className = 'd-flex justify-content-between border-bottom py-1';
            const nameHtml = clientName ? ` <span class="text-muted small">(${this.escapeHtml(clientName)})</span>` : '';

            div.innerHTML = `
                <div class="me-2"><b>${this.escapeHtml(clientId)}</b>${nameHtml}</div>
                <div>
                    <span class="badge bg-${type}">
                        ${type === 'success' ? 'Success' : 'Failed'}
                    </span> 
                    ${type !== 'success' 
                        ? `<span class="text-muted small ms-1">${this.escapeHtml(message)}</span>` 
                        : ''
                    }
                </div>
            `;
            resultDetails.appendChild(div);
            resultDetails.scrollTop = resultDetails.scrollHeight;
        }
    }

    handleSelectAll(isChecked) {
        this.filteredWorkItems.forEach(item => {
            const id = item.registrationNumber || '';
            if (id) {
                if (isChecked) this.selectedClientIds.add(id);
                else this.selectedClientIds.delete(id);
            }
        });
        this.renderTable();
    }

    handleItemSelect(clientId, isChecked) {
        if (isChecked) this.selectedClientIds.add(clientId);
        else this.selectedClientIds.delete(clientId);
        this.updateSelectAllCheckboxState();
    }

    updateSelectAllCheckboxState() {
        const selectAllCheckbox = document.getElementById(this.config.ids.selectAll);
        if (!selectAllCheckbox) return;

        if (this.filteredWorkItems.length === 0) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
            return;
        }

        let selectedCountInFilter = 0;
        this.filteredWorkItems.forEach(item => {
            const id = item.registrationNumber || '';
            if (id && this.selectedClientIds.has(id)) {
                selectedCountInFilter++;
            }
        });

        selectAllCheckbox.checked = selectedCountInFilter > 0 && selectedCountInFilter === this.filteredWorkItems.length;
        selectAllCheckbox.indeterminate = selectedCountInFilter > 0 && selectedCountInFilter < this.filteredWorkItems.length;

        const processBtn = document.getElementById(this.config.ids.processBtn);
        if (processBtn) {
            processBtn.disabled = this.isProcessing || this.selectedClientIds.size === 0;
        }
    }

    goToPage(page) {
        const totalPages = this.getTotalPages();
        if (page >= 1 && page <= totalPages) {
            this.currentPage = page;
            this.render();
            document.getElementById(this.config.ids.tableBody)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    updateLocalStatus(clientId, field, value) {
        const client = this.allWorkItems.find(c => String(c.registrationNumber).trim() === clientId);
        if (client) {
            client[field] = value;
        }
    }

    escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async updateLoadTime() {
        // For Karbon, we can just use current time
        const timeEl = document.getElementById(this.config.ids.loadTime);
        if (timeEl) {
            const now = new Date();
            timeEl.innerHTML = `<i class="bi bi-clock me-1"></i> Loaded: ${now.toLocaleString()}`;
            timeEl.style.display = 'inline';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.drakeFEMgr = new DrakeFEManager();
});