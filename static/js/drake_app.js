document.addEventListener('DOMContentLoaded', () => {
    const DRAKE_APP_JS_VERSION = 'v7-poll-stop-fix';
    console.log(`[Drake UI] Loaded ${DRAKE_APP_JS_VERSION}`);
    // State for the Drake module
    let drakeJobId = null;
    let drakeSelectedFile = null;
    let drakeResults = null;
    let drakeClientId = null;
    let drakeSelectedGroups = {}; // Store detected/selected groups
    let currentDrakeStep = 1;

    /**
     * Returns a user-friendly name for a given form type code.
     * @param {string} formType - The short code for the form (e.g., "W2", "1099DIV").
     * @returns {string} The full, descriptive name of the form.
     */
    function getFriendlyFormName(formType) {
        const formNames = {
            'DIV': '1099-DIV (Dividends and Distributions)',
            'INT': '1099-INT (Interest Income)',
            '1099': '1099-R (Distributions From Pensions, etc.)',
            'SSA': '1099-SSA (Social Security Benefit)',
            'W2': 'W-2 (Wage and Tax Statement)'
        };
        return formNames[formType] || formType; // Fallback to the code itself
    }

    async function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async function startDrakeLaunchAndWait(payload) {
        const launchResp = await fetch('/api/drake/launch-async', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        let launchData = {};
        try {
            launchData = await launchResp.json();
        } catch (e) {
            launchData = {};
        }

        if (!launchResp.ok) {
            throw new Error(launchData.detail || `Failed to start Drake task (${launchResp.status})`);
        }

        const taskId = launchData.task_id;
        if (!taskId) {
            throw new Error('No task_id returned from launch endpoint.');
        }

        const timeoutMs = 45 * 60 * 1000; // 45 minutes
        const pollMs = 5000;
        const startAt = Date.now();
        let transientErrors = 0;

        while ((Date.now() - startAt) < timeoutMs) {
            let pollResp;
            let pollData;
            try {
                pollResp = await fetch(`/api/drake/tasks/${encodeURIComponent(taskId)}`);
                pollData = await pollResp.json().catch(() => ({}));
            } catch (err) {
                transientErrors++;
                if (transientErrors >= 6) {
                    throw err;
                }
                await sleep(pollMs);
                continue;
            }

            if (!pollResp.ok) {
                transientErrors++;
                if (transientErrors >= 6) {
                    throw new Error(pollData.detail || `Task polling failed (${pollResp.status})`);
                }
                await sleep(pollMs);
                continue;
            }

            transientErrors = 0;
            const status = String(pollData.status || '').trim().toLowerCase();
            if (status === 'success') {
                const result = pollData.result || {};
                if (result && String(result.status || '').trim().toLowerCase() === 'failed') {
                    throw new Error(result.message || 'Drake automation failed.');
                }
                return result;
            }
            if (status === 'failure') {
                throw new Error(pollData.error || 'Drake automation failed.');
            }
            await sleep(pollMs);
        }

        throw new Error('Timed out waiting for Drake automation to finish.');
    }

    // Get all necessary DOM elements for the Drake 2025 module
    const drakeModule = document.getElementById('DrakeAutomationModule');
    if (!drakeModule) return; // Don't run if the module isn't on the page

    // Attempt to widen the parent container to accommodate large tax tables
    try {
        let parent = drakeModule.parentElement;
        // Traverse up to find the main container (Bootstrap .container usually)
        while (parent && parent.tagName !== 'BODY') {
            if (parent.classList.contains('container')) {
                parent.style.maxWidth = '1600px';
                break;
            }
            parent = parent.parentElement;
        }
    } catch (e) {
        console.warn("Could not auto-expand container width:", e);
    }

    // Step Indicators
    const drakeStepIndicators = [
        document.getElementById('drakeStep1'),
        document.getElementById('drakeStep2'),
        document.getElementById('drakeStep3'),
        document.getElementById('drakeStep4')
    ];

    // Step Content
    const drakeStepContents = [
        document.getElementById('drakeStep1Content'),
        document.getElementById('drakeStep2Content'),
        document.getElementById('drakeStep3Content'),
        document.getElementById('drakeStep4Content')
    ];

    // Setup step indicator clicks
    drakeStepIndicators.forEach((step, index) => {
        if (!step) return;
        
        step.style.cursor = 'pointer';
        step.addEventListener('click', () => {
            const stepNum = index + 1;
            if (stepNum < currentDrakeStep || step.classList.contains('completed')) {
                goToDrakeStep(stepNum);
            }
        });
    });

    // Step 1 Elements (New)
    const drakeUploadArea = document.getElementById('drakeUploadArea');
    const drakeFileInput = document.getElementById('drakeFileInput');
    const drakeUploadStatus = document.getElementById('drakeUploadStatus');
    const drakeNextBtn = document.getElementById('drakeNextBtn');
    // const drakeFormTypeSelect = document.getElementById('drakeFormTypeSelect');
    const drakeStep2FormSelect = document.getElementById('drakeStep2FormSelect');
    const drakeBackBtn = document.getElementById('drakeBackBtn');

    // Step 2 Elements (New)
    const drakeClientIdInput = document.getElementById('drakeClientIdInput');
    const drakePageGroupsList = document.getElementById('drakePageGroupsList');
    const drakeFilePreview = document.getElementById('drakeFilePreview');
    const drakePdfFrame = document.getElementById('drakePdfFrame');
    const drakeExtractBtn = document.getElementById('drakeExtractBtn');
    const drakeDetectBtn = document.getElementById('drakeDetectBtn');

    // Step 3 Elements
    const drakeProcessingStatus = document.getElementById('drakeProcessingStatus');
    const drakeResultsView = document.getElementById('drakeResultsView');
    const drakeAccordionContainer = document.getElementById('drakeAccordionContainer');
    const drakePdfReviewFrame = document.getElementById('drakePdfReviewFrame');
    const launchDrakeBtn = document.getElementById('launchDrakeBtn');
    const drakeLaunchContainer = document.getElementById('drakeLaunchContainer');

    // Step 4 Elements
    const drakeImportStatus = document.getElementById('drakeImportStatus');

    /**
     * Attempts to open the Drake desktop software using a custom URL scheme.
     * This is now handled by sending a request to the backend.
     */
    async function openDrakeSoftware() {
        console.log('Sending request to backend to launch Drake software...');
        let jobId = drakeModule.dataset.jobId;
        try { if (!jobId && typeof drakeJobId !== 'undefined') jobId = drakeJobId; } catch(e) {}

        if (!jobId || !drakeResults) {
            console.error('Cannot launch Drake: Job ID or extracted data is missing.');
            drakeImportStatus.innerHTML = `<p class="status-message status-error">Error: Extracted data is not available. Please process a document first.</p>`;
            drakeImportStatus.classList.remove('hidden');
            goToDrakeStep(3); // Go back to review step
            return;
        }

        // Get client name for email notification
        let clientName = 'N/A';
        if (drakeClientIdInput && drakeClientIdInput.value) {
            const selectedOption = drakeClientIdInput.querySelector(`option[value="${drakeClientIdInput.value}"]`);
            if (selectedOption) {
                const selectedText = selectedOption.textContent;
                // Example text: "John Doe (SSN: ...)"
                const match = selectedText.match(/(.*)\s\(SSN:.*\)/);
                if (match && match[1]) {
                    clientName = match[1].trim();
                } else {
                    clientName = selectedText; // Fallback to full text if format is unexpected
                }
            }
        }

        let displayFormType; // For use in catch block
        let itemsCountForEmail = 0;
        try {
            // Prepare data payload. drakeResults should be an array now.
            let rawDataList = Array.isArray(drakeResults) ? drakeResults : [drakeResults];
            let dataToSendList = [];
            
            const globalFormType = drakeStep2FormSelect ? drakeStep2FormSelect.value : '';

            for (let rawData of rawDataList) {
                // Deep copy results to avoid modifying the original state object
                let dataToSend = JSON.parse(JSON.stringify(rawData));
            
                // Normalize structure: if 'fields' is missing but we have a group key, unwrap it.
                if (!dataToSend.fields && Object.keys(dataToSend).length > 0) {
                     // Check if the first key holds the data (e.g. "Form_1099DIV")
                     const firstKey = Object.keys(dataToSend)[0];
                     if (dataToSend[firstKey] && dataToSend[firstKey].fields) {
                         console.log(`Unwrapping nested data from key: ${firstKey}`);
                         dataToSend = dataToSend[firstKey];
                     } else if (dataToSend[firstKey] && (dataToSend[firstKey].FormType || dataToSend[firstKey].TaxYear)) {
                         // The key contains the fields directly
                         console.log(`Wrapping direct data from key: ${firstKey}`);
                         dataToSend = { fields: dataToSend[firstKey] };
                     }
                }

                // Ensure fields object exists
                if (!dataToSend.fields) dataToSend.fields = {};

                // Ensure FormType is set in the data sent to backend
                // Only force if global selector is specific (not Auto)
                if (globalFormType) {
                    if (!dataToSend.fields.FormType) {
                        dataToSend.fields.FormType = { value: globalFormType };
                    } else if (typeof dataToSend.fields.FormType === 'object') {
                        dataToSend.fields.FormType.value = globalFormType;
                    }
                }

                // Determine effective form type for this item
                let itemFormType = '';
                if (dataToSend.fields.FormType) {
                    itemFormType = dataToSend.fields.FormType.value;
                }
                
                // Inject manually entered Client ID to ensure it's used by the backend automation.
                if (drakeClientId) {
                    console.log(`Injecting manual Client ID: ${drakeClientId} for form type: ${itemFormType}`);
                    
                    if (itemFormType === 'W2') {
                        if (!dataToSend.fields.Employee) dataToSend.fields.Employee = { value: {} };
                        if (typeof dataToSend.fields.Employee.value !== 'object' || dataToSend.fields.Employee.value === null) dataToSend.fields.Employee.value = {};
                        dataToSend.fields.Employee.value.SSN = drakeClientId;
                    } else if (itemFormType === '1099SSA') {
                        if (!dataToSend.fields.Beneficiary) dataToSend.fields.Beneficiary = { value: {} };
                        if (typeof dataToSend.fields.Beneficiary.value !== 'object' || dataToSend.fields.Beneficiary.value === null) dataToSend.fields.Beneficiary.value = {};
                        dataToSend.fields.Beneficiary.value.SSN = drakeClientId;
                    } else if (['1099DIV', '1099INT', '1099R', '1099MISC', '1099NEC'].includes(itemFormType)) {
                        if (!dataToSend.fields.Recipient) dataToSend.fields.Recipient = { value: {} };
                        if (typeof dataToSend.fields.Recipient.value !== 'object' || dataToSend.fields.Recipient.value === null) dataToSend.fields.Recipient.value = {};
                        dataToSend.fields.Recipient.value.TIN = drakeClientId;
                    }
                }
                
                dataToSendList.push(dataToSend);
            }
            itemsCountForEmail = dataToSendList.length;

            // Collect all unique form types from the data being sent
            const allFormTypes = new Set();
            dataToSendList.forEach(item => {
                if (item.fields && item.fields.FormType && item.fields.FormType.value) {
                    allFormTypes.add(item.fields.FormType.value);
                }
            });

            // Update status with details before sending request
            let formTypeLabel = 'Form Type';
            if (globalFormType === 'Auto' || !globalFormType) {
                displayFormType = Array.from(allFormTypes).map(ft => getFriendlyFormName(ft)).join(', ');
                if (allFormTypes.size > 1) formTypeLabel = 'Form Type(s)';
            } else {
                displayFormType = getFriendlyFormName(globalFormType);
            }
            drakeImportStatus.innerHTML = `
                <div style="text-align: center; padding: 20px;">
                    <div class="spinner" style="margin: 0 auto 15px auto;"></div>
                    <h5 style="color: #0d6efd;">Drake Automation Running...</h5>
                    <p class="mb-1"><strong>Client ID:</strong> ${drakeClientId || 'N/A'}</p>
                    <p class="mb-1"><strong>${formTypeLabel}:</strong> ${displayFormType || 'N/A'}</p>
                    <p class="text-muted" style="font-size: 0.9em; margin-top: 10px;">Please keep the Drake software window visible and do not use the mouse/keyboard.</p>
                </div>
            `;
            drakeImportStatus.classList.remove('hidden');

            const startTime = performance.now();
            const successData = await startDrakeLaunchAndWait({
                job_id: jobId,
                client_id: drakeClientId,
                data: dataToSendList
            });

            const endTime = performance.now();
            const duration = ((endTime - startTime) / 1000).toFixed(2);
            console.log(`[Drake] Import process took ${duration} seconds.`);
            console.log("Drake automation completed successfully:", successData);

            let friendlyFormDisplay;
            let successFormTypeLabel = 'Form Type';
            if (successData.form_type) {
                if (Array.isArray(successData.form_type)) {
                    friendlyFormDisplay = successData.form_type.map(ft => getFriendlyFormName(ft)).join(', ');
                    if (successData.form_type.length > 1) {
                        successFormTypeLabel = 'Form Type(s)';
                    }
                } else {
                    friendlyFormDisplay = getFriendlyFormName(successData.form_type);
                }
            }

            drakeImportStatus.innerHTML = `
                <div class="status-message status-success" style="padding: 15px;">
                    <div style="font-size: 1.1em; font-weight: bold; margin-bottom: 5px;">
                        Success: ${successData.message || 'Import completed successfully'}
                    </div>
                    ${friendlyFormDisplay ? `<div style="margin-bottom: 8px; color: #555;">${successFormTypeLabel}: <strong>${friendlyFormDisplay}</strong></div>` : ''}
                    <div style="margin-top: 5px; font-size: 0.95em; color: #0f5132;">
                        <i class="bi bi-stopwatch-fill"></i> Execution time: <strong>${duration}s</strong>
                    </div>
                </div>
            `;

            sendCompletionEmail({
                status: 'Success',
                clientName: clientName,
                clientId: drakeClientId,
                items: dataToSendList.length,
                formType: friendlyFormDisplay || displayFormType,
                jobId: jobId
            });
        } catch (error) {
            console.error('Error sending launch command:', error);
            drakeImportStatus.innerHTML = `<p class="status-message status-error">Error during "Import to Drake": ${error.message}</p>`;

            // Send failure email
            sendCompletionEmail({
                status: 'Failed',
                clientName: clientName,
                clientId: drakeClientId,
                items: itemsCountForEmail,
                formType: displayFormType || 'N/A',
                errorMessage: error.message || 'An unexpected error occurred while contacting the server.',
                jobId: jobId
            });
        }
    }

    /**
     * Sends a completion notification email via the backend.
     * @param {object} details - The details for the email.
     * @param {string} details.status - 'Success' or 'Failed'.
     * @param {string} details.clientName - The name of the client.
     * @param {string} details.clientId - The ID of the client (SSN/TIN).
     * @param {string} details.formType - The form type(s) processed.
     * @param {string} details.items - The Items processed.
     * @param {string} [details.errorMessage] - An optional error message.
     * @param {string} [details.jobId] - The Job ID to link to detailed results file.
     */
    async function sendCompletionEmail(details) {
        console.log('Preparing to send completion email with details:', details);
        try {
            const response = await fetch('/api/drake/notify-completion', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(details)
            });
            if (response.ok) {
                console.log('Completion email request sent successfully.');
            } else {
                const errorData = await response.json().catch(() => ({ detail: 'Failed to send email, unknown server error.' }));
                console.error('Failed to send completion email:', errorData.detail);
            }
        } catch (error) {
            console.error('Network error while trying to send completion email:', error);
        }
    }

    /**
     * Navigates to a specific step in the Drake module.
     * @param {number} stepNumber - The step number to navigate to (1-based).
     */
    function goToDrakeStep(stepNumber) {
        // If going backwards, hide the final status message to avoid confusion
        if (stepNumber < currentDrakeStep) {
            if (drakeImportStatus) {
                drakeImportStatus.classList.add('hidden');
                drakeImportStatus.innerHTML = '';
            }
        }

        currentDrakeStep = stepNumber;
        const stepIndex = stepNumber - 1;

        drakeStepContents.forEach((content, index) => {
            content.classList.toggle('active', index === stepIndex);
        });

        drakeStepIndicators.forEach((indicator, index) => {
            if (index < stepIndex) {
                indicator.classList.add('completed');
                indicator.classList.remove('active');
            } else if (index === stepIndex) {
                indicator.classList.add('active');
                indicator.classList.remove('completed');
            } else {
                indicator.classList.remove('active', 'completed');
            }
        });

        // Update Back Button visibility and text
        if (drakeBackBtn) {
            const backBtnText = drakeBackBtn.querySelector('.btn-back-text');
            if (stepNumber > 1) {
                drakeBackBtn.classList.remove('hidden');
                if (backBtnText) {
                    const previousStepLabels = {
                        2: 'Upload Document',
                        3: 'Client ID & Form Type',
                        4: 'Extract & Review'
                    };
                    const previousLabel = previousStepLabels[stepNumber] || 'Previous Step';
                    backBtnText.textContent = `Back to ${previousLabel}`;
                }
            } else {
                drakeBackBtn.classList.add('hidden');
            }
        }
    }

    // --- Step 1: Upload Document ---

    /**
     * Handles the selected file, uploads it, and prepares for next step.
     * @param {File} file - The file selected by the user.
     */
    const handleFile = async (file) => {
        if (!file) return;

        if (file.type !== 'application/pdf') {
            drakeUploadStatus.textContent = 'Invalid file type. Please upload a PDF file.';
            drakeUploadStatus.className = 'status-message status-error';
            drakeUploadStatus.classList.remove('hidden');
            return;
        }

        drakeSelectedFile = file;

        // Reset state dependent on file
        drakeSelectedGroups = {};
        drakeResults = null;
        if (drakeModule) drakeModule.dataset.selectedGroups = '{}';
        
        // Clear UI elements dependent on file
        if (drakePageGroupsList) drakePageGroupsList.innerHTML = '';

        // Clear Client ID options
        if (drakeClientIdInput) {
            drakeClientIdInput.innerHTML = '<option value="">-- Select Client --</option>';
            const msgEl = document.getElementById('drakeClientDetectMsg');
            if (msgEl) {
                msgEl.style.display = 'none';
                msgEl.textContent = '';
            }
        }

        // Clear Detected Types Container
        const detectedTypesContainer = document.getElementById('drakeDetectedTypesContainer');
        if (detectedTypesContainer) {
            detectedTypesContainer.innerHTML = '';
            detectedTypesContainer.classList.add('hidden');
        }

        // Ensure manual form select is visible
        if (drakeStep2FormSelect && drakeStep2FormSelect.parentElement) {
            drakeStep2FormSelect.parentElement.classList.remove('hidden');
            drakeStep2FormSelect.value = ''; // Reset selection
        }

        // Reset Extract button
        if (drakeExtractBtn) {
            drakeExtractBtn.disabled = true;
        }

        // Clear Step 3 results (Debug view cleanup)
        const debugContainer = document.getElementById('drakeDebugSplitContainer');
        if (debugContainer) debugContainer.innerHTML = '';
        const mainTable = document.getElementById('drakeMainLayoutTable');
        if (mainTable) mainTable.style.display = '';
        if (drakeAccordionContainer) drakeAccordionContainer.innerHTML = '';
        if (drakeResultsView) drakeResultsView.classList.add('hidden');

        // Show file selection status and hide the upload box
        drakeUploadStatus.textContent = `Uploading ${file.name}...`;
        drakeUploadStatus.className = 'status-message status-info';
        drakeUploadStatus.classList.remove('hidden');
        // drakeUploadArea.classList.add('hidden');
        drakeNextBtn.disabled = true; // Disable Next while uploading

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Upload failed');
            }

            const result = await response.json();
            drakeJobId = result.job_id;
            drakeModule.dataset.jobId = drakeJobId;

            // Show success status
            drakeUploadStatus.textContent = `File uploaded: ${file.name}`;
            drakeUploadStatus.className = 'status-message status-success';
            drakeNextBtn.disabled = false; // Enable Next

        } catch (error) {
            console.error('Upload error:', error);
            drakeUploadStatus.textContent = `Upload failed: ${error.message}`;
            drakeUploadStatus.className = 'status-message status-error';
            // drakeUploadArea.classList.remove('hidden'); // Allow retry
            drakeSelectedFile = null;
        }
    };


    // Drag and Drop listeners
    drakeUploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        drakeUploadArea.classList.add('dragover'); // Add this class to your CSS for visual feedback
    });

    drakeUploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        drakeUploadArea.classList.remove('dragover');
    });

    drakeUploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        drakeUploadArea.classList.remove('dragover');
        handleFile(e.dataTransfer.files[0]);
    });

    // Event listeners for file upload area
    drakeUploadArea.addEventListener('click', () => drakeFileInput.click());
    drakeFileInput.addEventListener('change', (e) => {
        handleFile(e.target.files[0]);
        drakeFileInput.value = ''; // Reset to allow re-uploading same file
    });

    // Back button listener
    if (drakeBackBtn) {
        drakeBackBtn.addEventListener('click', () => {
            if (currentDrakeStep > 1) {
                goToDrakeStep(currentDrakeStep - 1);
            }
        });
    }

    // Event listener for the Next button to go to Step 2
    drakeNextBtn.addEventListener('click', async () => {
        let jobId = drakeModule.dataset.jobId;
        try { if (!jobId && typeof drakeJobId !== 'undefined') jobId = drakeJobId; } catch(e) {}

        if (!jobId) {
            alert('Please upload a file first.');
            return;
        }

        // Create a URL for the PDF and display it in the iframe in Step 2
        if (drakeSelectedFile) {
            const fileURL = URL.createObjectURL(drakeSelectedFile);
            drakePdfFrame.src = fileURL;
        }
        // Show the preview section in Step 2
        drakeFilePreview.classList.remove('hidden');

        goToDrakeStep(2);

        // Auto-select "Auto" and trigger detection immediately
        if (drakeStep2FormSelect) {
            drakeStep2FormSelect.value = 'Auto';
            drakeStep2FormSelect.dispatchEvent(new Event('change'));
        }
        if (drakeDetectBtn) {
            setTimeout(() => drakeDetectBtn.click(), 100);
        }
    });

    // Event listener for Detect/Analyze button in Step 2
    if (drakeDetectBtn) {
        drakeDetectBtn.addEventListener('click', async () => {
            const formType = drakeStep2FormSelect ? drakeStep2FormSelect.value : "";

            // ✅ CHỈ chặn khi rỗng, KHÔNG chặn Auto
            if (!formType) {
            alert('Please select a form type.');
            return;
            }

            drakePageGroupsList.innerHTML = '';

            if (typeof showDetectionModal === 'function') {
            showDetectionModal('Analyzing PDF document with OCR to automatically detect page numbers...');
            }

            let shouldHideModal = true;
            const startTime = performance.now();

            try {
            const detectFormData = new FormData();

            // ✅ Gửi luôn form_type (kể cả Auto) để rõ ràng
            detectFormData.append('form_type', formType || 'Auto');

            let jobId = drakeModule.dataset.jobId;
            try { if (!jobId && typeof drakeJobId !== 'undefined') jobId = drakeJobId; } catch(e) {}

            const detectResponse = await fetch(`/api/jobs/${jobId}/detect-pages`, {
                method: 'POST',
                body: detectFormData
            });

            const endTime = performance.now();
            const duration = ((endTime - startTime) / 1000).toFixed(2);
            console.log(`[Drake] Page detection took ${duration} seconds.`);

            drakeSelectedGroups = {};
            drakeModule.dataset.selectedGroups = '{}';
            let clientsFound = [];

            // Reset detected types UI nếu không phải Auto (để hiện lại dropdown)
            if (formType !== 'Auto') {
                renderDetectedTypesSelection([]); // Hide checkboxes, show dropdown
            }

            if (detectResponse.ok) {
                const detectData = await detectResponse.json();
                console.log('[Drake] Detection Data:', detectData);

                drakeSelectedGroups = detectData.detected_groups || {};
                drakeModule.dataset.selectedGroups = JSON.stringify(drakeSelectedGroups);

                // Nếu Auto và backend trả về 1 form_type cụ thể, sync dropdown cho tiện debug
                if (detectData.form_type && formType === 'Auto') {
                if (drakeStep2FormSelect) {
                    drakeStep2FormSelect.value = 'Auto'; 
                    // bạn có thể giữ Auto, hoặc set sang detectData.form_type nếu muốn
                    // drakeStep2FormSelect.value = detectData.form_type;
                }
                }

                // ✅ Auto: render checkbox detected_types
                if (formType === 'Auto') {
                renderDetectedTypesSelection(detectData.detected_types || []);
                }

                clientsFound = detectData.list_clients || [];
                renderClientOptions(clientsFound);
            }

            // Update modal message
            if (Object.keys(drakeSelectedGroups).length > 0) {
                if (typeof updateDetectionModalMessage === 'function') {
                let msg = 'Page numbers have been automatically detected.';
                if (clientsFound.length === 0) msg += ' (No clients found in file)';
                updateDetectionModalMessage(
                    'Page detection completed successfully!',
                    `${msg}<br><span style="display:inline-block;margin-top:8px;font-weight:bold;color:#0d6efd;">⏱ Time: ${duration}s</span>`
                );
                await new Promise(resolve => setTimeout(resolve, 1500));
                }
            } else {
                if (typeof updateDetectionModalMessage === 'function') {
                updateDetectionModalMessage('Could not automatically detect page numbers.', 'Please check the document or form type.');
                await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }

            renderDrakePageGroups(drakeSelectedGroups);
            checkCanExtract();

            // Auto-process if Skip Preview is checked
            const skipPreviewCheckbox = document.getElementById('drakeSkipPreviewCheckbox');
            if (skipPreviewCheckbox && skipPreviewCheckbox.checked) {
                if (Object.keys(drakeSelectedGroups).length === 0) {
                if (typeof hideDetectionModal === 'function') hideDetectionModal();
                shouldHideModal = false;
                return;
                }

                if (clientsFound.length === 0) {
                if (typeof hideDetectionModal === 'function') hideDetectionModal();
                shouldHideModal = false;
                return;
                }

                if (!drakeClientIdInput.value && clientsFound.length > 0) {
                drakeClientIdInput.value = clientsFound[0].ssn;
                drakeClientIdInput.dispatchEvent(new Event('change'));
                }

                checkCanExtract();

                if (!drakeExtractBtn.disabled) {
                if (typeof updateDetectionModalMessage === 'function') {
                    updateDetectionModalMessage('Extracting Data...', 'Proceeding to extraction automatically.');
                }
                shouldHideModal = false;
                drakeExtractBtn.click();
                }
            }

            } catch (error) {
            console.error('Page detection error:', error);
            alert('Failed to detect pages. Please try again.');
            } finally {
            if (shouldHideModal && typeof hideDetectionModal === 'function') {
                hideDetectionModal();
            }
            }
        });
    }


    /**
     * Populates the Client ID select with detected clients.
     * @param {Array} clients - List of detected clients {name, ssn}
     */
    function renderClientOptions(clients) {
        console.log('[Drake] renderClientOptions called with:', clients);
        const select = document.getElementById('drakeClientIdInput');
        if (!select) {
            console.error('[Drake] drakeClientIdInput element not found');
            return;
        }

        // Helper to manage the message element
        let msgEl = document.getElementById('drakeClientDetectMsg');
        if (!msgEl) {
            msgEl = document.createElement('div');
            msgEl.id = 'drakeClientDetectMsg';
            msgEl.style.marginTop = '0px';
            msgEl.style.fontSize = '0.9em';
            msgEl.style.fontWeight = 'bold';
            msgEl.style.textAlign = 'center';
        }
        
        const extractBtn = document.getElementById('drakeExtractBtn');
        const selectWrapper = select.parentElement;

        // Ensure message is placed BETWEEN select and button
        if (extractBtn && extractBtn.parentNode) {
            extractBtn.parentNode.insertBefore(msgEl, extractBtn);
        } else {
            select.parentNode.appendChild(msgEl);
        }
        
        select.innerHTML = '<option value="">-- Select Client --</option>';
        
        if (clients && clients.length > 0) {
            clients.forEach(client => {
                if (client.name && client.ssn) {
                    const option = document.createElement('option');
                    option.value = client.ssn;
                    option.textContent = `${client.name} (SSN: ${client.ssn})`;
                    select.appendChild(option);
                }
            });
            
            console.log(`[Drake] Added ${select.options.length - 1} client options`);

            // Hide message
            msgEl.style.display = 'none';
            msgEl.textContent = '';
            
            // Restore margins
            if (selectWrapper) selectWrapper.style.marginBottom = '25px';
            if (extractBtn) extractBtn.style.marginTop = '15px';
            
            // Auto-select if only one client
            if (!select.value && clients.length > 0) {
                select.value = clients[0].ssn;
                select.dispatchEvent(new Event('change'));
            }

        } else {
            // const option = document.createElement('option');
            // option.disabled = true;
            // option.textContent = "No clients found in file";
            // select.appendChild(option);

            // Show message in red
            msgEl.style.color = '#dc3545'; // Red color
            msgEl.textContent = 'No clients found in file';
            msgEl.style.display = 'block';
            
            // Adjust margins to prevent layout shift (compensate for message height)
            // Original gap: 25px + 15px = 40px. New gap: 10px + ~20px(msg) + 10px = ~40px.
            if (selectWrapper) selectWrapper.style.marginBottom = '10px';
            if (extractBtn) extractBtn.style.marginTop = '10px';
        }
    }

    /**
     * Renders the detected page groups into Step 2 for review.
     * @param {Object} groups - The detected groups object { "GroupName": [0, 1], ... }
     */
    function renderDrakePageGroups(groups) {
        drakePageGroupsList.innerHTML = '<label class="form-label">Detected Pages</label>';
        
        const groupEntries = Object.entries(groups);

        if (groupEntries.length === 0) {
            drakePageGroupsList.innerHTML += '<p class="text-muted" style="color: #dc3545;">No pages detected. Please check the document.</p>';
            return;
        }

        const showCheckbox = groupEntries.length >= 2;

        for (const [groupName, pages] of groupEntries) {
            const displayName = groupName.replace(/_/g, ' ').replace(/pages/i, 'Pages');
            const displayPages = pages.map(p => p + 1).join(', ');

            const groupDiv = document.createElement('div');
            groupDiv.className = 'card p-3 mb-2';
            groupDiv.style.backgroundColor = '#f8f9fa';
            groupDiv.style.border = '1px solid #e9ecef';

            const checkboxHTML = showCheckbox ? `
                <input
                    type="checkbox"
                    class="form-check-input drake-page-checkbox me-2"
                    value="${groupName}"
                    id="check_${groupName}"
                    checked
                >
            ` : '';

            groupDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">

                    <div class="d-flex align-items-center">
                        ${checkboxHTML}
                        <label for="check_${groupName}" class="mb-0">
                            <strong>${displayName}</strong>
                        </label>
                    </div>

                    <span class="badge bg-success" style="font-size: 0.9em;">
                        Pages: ${displayPages}
                    </span>

                </div>
            `;

            drakePageGroupsList.appendChild(groupDiv);
        }

        // Add event listeners to checkboxes to update the extract button state
        drakePageGroupsList.querySelectorAll('.drake-page-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                // This function will enable/disable the extract button based on selections
                checkCanExtract();
            });
        });
    }

    /**
     * Hides detected form type checkboxes and always uses the dropdown.
     * @param {Array} types - List of detected form types
     */
    function renderDetectedTypesSelection(types) {
        // Ensure container exists then hide it
        let container = document.getElementById('drakeDetectedTypesContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'drakeDetectedTypesContainer';
            container.style.marginBottom = '15px';
            if (drakeStep2FormSelect && drakeStep2FormSelect.parentNode) {
                drakeStep2FormSelect.parentNode.insertBefore(container, drakeStep2FormSelect.nextSibling);
            }
        }

        // Hide and clear checkbox UI
        container.innerHTML = '';
        container.classList.add('hidden');

        // Always show dropdown
        if (drakeStep2FormSelect && drakeStep2FormSelect.parentElement) {
            drakeStep2FormSelect.parentElement.classList.remove('hidden');
        }

        // (Optional) If Auto detected exactly one type, auto-set dropdown to that type
        if (Array.isArray(types) && types.length === 1 && drakeStep2FormSelect) {
            drakeStep2FormSelect.value = types[0];
            drakeStep2FormSelect.dispatchEvent(new Event('change'));
        }

        checkCanExtract();
    }

    // --- Step 2: Extract Data ---

    drakeExtractBtn.addEventListener('click', async () => {
        console.log('Extract button clicked, running debug split flow.');

        // --- Start: Setup and Validation ---
        const clientId = drakeClientIdInput ? drakeClientIdInput.value.trim() : '';
        try { drakeClientId = clientId; } catch(e) {}
    
        let jobId = drakeModule.dataset.jobId;
        try {
            if (!jobId && typeof drakeJobId !== 'undefined') jobId = drakeJobId;
        } catch (e) {}
    
        if (!jobId) {
            alert('Please upload a file first.');
            goToDrakeStep(1);
            return;
        }
    
        if (!clientId) {
            alert('Please enter a Client ID.');
            return;
        }
    
        // Get the form type from the dropdown. This tells the backend if we are in "Auto" mode.
        const formTypeForBackend = drakeStep2FormSelect ? drakeStep2FormSelect.value : '';
        if (!formTypeForBackend) {
            alert('Please select a form type from the dropdown.');
            return;
        }
    
        // Get the groups to process from the checkboxes if they exist.
        const allDetectedGroups = drakeSelectedGroups || JSON.parse(drakeModule.dataset.selectedGroups || '{}');
        const groupsToProcess = {};
        const pageCheckboxes = document.querySelectorAll('.drake-page-checkbox');
    
        if (pageCheckboxes.length > 0) {
            // Checkboxes are visible, so use them to filter.
            const checkedBoxes = document.querySelectorAll('.drake-page-checkbox:checked');
            if (checkedBoxes.length === 0) {
                alert('Please select at least one page group to extract.');
                return;
            }
            checkedBoxes.forEach(cb => {
                const groupName = cb.value;
                if (allDetectedGroups[groupName]) {
                    groupsToProcess[groupName] = allDetectedGroups[groupName];
                }
            });
        } else {
            // No checkboxes, so use all detected groups.
            Object.assign(groupsToProcess, allDetectedGroups);
        }
    
        if (Object.keys(groupsToProcess).length === 0) {
             alert('No pages selected for extraction. Please go back and retry detection.');
             return;
        }
        // --- End: Setup and Validation ---

        // --- Start: API Call and Rendering ---
        const btn = drakeExtractBtn;
        btn.disabled = true;
        const originalText = btn.textContent;
        btn.textContent = 'Extracting...';
        
        // Show modal to block user interaction
        if (typeof showDetectionModal === 'function') {
            showDetectionModal('Running OCR to extract data...', 'Extracting Data');
            if (typeof updateDetectionModalMessage === 'function') {
                updateDetectionModalMessage('Running OCR to extract data...', 'Analyzing document pages with OCR. Please wait.');
            }
        }

        const formData = new FormData();
        formData.append('form_type', formTypeForBackend); // Send 'Auto' or specific type
        formData.append('selected_groups', JSON.stringify(groupsToProcess));

        try {
            const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/debug-split-pages`, { 
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const res = await response.json();

                const isSkippingPreview = document.getElementById('drakeSkipPreviewCheckbox')?.checked;

                // Only show completion modal and go to review step if NOT skipping
                if (!isSkippingPreview) {
                    if (typeof updateDetectionModalMessage === 'function') {
                        updateDetectionModalMessage('Extraction Complete!', 'Preparing results view...');
                    }
                    await new Promise(resolve => setTimeout(resolve, 1500)); // Give user time to read
                    goToDrakeStep(3);
                }

                // 2. Switch to Debug View (Hide main table, show debug container)
                const mainTable = document.getElementById('drakeMainLayoutTable');
                if (mainTable) mainTable.style.display = 'none';

                let debugContainer = document.getElementById('drakeDebugSplitContainer');
                if (!debugContainer) {
                    debugContainer = document.createElement('div');
                    debugContainer.id = 'drakeDebugSplitContainer';
                    const step3Content = document.getElementById('drakeStep3Content');
                    const launchContainer = document.getElementById('drakeLaunchContainer');
                    if (step3Content && launchContainer) {
                        step3Content.insertBefore(debugContainer, launchContainer);
                    } else if (step3Content) {
                        step3Content.appendChild(debugContainer);
                    }
                }
                debugContainer.style.display = 'block';
                debugContainer.innerHTML = ''; // Clear previous content
                
                // 3. Render Split Pages Table
                const results = res.results || res.files;
                if (results && results.length > 0) {

                    // Add a "Test Import All" button
                    const testImportAllBtn = document.createElement('button');
                    testImportAllBtn.id = 'drakeTestImportAllBtn';
                    testImportAllBtn.className = 'btn btn-primary mb-3';
                    testImportAllBtn.innerHTML = '<i class="bi bi-play-circle-fill"></i> Import to Drake';
                    debugContainer.appendChild(testImportAllBtn);

                    const runImport = async () => {
                        const originalText = testImportAllBtn.innerHTML;
                        testImportAllBtn.innerHTML = 'Preparing & Sending...';
                        testImportAllBtn.disabled = true;

                        let dataToSendList = [];
                        let displayFormType = 'Unknown';

                        // Get client name for email notification
                        let clientName = 'N/A';
                        if (drakeClientIdInput && drakeClientIdInput.value) {
                            const selectedOption = drakeClientIdInput.querySelector(`option[value="${drakeClientIdInput.value}"]`);
                            if (selectedOption) {
                                const selectedText = selectedOption.textContent;
                                const match = selectedText.match(/(.*)\s\(SSN:.*\)/);
                                if (match && match[1]) {
                                    clientName = match[1].trim();
                                } else {
                                    clientName = selectedText; // Fallback to full text
                                }
                            }
                        }

                        try {
                            // Iterate over ALL results, not just the current page
                            for (const item of results) {
                                if (item.extracted_data && !item.extracted_data.error) {
                                    let dataToSend = JSON.parse(JSON.stringify(item.extracted_data));
                                    
                                    // Normalize structure logic
                                    if (!dataToSend.fields && Object.keys(dataToSend).length > 0) {
                                        const firstKey = Object.keys(dataToSend)[0];
                                        if (dataToSend[firstKey] && dataToSend[firstKey].fields) {
                                            dataToSend = dataToSend[firstKey];
                                         } else if (dataToSend[firstKey] && (dataToSend[firstKey].FormType || dataToSend[firstKey].TaxYear)) {
                                             dataToSend = { fields: dataToSend[firstKey] };
                                        }
                                    }
                                    if (!dataToSend.fields) dataToSend.fields = {};
                                    
                                    // Inject Client ID
                                    let itemFormType = '';
                                    if (dataToSend.fields.FormType) {
                                        itemFormType = dataToSend.fields.FormType.value;
                                    }
                                    
                                    if (drakeClientId) {
                                        if (itemFormType === 'W2') {
                                            if (!dataToSend.fields.Employee) dataToSend.fields.Employee = { value: {} };
                                            if (typeof dataToSend.fields.Employee.value !== 'object' || dataToSend.fields.Employee.value === null) dataToSend.fields.Employee.value = {};
                                            dataToSend.fields.Employee.value.SSN = drakeClientId;
                                        } else if (itemFormType === '1099SSA') {
                                            if (!dataToSend.fields.Beneficiary) dataToSend.fields.Beneficiary = { value: {} };
                                            if (typeof dataToSend.fields.Beneficiary.value !== 'object' || dataToSend.fields.Beneficiary.value === null) dataToSend.fields.Beneficiary.value = {};
                                            dataToSend.fields.Beneficiary.value.SSN = drakeClientId;
                                        } else if (['1099DIV', '1099INT', '1099R', '1099MISC', '1099NEC'].includes(itemFormType)) {
                                            if (!dataToSend.fields.Recipient) dataToSend.fields.Recipient = { value: {} };
                                            if (typeof dataToSend.fields.Recipient.value !== 'object' || dataToSend.fields.Recipient.value === null) dataToSend.fields.Recipient.value = {};
                                            dataToSend.fields.Recipient.value.TIN = drakeClientId;
                                        }
                                    }
                                    dataToSendList.push(dataToSend);
                                }
                            }

                            if (dataToSendList.length === 0) {
                                alert('No valid data found to import.');
                                return;
                            }
                            
                            // Collect all unique form types for display
                            const allFormTypes = new Set();
                            dataToSendList.forEach(item => {
                                if (item.fields && item.fields.FormType && item.fields.FormType.value) {
                                    allFormTypes.add(item.fields.FormType.value);
                                }
                            });

                            let formTypeLabel = 'Form Type(s)';
                            if (allFormTypes.size > 0) {
                                displayFormType = Array.from(allFormTypes).map(ft => getFriendlyFormName(ft)).join(', ');
                            }
                            if (allFormTypes.size <= 1) {
                                formTypeLabel = 'Form Type';
                            }

                            // Switch to Step 4 and show status
                            goToDrakeStep(4);
                            drakeImportStatus.innerHTML = `
                                <div style="text-align: center; padding: 20px;">
                                    <div class="spinner" style="margin: 0 auto 15px auto;"></div>
                                    <h5 style="color: #0d6efd;">Drake Automation Running...</h5>
                                    <p class="mb-1"><strong>Client ID:</strong> ${drakeClientId || 'N/A'}</p>
                                    <p class="mb-1"><strong>${formTypeLabel}:</strong> ${displayFormType || 'N/A'}</p>
                                    <p class="text-muted" style="font-size: 0.9em; margin-top: 10px;">Please keep the Drake software window visible and do not use the mouse/keyboard.</p>
                                </div>
                            `;
                            drakeImportStatus.classList.remove('hidden');

                            const startTime = performance.now();
                            const asyncSuccessData2 = await startDrakeLaunchAndWait({
                                job_id: jobId,
                                client_id: drakeClientId,
                                data: dataToSendList
                            });

                            const asyncEndTime2 = performance.now();
                            const asyncDuration2 = ((asyncEndTime2 - startTime) / 1000).toFixed(2);
                            console.log(`[Drake] Import process took ${asyncDuration2} seconds.`);

                            let asyncFriendlyFormDisplay2;
                            let asyncSuccessFormTypeLabel2 = 'Form Type';
                            if (asyncSuccessData2.form_type) {
                                if (Array.isArray(asyncSuccessData2.form_type)) {
                                    asyncFriendlyFormDisplay2 = asyncSuccessData2.form_type.map(ft => getFriendlyFormName(ft)).join(', ');
                                    if (asyncSuccessData2.form_type.length > 1) {
                                        asyncSuccessFormTypeLabel2 = 'Form Type(s)';
                                    }
                                } else {
                                    asyncFriendlyFormDisplay2 = getFriendlyFormName(asyncSuccessData2.form_type);
                                }
                            }
                            
                            drakeImportStatus.innerHTML = `
                                <div class="status-message status-success" style="padding: 15px;">
                                    <div style="font-size: 1.1em; font-weight: bold; margin-bottom: 5px;">
                                        ${asyncSuccessData2.message || 'Import completed successfully'}
                                    </div>
                                    ${asyncFriendlyFormDisplay2 ? `<div style="margin-bottom: 8px; color: #555;">${asyncSuccessFormTypeLabel2}: <strong>${asyncFriendlyFormDisplay2}</strong></div>` : ''}
                                    <div style="margin-top: 5px; font-size: 0.95em; color: #0f5132;">
                                        <i class="bi bi-stopwatch-fill"></i> Execution time: <strong>${asyncDuration2}s</strong>
                                    </div>
                                </div>`;

                            sendCompletionEmail({
                                status: 'Success',
                                clientName: clientName,
                                clientId: drakeClientId,
                                items: dataToSendList.length,
                                formType: asyncFriendlyFormDisplay2 || displayFormType,
                                jobId: jobId
                            });
                            return;

                            const response = await fetch('/api/drake/launch', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ job_id: jobId, client_id: drakeClientId, data: dataToSendList })
                            });
                            
                            if (!response.ok) {
                                let errorData = {};
                                try {
                                    errorData = await response.json();
                                } catch (e) {
                                    errorData = { detail: `Request failed (${response.status}). The server returned an invalid response.` };
                                }
                                throw new Error(errorData.detail || 'Drake automation failed.');
                            }

                            const endTime = performance.now();
                            const duration = ((endTime - startTime) / 1000).toFixed(2);
                            console.log(`[Drake] Import process took ${duration} seconds.`);

                            const successData = await response.json();
                            
                            let friendlyFormDisplay;
                            let successFormTypeLabel = 'Form Type';
                            if (successData.form_type) {
                                if (Array.isArray(successData.form_type)) {
                                    friendlyFormDisplay = successData.form_type.map(ft => getFriendlyFormName(ft)).join(', ');
                                    if (successData.form_type.length > 1) {
                                        successFormTypeLabel = 'Form Type(s)';
                                    }
                                } else {
                                    friendlyFormDisplay = getFriendlyFormName(successData.form_type);
                                }
                            }
                            
                            drakeImportStatus.innerHTML = `
                                <div class="status-message status-success" style="padding: 15px;">
                                    <div style="font-size: 1.1em; font-weight: bold; margin-bottom: 5px;">
                                        ✅ ${successData.message || 'Import completed successfully'}
                                    </div>
                                    ${friendlyFormDisplay ? `<div style="margin-bottom: 8px; color: #555;">${successFormTypeLabel}: <strong>${friendlyFormDisplay}</strong></div>` : ''}
                                    <div style="margin-top: 5px; font-size: 0.95em; color: #0f5132;">
                                        <i class="bi bi-stopwatch-fill"></i> Execution time: <strong>${duration}s</strong>
                                    </div>
                                </div>`;

                            sendCompletionEmail({
                                status: 'Success',
                                clientName: clientName,
                                clientId: drakeClientId,
                                items: dataToSendList.length,
                                formType: friendlyFormDisplay || displayFormType,
                                jobId: jobId
                            });

                        } catch (e) {
                            console.error(e);
                            // Ensure we are on the status step to show the error
                            goToDrakeStep(4);

                            let errorMsg = e.message;
                            if (typeof errorMsg === 'string' && errorMsg.toLowerCase().includes('not found in the drake client list')) {
                                errorMsg = `<strong>${errorMsg}</strong><br><br>` +
                                           `The client list might be outdated. Please go to the <b>Client List</b> tab, ` +
                                           `click <b>"Query Drake"</b> to refresh the database, and then try again.`;
                            }

                            drakeImportStatus.innerHTML = `<div class="status-message status-error"><strong>Error during "Import to Drake":</strong><br><br>${errorMsg}</div>`;
                            sendCompletionEmail({
                                status: 'Failed',
                                clientName: clientName,
                                clientId: drakeClientId,
                                formType: displayFormType,
                                items: e.items_processed || 0,
                                errorMessage: e.message,
                                jobId: jobId
                            });
                        } finally {
                            testImportAllBtn.innerHTML = originalText;
                            testImportAllBtn.disabled = false;
                        }
                    };

                    testImportAllBtn.onclick = runImport;

                    debugContainer.appendChild(testImportAllBtn);

                    // Pagination setup
                    const itemsPerPage = 1;
                    let currentPage = 1;
                    const totalPages = Math.ceil(results.length / itemsPerPage);

                    // Pagination Controls (Moved to top)
                    if (totalPages > 1) {
                        const paginationContainer = document.createElement('div');
                        paginationContainer.style.display = 'flex';
                        paginationContainer.style.justifyContent = 'space-between';
                        paginationContainer.style.alignItems = 'center';
                        paginationContainer.style.padding = '15px';
                        paginationContainer.style.backgroundColor = '#f8f9fa';
                        paginationContainer.style.borderBottom = '1px solid #ddd';
                        paginationContainer.style.marginBottom = '10px';

                        paginationContainer.innerHTML = `
                            <div style="display: flex; gap: 5px; justify-content: center; align-items: center; width: 100%;">
                                <button type="button" class="btn btn-sm btn-primary" id="drakeSplitPrevBtn">Previous</button>
                                <span class="btn btn-sm btn-outline-secondary disabled" id="drakeSplitPageDisplay" style="border: none; background: transparent; color: #333;">Page 1</span>
                                <button type="button" class="btn btn-sm btn-primary" id="drakeSplitNextBtn">Next</button>
                            </div>
                        `;
                        debugContainer.appendChild(paginationContainer);
                    }

                    const table = document.createElement('table');
                    table.style.width = '100%';
                    table.style.borderCollapse = 'collapse';
                    table.innerHTML = `
                        <thead>
                            <tr>
                                <th style="width: 50%; padding: 10px; text-align: left; border-bottom: 2px solid #ddd; background: #f8f9fa;">Page Image</th>
                                <th style="width: 50%; padding: 10px; text-align: left; border-bottom: 2px solid #ddd; background: #f8f9fa;">Extracted Data</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    `;
                    const tbody = table.querySelector('tbody');
                    debugContainer.appendChild(table);

                    const renderPage = (page) => {
                        if (page < 1) page = 1;
                        if (page > totalPages) page = totalPages;
                        currentPage = page;

                        const startIdx = (currentPage - 1) * itemsPerPage;
                        const endIdx = Math.min(startIdx + itemsPerPage, results.length);
                        
                        tbody.innerHTML = '';

                        for (let i = startIdx; i < endIdx; i++) {
                            const itemData = results[i];
                            const index = i;
                            
                            const filename = typeof itemData === 'string' ? itemData : itemData.filename;
                            const extractedData = typeof itemData === 'object' ? itemData.extracted_data : null;
                            const match = filename.match(/_page_(\d+)\.png$/i);
                            const pageNum = match ? match[1] : (index + 1);

                            // Determine form type for display
                            let formTypeDisplay = '';
                            if (extractedData) {
                                let fields = extractedData.fields;
                                if (!fields && Object.keys(extractedData).length > 0) {
                                    const firstKey = Object.keys(extractedData)[0];
                                    if (extractedData[firstKey] && extractedData[firstKey].fields) {
                                        fields = extractedData[firstKey].fields;
                                    } else if (extractedData[firstKey] && extractedData[firstKey].FormType) {
                                        fields = extractedData[firstKey];
                                    }
                                }
                                if (!fields && extractedData.FormType) fields = extractedData;

                                if (fields && fields.FormType) {
                                    const ft = fields.FormType.value || fields.FormType;
                                    if (ft) formTypeDisplay = ` - ${getFriendlyFormName(ft)}`;
                                }
                            }

                            const tr = document.createElement('tr');
                            tr.style.borderBottom = '1px solid #eee';

                            // Image Cell
                            const tdImg = document.createElement('td');
                            tdImg.style.verticalAlign = 'top';
                            tdImg.style.padding = '15px';
                            tdImg.style.borderRight = '1px solid #eee';
                            
                            tdImg.innerHTML = `<div style="font-weight:bold; margin-bottom:5px;">Page ${pageNum}${formTypeDisplay}</div>`;


                            const img = document.createElement('img');
                            img.src = `/api/jobs/${encodeURIComponent(jobId)}/split_pages/${filename}`;
                            img.style.maxWidth = '100%';
                            img.style.border = '1px solid #ccc';
                            img.style.boxShadow = '0 2px 5px rgba(0,0,0,0.1)';
                            tdImg.appendChild(img);

                            // Data Cell
                            const tdData = document.createElement('td');
                            tdData.style.verticalAlign = 'top';
                            tdData.style.padding = '15px';

                            const dataWrapper = document.createElement('div');
                            dataWrapper.style.maxHeight = '1300px';
                            dataWrapper.style.overflowY = 'auto';
                            dataWrapper.style.paddingRight = '5px';
                            
                            if (extractedData) {
                                renderDrakeResultsUI(extractedData, dataWrapper);
                            } else {
                                dataWrapper.innerHTML = '<div class="text-muted">No data extracted</div>';
                            }
                            tdData.appendChild(dataWrapper);

                            tr.appendChild(tdImg);
                            tr.appendChild(tdData);
                            tbody.appendChild(tr);
                        }

                        // Update controls
                        if (totalPages > 1) {
                            const displayEl = document.getElementById('drakeSplitPageDisplay');
                            if (displayEl) displayEl.textContent = `Page ${currentPage} of ${totalPages}`;
                            
                            const prevBtn = document.getElementById('drakeSplitPrevBtn');
                            prevBtn.style.visibility = currentPage <= 1 ? 'hidden' : 'visible';
                            
                            const nextBtn = document.getElementById('drakeSplitNextBtn');
                            nextBtn.style.visibility = currentPage >= totalPages ? 'hidden' : 'visible';
                        }
                    };

                    // Attach listeners
                    if (totalPages > 1) {
                        document.getElementById('drakeSplitPrevBtn').onclick = () => renderPage(currentPage - 1);
                        document.getElementById('drakeSplitNextBtn').onclick = () => renderPage(currentPage + 1);
                    }

                    // Initial render
                    renderPage(1);

                    const skipPreview = document.getElementById('drakeSkipPreviewCheckbox')?.checked;
                    if (skipPreview) {
                        // Hide the "Extracting..." modal before starting the import process,
                        // as the import step has its own status indicator.
                        if (typeof hideDetectionModal === 'function') {
                            hideDetectionModal();
                        }
                        await runImport();
                        return;
                    }
                } else {
                    debugContainer.innerHTML = '<div class="alert alert-warning">No pages found.</div>';
                }

                // 4. Prepare the right pane
                if (drakeProcessingStatus) drakeProcessingStatus.classList.add('hidden');
                if (drakeResultsView) drakeResultsView.classList.add('hidden'); // Hide default results view
                if (drakeLaunchContainer) drakeLaunchContainer.classList.add('hidden'); // Hide "Import to Drake" for this debug view
            } else {
                const err = await response.json();
                if (typeof updateDetectionModalMessage === 'function') {
                    updateDetectionModalMessage('Extraction Failed', err.detail || 'An unknown error occurred.');
                }
                await new Promise(resolve => setTimeout(resolve, 3000)); // Longer delay for error
                alert('Error: ' + (err.detail || 'Failed to extract pages.'));
            }
        } catch (error) {
            if (typeof updateDetectionModalMessage === 'function') {
                updateDetectionModalMessage('An Error Occurred', error.message);
            }
            await new Promise(resolve => setTimeout(resolve, 3000));
            console.error('Error extracting pages:', error);
            alert('Error: ' + error.message);
        } finally {
            if (typeof hideDetectionModal === 'function') {
                hideDetectionModal();
            }
            btn.disabled = false;
            btn.textContent = originalText;
        }
        // --- End: API Call and Rendering ---
    });

    // --- Step 2: Select Form Type ---
    function checkCanExtract() {
        // 1. Check if a form type is selected in the dropdown
        const hasFormType = drakeStep2FormSelect && !!drakeStep2FormSelect.value;
    
        // 2. Check if at least one page group is selected
        let hasPageGroupSelection = false;
        const pageCheckboxes = document.querySelectorAll('.drake-page-checkbox');
        if (pageCheckboxes.length > 0) {
            // If checkboxes are visible, at least one must be checked
            hasPageGroupSelection = document.querySelectorAll('.drake-page-checkbox:checked').length > 0;
        } else {
            // If no checkboxes, we just need to have detected groups
            const allDetectedGroups = drakeSelectedGroups || JSON.parse(drakeModule.dataset.selectedGroups || '{}');
            hasPageGroupSelection = Object.keys(allDetectedGroups).length > 0;
        }
    
        // 3. Check if Client ID is entered
        const clientId = drakeClientIdInput ? drakeClientIdInput.value.trim() : '';
    
        drakeExtractBtn.disabled = !hasFormType || !hasPageGroupSelection || !clientId;
    }
    
    if (drakeStep2FormSelect) drakeStep2FormSelect.addEventListener('change', checkCanExtract);
    if (drakeClientIdInput) {
        drakeClientIdInput.addEventListener('change', checkCanExtract);
        drakeClientIdInput.addEventListener('input', checkCanExtract);
    }


    /**
     * Renders a JSON object as a readable HTML table.
     * @param {Object} data - The JSON data to render.
     * @returns {string} - HTML string.
     */
    function renderDataAsHtml(data) {
        if (!data) return '<p>No data</p>';

        let html = '';

        // Helper to render complex values recursively (Arrays, Objects, Nested Values)
        const renderComplexValue = (val, contextKey = '') => {
            if (val === null || val === undefined) return '';
            
            // Handle Array (e.g., Transactions, StateTaxesWithheld)
            if (Array.isArray(val)) {
                if (val.length === 0) return '<span style="color: #999; font-style: italic;">Empty List</span>';
                
                // Try to render as a table if items are objects
                const unwrappedItems = val.map(item => {
                    if (item && typeof item === 'object' && 'value' in item) {
                        return item.value;
                    }
                    return item;
                });

                // Check if all items are objects (and not null/arrays) to render as table
                const isListOfObjects = unwrappedItems.length > 0 && unwrappedItems.every(item => item && typeof item === 'object' && !Array.isArray(item));

                // Render as table, unless it's 'clients' (user requested key-value style for clients)
                if (isListOfObjects && contextKey !== 'clients') {
                     // Collect all unique keys
                    const allKeys = new Set();
                    unwrappedItems.forEach(item => {
                        Object.keys(item).forEach(k => {
                            if (!k.startsWith('_')) allKeys.add(k);
                        });
                    });

                    if (allKeys.size > 0) {
                        const headers = Array.from(allKeys);
                        let tableHtml = '<div style="overflow-x: auto; margin-top: 5px; border: 1px solid #e0e0e0; border-radius: 4px;">';
                        tableHtml += '<table style="width: 100%; font-size: 13px; background: #fff; border-collapse: collapse;">';
                        
                        // Header
                        tableHtml += '<thead style="background-color: #f5f5f5;"><tr>';
                        headers.forEach(header => {
                            tableHtml += `<th style="text-align: left; padding: 6px 8px; border-bottom: 1px solid #ddd; color: #555; font-weight: 600; white-space: nowrap;">${header}</th>`;
                        });
                        tableHtml += '</tr></thead>';
                        
                        // Body
                        tableHtml += '<tbody>';
                        unwrappedItems.forEach((item, idx) => {
                            const bg = idx % 2 === 0 ? '#fff' : '#f9f9f9';
                            tableHtml += `<tr style="background-color: ${bg};">`;
                            headers.forEach(key => {
                                let cellVal = item[key];
                                // Unwrap value if needed
                                if (cellVal && typeof cellVal === 'object' && 'value' in cellVal) {
                                    cellVal = cellVal.value;
                                }
                                const displayVal = renderComplexValue(cellVal, key);
                                tableHtml += `<td style="padding: 6px 8px; border-bottom: 1px solid #eee; vertical-align: top;">${displayVal}</td>`;
                            });
                            tableHtml += '</tr>';
                        });
                        tableHtml += '</tbody></table></div>';
                        return tableHtml;
                    }
                }

                let arrayHtml = '<div style="display: flex; flex-direction: column; gap: 10px; margin-top: 5px;">';
                val.forEach((item, idx) => {
                    arrayHtml += `<div style="border: 1px solid #e0e0e0; padding: 8px; background-color: #f9f9f9; border-radius: 4px;">`;
                    
                    // Unwrap 'value' if it exists on the item (common in this JSON structure)
                    let itemVal = item;
                    if (item && typeof item === 'object' && 'value' in item) {
                        itemVal = item.value;
                    }
                    
                    arrayHtml += renderComplexValue(itemVal);
                    arrayHtml += `</div>`;
                });
                arrayHtml += '</div>';
                return arrayHtml;
            }
            
            // Handle Object
            if (typeof val === 'object') {
                // Render as table
                let tableHtml = '<table style="width: 100%; font-size: 13px; background: transparent; border-collapse: collapse;">';
                let hasProps = false;
                for (const subKey in val) {
                    if (Object.prototype.hasOwnProperty.call(val, subKey)) {
                        // Skip internal keys
                        if (subKey.startsWith('_')) continue;
                        hasProps = true;
                        
                        let subVal = val[subKey];
                        
                        // Unwrap 'value' property if it exists (e.g. Box1a: { value: 1180 })
                        if (subVal && typeof subVal === 'object' && 'value' in subVal) {
                             subVal = subVal.value;
                        }

                        let displaySubVal = renderComplexValue(subVal, subKey);

                        tableHtml += `<tr>
                            <td style="color: #666; padding: 3px 10px 3px 0; width: 40%; vertical-align: top; border-bottom: 1px solid #eee; font-weight: 500;">${subKey}:</td>
                            <td style="padding: 3px 0; vertical-align: top; border-bottom: 1px solid #eee;">${displaySubVal}</td>
                        </tr>`;
                    }
                }
                tableHtml += '</table>';
                if (!hasProps) return JSON.stringify(val);
                return tableHtml;
            }
            
            return String(val);
        };

        // Helper to render a single table for a dictionary of fields
        const renderTable = (fields, title) => {
            let tableHtml = `<div class="result-section" style="margin-bottom: 20px; border: 1px solid #e0e0e0; border-radius: 5px; overflow: hidden;">`;
            if (title) {
                tableHtml += `<div style="background-color: #f5f5f5; padding: 10px; font-weight: bold; border-bottom: 1px solid #e0e0e0; color: #333;">${title}</div>`;
            }
            tableHtml += `<table style="width: 100%; border-collapse: collapse; font-size: 14px;">`;
            tableHtml += `<thead style="background-color: #fafafa;"><tr><th style="text-align: left; padding: 8px; border-bottom: 1px solid #eee; width: 35%; color: #555;">Field Name</th><th style="text-align: left; padding: 8px; border-bottom: 1px solid #eee; color: #555;">Extracted Value</th></tr></thead>`;
            tableHtml += `<tbody>`;

            let hasRows = false;
            for (const key in fields) {
                if (Object.prototype.hasOwnProperty.call(fields, key)) {
                    // Skip internal keys if any
                    if (key.startsWith('_')) continue;

                    const val = fields[key];
                    let displayVal = val;

                    // Handle object with 'value' property
                    if (val && typeof val === 'object' && val !== null) {
                        if ('value' in val) {
                            displayVal = renderComplexValue(val.value, key);
                        } else {
                            displayVal = renderComplexValue(val, key);
                        }
                    } else {
                        displayVal = renderComplexValue(val, key);
                    }

                    // Special handling for complex objects to show the field name as a header
                    if (key === 'Payer' || key === 'Recipient' || key === 'TaxInfos' || key === 'Employer' || key === 'Employee' || key === 'Beneficiary') {
                        tableHtml += `<tr>
                            <td colspan="2" style="padding: 10px 8px 5px 8px; border-bottom: none; font-weight: bold; color: #555; background-color: #f9f9f9;">${key}</td>
                        </tr>
                        <tr>
                            <td colspan="2" style="padding: 0 8px 10px 8px; border-bottom: 1px solid #eee;">${displayVal !== null && displayVal !== undefined ? displayVal : ''}</td>
                        </tr>`;
                    } else {
                        tableHtml += `<tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; color: #333; font-weight: 500; vertical-align: top;">${key}</td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; color: #555; vertical-align: top;">${displayVal !== null && displayVal !== undefined ? displayVal : null}</td>
                        </tr>`;
                    }
                    hasRows = true;
                }
            }
            
            if (!hasRows) {
                tableHtml += `<tr><td colspan="2" style="padding: 8px; text-align: center; color: #999;">No fields found</td></tr>`;
            }

            tableHtml += `</tbody></table></div>`;
            return tableHtml;
        };

        // Check for standard structure (fields / models)
        let rendered = false;
        if (data.fields) {
            html += renderTable(data.fields, 'Extracted Fields');
            rendered = true;
        }
        
        if (data.models) {
            for (const [modelName, modelData] of Object.entries(data.models)) {
                if (modelData.fields) {
                    html += renderTable(modelData.fields, `Model: ${modelName}`);
                    rendered = true;
                }
            }
        }

        // Fallback: if no standard structure detected, try to render the root object
        if (!rendered) {
            // Check if it looks like a flat object of fields
            if (typeof data === 'object' && data !== null) {
                html += renderTable(data, 'Data');
            }
        }

        return html;
    }

    /**
     * Fetches the final JSON results and displays them in an accordion.
     * @param {string} jobId The ID of the completed job.
     */
    async function fetchAndDisplayDrakeResults(jobId) {
        try {
            const response = await fetch(`/api/jobs/${jobId}/results?raw=true`);
            if (!response.ok) throw new Error('Failed to fetch results.');
            const rawResultsContainer = await response.json();

            // The raw result is an array of objects with filename and data
            if (!Array.isArray(rawResultsContainer) || rawResultsContainer.length === 0) {
                throw new Error('No raw result files found in the job output.');
            }
            
            // Filter for merged files (e.g. W2_merged.json, 1099SSA_merged.json)
            // or fallback to any JSON if no merged files found.
            let targetItems = rawResultsContainer.filter(item => item.filename.toLowerCase().includes('merged'));
            if (targetItems.length === 0) {
                targetItems = [rawResultsContainer[0]];
            }

            // Clear container once before appending
            drakeAccordionContainer.innerHTML = '';
            drakeResults = [];

            // Render each file
            for (const item of targetItems) {
                const results = item.data;
                drakeResults.push(results); // Store results for launch
                renderDrakeResultsUI(results, drakeAccordionContainer, item.filename);
            }

            if (drakeProcessingStatus) drakeProcessingStatus.classList.add('hidden');
            if (drakeResultsView) drakeResultsView.classList.remove('hidden');
            if (drakeLaunchContainer) drakeLaunchContainer.classList.remove('hidden');
            
            if (launchDrakeBtn) launchDrakeBtn.disabled = false;

            // Reset Step 2 UI for a potential new run
            drakeUploadStatus.classList.add('hidden');
            drakePdfFrame.style.display = 'block';
            drakeExtractBtn.disabled = false;

        } catch (error) {
            console.error('Error displaying results:', error);
            // Show error in Step 3
            drakeProcessingStatus.innerHTML = `<p class="status-message status-error">Error displaying results: ${error.message}</p>`;
            drakeProcessingStatus.classList.remove('hidden');
        }
    }

    // --- Step 3: Import to Drake ---
    if (launchDrakeBtn) {
        launchDrakeBtn.addEventListener('click', async () => {
            // Navigate to Step 4 to show the import status
            goToDrakeStep(4);

            // Show "in progress" message immediately
            drakeImportStatus.innerHTML = `<div class="spinner"></div><p>Drake automation in progress... Please check the Drake software window.</p>`;
            drakeImportStatus.classList.remove('hidden');

            // Attempt to launch the local Drake software
            await openDrakeSoftware();
        });
    }

