/**
 * API calls and data fetching
 */

/**
 * Load page groups for the selected form type and run automated page detection
 * @returns {Promise<void>}
 */
async function loadPageGroups() {
    try {
        // Step 1: Fetch page groups configuration
        const response = await fetch(`${API_BASE}/forms/${selectedFormType}/page-groups`);
        if (!response.ok) {
            throw new Error(`Failed to load page groups: ${response.status} ${response.statusText}`);
        }
        const data = await response.json();
        if (!data || !data.page_groups) {
            throw new Error('Invalid response format: missing page_groups');
        }
        availablePageGroups = data.page_groups;
        if (!Array.isArray(availablePageGroups)) {
            throw new Error('Invalid response format: page_groups is not an array');
        }
        
        // Step 2: Run automated page detection
        console.log('[Page Detection] Starting page detection for form type:', selectedFormType);
        
        // Show detection modal
        showDetectionModal('Analyzing PDF document with OCR to automatically detect page numbers...');
        updateFileInfo(currentFileName, 'Detecting pages...');
        
        try {
            const detectionResult = await detectPages(currentJobId, selectedFormType);
            detectedPageGroups = detectionResult.detected_groups || {};
            
            if (detectionResult.error) {
                console.warn('[Page Detection] Detection had error:', detectionResult.error);
                // Update modal message for error case
                updateDetectionModalMessage(
                    'Page detection completed with some issues.',
                    'Some pages may need to be entered manually.'
                );
                // Wait a moment before hiding
                await new Promise(resolve => setTimeout(resolve, 1500));
            } else if (Object.keys(detectedPageGroups).length > 0) {
                // Success - detected pages
                updateDetectionModalMessage(
                    'Page detection completed successfully!',
                    'Page numbers have been automatically detected from OCR data. You can review and modify them if needed.'
                );
                await new Promise(resolve => setTimeout(resolve, 2000));
            } else {
                // No pages detected
                updateDetectionModalMessage(
                    'Could not automatically detect page numbers from OCR data.',
                    'Please enter the page numbers manually below.'
                );
                await new Promise(resolve => setTimeout(resolve, 2000));
            }
            
            console.log('[Page Detection] Detected groups:', detectedPageGroups);
        } catch (detectionError) {
            console.warn('[Page Detection] Failed to detect pages:', detectionError);
            detectedPageGroups = {}; // Empty object indicates detection was attempted but failed
            updateDetectionModalMessage(
                'Page detection encountered an error.',
                'Please enter the page numbers manually below.'
            );
            await new Promise(resolve => setTimeout(resolve, 2000));
        } finally {
            // Hide modal
            hideDetectionModal();
            updateFileInfo(currentFileName, 'Ready');
        }
        
        // Step 3: Display page groups with detected values
        displayPageGroups(detectedPageGroups);
        
    } catch (error) {
        console.error('Error loading page groups:', error);
        alert(`Error loading page groups: ${error.message}`);
        availablePageGroups = []; // Set to empty array to prevent further errors
        detectedPageGroups = null; // Reset detection
    }
}

/**
 * Detect pages using automated OCR analysis for the uploaded PDF
 * @param {string} jobId - The job ID from upload
 * @param {string} formType - The selected form type
 * @returns {Promise<Object>} - Detection result with detected_groups
 */
