/**
 * Accordion section functionality
 */

/**
 * Create an accordion section with preview and Excel viewer columns
 * @param {string} title - Section title
 * @param {string} previewUrl - Preview URL
 * @param {string} excelUrl - Excel file URL
 * @param {string} sheetName - Sheet name in Excel file
 * @param {boolean} isExpanded - Whether section should be expanded
 * @returns {HTMLElement} Accordion section element
 */
function createAccordionSection(title, previewUrl, excelUrl, sheetName, isExpanded = false) {
    const section = document.createElement('div');
    section.className = `accordion-section ${isExpanded ? 'expanded' : ''}`;
    section.dataset.sectionId = title.toLowerCase().replace(/\s+/g, '-');
    const isW2Section = typeof isW2SectionTitle === 'function' && isW2SectionTitle(title);

    // Create header
    const header = document.createElement('div');
    header.className = 'accordion-header';
    header.innerHTML = `
        <h3>${title}</h3>
        <span class="accordion-icon">${isExpanded ? '▼' : '►'}</span>
    `;
    section.appendChild(header);

    // Create content
    const content = document.createElement('div');
    content.className = `accordion-content ${isExpanded ? 'expanded' : ''}`;
    
    // Create paired columns container
    const pairedColumns = document.createElement('div');
    pairedColumns.className = 'paired-columns';

    // Preview column (left)
    const previewColumn = document.createElement('div');
    previewColumn.className = 'preview-column';
    if (previewUrl) {
        previewColumn.innerHTML = `
            <h4>Document Preview</h4>
            <iframe class="preview-iframe" src="${previewUrl}"></iframe>
        `;
    } else {
        previewColumn.innerHTML = `
            <h4>Document Preview</h4>
            <p style="color: #999; font-style: italic;">No preview available</p>
        `;
    }
    pairedColumns.appendChild(previewColumn);

    // Excel viewer column (right) - using SheetJS
    const excelColumn = document.createElement('div');
    excelColumn.className = 'excel-column';
    excelColumn.innerHTML = `
        <h4>Extracted Data</h4>
        <div class="excel-viewer-container">
            <div class="excel-loading">
                <div class="spinner"></div>
                <p>Loading Excel data...</p>
            </div>
            <div class="excel-table-container" style="display: none;"></div>
            <div class="excel-error" style="display: none;">
                <p style="color: #d32f2f;">Error loading Excel file. <a href="${excelUrl}" download>Download file</a> instead.</p>
            </div>
        </div>
    `;
    pairedColumns.appendChild(excelColumn);

    // Load and display Excel file when section is expanded
    const loadExcelData = async () => {
        // Prevent multiple simultaneous loads
        if (section._excelLoading) {
            console.log('Excel data already loading for section:', section.dataset.sectionId);
            return;
        }
        
        // Check if already loaded
        if (section._excelLoaded) {
            console.log('Excel data already loaded for section:', section.dataset.sectionId);
            return;
        }
        
        section._excelLoading = true;

        const loadingDiv = excelColumn.querySelector('.excel-loading');
        const tableContainer = excelColumn.querySelector('.excel-table-container');
        const errorDiv = excelColumn.querySelector('.excel-error');
        
        // Show loading state
        if (loadingDiv) loadingDiv.style.display = 'block';
        if (tableContainer) tableContainer.style.display = 'none';
        if (errorDiv) errorDiv.style.display = 'none';
        
        console.log('Loading Excel data for section:', section.dataset.sectionId, 'URL:', excelUrl);

        try {
            // Check if XLSX is available
            if (typeof XLSX === 'undefined') {
                throw new Error('SheetJS library not loaded. Please refresh the page.');
            }

            // Fetch Excel file
            console.log('Fetching Excel file from:', excelUrl);
            const response = await fetch(excelUrl);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            console.log('Excel file fetched successfully, parsing...');

            const arrayBuffer = await response.arrayBuffer();
            const data = new Uint8Array(arrayBuffer);
            
            // Parse Excel file
            const workbook = XLSX.read(data, { type: 'array' });
            
            // Find the sheet by name (case-insensitive match)
            let worksheet = null;
            let foundSheetName = null;
            
            console.log(`Looking for sheet: "${sheetName}" in workbook with sheets:`, workbook.SheetNames);
            
            // Try exact match first
            if (workbook.SheetNames.includes(sheetName)) {
                foundSheetName = sheetName;
                worksheet = workbook.Sheets[sheetName];
                console.log(`Found exact match: "${foundSheetName}"`);
            } else {
                // Try case-insensitive match
                const lowerSheetName = sheetName.toLowerCase();
                for (const name of workbook.SheetNames) {
                    if (name.toLowerCase() === lowerSheetName) {
                        foundSheetName = name;
                        worksheet = workbook.Sheets[name];
                        console.log(`Found case-insensitive match: "${foundSheetName}"`);
                        break;
                    }
                }
            }
            
            // If not found, show error instead of using first sheet
            if (!worksheet) {
                console.error(`Sheet "${sheetName}" not found in workbook. Available sheets:`, workbook.SheetNames);
                throw new Error(`Sheet "${sheetName}" not found in Excel file. Available sheets: ${workbook.SheetNames.join(', ')}`);
            }
            
            console.log(`Using sheet: "${foundSheetName}" for section: ${section.dataset.sectionId}`);

            // Convert sheet to HTML table
            const htmlString = XLSX.utils.sheet_to_html(worksheet, {
                id: `excel-table-${section.dataset.sectionId}`,
                editable: false
            });

            // Hide loading, show table
            loadingDiv.style.display = 'none';
            tableContainer.innerHTML = htmlString;
            tableContainer.style.display = 'block';

            // Apply styling to the table and add editing/selection functionality
            const table = tableContainer.querySelector('table');
            if (table) {
                table.className = 'excel-data-table';
                // Make table scrollable
                table.style.width = '100%';
                table.style.borderCollapse = 'collapse';
                
                // Generate unique table ID
                const tableId = `excel-table-${section.dataset.sectionId}-${Date.now()}`;
                table.dataset.tableId = tableId;
                
                // Initialize edited data storage for this table
                const dataStore = typeof editedData !== 'undefined' ? editedData : (window.editedData = window.editedData || {});
                if (!dataStore[tableId]) {
                    dataStore[tableId] = {};
                }
                
                // Make Value column (3rd column) editable and add selection
                // SheetJS generates tables - check structure
                const tbody = table.querySelector('tbody');
                const thead = table.querySelector('thead');
                const allRows = table.querySelectorAll('tr');
                
                console.log(`Excel table found: ${allRows.length} total rows, tbody: ${tbody ? 'yes' : 'no'}, thead: ${thead ? 'yes' : 'no'}`);
                
                let dataRowIndex = 0;

                const isLineHeaderText = (text) => {
                    const normalized = text.toLowerCase().replace(/[#.:]/g, '').trim();
                    if (!normalized) {
                        return true; // Some exports leave Line header blank
                    }
                    return normalized === 'line' ||
                        normalized.startsWith('line ') ||
                        normalized.startsWith('line no') ||
                        normalized.startsWith('line number') ||
                        normalized.includes('line');
                };
                
                allRows.forEach((row, globalIndex) => {
                    const isHeader = row.parentElement.tagName === 'THEAD' || 
                                    row.querySelector('th') !== null ||
                                    globalIndex === 0;
                    
                    if (isHeader) {
                        // Make header cells selectable
                        const headerCells = row.querySelectorAll('th, td');
                        headerCells.forEach((cell, colIndex) => {
                            cell.dataset.row = -1; // Header row
                            cell.dataset.col = colIndex;
                            setupExcelCellSelection(cell, table);
                            
                            // Add sorting to "Line" column (first column, index 0)
                            if (colIndex === 0) {
                                const headerText = cell.textContent.trim();
                                if (isLineHeaderText(headerText)) {
                                    cell.style.cursor = 'pointer';
                                    cell.style.userSelect = 'none';
                                    cell.title = 'Click to sort by Line';
                                    cell.classList.add('sortable-header');
                                    
                                    // Add sort indicator
                                    if (!cell.querySelector('.sort-indicator')) {
                                        const sortIndicator = document.createElement('span');
                                        sortIndicator.className = 'sort-indicator';
                                        sortIndicator.textContent = ' ↕';
                                        sortIndicator.style.marginLeft = '5px';
                                        sortIndicator.style.opacity = '0.5';
                                        cell.appendChild(sortIndicator);
                                    }
                                    
                                    // Add click handler for sorting
                                    cell.addEventListener('click', (e) => {
                                        e.stopPropagation();
                                        sortTableByLine(table, cell);
                                    });
                                }
                            }
                        });
                        return;
                    }
                    
                    // Data row
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 3) {
                        // Value column is the 3rd column (index 2)
                        const valueCell = cells[2];
                        
                        // Make it editable
                        valueCell.contentEditable = 'true';
                        valueCell.classList.add('editable-cell');
                        
                        // Add row and column indices for selection
                        valueCell.dataset.row = dataRowIndex;
                        valueCell.dataset.col = 2;
                        
                        // Store original value
                        const labelCell = cells[1];
                        const fieldKey = labelCell.textContent.trim() || `field_${dataRowIndex}`;
                        valueCell.dataset.fieldKey = fieldKey;
                        
                        let originalValue = valueCell.textContent.trim();
                        if (isW2Section && typeof isW2NumericLabel === 'function' && typeof formatTwoDecimal === 'function') {
                            if (isW2NumericLabel(fieldKey)) {
                                originalValue = formatTwoDecimal(originalValue);
                                valueCell.textContent = originalValue;
                            }
                        }
                        valueCell.dataset.originalValue = originalValue;
                        
                        // Add field key (use label from 2nd column)
                        // Setup cell selection
                        setupExcelCellSelection(valueCell, table);
                        
                        // Setup cell editing
                        setupExcelCellEditing(valueCell, table, tableId, fieldKey, originalValue, isW2Section);
                    }
                    
                    // Also make other cells selectable (but not editable)
                    cells.forEach((cell, colIndex) => {
                        if (colIndex !== 2) { // Not the value column
                            cell.dataset.row = dataRowIndex;
                            cell.dataset.col = colIndex;
                            setupExcelCellSelection(cell, table);
                        }
                    });
                    
                    dataRowIndex++;
                });
                
                console.log(`Excel table setup complete: ${dataRowIndex} data rows processed, tableId: ${tableId}`);
                
                // Initialize sort state
                table.dataset.sortDirection = 'none'; // 'asc', 'desc', or 'none'
                
                // Auto-sort by Line column when table is first displayed
                const lineHeader = table.querySelector('thead th:first-child, thead tr:first-child th:first-child, tr:first-child th:first-child, tr:first-child td:first-child');
                if (lineHeader) {
                    const headerText = lineHeader.textContent.trim();
                    // Some Excel exports leave the Line header blank; treat it as the Line column
                    if (isLineHeaderText(headerText)) {
                        // Set initial sort direction to 'none' so the function will set it to 'asc'
                        table.dataset.sortDirection = 'none';
                        // Automatically sort the table (will set to ascending: null -> 1 -> 100)
                        sortTableByLine(table, lineHeader);
                    }
                }
                
                section._excelLoaded = true;
                section._excelLoading = false;
            } else {
                console.error('Excel table not found in container');
                throw new Error('Excel table not found after parsing');
            }

        } catch (error) {
            console.error('Error loading Excel file for section', section.dataset.sectionId, ':', error);
            if (loadingDiv) loadingDiv.style.display = 'none';
            if (tableContainer) tableContainer.style.display = 'none';
            if (errorDiv) {
                errorDiv.style.display = 'block';
                const errorLink = errorDiv.querySelector('a');
                if (errorLink) {
                    errorLink.href = excelUrl;
                }
            }
            section._excelLoaded = false; // Allow retry
            section._excelLoading = false;
        }
    };

    // Store loadExcelData function on the section element so setupAccordionHandlers can call it
    section._loadExcelData = loadExcelData;
    section._excelLoaded = false;
    section._excelLoading = false;

    // If initially expanded, load immediately
    if (isExpanded) {
        setTimeout(() => loadExcelData(), 100);
    }

    content.appendChild(pairedColumns);
    section.appendChild(content);

    return section;
}

// Global variables for Excel table selection
// Note: These are separate from table.js selection variables to avoid conflicts
let excelSelectionStart = null;
let excelIsDragging = false;
let excelIsClick = false;

/**
 * Setup Excel cell selection functionality
 * @param {HTMLElement} cell - Cell element
 * @param {HTMLElement} table - Table element
 */
function setupExcelCellSelection(cell, table) {
    cell.addEventListener('mousedown', (e) => {
        excelIsDragging = false;
        excelIsClick = true;
        
        // For editable cells, prevent focus if we're selecting (not editing)
        if (cell.classList.contains('editable-cell')) {
            // If clicking on selected cell, allow editing
            if (cell.classList.contains('selected')) {
                setTimeout(() => {
                    if (!excelIsDragging && excelIsClick) {
                        cell.focus();
                    }
                }, 100);
                return;
            }
            // Otherwise, prevent focus and select instead
            e.preventDefault();
        }
        
        if (!e.shiftKey && !e.ctrlKey && !e.metaKey) {
            clearExcelSelection(table);
            excelSelectionStart = cell;
            cell.classList.add('selected');
            console.log('Cell selected:', cell.dataset.row, cell.dataset.col);
        } else if (e.shiftKey && excelSelectionStart) {
            // Shift+Click: Select range
            e.preventDefault();
            selectExcelRange(excelSelectionStart, cell, table);
            console.log('Range selected from', excelSelectionStart.dataset.row, 'to', cell.dataset.row);
        } else if (e.ctrlKey || e.metaKey) {
            // Ctrl/Cmd+Click: Toggle selection
            e.preventDefault();
            cell.classList.toggle('selected');
            if (!excelSelectionStart) {
                excelSelectionStart = cell;
            }
            console.log('Cell toggled:', cell.classList.contains('selected'));
        } else {
            excelSelectionStart = cell;
            cell.classList.add('selected');
            console.log('Cell selected:', cell.dataset.row, cell.dataset.col);
        }
    });
    
    // Mouse drag for range selection
    cell.addEventListener('mouseenter', (e) => {
        if (e.buttons === 1 && excelSelectionStart) {
            excelIsDragging = true;
            e.preventDefault();
            e.stopPropagation();
            
            // If starting from a specific column, restrict selection to that column
            const startCol = parseInt(excelSelectionStart.dataset.col);
            const endCol = parseInt(cell.dataset.col);
            
            if (startCol === endCol) {
                selectExcelRange(excelSelectionStart, cell, table);
            } else {
                const startRow = parseInt(excelSelectionStart.dataset.row);
                const endRow = parseInt(cell.dataset.row);
                selectExcelColumnRange(table, startCol, startRow, endRow);
            }
        }
    });
    
    cell.addEventListener('mouseup', () => {
        setTimeout(() => {
            excelIsDragging = false;
            excelIsClick = false;
        }, 100);
    });
}

/**
 * Select a range of Excel cells
 */
function selectExcelRange(startCell, endCell, table) {
    const startRow = parseInt(startCell.dataset.row);
    const startCol = parseInt(startCell.dataset.col);
    const endRow = parseInt(endCell.dataset.row);
    const endCol = parseInt(endCell.dataset.col);
    
    const minRow = Math.min(startRow, endRow);
    const maxRow = Math.max(startRow, endRow);
    const minCol = Math.min(startCol, endCol);
    const maxCol = Math.max(startCol, endCol);
    
    clearExcelSelection(table);
    
    // Get all rows (including header)
    const allRows = Array.from(table.querySelectorAll('tr'));
    // Find header row index
    const headerRowIndex = allRows.findIndex(row => 
        row.parentElement.tagName === 'THEAD' || row.querySelector('th') !== null
    );
    const dataStartIndex = headerRowIndex >= 0 ? headerRowIndex + 1 : 1;
    
    // Select data rows (skip header)
    for (let r = minRow + dataStartIndex; r <= maxRow + dataStartIndex; r++) {
        if (allRows[r]) {
            const cells = allRows[r].querySelectorAll('td');
            for (let c = minCol; c <= maxCol; c++) {
                if (cells[c]) {
                    cells[c].classList.add('selected');
                }
            }
        }
    }
}

/**
 * Select a range within a single column
 */
function selectExcelColumnRange(table, colIndex, startRow, endRow) {
    const minRow = Math.min(startRow, endRow);
    const maxRow = Math.max(startRow, endRow);
    
    clearExcelSelection(table);
    
    // Get all rows (including header)
    const allRows = Array.from(table.querySelectorAll('tr'));
    // Find header row index
    const headerRowIndex = allRows.findIndex(row => 
        row.parentElement.tagName === 'THEAD' || row.querySelector('th') !== null
    );
    const dataStartIndex = headerRowIndex >= 0 ? headerRowIndex + 1 : 1;
    
    // Select data rows (skip header)
    for (let r = minRow + dataStartIndex; r <= maxRow + dataStartIndex; r++) {
        if (allRows[r]) {
            const cells = allRows[r].querySelectorAll('td');
            if (cells[colIndex]) {
                cells[colIndex].classList.add('selected');
            }
        }
    }
}

/**
 * Clear all selections in a table
 */
function clearExcelSelection(table) {
    const selectedCells = table.querySelectorAll('.selected');
    selectedCells.forEach(cell => cell.classList.remove('selected'));
}

/**
 * Setup Excel cell editing functionality
 */
function setupExcelCellEditing(cell, table, tableId, fieldKey, originalValue, isW2Section = false) {
    let isEditing = false;
    let shouldEdit = false;
    
    // Only allow editing on double-click
    cell.addEventListener('dblclick', (e) => {
        e.stopPropagation();
        e.preventDefault();
        shouldEdit = true;
        excelIsClick = false; // Prevent selection from interfering
        cell.focus();
    });
    
    // Focus event - start editing
    cell.addEventListener('focus', () => {
        if (!shouldEdit) {
            setTimeout(() => {
                if (!isEditing) {
                    cell.blur();
                }
            }, 0);
            return;
        }
        isEditing = true;
        shouldEdit = false;
        cell.classList.add('editing');
        // Select all text for easy replacement
        const range = document.createRange();
        range.selectNodeContents(cell);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
    });
    
    // Blur event - save edit
    cell.addEventListener('blur', () => {
        if (!isEditing) return;
        
        isEditing = false;
        cell.classList.remove('editing');
        let newValue = cell.textContent.trim();
        if (isW2Section && typeof isW2NumericLabel === 'function' && typeof formatTwoDecimal === 'function') {
            if (isW2NumericLabel(fieldKey)) {
                newValue = formatTwoDecimal(newValue);
                cell.textContent = newValue;
            }
        }
        
        if (newValue !== originalValue) {
            // Use global editedData (from table.js)
            const dataStore = typeof editedData !== 'undefined' ? editedData : window.editedData;
            if (!dataStore[tableId]) {
                dataStore[tableId] = {};
            }
            dataStore[tableId][fieldKey] = newValue;
            cell.classList.add('edited');
            if (typeof updateSaveButtonState === 'function') {
                updateSaveButtonState();
            }
        } else {
            const dataStore = typeof editedData !== 'undefined' ? editedData : window.editedData;
            if (dataStore[tableId]) {
                delete dataStore[tableId][fieldKey];
            }
            cell.classList.remove('edited');
            if (typeof updateSaveButtonState === 'function') {
                updateSaveButtonState();
            }
        }
    });
    
    // Keyboard navigation
    cell.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const row = parseInt(cell.dataset.row);
            const col = parseInt(cell.dataset.col);
            const rows = table.querySelectorAll('tbody tr');
            if (rows[row + 1]) {
                const nextRowCells = rows[row + 1].querySelectorAll('td');
                if (nextRowCells[col]) {
                    shouldEdit = true;
                    nextRowCells[col].focus();
                }
            }
        } else if (e.key === 'Escape') {
            e.preventDefault();
            cell.textContent = originalValue;
            cell.blur();
        }
    });
}

