/**
 * OCR Tax Return Module Logic
 * Handles the flow for the new OCR Tax Return module (ocr_ IDs)
 */

class OCRTaxReturnManager {
    constructor() {
        this.jobId = null;
        this.clientId = null;
        this.selectedFormType = null;
        this.uploadedFileName = null;
        this.pageGroupsConfig = [];
        this.selectedGroups = {};
        
        this.init();
    }

    init() {
        // Process Button
        const processBtn = document.getElementById('ocr_processBtn');
        if (processBtn) processBtn.addEventListener('click', () => this.handleProcess());

        // Step 4: Export Buttons
        const exportCsvBtn = document.getElementById('ocr_exportCsvBtn');
        const downloadJsonBtn = document.getElementById('ocr_downloadJsonBtn');
        
        if (exportCsvBtn) {
            exportCsvBtn.addEventListener('click', () => this.exportExcel());
        }
        if (downloadJsonBtn) {
            downloadJsonBtn.addEventListener('click', () => this.downloadJson());
        }
    }

    async startJobWithId(jobId, formType, fileName) {
        console.log(`[OCR Tax Return] Starting job from external trigger. Job ID: ${jobId}, Form Type: ${formType}`);

        // 1. Reset the UI to a clean state
        this.resetState();

        // 2. Set internal state
        this.jobId = jobId;
        // this.clientId will be set from job details
        this.selectedFormType = formType;
        this.uploadedFileName = fileName;

        // 4. Fetch job details to get page count
        let pageCount = 0;
        let detectedGroups = null;
        try {
            const response = await fetch(`/api/jobs/${jobId}`);
            if (!response.ok) throw new Error('Failed to fetch job details');
            const jobData = await response.json();
            pageCount = jobData.page_count || 0;
            detectedGroups = jobData.detected_groups || null;
            this.clientId = jobData.client_id || null;
            if (this.clientId) {
                console.log(`[OCR Tax Return] Associated Client ID: ${this.clientId}`);
            } else {
                console.warn(`[OCR Tax Return] No Client ID found for job ${jobId}. Status update will not occur.`);
            }
        } catch (error) {
            console.error('Error fetching job details for auto-start:', error);
            alert('Could not retrieve job details to start the OCR flow.');
            return;
        }

        // 5. Update UI (Simplified View)
        const statusPanel = document.getElementById('ocr_jobStatusPanel');
        if (statusPanel) {
            // Hide the file name and page count panel to keep the UI clean
            statusPanel.style.display = 'none';
        }

        // Hidden fields for logic
        const pageCountEl = document.getElementById('ocr_pageCount');
        const maxPageEl = document.getElementById('ocr_maxPage');
        if (pageCountEl) pageCountEl.textContent = pageCount;
        if (maxPageEl) maxPageEl.textContent = pageCount;

        // 6. Fetch page groups and render inputs for Step 3
        await this.fetchPageGroups(formType);
        this.renderPageGroupsInputs(detectedGroups);

        // 8. Auto-process if groups are selected (Step 4)
        if (Object.keys(this.selectedGroups).length > 0) {
                        
            // Hide config section to skip the "preview" step visually
            const configSection = document.getElementById('ocr_configSection');
            if (configSection) configSection.style.display = 'none';

            setTimeout(() => this.handleProcess(), 500);
        }
    }

    async fetchPageGroups(formType) {
        try {
            const response = await fetch(`/api/forms/${formType}/page-groups`);
            if (response.ok) {
                const data = await response.json();
                this.pageGroupsConfig = data.page_groups || [];
            }
        } catch (error) {
            console.error('Error fetching page groups:', error);
        }
    }