/**
 * Renders the Drake results JSON into a structured UI with Accordions and Tables.
 * @param {Object} json - The extracted JSON data.
 * @param {HTMLElement} container - The container to render into.
 * @param {string} filename - The filename associated with the data.
 */
function renderDrakeResultsUI(json, container, filename) {
    // container.innerHTML = ''; // Removed to allow appending multiple forms
    
    if (filename) {
            container.innerHTML += `<div style="margin-bottom: 15px; font-weight: bold; font-size: 1.1em; color: #555;">File: ${filename}</div>`;
    }

    // Normalize structure: find 'fields'
    let fields = json.fields;
    if (!fields && Object.keys(json).length > 0) {
        const firstKey = Object.keys(json)[0];
        if (json[firstKey] && json[firstKey].fields) {
            fields = json[firstKey].fields;
        } else if (json[firstKey] && (json[firstKey].FormType || json[firstKey].TaxYear || json[firstKey].Employer || json[firstKey].Payer || json[firstKey].Recipient || json[firstKey].Employee)) {
            // The first key contains the fields directly (e.g. { "Form_W2": { ...fields... } })
            fields = json[firstKey];
        }
    }
    
    // Fallback: if json itself looks like the fields object (has common keys)
    if (!fields && (json.FormType || json.TaxYear || json.Payer || json.Employer || json.Recipient || json.Employee)) {
        fields = json;
    }

    if (!fields) {
        container.innerHTML += '<div class="alert alert-warning">Could not find structured data fields.</div><pre style="background: #f5f5f5; padding: 15px;">' + JSON.stringify(json, null, 2) + '</pre>';
        return;
    }

    const data = deepUnwrap(fields);

    // 1. Header Info (Table View)
    const headerData = {
        "Form Type": data.FormType,
        "Tax Year": data.TaxYear,
    };

    const headerHtml = `
        <div class="card mb-4 shadow-sm border-0">
            <div class="card-header bg-white border-bottom px-4 py-3">
                <h4 class="mb-0 fw-bold text-uppercase text-muted">
                    Form Information
                </h4>
            </div>

            <div class="card-body px-3 pb-3 pt-2">
                ${renderKeyValueTable(headerData)}
            </div>
        </div>
    `;
    container.innerHTML += headerHtml;

    // 2. Payer / Employer (Card View)
    const payerData = data.Payer || data.Employer;
    if (payerData) {
        const title = data.Employer ? "Employer Information" : "Payer Information";
        container.innerHTML += createSectionCard(title, renderKeyValueTable(payerData));
    }

    // 3. Recipient / Employee (Card View)
    const recipientData = data.Recipient || data.Employee || data.Beneficiary;
    if (recipientData) {
        let title = "Recipient Information";
        if (data.Employee) title = "Employee Information";
        if (data.Beneficiary) title = "Beneficiary Information";
        container.innerHTML += createSectionCard(title, renderKeyValueTable(recipientData));
    }

    // 4. Entries (Accordion for complex data)
    const entries = data.Entries;
    if (entries) {
        const accordionId = 'drakeResultsAccordion';
        const accordion = document.createElement('div');
        accordion.className = 'accordion';
        accordion.id = accordionId;

        let entriesHtml = '';
        const scalarData = {};
        const listData = {};
        
        for (const [key, val] of Object.entries(entries)) {
            if (Array.isArray(val)) {
                // Check if array contains objects or primitives (e.g. box7 in 1099R is ["7", "A"])
                const isPrimitiveArray = val.length > 0 && val.every(item => typeof item !== 'object' || item === null);
                
                if (isPrimitiveArray) {
                    scalarData[key] = val.filter(v => v !== null && v !== undefined).join(' | ');
                } else {
                    listData[key] = val;
                }
            } else {
                scalarData[key] = val;
            }
        }
        
        if (Object.keys(scalarData).length > 0) {
            // Sort keys naturally (box1, box2, box10...)
            const sortedScalar = {};
            Object.keys(scalarData).sort(new Intl.Collator(undefined, {numeric:true, sensitivity:'base'}).compare).forEach(key => {
                sortedScalar[key] = scalarData[key];
            });

            entriesHtml += `
                <div class="card mb-3 shadow-sm border-0">
                    <div class="card-header bg-white border-bottom px-4 py-2">
                        <h4 class="mb-0 fw-bold text-uppercase text-dark">Income & Tax Details</h4>
                    </div>
                    <div class="card-body p-3">
                        ${renderKeyValueTable(sortedScalar)}
                    </div>
                </div>`;
        }
        
        // If backend has separated tax infos, remove the combined TaxInfos to prevent duplication
        if (listData.StateTaxInfos || listData.LocalTaxInfos) {
            delete listData.TaxInfos;
        }

        for (const [key, list] of Object.entries(listData)) {
            entriesHtml += renderDataTable(key, list);
        }
        
        if (entriesHtml) {
            accordion.appendChild(createAccordionItem(accordionId, 'Entries', '', entriesHtml, true));
            container.appendChild(accordion);
        }
    }
}
function createSectionCard(title, content) {
    return `
        <div class="card mb-4 shadow-sm border-0">
            <div class="card-header bg-white border-bottom px-4 py-3">
                <h4 class="fw-bold text-primary mb-0">
                    <i class="bi bi-person-lines-fill me-2"></i>${title}
                </h4>
            </div>
            <div class="card-body px-3 pb-3 pt-2">
                ${content}
            </div>
        </div>
    `;
}