/**
 * Copy selected Excel cells to clipboard
 * Exposed globally for keyboard shortcuts
 */
function copySelectedExcelCells() {
    const allTables = document.querySelectorAll('.excel-data-table');
    const selectedCells = [];
    
    allTables.forEach(table => {
        const cells = table.querySelectorAll('td.selected, th.selected');
        cells.forEach(cell => selectedCells.push(cell));
    });
    
    console.log('copySelectedExcelCells called, selectedCells:', selectedCells.length);
    
    if (selectedCells.length === 0) {
        console.log('No cells selected, returning');
        return;
    }
    
    // Group cells by row
    const rows = {};
    selectedCells.forEach(cell => {
        const rowIndex = parseInt(cell.dataset.row);
        const colIndex = parseInt(cell.dataset.col);
        
        if (isNaN(rowIndex) || isNaN(colIndex)) return;
        
        if (!rows[rowIndex]) {
            rows[rowIndex] = {};
        }
        
        let cellValue = cell.textContent.trim();
        // Check if cell has edited value
        const tableId = cell.closest('table')?.dataset.tableId;
        const dataStore = typeof editedData !== 'undefined' ? editedData : window.editedData;
        if (tableId && dataStore[tableId]) {
            const fieldKey = cell.dataset.fieldKey;
            if (fieldKey && dataStore[tableId][fieldKey] !== undefined) {
                cellValue = dataStore[tableId][fieldKey];
            }
        }
        
        rows[rowIndex][colIndex] = cellValue;
    });
    
    // Build tab-separated text (Excel format)
    const rowIndices = Object.keys(rows).map(Number).sort((a, b) => a - b);
    const data = [];
    
    // Check if all selected cells are from the same column
    const allColIndices = new Set();
    rowIndices.forEach(rowIndex => {
        Object.keys(rows[rowIndex]).forEach(col => allColIndices.add(parseInt(col)));
    });
    const isSingleColumn = allColIndices.size === 1;
    
    rowIndices.forEach(rowIndex => {
        const rowData = rows[rowIndex];
        const colIndices = Object.keys(rowData).map(Number).sort((a, b) => a - b);
        
        if (isSingleColumn) {
            const value = rowData[colIndices[0]] || '';
            data.push(String(value).replace(/\t/g, ' ').replace(/\n/g, ' '));
        } else {
            const values = colIndices.map(colIndex => {
                const value = rowData[colIndex] || '';
                return String(value).replace(/\t/g, ' ').replace(/\n/g, ' ');
            });
            data.push(values.join('\t'));
        }
    });
    
    const text = data.join('\n');
    
    console.log('Copying to clipboard:', text.substring(0, 100) + '...');
    
    // Copy to clipboard with fallback for browsers without clipboard API
    const copyToClipboard = (text) => {
        // Try modern clipboard API first
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text).then(() => {
                console.log('Successfully copied to clipboard');
                if (typeof showCopyNotification === 'function') {
                    showCopyNotification(`Copied ${selectedCells.length} cell(s) - Ready to paste in Excel`);
                }
            }).catch(err => {
                console.warn('Clipboard API failed, trying fallback:', err);
                return fallbackCopy(text);
            });
        } else {
            // Fallback for browsers without clipboard API
            console.log('Clipboard API not available, using fallback');
            return fallbackCopy(text);
        }
    };
    
    // Fallback method using execCommand
    const fallbackCopy = (text) => {
        return new Promise((resolve, reject) => {
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.top = '-9999px';
            textArea.style.left = '-9999px';
            textArea.style.opacity = '0';
            textArea.setAttribute('readonly', '');
            document.body.appendChild(textArea);
            
            // Select and copy
            textArea.select();
            textArea.setSelectionRange(0, text.length); // For mobile devices
            
            try {
                const successful = document.execCommand('copy');
                document.body.removeChild(textArea);
                
                if (successful) {
                    console.log('Successfully copied using fallback method');
                    if (typeof showCopyNotification === 'function') {
                        showCopyNotification(`Copied ${selectedCells.length} cell(s) - Ready to paste in Excel`);
                    }
                    resolve();
                } else {
                    throw new Error('execCommand copy failed');
                }
            } catch (e) {
                document.body.removeChild(textArea);
                console.error('Fallback copy failed:', e);
                alert('Failed to copy. Please select and copy manually (Ctrl/Cmd+C).');
                reject(e);
            }
        });
    };
    
    // Execute copy
    copyToClipboard(text).catch(err => {
        console.error('All copy methods failed:', err);
    });
}