async function detectPages(jobId, formType) {
    try {
        const formData = new FormData();
        formData.append('form_type', formType);
        
        const response = await fetch(`${API_BASE}/jobs/${jobId}/detect-pages`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `Detection failed: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('[Page Detection] Result:', data);
        
        return data;
    } catch (error) {
        console.error('[Page Detection] Error:', error);
        // Return empty result on error - UI will fall back to defaults
        return {
            detected_groups: {},
            error: error.message,
            message: 'Page detection failed, using default pages'
        };
    }
}

/**
 * Poll for job results
 * @returns {Promise<void>}
 */
async function pollForResults() {
    console.log('[POLL] 🔄 Starting result polling...');
    const maxAttempts = 400; // Increased from 60 to allow up to 10 minutes of processing time
    let attempts = 0;

    const poll = async () => {
        try {
            console.log(`[POLL] Attempt ${attempts + 1}/${maxAttempts}: Checking job status...`);
            const jobInfo = await fetch(`${API_BASE}/jobs/${currentJobId}`).then(r => r.json());
            if (jobInfo && jobInfo.queue_empty === true) {
                console.warn('[POLL] No active background jobs remain. Stopping polling.');
                updateFileInfo(currentFileName || jobInfo.filename || 'File', 'Idle');
                return;
            }
            
            console.log('[POLL] Job status:', jobInfo.status);
            
            // Update filename from job info if available
            if (jobInfo.filename && !currentFileName) {
                currentFileName = jobInfo.filename;
                updateFileInfo(currentFileName, jobInfo.status === 'completed' ? 'Completed' : 
                             jobInfo.status === 'failed' ? 'Failed' : 'Processing...');
            }
            
            if (jobInfo.status === 'completed') {
                console.log('%c✅ [POLL] Job COMPLETED!', 'color: #28a745; font-weight: bold; font-size: 1.1em');
                
                if (jobInfo.execution_stats) {
                    const stats = jobInfo.execution_stats;
                    console.log('%c⏱️ OCR Execution Stats:', 'color: #0d6efd; font-weight: bold;');
                    console.log(`   - Total Pipeline Time: ${stats.total_time.toFixed(2)}s`);
                    console.log(`   - Azure Analysis Time: ${stats.azure_analysis_time.toFixed(2)}s`);
                    console.log(`   - PDF Splitting Time: ${stats.split_time.toFixed(2)}s`);
                }
                
                const processingStatus = document.getElementById('processingStatus');
                if (processingStatus) processingStatus.classList.add('hidden');
                updateFileInfo(currentFileName || jobInfo.filename || 'File', 'Completed');
                console.log('[POLL] Displaying results...');
                await displayResults();
                return;
            } else if (jobInfo.status === 'failed') {
                console.error('%c❌ [POLL] Job FAILED!', 'color: #dc3545; font-weight: bold; font-size: 1.1em');
                updateFileInfo(currentFileName || jobInfo.filename || 'File', 'Failed');
                throw new Error(jobInfo.error || 'Processing failed');
            } else {
                // Update status while processing
                console.log('[POLL] Still processing... Updated status at attempt', attempts + 1);
                updateFileInfo(currentFileName || jobInfo.filename || 'File', 'Processing...');
            }

            attempts++;
            if (attempts < maxAttempts) {
                setTimeout(poll, 2000);
            } else {
                throw new Error('Processing timeout');
            }
        } catch (error) {
            document.getElementById('processingStatus').innerHTML = 
                `<div class="status-message status-error">Error: ${error.message}</div>`;
        }
    };

    poll();
}

/**
 * Display results in accordion format
 * @returns {Promise<void>}
 */
async function displayResults() {
    try {
        console.log('%c📊 [DISPLAY] Starting results display...', 'color: #6C63FF; font-weight: bold; font-size: 1.1em');
        const response = await fetch(`${API_BASE}/jobs/${currentJobId}/results/with-bounding-boxes`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        console.log('[DISPLAY] ✅ Results fetched successfully. Keys:', Object.keys(data));
        console.log('[DISPLAY] Results data:', data);

        const accordionContainer = document.getElementById('accordionContainer');
        if (!accordionContainer) {
            throw new Error('Accordion container not found');
        }
        accordionContainer.innerHTML = '';

        // First, ensure Excel file is generated
        const jobId = currentJobId;
        if (!jobId) {
            throw new Error('Job ID not found');
        }
        
        console.log('[DISPLAY] Generating Excel file...');
        // Generate Excel file (this will be cached on server)
        try {
            await fetch(`${API_BASE}/jobs/${jobId}/excel`);
            console.log('[DISPLAY] ✅ Excel file generated');
        } catch (error) {
            console.warn('[DISPLAY] ⚠️ Excel generation warning:', error);
            // Continue even if Excel generation fails
        }
        
        // Get Excel file URL for viewing
        const excelViewUrl = `${API_BASE}/jobs/${jobId}/excel/view`;

        // Process results and create accordion sections
        const sections = [];
        let isFirstSection = true;

        if (!data.results || Object.keys(data.results).length === 0) {
            accordionContainer.innerHTML = '<div class="status-message status-info">No results found. Please check if processing completed successfully.</div>';
            document.getElementById('resultsView').classList.remove('hidden');
            return;
        }

        // Define sort order for groups (Form 1065 first, then Schedule_M_L)
        const groupOrder = ['Form_1065', 'Schedule_M_L', 'Schedule_M_L_1120', 'Form_1120'];
        
        // Define sort order for models within Schedule_M_L group
        const modelOrder = [
            'Train_model_1065_v4',           // Form 1065
            'Train_1065_schedule_L_v4', // Schedule L
            'Train_1065_schedule_m1_v2', // Schedule M-1
            'Train_1065_schedule_m2_v3', // Schedule M-2
            'Train_1120_v2',           // Form 1120
            'Train_1120_schedule_L_v3', // Schedule L
            'Train_1120_schedule_M1_v2', // Schedule M-1
            'Train_1120_schedule_M2_v3'  // Schedule M-2
        ];

        // Sort groups according to groupOrder
        const sortedGroups = Object.entries(data.results).sort(([nameA], [nameB]) => {
            const indexA = groupOrder.indexOf(nameA);
            const indexB = groupOrder.indexOf(nameB);
            // If both are in the order list, sort by their position
            if (indexA !== -1 && indexB !== -1) return indexA - indexB;
            // If only A is in the list, A comes first
            if (indexA !== -1) return -1;
            // If only B is in the list, B comes first
            if (indexB !== -1) return 1;
            // If neither is in the list, maintain original order
            return 0;
        });

        for (const [groupName, groupData] of sortedGroups) {
            // Skip metadata fields
            if (groupName.startsWith('_')) continue;

            // Debug logging for 1099-MISC
            if (groupName.includes('1099MISC') || groupName.includes('1099-MISC')) {
                console.log('Processing 1099-MISC group:', groupName, groupData);
            }

            // Handle separate state_taxes_withheld groups (e.g., Form_1099MISC_state_taxes_withheld)
            if (groupName.endsWith('_state_taxes_withheld')) {
                const baseGroupName = groupName.replace('_state_taxes_withheld', '');
                let formType = null;
                
                if (baseGroupName === 'Form_1099DIV') {
                    formType = '1099-DIV';
                } else if (baseGroupName === 'Form_1099INT') {
                    formType = '1099-INT';
                } else if (baseGroupName === 'Form_1099MISC') {
                    formType = '1099-MISC';
                } else if (baseGroupName === 'Form_1099NEC') {
                    formType = '1099-NEC';
                }
                
                if (formType && groupData && Array.isArray(groupData)) {
                    // groupData is an array of field objects, convert to expected structure
                    const stateTaxesData = {
                        rows: groupData.map(item => {
                            // Convert field structure to row structure
                            const row = {};
                            if (formType === '1099-MISC' || formType === '1099-NEC') {
                                row.StateTaxWithheld = item.StateTaxWithheld || item.value || '';
                                row.StateIdentificationNumber = item.StateIdentificationNumber || '';
                                row.StateIncome = item.StateIncome || '';
                            } else {
                                row.State = item.State || '';
                                row.StateIdentificationNumber = item.StateIdentificationNumber || '';
                                row.StateTaxWithheld = item.StateTaxWithheld || item.value || '';
                            }
                            return row;
                        }),
                        fields: (formType === '1099-MISC' || formType === '1099-NEC')
                            ? ['StateTaxWithheld', 'StateIdentificationNumber', 'StateIncome']
                            : ['State', 'StateIdentificationNumber', 'StateTaxWithheld']
                    };
                    
                    const previewUrl = data.group_previews && data.group_previews[baseGroupName] 
                        ? data.group_previews[baseGroupName] 
                        : null;
                    const stateTaxesSection = createStateTaxesWithheldSection(
                        stateTaxesData,
                        previewUrl,
                        excelViewUrl,
                        isFirstSection,
                        formType
                    );
                    if (stateTaxesSection) {
                        sections.push(stateTaxesSection);
                        isFirstSection = false;
                    }
                } else if (formType && groupData && typeof groupData === 'object' && groupData.rows) {
                    // Already in the correct structure
                    const previewUrl = data.group_previews && data.group_previews[baseGroupName] 
                        ? data.group_previews[baseGroupName] 
                        : null;
                    const stateTaxesSection = createStateTaxesWithheldSection(
                        groupData,
                        previewUrl,
                        excelViewUrl,
                        isFirstSection,
                        formType
                    );
                    if (stateTaxesSection) {
                        sections.push(stateTaxesSection);
                        isFirstSection = false;
                    }
                }
                continue; // Skip normal processing for these special groups
            }

            const previewUrl = data.group_previews && data.group_previews[groupName] ? data.group_previews[groupName] : null;
            const sectionTitle = GROUP_DISPLAY_NAMES[groupName] || groupName;

            // Check if this group has models (like pages_13)
            if (groupData.models) {
                // Sort models according to modelOrder
                const sortedModels = Object.entries(groupData.models).sort(([modelIdA], [modelIdB]) => {
                    const indexA = modelOrder.indexOf(modelIdA);
                    const indexB = modelOrder.indexOf(modelIdB);
                    // If both are in the order list, sort by their position
                    if (indexA !== -1 && indexB !== -1) return indexA - indexB;
                    // If only A is in the list, A comes first
                    if (indexA !== -1) return -1;
                    // If only B is in the list, B comes first
                    if (indexB !== -1) return 1;
                    // If neither is in the list, maintain original order
                    return 0;
                });

                // Display each model as a separate accordion section
                for (const [modelId, modelData] of sortedModels) {
                    if (modelData && modelData.fields) {
                        const modelTitle = MODEL_DISPLAY_NAMES[modelId] || modelId;
                        console.log(`Model ID: ${modelId}, Display Name: ${modelTitle}, Available mappings:`, Object.keys(MODEL_DISPLAY_NAMES));
                        // Get sheet name for this model
                        const sheetName = modelTitle;
                        const section = createAccordionSection(
                            modelTitle,
                            previewUrl,
                            excelViewUrl,
                            sheetName,
                            isFirstSection
                        );
                        sections.push(section);
                        isFirstSection = false;
                    }
                    
                    // Check for state_local_taxes data in this model
                    if (modelData && modelData.state_local_taxes) {
                        const stateLocalSection = createStateLocalTaxesSection(
                            modelData.state_local_taxes,
                            previewUrl,
                            excelViewUrl,
                            isFirstSection
                        );
                        if (stateLocalSection) {
                            sections.push(stateLocalSection);
                            isFirstSection = false;
                        }
                    }
                    // Check for 1099-DIV state taxes withheld in this model
                    if (modelData && modelData.state_taxes_withheld && modelId === 'prebuilt-tax.us.1099DIV') {
                        const stateTaxesSection = createStateTaxesWithheldSection(
                            modelData.state_taxes_withheld,
                            previewUrl,
                            excelViewUrl,
                            isFirstSection,
                            '1099-DIV'
                        );
                        if (stateTaxesSection) {
                            sections.push(stateTaxesSection);
                            isFirstSection = false;
                        }
                    }
                    // Check for 1099-INT state taxes withheld in this model
                    if (modelData && modelData.state_taxes_withheld && modelId === 'prebuilt-tax.us.1099INT') {
                        const stateTaxesSection = createStateTaxesWithheldSection(
                            modelData.state_taxes_withheld,
                            previewUrl,
                            excelViewUrl,
                            isFirstSection,
                            '1099-INT'
                        );
                        if (stateTaxesSection) {
                            sections.push(stateTaxesSection);
                            isFirstSection = false;
                        }
                    }
                    // Check for 1099-MISC state taxes withheld in this model
                    if (modelData && modelId === 'prebuilt-tax.us.1099MISC') {
                        console.log('Found 1099-MISC model, checking state_taxes_withheld:', modelData.state_taxes_withheld);
                        if (modelData.state_taxes_withheld) {
                            const stateTaxesSection = createStateTaxesWithheldSection(
                                modelData.state_taxes_withheld,
                                previewUrl,
                                excelViewUrl,
                                isFirstSection,
                                '1099-MISC'
                            );
                            if (stateTaxesSection) {
                                sections.push(stateTaxesSection);
                                isFirstSection = false;
                            } else {
                                console.warn('createStateTaxesWithheldSection returned null for 1099-MISC');
                            }
                        } else {
                            console.log('No state_taxes_withheld found in 1099-MISC model data');
                        }
                    }
                    // Check for 1099-NEC state taxes withheld in this model
                    if (modelData && modelId === 'prebuilt-tax.us.1099NEC') {
                        if (modelData.state_taxes_withheld) {
                            const stateTaxesSection = createStateTaxesWithheldSection(
                                modelData.state_taxes_withheld,
                                previewUrl,
                                excelViewUrl,
                                isFirstSection,
                                '1099-NEC'
                            );
                            if (stateTaxesSection) {
                                sections.push(stateTaxesSection);
                                isFirstSection = false;
                            }
                        }
                    }
                    // Check for 1099-R state taxes withheld in this model
                    if (modelData && modelId === 'prebuilt-tax.us.1099R') {
                        if (modelData.state_taxes_withheld) {
                            const stateTaxesSection = createStateTaxesWithheldSection(
                                modelData.state_taxes_withheld,
                                previewUrl,
                                excelViewUrl,
                                isFirstSection,
                                '1099-R'
                            );
                            if (stateTaxesSection) {
                                sections.push(stateTaxesSection);
                                isFirstSection = false;
                            }
                        }
                        // Check for 1099-R local taxes withheld in this model
                        if (modelData.local_taxes_withheld) {
                            const localTaxesSection = createStateTaxesWithheldSection(
                                modelData.local_taxes_withheld,
                                previewUrl,
                                excelViewUrl,
                                isFirstSection,
                                '1099-R Local'
                            );
                            if (localTaxesSection) {
                                sections.push(localTaxesSection);
                                isFirstSection = false;
                            }
                        }
                    }
                }
            } else if (groupData.fields) {
                // Direct fields structure (e.g., pages_8_9, pages_12)
                // Get sheet name for this group
                const sheetName = sectionTitle;
                const section = createAccordionSection(
                    sectionTitle,
                    previewUrl,
                    excelViewUrl,
                    sheetName,
                    isFirstSection
                );
                sections.push(section);
                isFirstSection = false;
            }
            
            // Check for state_local_taxes data in direct fields structure
            if (groupData.state_local_taxes) {
                const stateLocalSection = createStateLocalTaxesSection(
                    groupData.state_local_taxes,
                    previewUrl,
                    excelViewUrl,
                    isFirstSection
                );
                if (stateLocalSection) {
                    sections.push(stateLocalSection);
                    isFirstSection = false;
                }
            }
            // Check for 1099-DIV state taxes withheld in direct fields
            if (groupData.state_taxes_withheld && groupName === 'Form_1099DIV') {
                const stateTaxesSection = createStateTaxesWithheldSection(
                    groupData.state_taxes_withheld,
                    previewUrl,
                    excelViewUrl,
                    isFirstSection,
                    '1099-DIV'
                );
                if (stateTaxesSection) {
                    sections.push(stateTaxesSection);
                    isFirstSection = false;
                }
            }
            // Check for 1099-INT state taxes withheld in direct fields
            if (groupData.state_taxes_withheld && groupName === 'Form_1099INT') {
                const stateTaxesSection = createStateTaxesWithheldSection(
                    groupData.state_taxes_withheld,
                    previewUrl,
                    excelViewUrl,
                    isFirstSection,
                    '1099-INT'
                );
                if (stateTaxesSection) {
                    sections.push(stateTaxesSection);
                    isFirstSection = false;
                }
            }
            // Check for 1099-MISC state taxes withheld in direct fields
            if (groupName === 'Form_1099MISC') {
                console.log('Found Form_1099MISC group, checking state_taxes_withheld:', groupData.state_taxes_withheld);
                if (groupData.state_taxes_withheld) {
                    const stateTaxesSection = createStateTaxesWithheldSection(
                        groupData.state_taxes_withheld,
                        previewUrl,
                        excelViewUrl,
                        isFirstSection,
                        '1099-MISC'
                    );
                    if (stateTaxesSection) {
                        sections.push(stateTaxesSection);
                        isFirstSection = false;
                    } else {
                        console.warn('createStateTaxesWithheldSection returned null for Form_1099MISC');
                    }
                } else {
                    console.log('No state_taxes_withheld found in Form_1099MISC group data');
                }
            }
            // Check for 1099-NEC state taxes withheld in direct fields
            if (groupData.state_taxes_withheld && groupName === 'Form_1099NEC') {
                const stateTaxesSection = createStateTaxesWithheldSection(
                    groupData.state_taxes_withheld,
                    previewUrl,
                    excelViewUrl,
                    isFirstSection,
                    '1099-NEC'
                );
                if (stateTaxesSection) {
                    sections.push(stateTaxesSection);
                    isFirstSection = false;
                }
            }
            // Check for 1099-R state taxes withheld in direct fields
            if (groupData.state_taxes_withheld && groupName === 'Form_1099R') {
                const stateTaxesSection = createStateTaxesWithheldSection(
                    groupData.state_taxes_withheld,
                    previewUrl,
                    excelViewUrl,
                    isFirstSection,
                    '1099-R'
                );
                if (stateTaxesSection) {
                    sections.push(stateTaxesSection);
                    isFirstSection = false;
                }
            }
            // Check for 1099-R local taxes withheld in direct fields
            if (groupData.local_taxes_withheld && groupName === 'Form_1099R') {
                const localTaxesSection = createStateTaxesWithheldSection(
                    groupData.local_taxes_withheld,
                    previewUrl,
                    excelViewUrl,
                    isFirstSection,
                    '1099-R Local'
                );
                if (localTaxesSection) {
                    sections.push(localTaxesSection);
                    isFirstSection = false;
                }
            }
        }

        if (sections.length === 0) {
            accordionContainer.innerHTML = '<div class="status-message status-info">No data sections found in results. Please check the data structure.</div>';
            document.getElementById('resultsView').classList.remove('hidden');
            return;
        }

        // Append all sections to container
        sections.forEach(section => {
            accordionContainer.appendChild(section);
        });

        // Setup accordion handlers after sections are added
        setupAccordionHandlers();

        document.getElementById('resultsView').classList.remove('hidden');
        
        // Initialize save button state (if still needed)
        if (typeof updateSaveButtonState === 'function') {
            updateSaveButtonState();
        }
    } catch (error) {
        console.error('Error displaying results:', error);
        const processingStatus = document.getElementById('processingStatus');
        if (processingStatus) {
            processingStatus.innerHTML = 
                `<div class="status-message status-error">Error displaying results: ${error.message}</div>`;
            processingStatus.classList.remove('hidden');
        }
    }
}

/**
 * Create a section for displaying state/local taxes table
 * Uses the same Excel viewer format as Form W2
 * @param {Object} stateLocalData - State/local taxes data with rows and states
 * @param {string} previewUrl - Preview URL
 * @param {string} excelUrl - Excel file URL
 * @param {boolean} isExpanded - Whether section should be expanded
 * @returns {HTMLElement} Section element
 */
function createStateLocalTaxesSection(stateLocalData, previewUrl, excelUrl, isExpanded = false) {
    if (!stateLocalData || !stateLocalData.rows || !stateLocalData.states) {
        return null;
    }
    
    // Use the same accordion section creation as Form W2
    // The sheet name in Excel is "State & Local Taxes"
    const section = createAccordionSection(
        'State & Local Taxes',
        previewUrl,
        excelUrl,
        'State & Local Taxes',
        isExpanded
    );
    
    return section;
}

/**
 * Create a section for displaying 1099-DIV, 1099-INT, or 1099-MISC State Tax table.
 * Renders via the Excel preview/export sheet.
 * @param {Object} stateTaxesData - state_taxes_withheld data with rows/fields
 * @param {string} previewUrl - Preview URL
 * @param {string} excelUrl - Excel file URL
 * @param {boolean} isExpanded - Whether section should be expanded
 * @param {string} formType - Form type ("1099-DIV", "1099-INT", or "1099-MISC")
 * @returns {HTMLElement} Section element
 */
function createStateTaxesWithheldSection(stateTaxesData, previewUrl, excelUrl, isExpanded = false, formType = '1099-DIV') {
    if (!stateTaxesData || !stateTaxesData.rows) {
        return null;
    }
    
    // Title by form type
    let sectionTitle = `State Tax Withheld (${formType})`;
    if (formType === '1099-MISC') {
        sectionTitle = 'State Tax Information (1099-MISC)';
    } else if (formType === '1099-NEC') {
        sectionTitle = 'State Tax Withheld (1099-NEC)';
    } else if (formType === '1099-R Local') {
        sectionTitle = 'Local Tax Withheld (1099-R Local)';
    }
    const section = createAccordionSection(
        sectionTitle,
        previewUrl,
        excelUrl,
        sectionTitle,
        isExpanded
    );
    
    return section;
}

/**
 * Save edited data to server
 * @returns {Promise<void>}
 */
async function saveEditedData() {
    const saveBtn = document.getElementById('saveChangesBtn');
    if (!saveBtn || saveBtn.disabled) return;
    
    // Collect all edited data from all tables
    const allTables = document.querySelectorAll('.data-table');
    const editedFieldsByGroup = {};
    
    for (const table of allTables) {
        const tableId = table.dataset.tableId;
        if (!tableId || !editedData[tableId]) continue;
        
        // Find the accordion section this table belongs to
        const accordionSection = table.closest('.accordion-section');
        if (!accordionSection) continue;
        
        const sectionTitle = accordionSection.querySelector('h3')?.textContent || '';
        // Map section title to group name (reverse lookup)
        const groupName = Object.keys(GROUP_DISPLAY_NAMES).find(
            key => GROUP_DISPLAY_NAMES[key] === sectionTitle
        ) || sectionTitle.toLowerCase().replace(/\s+/g, '_');
        
        if (!editedFieldsByGroup[groupName]) {
            editedFieldsByGroup[groupName] = {};
        }
        
        // Get original fields structure to preserve line and label
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            const fieldKey = cells[2]?.dataset.fieldKey; // Value cell
            if (fieldKey && editedData[tableId][fieldKey] !== undefined) {
                const lineCell = cells[0];
                const labelCell = cells[1];
                editedFieldsByGroup[groupName][fieldKey] = {
                    line: lineCell.textContent.trim(),
                    label: labelCell.textContent.trim(),
                    value: editedData[tableId][fieldKey]
                };
            }
        });
    }
    
    if (Object.keys(editedFieldsByGroup).length === 0) {
        alert('No changes to save');
        return;
    }
    
    // Show loading state
    const originalText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    
    try {
        const response = await fetch(`${API_BASE}/jobs/${currentJobId}/save-edited-data`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                edited_fields: editedFieldsByGroup
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Save failed');
        }
        
        const result = await response.json();
        
        // Clear edited data after successful save
        for (const table of allTables) {
            const tableId = table.dataset.tableId;
            if (tableId) {
                clearEditedDataForTable(tableId);
            }
        }
        
        // Remove edited class from cells
        document.querySelectorAll('.edited').forEach(cell => {
            cell.classList.remove('edited');
        });
        
        saveBtn.textContent = 'Saved!';
        setTimeout(() => {
            saveBtn.textContent = originalText;
            saveBtn.disabled = false;
        }, 2000);
        
        showCopyNotification('Changes saved successfully');
    } catch (error) {
        saveBtn.textContent = originalText;
        saveBtn.disabled = false;
        alert(`Error saving changes: ${error.message}`);
    }
}

/**
 * Handle file upload
 * @param {File} file - File to upload
 * @returns {Promise<void>}
 */
async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append('file', file);

    // Update file info display
    currentFileName = file.name;
    updateFileInfo(file.name, 'Uploading...');

    const uploadStatus = document.getElementById('uploadStatus');
    uploadStatus.className = 'status-message status-info';
    uploadStatus.textContent = 'Uploading document...';
    uploadStatus.classList.remove('hidden');

    try {
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }

        const result = await response.json();
        currentJobId = result.job_id;
        
        // Update file info with filename from server response
        if (result.filename) {
            currentFileName = result.filename;
            updateFileInfo(result.filename, 'Uploaded');
        } else {
            updateFileInfo(file.name, 'Uploaded');
        }
        
        uploadStatus.className = 'status-message status-success';
        uploadStatus.textContent = `Document uploaded successfully! ${result.page_count} pages detected.`;
        
        document.getElementById('pageCount').textContent = result.page_count;
        document.getElementById('maxPage').textContent = result.page_count;
        document.getElementById('pageCountInfo').classList.remove('hidden');
        
        await loadPageGroups();
        
        setTimeout(() => {
            goToStep(3);
        }, 1000);
    } catch (error) {
        uploadStatus.className = 'status-message status-error';
        uploadStatus.textContent = `Error: ${error.message}`;
        updateFileInfo(file.name, 'Upload Failed');
    }
}