function createAccordionItem(parentId, idSuffix, title, content, isOpen) {
    const item = document.createElement('div');
    item.className = 'accordion-item mb-2 border';
    const showClass = isOpen ? 'show' : '';
    const collapsedClass = isOpen ? '' : 'collapsed';
    
    item.innerHTML = `
        <div id="collapse${idSuffix}" class="accordion-collapse collapse ${showClass}" aria-labelledby="heading${idSuffix}" data-bs-parent="#${parentId}">
            <div class="accordion-body">
                ${content}
            </div>
        </div>
    `;
    return item;
}

function renderKeyValueTable(data) {
    if (!data || Object.keys(data).length === 0) {
        return `<div class="text-muted fst-italic px-4 py-3">No data</div>`;
    }

    let rows = '';
    let rowIndex = 0;
    for (const [key, val] of Object.entries(data)) {
        let displayKey = key;
        let displayVal = val;

        if (val && typeof val === 'object' && val !== null && 'value' in val && 'label' in val) {
            displayKey = val.label;
            displayVal = val.value;
        }

        const bg = rowIndex % 2 === 0 ? '#fff' : '#fafafa';
        rows += `
            <tr style="background-color: ${bg};">
                <td style="padding: 8px 12px; border-right: 1px solid #e0e0e0; border-bottom: 1px solid #e0e0e0; width: 50%; color: #000;">
                    ${displayKey}
                </td>
                <td style="padding: 8px 12px; border-right: 1px solid #e0e0e0; border-bottom: 1px solid #e0e0e0; font-family: 'Consolas', monospace; color: #000; text-align: right;">
                    ${displayVal ?? ''}
                </td>
            </tr>
        `;
        rowIndex++;
    }

    return `
        <div class="table-responsive" style="border: 1px solid #d0d7e5; border-radius: 4px;">
            <table class="table mb-0" style="width: 100%; border-collapse: collapse;">
                <thead style="background-color: #f2f2f2; border-bottom: 2px solid #d0d7e5;">
                    <tr>
                        <th style="padding: 8px 12px; text-align: left; font-weight: 700; color: #000; border-right: 1px solid #d0d7e5;">Description</th>
                        <th style="padding: 8px 12px; text-align: right; font-weight: 700; color: #000;">Value</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        </div>
    `;
}