    renderPageGroupsInputs(detectedGroups = null) {
        const container = document.getElementById('ocr_pageGroupsList');
        if (!container) return;
        
        container.innerHTML = '';
        this.selectedGroups = {}; // Reset selections

        if (this.pageGroupsConfig.length === 0) {
            container.innerHTML = '<div class="alert alert-warning">No page groups configured for this form type.</div>';
            return;
        }

        // Get max page from UI for validation
        const maxPageEl = document.getElementById('ocr_maxPage');
        const maxPage = parseInt(maxPageEl ? maxPageEl.textContent : '0') || 999;

        this.pageGroupsConfig.forEach(group => {
            const div = document.createElement('div');
            div.className = 'page-group-input-card'; // Use shared CSS class for consistent look
            div.dataset.groupName = group.name;
            
            // Determine input type based on form logic (similar to ui.js)
            let needsRange = false;
            const formType = this.selectedFormType ? this.selectedFormType.toLowerCase() : '';
            
            if (formType === '1120' || formType === '1065') {
                needsRange = false;
            } else if (formType === '1120s') {
                needsRange = group.display_name === 'Form 1120S';
            } else {
                needsRange = group.pages && group.pages.length > 1 && 
                            group.display_name !== 'Schedule L' && 
                            group.display_name !== 'Schedule M';
            }
            
            // Determine pages to use: detected > default
            const detectedPages = detectedGroups && detectedGroups[group.name] 
                ? detectedGroups[group.name] 
                : null;
            
            const pages = detectedPages || group.pages || [];
            const displayPages = pages.map(p => p + 1).sort((a, b) => a - b);
            const isAutoDetected = detectedPages !== null && detectedPages.length > 0;

            const autoDetectedBadge = isAutoDetected 
                ? '<span class="badge bg-success ms-2" style="font-size: 0.7em;">✓ Auto-Detected</span>' 
                : '';

            let inputHTML = '';
            if (needsRange) {
                inputHTML = `
                    <div class="page-input-group">
                        <label class="page-input-label">Start Page</label>
                        <input type="number" class="page-input-field ocr-page-input" 
                               data-group="${group.name}" data-type="start"
                               min="1" max="${maxPage}" 
                               placeholder="1" 
                               value="${displayPages.length > 0 ? displayPages[0] : ''}">
                    </div>
                    <div class="page-input-group">
                        <label class="page-input-label">End Page</label>
                        <input type="number" class="page-input-field ocr-page-input" 
                               data-group="${group.name}" data-type="end"
                               min="1" max="${maxPage}" 
                               placeholder="1" 
                               value="${displayPages.length > 0 ? displayPages[displayPages.length - 1] : ''}">
                    </div>
                `;
            } else {
                inputHTML = `
                    <div class="page-input-group">
                        <label class="page-input-label">Page Number</label>
                        <input type="number" class="page-input-field ocr-page-input" 
                               data-group="${group.name}" data-type="single"
                               min="1" max="${maxPage}" 
                               placeholder="1" 
                               value="${displayPages.length > 0 ? displayPages[0] : ''}">
                    </div>
                `;
            }

            div.innerHTML = `
                <div class="page-group-input-header">
                    <div>
                        <div class="page-group-input-title">${group.display_name || group.name}${autoDetectedBadge}</div>
                        <div class="page-group-input-description">
                            ${needsRange ? 'Enter start and end page numbers' : 'Enter page number'}
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

            // Add listeners
            div.querySelectorAll('input').forEach(input => {
                input.addEventListener('input', () => this.handlePageInputChange(group.name, div, needsRange));
                input.addEventListener('change', () => this.handlePageInputChange(group.name, div, needsRange));
            });

            container.appendChild(div);
            
            // Initialize selection state if defaults exist
            if (pages.length > 0) {
                this.handlePageInputChange(group.name, div, needsRange);
            }
        });
        
        this.updateProcessButton();
    }

    handlePageInputChange(groupName, card, needsRange) {
        let pages = [];
        
        if (needsRange) {
            const startInput = card.querySelector('[data-type="start"]');
            const endInput = card.querySelector('[data-type="end"]');
            const start = parseInt(startInput.value);
            const end = parseInt(endInput.value);
            
            if (!isNaN(start) && !isNaN(end) && start <= end && start >= 1) {
                // Generate range (0-based)
                for (let i = start; i <= end; i++) pages.push(i - 1);
            }
        } else {
            const input = card.querySelector('[data-type="single"]');
            const val = parseInt(input.value);
            if (!isNaN(val) && val >= 1) {
                pages.push(val - 1); // 0-based
            }
        }

        if (pages.length > 0) {
            this.selectedGroups[groupName] = pages;
            card.classList.add('has-value');
            // Show preview for this specific group
            const displayPages = pages.map(p => p + 1);
            this.updateGroupPreview(groupName, pages, card, displayPages);
        } else {
            delete this.selectedGroups[groupName];
            card.classList.remove('has-value');
            this.hideGroupPreview(card);
        }
        
        this.updateProcessButton();
    }

    updateProcessButton() {
        const btn = document.getElementById('ocr_processBtn');
        if (btn) {
            btn.disabled = Object.keys(this.selectedGroups).length === 0;
        }
    }

    updateGroupPreview(groupName, pages, card, displayPages = null) {
        const previewContainer = card.querySelector(`[data-preview-group="${groupName}"]`);
        const previewLoading = previewContainer?.querySelector('.page-group-preview-loading');
        const previewContent = previewContainer?.querySelector('.page-group-preview-content');
        
        if (!previewContainer) return;
        
        // Show preview container
        previewContainer.style.display = 'block';
        if (previewLoading) previewLoading.style.display = 'block';
        if (previewContent) previewContent.style.display = 'none';
        
        const groupInfo = this.pageGroupsConfig.find(g => g.name === groupName);
        const displayName = groupInfo?.display_name || groupName;
        const previewUrl = `/api/jobs/${this.jobId}/preview-group/${groupName}?pages=${encodeURIComponent(JSON.stringify(pages))}`;
        
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

    hideGroupPreview(card) {
        const previewContainer = card.querySelector('.page-group-preview-container');
        if (previewContainer) {
            previewContainer.style.display = 'none';
        }
    }

    async handleProcess() {
        if (Object.keys(this.selectedGroups).length === 0) {
            alert('Please enter at least one page number to process.');
            return;
        }

        const resultsSection = document.getElementById('ocr_resultsSection');
        if (resultsSection) resultsSection.style.display = 'block';
        
        const statusEl = document.getElementById('ocr_processingStatus');
        const resultsView = document.getElementById('ocr_resultsView');
        
        if (statusEl) {
            statusEl.classList.remove('hidden');
            statusEl.innerHTML = '<div class="spinner"></div><p class="mt-2">Processing document... This may take a minute.</p>';
        }
        if (resultsView) resultsView.classList.add('hidden');


        try {
            const formData = new FormData();
            formData.append('form_type', this.selectedFormType);
            formData.append('selected_groups', JSON.stringify(this.selectedGroups));

            const response = await fetch(`/api/jobs/${this.jobId}/process-groups`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Processing start failed');

            // Start polling
            this.pollResults();

        } catch (error) {
            console.error('Process error:', error);
            if (statusEl) statusEl.innerHTML = `<div class="status-message status-error">Error: ${error.message}</div>`;
        }
    }

    async pollResults() {
        const jobId = this.jobId;
        const clientId = this.clientId;

        const pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/jobs/${jobId}`);
                if (response.ok) {
                    const job = await response.json();
                    
                    if (job.status === 'completed') {
                        clearInterval(pollInterval);
                        this.renderResults(jobId, clientId);
                    } else if (job.status === 'failed') {
                        clearInterval(pollInterval);
                        const statusEl = document.getElementById('ocr_processingStatus');
                        if (statusEl) statusEl.innerHTML = `<div class="status-message status-error">Job Failed: ${job.error}</div>`;
                        if (clientId && window.clientTableMgr) {
                            window.clientTableMgr.updateStatus(clientId, 'ocr', 'Extracted Fail');
                        }
                    }
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 2000);
    }

    async renderResults(jobId, clientId) {
        const statusEl = document.getElementById('ocr_processingStatus');
        const resultsView = document.getElementById('ocr_resultsView');
        const container = document.getElementById('ocr_accordionContainer');

        // Update the instance's current job ID so that export buttons work correctly.
        this.jobId = jobId;
        this.clientId = clientId;

        try {
            const response = await fetch(`/api/jobs/${jobId}/results/with-bounding-boxes`);
            if (!response.ok) {
                throw new Error(`Failed to fetch results: ${response.status}`);
            }
            const data = await response.json();

            if (statusEl) statusEl.classList.add('hidden');
            if (resultsView) resultsView.classList.remove('hidden');
            if (container) container.innerHTML = ''; // Clear previous results

            if (!data.results || Object.keys(data.results).length === 0) {
                if (container) container.innerHTML = '<div class="alert alert-warning">No results found to display.</div>';
                return;
            }

            // Pre-generate Excel file in the background
            try {
                await fetch(`/api/jobs/${jobId}/excel`);
            } catch (excelError) {
                console.warn('Could not pre-generate Excel file:', excelError);
            }
            const excelViewUrl = `/api/jobs/${jobId}/excel/view`;

            const sections = [];
            let isFirstSection = true;

            // Define sort order for groups (same as in api.js)
            const groupOrder = ['Form_1065', 'Schedule_M_L', 'Schedule_M_L_1120', 'Form_1120'];
            const modelOrder = [
                'Train_model_1065_v4', 'Train_1065_schedule_L_v4', 'Train_1065_schedule_m1_v2', 'Train_1065_schedule_m2_v3',
                'Train_1120_v2', 'Train_1120_schedule_L_v3', 'Train_1120_schedule_M1_v2', 'Train_1120_schedule_M2_v3'
            ];

            const sortedGroups = Object.entries(data.results).sort(([nameA], [nameB]) => {
                const indexA = groupOrder.indexOf(nameA);
                const indexB = groupOrder.indexOf(nameB);
                if (indexA !== -1 && indexB !== -1) return indexA - indexB;
                if (indexA !== -1) return -1;
                if (indexB !== -1) return 1;
                return 0;
            });

            for (const [groupName, groupData] of sortedGroups) {
                if (groupName.startsWith('_')) continue;

                const previewUrl = data.group_previews?.[groupName] || null;
                const sectionTitle = GROUP_DISPLAY_NAMES[groupName] || groupName;

                if (groupData.models) {
                    const sortedModels = Object.entries(groupData.models).sort(([modelIdA], [modelIdB]) => {
                        const indexA = modelOrder.indexOf(modelIdA);
                        const indexB = modelOrder.indexOf(modelIdB);
                        if (indexA !== -1 && indexB !== -1) return indexA - indexB;
                        if (indexA !== -1) return -1;
                        if (indexB !== -1) return 1;
                        return 0;
                    });

                    for (const [modelId, modelData] of sortedModels) {
                        if (modelData && modelData.fields) {
                            const modelTitle = MODEL_DISPLAY_NAMES[modelId] || modelId;
                            const section = createAccordionSection(modelTitle, previewUrl, excelViewUrl, modelTitle, isFirstSection);
                            sections.push(section);
                            isFirstSection = false;
                        }
                    }
                } else if (groupData.fields) {
                    const section = createAccordionSection(sectionTitle, previewUrl, excelViewUrl, sectionTitle, isFirstSection);
                    sections.push(section);
                    isFirstSection = false;
                }
            }

            if (container) {
                if (sections.length === 0) {
                    container.innerHTML = '<div class="alert alert-info">No data sections found in results.</div>';
                } else {
                    sections.forEach(section => container.appendChild(section));
                    if (typeof setupAccordionHandlers === 'function') {
                        setupAccordionHandlers();
                    }
                }
            }

            if (clientId && window.clientTableMgr) {
                console.log(`[OCR Tax Return] Updating status for client ${clientId} in client table.`);
                window.clientTableMgr.updateStatus(clientId, 'ocr', 'Extracted');

                // --- NEW: Send completion email ---
                try {
                    const client = window.clientTableMgr.allClients.find(c => String(c['Taxpayer ID']).trim() === String(clientId).trim());
                    const clientName = client ? client['Taxpayer Name'] : 'Unknown';
                    const formType = this.selectedFormType || 'Unknown';

                    console.log(`[OCR Tax Return] Sending completion email for client ${clientName} (${clientId})`);

                    // The backend will determine the recipient from environment variables.
                    await fetch(`/api/jobs/${jobId}/notify-ocr-completion`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            client_id: clientId,
                            client_name: clientName,
                            form_type: formType,
                        })
                    });
                } catch (emailError) {
                    console.warn('[OCR Tax Return] Failed to send completion email:', emailError);
                    // Don't block the UI for this, just log it.
                }
                // --- END NEW ---
            } else if (clientId) {
                console.warn(`[OCR Tax Return] Could not update client table status. window.clientTableMgr is missing.`);
            }
        } catch (error) {
            console.error('Error fetching results:', error);
            if (container) container.innerHTML = '<div class="alert alert-danger">Failed to load results.</div>';
        }
    }

    exportExcel() {
        if (!this.jobId) return;
        window.location.href = `/api/jobs/${this.jobId}/export/excel`;
    }

    downloadJson() {
        if (!this.jobId) return;
        window.location.href = `/api/jobs/${this.jobId}/export/json`;
    }

    resetState() {
        this.jobId = null;
        this.clientId = null;
        this.selectedFormType = null;
        this.uploadedFileName = null;
        this.pageGroupsConfig = [];
        this.selectedGroups = {};

        // Reset UI
        const statusPanel = document.getElementById('ocr_jobStatusPanel');
        if (statusPanel) statusPanel.style.display = 'none';
        const resultsSection = document.getElementById('ocr_resultsSection');
        if (resultsSection) resultsSection.style.display = 'none';
        const pageGroupsList = document.getElementById('ocr_pageGroupsList');
        if (pageGroupsList) pageGroupsList.innerHTML = '<div class="text-center text-muted py-4 bg-light rounded">No active job. Please start from "Extract Drake Client List".</div>';

        const statusTextEl = document.getElementById('ocr_statusText');
        if (statusTextEl) {
            statusTextEl.style.display = 'none';
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.ocrTaxReturnMgr = new OCRTaxReturnManager();
});