// Expose globally for keyboard shortcuts
window.copySelectedExcelCells = copySelectedExcelCells;


/**
 * Setup accordion toggle functionality
 */
function setupAccordionHandlers() {
    // Remove existing listeners by cloning headers
    document.querySelectorAll('.accordion-header').forEach(header => {
        const newHeader = header.cloneNode(true);
        const section = header.parentElement;
        header.parentNode.replaceChild(newHeader, header);
        
        newHeader.addEventListener('click', function() {
            const content = section.querySelector('.accordion-content');
            const icon = this.querySelector('.accordion-icon');
            const isExpanded = section.classList.contains('expanded');

            if (isExpanded) {
                section.classList.remove('expanded');
                content.classList.remove('expanded');
                if (icon) icon.textContent = '►';
            } else {
                section.classList.add('expanded');
                content.classList.add('expanded');
                if (icon) icon.textContent = '▼';
                
                // Load Excel data when section is expanded
                if (section._loadExcelData && !section._excelLoaded && !section._excelLoading) {
                    console.log('Expanding section, loading Excel data...');
                    setTimeout(() => {
                        if (section._loadExcelData) {
                            section._loadExcelData();
                        }
                    }, 100);
                } else {
                    console.log('Section Excel data status - loaded:', section._excelLoaded, 'loading:', section._excelLoading);
                }
            }
        });
    });
}