function renderDataTable(title, list) {
    if (!list || list.length === 0) return '';
    
    const firstItem = list[0];
    if (typeof firstItem !== 'object') return '';

    // Format title for display
    let displayTitle = title;
    if (title === 'box12') displayTitle = 'Box 12';
    else if (title === 'TaxInfos') displayTitle = 'State & Local Tax Info';
    else if (title === 'StateTaxInfos') displayTitle = 'State Tax Info';
    else if (title === 'LocalTaxInfos') displayTitle = 'Local Tax Info';
    else displayTitle = title.replace(/([A-Z])/g, ' $1').trim();
    
    const columns = Object.keys(firstItem);
    let thead = '<thead style="background-color: #f2f2f2; border-bottom: 2px solid #d0d7e5;"><tr>';
    columns.forEach(col => {
        let headerName = col;
        const val = firstItem[col];
        if (val && typeof val === 'object' && val !== null && 'label' in val) {
            headerName = val.label;
        }
        thead += `<th style="padding: 8px 12px; text-align: left; font-weight: 700; color: #333; border-right: 1px solid #d0d7e5; white-space: nowrap;">${headerName}</th>`;
    });
    thead += '</tr></thead>';
    
    let tbody = '<tbody>';
    list.forEach((row, rowIndex) => {
        const bg = rowIndex % 2 === 0 ? '#fff' : '#fafafa';
        tbody += `<tr style="background-color: ${bg};">`;
        columns.forEach(col => {
            let cellVal = row[col];
            if (cellVal && typeof cellVal === 'object' && cellVal !== null && 'value' in cellVal && 'label' in cellVal) {
                cellVal = cellVal.value;
            }
            tbody += `<td style="padding: 6px 12px; border-right: 1px solid #e0e0e0; border-bottom: 1px solid #e0e0e0; font-family: 'Consolas', monospace; color: #000;">${cellVal !== undefined && cellVal !== null ? cellVal : ''}</td>`;
        });
        tbody += '</tr>';
    });
    tbody += '</tbody>';

    return `
        <div class="card mb-3 shadow-sm border-0">
            <div class="card-header bg-white border-bottom px-4 py-2">
                <h4 class="mb-0 fw-bold text-uppercase text-dark">${displayTitle}</h4>
            </div>
            <div class="table-responsive" style="overflow-x: auto; border: 1px solid #d0d7e5; border-radius: 0 0 4px 4px;">
                <table class="table mb-0" style="min-width: 100%; border-collapse: collapse;">${thead}${tbody}</table>
            </div>
        </div>`;
}

function renderVerticalDataTable(title, list) {
    if (!list || list.length === 0) return '';

    let itemsHtml = '';
    list.forEach((item, index) => {
        itemsHtml += `
            <div class="mb-4 border rounded shadow-sm overflow-hidden">
                <div class="bg-light px-3 py-2 border-bottom d-flex justify-content-between align-items-center">
                    <span class="fw-bold text-primary small text-uppercase">${title} Record #${index + 1}</span>
                </div>
                ${renderKeyValueTable(item)}
            </div>
        `;
    });

    return `
        <div class="card mb-3 shadow-sm border-0">
            <div class="card-header bg-white border-bottom px-4 py-2">
                <h6 class="mb-0 fw-bold text-uppercase text-dark">${title}</h6>
            </div>
            <div class="card-body p-3">
                ${itemsHtml}
            </div>
        </div>`;
}

function deepUnwrap(data) {
    if (data === null || data === undefined) return "";
    if (typeof data === 'object' && data !== null && 'value' in data && 'label' in data) {
        const val = deepUnwrap(data.value);
        return { value: val, label: data.label };
    }
    if (typeof data === 'object' && data !== null && 'value' in data) {
        return deepUnwrap(data.value);
    }
    if (Array.isArray(data)) {
        return data.map(item => deepUnwrap(item));
    }
    if (typeof data === 'object') {
        const result = {};
        for (const key in data) {
            result[key] = deepUnwrap(data[key]);
        }
        return result;
    }
    return data;
}

    // --- Client Tax Return Module ---
    // Query button logic moved to ClientTableManager in client_table.js

    function renderClientTable(clients) {
        if (typeof clientTableMgr !== 'undefined' && clientTableMgr) {
            clientTableMgr.setClients(clients);
        }
    }
});
