/**
 * Excel-like table functionality
 */

// Global storage for edited data: editedData[tableId][fieldKey] = newValue
const editedData = {};

/**
 * Create a data section with table or card layout
 * @param {string} title - Section title
 * @param {Object} fields - Fields data
 * @returns {HTMLElement} Section div element
 */
function createDataSection(title, fields) {
    const sectionDiv = document.createElement('div');
    sectionDiv.className = 'data-section';
    sectionDiv.style.marginBottom = '30px';
    sectionDiv.style.border = '1px solid #e0e0e0';
    sectionDiv.style.borderRadius = '8px';
    sectionDiv.style.padding = '20px';
    sectionDiv.style.backgroundColor = '#fafafa';

    const titleDiv = document.createElement('div');
    titleDiv.className = 'data-section-title';
    titleDiv.style.fontSize = '18px';
    titleDiv.style.fontWeight = 'bold';
    titleDiv.style.marginBottom = '15px';
    titleDiv.style.color = '#333';
    titleDiv.style.borderBottom = '2px solid #007bff';
    titleDiv.style.paddingBottom = '8px';
    titleDiv.style.position = 'relative';
    titleDiv.textContent = title;
    sectionDiv.appendChild(titleDiv);

    // Check if fields exist and have data
    if (!fields || Object.keys(fields).length === 0) {
        const noDataMsg = document.createElement('div');
        noDataMsg.className = 'status-message status-info';
        noDataMsg.textContent = 'No data available for this section';
        sectionDiv.appendChild(noDataMsg);
        return sectionDiv;
    }

    // Check if fields have line/label/value structure
    const sampleField = Object.values(fields)[0];
    const hasMappedStructure = sampleField && typeof sampleField === 'object' && 
                              sampleField !== null && 
                              ('line' in sampleField || 'label' in sampleField || 'value' in sampleField);

    if (hasMappedStructure) {
        createTableLayout(sectionDiv, fields, title);
    } else {
        createCardLayout(sectionDiv, fields);
    }

    return sectionDiv;
}

/**
 * Create table layout for mapped fields
 * @param {HTMLElement} sectionDiv - Section container
 * @param {Object} fields - Fields data
 */
function createTableLayout(sectionDiv, fields, sectionTitle = '') {
    // Create table container for Excel-like scrolling
    const tableContainer = document.createElement('div');
    tableContainer.style.width = '100%';
    tableContainer.style.overflowX = 'auto';
    tableContainer.style.overflowY = 'auto';
    tableContainer.style.maxHeight = '600px';
    tableContainer.style.border = '1px solid #d0d7e5';
    tableContainer.style.borderRadius = '4px';
    tableContainer.style.backgroundColor = '#fff';
    
    // Create table for mapped fields (Line, Label, Value)
    const table = document.createElement('table');
    table.className = 'data-table';
    table.style.width = '100%';
    table.style.borderCollapse = 'collapse';
    table.style.backgroundColor = '#fff';

    // Create table header
    const thead = document.createElement('thead');
    thead.style.backgroundColor = '#f2f2f2';
    const headerRow = document.createElement('tr');
    
    const headers = ['Line', 'Label', 'Value'];
    headers.forEach((headerText, colIndex) => {
        const th = document.createElement('th');
        th.textContent = headerText;
        th.dataset.columnIndex = colIndex;
        
        // Special handling for Line column - add sorting
        if (colIndex === 0 && headerText === 'Line') {
            th.title = 'Click to sort by Line';
            th.style.cursor = 'pointer';
            th.style.userSelect = 'none';
            th.classList.add('sortable-header');
            
            // Add sort indicator
            const sortIndicator = document.createElement('span');
            sortIndicator.className = 'sort-indicator';
            sortIndicator.textContent = ' ↕';
            sortIndicator.style.marginLeft = '5px';
            sortIndicator.style.opacity = '0.5';
            th.appendChild(sortIndicator);
        
            // Add click handler for sorting (prevent column selection)
            th.addEventListener('click', (e) => {
                e.stopPropagation();
                sortTableByLine(table, th);
            });
        } else {
            th.title = 'Click to select column';
            // Add column selection for other columns
        th.addEventListener('click', (e) => {
            e.stopPropagation();
            selectColumn(table, colIndex);
        });
        }
        
        headerRow.appendChild(th);
    });
    
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Create table body
    const tbody = document.createElement('tbody');
    
    // Convert fields to array and sort by line number if available
    const fieldsArray = Object.entries(fields).map(([key, value]) => ({
        key,
        ...value
    }));
    
    // Sort by line number (handle numeric and string line numbers)
    fieldsArray.sort((a, b) => {
        const lineA = a.line || '';
        const lineB = b.line || '';
        
        // Try numeric comparison first
        const numA = parseFloat(lineA);
        const numB = parseFloat(lineB);
        
        if (!isNaN(numA) && !isNaN(numB)) {
            return numA - numB;
        }
        
        // Fallback to string comparison
        return lineA.localeCompare(lineB, undefined, { numeric: true, sensitivity: 'base' });
    });

    // Excel-like cell selection state (scoped to this table)
    let selectionStart = null;
    let isDragging = false;
    
    const isW2Section = typeof isW2SectionTitle === 'function' && isW2SectionTitle(sectionTitle);
    table.dataset.sectionTitle = sectionTitle;
    
    // Create unique table ID for tracking edits
    const tableId = `table-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    table.dataset.tableId = tableId;
    table.dataset.sortDirection = 'none'; // Initialize sort direction
    editedData[tableId] = {};
    
    fieldsArray.forEach((field, index) => {
        const row = document.createElement('tr');
        row.dataset.rowIndex = index;
        row.style.backgroundColor = '#fff';
        
        // Hover effect
        row.addEventListener('mouseenter', () => {
            if (!row.classList.contains('selected')) {
                row.style.backgroundColor = '#f0f7ff';
            }
        });
        row.addEventListener('mouseleave', () => {
            if (!row.classList.contains('selected')) {
                row.style.backgroundColor = '#fff';
            }
        });

        // Line column - Excel style (center, blue, bold)
        const lineCell = document.createElement('td');
        lineCell.textContent = field.line || '';
        lineCell.style.textAlign = 'center';
        lineCell.style.fontWeight = '600';
        lineCell.style.color = '#0066cc';
        lineCell.style.fontSize = '11pt';
        lineCell.style.padding = '6px 12px';
        lineCell.style.borderRight = '1px solid #e0e0e0';
        lineCell.style.borderBottom = '1px solid #e0e0e0';
        lineCell.style.backgroundColor = '#fff';
        lineCell.style.width = '80px';
        lineCell.style.minWidth = '80px';
        lineCell.dataset.row = index;
        lineCell.dataset.col = 0;
        setupCellSelection(lineCell, table);
        row.appendChild(lineCell);

        // Label column - Excel style (left aligned)
        const labelCell = document.createElement('td');
        labelCell.textContent = field.label || field.key || '';
        labelCell.style.textAlign = 'left';
        labelCell.style.color = '#333';
        labelCell.style.fontSize = '11pt';
        labelCell.style.padding = '6px 12px';
        labelCell.style.borderRight = '1px solid #e0e0e0';
        labelCell.style.borderBottom = '1px solid #e0e0e0';
        labelCell.style.backgroundColor = '#fff';
        labelCell.style.minWidth = '250px';
        labelCell.dataset.row = index;
        labelCell.dataset.col = 1;
        setupCellSelection(labelCell, table);
        row.appendChild(labelCell);

        // Value column - Excel style (right aligned, monospace) - EDITABLE
        const valueCell = document.createElement('td');
        let value = field.value !== null && field.value !== undefined ? String(field.value) : '';
        if (isW2Section && typeof isW2NumericLabel === 'function' && typeof formatTwoDecimal === 'function') {
            if (isW2NumericLabel(field.label || field.key || '')) {
                value = formatTwoDecimal(value);
            }
        }
        valueCell.textContent = value;
        valueCell.contentEditable = 'true';
        valueCell.style.textAlign = 'right';
        valueCell.style.fontFamily = 'Consolas, Monaco, "Courier New", monospace';
        valueCell.style.fontSize = '10.5pt';
        valueCell.style.color = '#000';
        valueCell.style.padding = '6px 12px';
        valueCell.style.borderRight = 'none';
        valueCell.style.borderBottom = '1px solid #e0e0e0';
        valueCell.style.backgroundColor = '#fff';
        valueCell.style.wordBreak = 'break-word';
        valueCell.style.minWidth = '150px';
        valueCell.style.cursor = 'text';
        valueCell.dataset.row = index;
        valueCell.dataset.col = 2;
        valueCell.dataset.fieldKey = field.key;
        valueCell.dataset.originalValue = value;
        valueCell.classList.add('editable-cell');
        setupCellSelection(valueCell, table);
        setupCellEditing(valueCell, table, tableId, field.key, value, isW2Section);
        row.appendChild(valueCell);

        tbody.appendChild(row);
    });
    
    // Setup Excel-like cell selection
    function setupCellSelection(cell, table) {
        let mouseDownTime = 0;
        let isClick = false;
        
        // Click to select single cell
        cell.addEventListener('mousedown', (e) => {
            mouseDownTime = Date.now();
            isDragging = false;
            isClick = true;
            
            // For editable cells, prevent focus if we're selecting (not editing)
            if (cell.classList.contains('editable-cell')) {
                // If clicking on selected cell, allow editing
                if (cell.classList.contains('selected')) {
                    // Small delay to allow selection to be cleared first if clicking elsewhere
                    setTimeout(() => {
                        if (!isDragging && isClick) {
                            cell.focus();
                        }
                    }, 100);
                    return;
                }
                // Otherwise, prevent focus and select instead
                e.preventDefault();
            }
            
            if (!e.shiftKey && !e.ctrlKey && !e.metaKey) {
                clearSelection(table);
                selectionStart = cell;
                cell.classList.add('selected');
            } else if (e.shiftKey && selectionStart) {
                // Shift+Click: Select range
                e.preventDefault();
                const startCol = parseInt(selectionStart.dataset.col);
                const endCol = parseInt(cell.dataset.col);
                
                // If same column, select column range; otherwise select full range
                if (startCol === endCol) {
                    const startRow = parseInt(selectionStart.dataset.row);
                    const endRow = parseInt(cell.dataset.row);
                    selectColumnRange(table, startCol, startRow, endRow);
                } else {
                    selectRange(selectionStart, cell, table);
                }
            } else if (e.ctrlKey || e.metaKey) {
                // Ctrl/Cmd+Click: Toggle selection
                e.preventDefault();
                cell.classList.toggle('selected');
                if (!selectionStart) {
                    selectionStart = cell;
                }
            } else {
                selectionStart = cell;
                cell.classList.add('selected');
            }
        });
        
        // Mouse drag for range selection
        cell.addEventListener('mouseenter', (e) => {
            if (e.buttons === 1 && selectionStart) {
                // Mouse is being dragged
                isDragging = true;
                isClick = false;
                e.preventDefault();
                e.stopPropagation();
                
                // If starting from a specific column, restrict selection to that column
                const startCol = parseInt(selectionStart.dataset.col);
                const endCol = parseInt(cell.dataset.col);
                
                // Only allow selection within the same column for better UX
                if (startCol === endCol) {
                    selectRange(selectionStart, cell, table);
                } else {
                    // If dragging to different column, select only the start column's range
                    const startRow = parseInt(selectionStart.dataset.row);
                    const endRow = parseInt(cell.dataset.row);
                    selectColumnRange(table, startCol, startRow, endRow);
                }
            }
        });
        
        // Track mouse up to stop dragging
        cell.addEventListener('mouseup', () => {
            const clickDuration = Date.now() - mouseDownTime;
            if (clickDuration < 200 && !isDragging) {
                isClick = true;
            } else {
                isClick = false;
            }
            setTimeout(() => {
                isDragging = false;
            }, 100);
        });
        
        // Double-click to copy (only for non-editable cells)
        if (!cell.classList.contains('editable-cell')) {
            cell.addEventListener('dblclick', () => {
                copyCellContent(cell);
            });
        }
    }
    
    /**
     * Setup cell editing functionality
     * @param {HTMLElement} cell - Cell element
     * @param {HTMLElement} table - Table element
     * @param {string} tableId - Table ID
     * @param {string} fieldKey - Field key
     * @param {string} originalValue - Original value
     */
    function setupCellEditing(cell, table, tableId, fieldKey, originalValue, isW2Section = false) {
        let isEditing = false;
        let shouldEdit = false;
        
        // Focus event - start editing (only if shouldEdit is true)
        cell.addEventListener('focus', () => {
            if (!shouldEdit) {
                // If focus happened without double-click, blur immediately to allow selection
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
            isEditing = false;
            cell.classList.remove('editing');
            let newValue = cell.textContent.trim();
            if (isW2Section && typeof isW2NumericLabel === 'function' && typeof formatTwoDecimal === 'function') {
                const labelCell = cell.parentElement ? cell.parentElement.querySelector('td[data-col="1"]') : null;
                const labelText = labelCell ? labelCell.textContent.trim() : '';
                if (isW2NumericLabel(labelText)) {
                    newValue = formatTwoDecimal(newValue);
                    cell.textContent = newValue;
                }
            }
            
            if (newValue !== originalValue) {
                // Value changed - mark as edited
                editedData[tableId][fieldKey] = newValue;
                cell.classList.add('edited');
                cell.classList.remove('selected');
                updateSaveButtonState();
            } else {
                // Value unchanged - remove edited mark
                delete editedData[tableId][fieldKey];
                cell.classList.remove('edited');
                updateSaveButtonState();
            }
        });
        
        // Keyboard navigation
        cell.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                // Move to cell below
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
            } else if (e.key === 'Tab') {
                e.preventDefault();
                // Move to next cell (right)
                const row = parseInt(cell.dataset.row);
                const col = parseInt(cell.dataset.col);
                const rows = table.querySelectorAll('tbody tr');
                const currentRowCells = rows[row].querySelectorAll('td');
                if (currentRowCells[col + 1]) {
                    shouldEdit = true;
                    currentRowCells[col + 1].focus();
                } else if (rows[row + 1]) {
                    // Move to first editable cell in next row
                    const nextRowCells = rows[row + 1].querySelectorAll('td');
                    const editableCell = Array.from(nextRowCells).find(c => c.classList.contains('editable-cell'));
                    if (editableCell) {
                        shouldEdit = true;
                        editableCell.focus();
                    }
                }
            } else if (e.key === 'Escape') {
                e.preventDefault();
                // Cancel edit - restore original value
                cell.textContent = originalValue;
                cell.blur();
            }
        });
        
        // Only allow editing on double-click, not single click
        // Single click should select, double-click should edit
        let clickTimer = null;
        cell.addEventListener('mousedown', (e) => {
            // Clear any pending single-click timer
            if (clickTimer) {
                clearTimeout(clickTimer);
                clickTimer = null;
            }
        });
        
        cell.addEventListener('dblclick', (e) => {
            // Double-click = edit mode
            e.stopPropagation();
            shouldEdit = true;
            cell.focus();
        });
    }
    
    function selectRange(startCell, endCell, table) {
        const startRow = parseInt(startCell.dataset.row);
        const startCol = parseInt(startCell.dataset.col);
        const endRow = parseInt(endCell.dataset.row);
        const endCol = parseInt(endCell.dataset.col);
        
        const minRow = Math.min(startRow, endRow);
        const maxRow = Math.max(startRow, endRow);
        const minCol = Math.min(startCol, endCol);
        const maxCol = Math.max(startCol, endCol);
        
        // Clear previous selection
        clearSelection(table);
        
        // Select range
        const rows = table.querySelectorAll('tbody tr');
        for (let r = minRow; r <= maxRow; r++) {
            const cells = rows[r].querySelectorAll('td');
            for (let c = minCol; c <= maxCol; c++) {
                if (cells[c]) {
                    cells[c].classList.add('selected');
                }
            }
        }
    }
    
    /**
     * Select a range within a single column
     * @param {HTMLElement} table - Table element
     * @param {number} colIndex - Column index
     * @param {number} startRow - Start row index
     * @param {number} endRow - End row index
     */
    function selectColumnRange(table, colIndex, startRow, endRow) {
        const minRow = Math.min(startRow, endRow);
        const maxRow = Math.max(startRow, endRow);
        
        // Clear previous selection
        clearSelection(table);
        
        // Select only cells in the specified column and row range
        const rows = table.querySelectorAll('tbody tr');
        for (let r = minRow; r <= maxRow; r++) {
            const cells = rows[r].querySelectorAll('td');
            if (cells[colIndex]) {
                cells[colIndex].classList.add('selected');
            }
        }
    }
    
    /**
     * Select a range within a single column
     * @param {HTMLElement} table - Table element
     * @param {number} colIndex - Column index
     * @param {number} startRow - Start row index
     * @param {number} endRow - End row index
     */
    function selectColumnRange(table, colIndex, startRow, endRow) {
        const minRow = Math.min(startRow, endRow);
        const maxRow = Math.max(startRow, endRow);
        
        // Clear previous selection
        clearSelection(table);
        
        // Select only cells in the specified column and row range
        const rows = table.querySelectorAll('tbody tr');
        for (let r = minRow; r <= maxRow; r++) {
            const cells = rows[r].querySelectorAll('td');
            if (cells[colIndex]) {
                cells[colIndex].classList.add('selected');
            }
        }
    }

    table.appendChild(tbody);
    tableContainer.appendChild(table);
    sectionDiv.appendChild(tableContainer);
    
    // Auto-sort by Line column when table is first displayed
    const lineHeader = table.querySelector('thead th:first-child');
    if (lineHeader && lineHeader.textContent.includes('Line')) {
        // Set initial sort direction to 'none' so the function will set it to 'asc'
        table.dataset.sortDirection = 'none';
        // Automatically sort the table (will set to ascending: null -> 1 -> 100)
        sortTableByLine(table, lineHeader);
    }
    
    // Make table focusable for keyboard events
    table.setAttribute('tabindex', '0');
    
    // Stop text selection only during active drag
    table.addEventListener('selectstart', (e) => {
        if (isDragging && selectionStart) {
            e.preventDefault();
        }
    });
    
    // Clear selection when clicking outside table
    document.addEventListener('mousedown', (e) => {
        if (!table.contains(e.target)) {
            clearSelection(table);
            selectionStart = null;
            isDragging = false;
        }
    });
}

/**
 * Create card layout for unmapped fields
 * @param {HTMLElement} sectionDiv - Section container
 * @param {Object} fields - Fields data
 */
function createCardLayout(sectionDiv, fields) {
    const fieldsContainer = document.createElement('div');
    fieldsContainer.className = 'data-fields-container';
    fieldsContainer.style.display = 'grid';
    fieldsContainer.style.gridTemplateColumns = 'repeat(auto-fill, minmax(250px, 1fr))';
    fieldsContainer.style.gap = '12px';

    for (const [key, value] of Object.entries(fields)) {
        const fieldItem = document.createElement('div');
        fieldItem.className = 'data-item';
        fieldItem.style.backgroundColor = '#fff';
        fieldItem.style.padding = '12px';
        fieldItem.style.borderRadius = '4px';
        fieldItem.style.border = '1px solid #e8e8e8';
        
        // Format the value for display
        let displayValue = value;
        if (typeof value === 'object') {
            displayValue = JSON.stringify(value, null, 2);
        } else {
            displayValue = String(value);
        }
        
        fieldItem.innerHTML = `
            <div class="data-label" style="font-weight: 600; color: #555; margin-bottom: 4px; font-size: 13px;">${key}</div>
            <div class="data-value" style="color: #333; font-size: 14px; word-break: break-word;">${displayValue || ''}</div>
        `;
        fieldsContainer.appendChild(fieldItem);
    }

    sectionDiv.appendChild(fieldsContainer);
}

/**
 * Select a column in the table
 * @param {HTMLElement} table - Table element
 * @param {number} columnIndex - Column index
 */
function selectColumn(table, columnIndex) {
    // Toggle column selection
    const headers = table.querySelectorAll('thead th');
    const header = headers[columnIndex];
    const isSelected = header.classList.contains('selected');
    
    // Clear all selections first
    clearSelection(table);
    
    if (!isSelected) {
        header.classList.add('selected');
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells[columnIndex]) {
                cells[columnIndex].classList.add('selected');
            }
        });
    }
}

/**
 * Copy selected cells to clipboard
 * @param {NodeList|Array} selectedCells - Selected cell elements
 */
function copySelectedCells(selectedCells) {
    // Convert NodeList to Array if needed
    const cellsArray = Array.from(selectedCells);
    
    if (cellsArray.length === 0) {
        console.log('No cells selected');
        return;
    }
    
    console.log(`Copying ${cellsArray.length} selected cells`);
    
    // Get the table to access tableId
    const table = cellsArray[0].closest('table');
    const tableId = table ? table.dataset.tableId : null;
    
    // Group cells by row
    const rows = {};
    cellsArray.forEach(cell => {
        const rowIndex = parseInt(cell.dataset.row);
        const colIndex = parseInt(cell.dataset.col);
        
        if (isNaN(rowIndex) || isNaN(colIndex)) {
            console.warn('Cell missing row/col data:', cell);
            return; // Skip cells without proper row/col data
        }
        
        if (!rows[rowIndex]) {
            rows[rowIndex] = {};
        }
        
        // Get cell value - use edited value if available, otherwise use text content
        let cellValue = cell.textContent.trim();
        if (cell.classList.contains('editable-cell') && tableId && editedData[tableId]) {
            const fieldKey = cell.dataset.fieldKey;
            if (fieldKey && editedData[tableId][fieldKey] !== undefined) {
                cellValue = editedData[tableId][fieldKey];
            }
        }
        
        rows[rowIndex][colIndex] = cellValue;
    });
    
    console.log('Grouped rows:', rows);
    
    // Build tab-separated text (Excel format)
    const rowIndices = Object.keys(rows).map(Number).sort((a, b) => a - b);
    const data = [];
    
    // Check if all selected cells are from the same column
    const allColIndices = new Set();
    rowIndices.forEach(rowIndex => {
        Object.keys(rows[rowIndex]).forEach(col => allColIndices.add(parseInt(col)));
    });
    const isSingleColumn = allColIndices.size === 1;
    
    console.log(`Selection: ${allColIndices.size} column(s) - Single column: ${isSingleColumn}`);
    
    rowIndices.forEach(rowIndex => {
        const rowData = rows[rowIndex];
        const colIndices = Object.keys(rowData).map(Number).sort((a, b) => a - b);
        
        // If only one column is selected, copy only that column's values (one per line)
        // If multiple columns selected, copy as tab-separated
        if (isSingleColumn) {
            // Single column selection - one value per line (better for Excel paste)
            const value = rowData[colIndices[0]] || '';
            data.push(String(value).replace(/\t/g, ' ').replace(/\n/g, ' '));
        } else {
            // Multiple columns - tab-separated
            const values = colIndices.map(colIndex => {
                const value = rowData[colIndex] || '';
                // Escape tabs and newlines for proper Excel formatting
                return String(value).replace(/\t/g, ' ').replace(/\n/g, ' ');
            });
            data.push(values.join('\t'));
        }
    });
    
    const text = data.join('\n');
    console.log('Copying text:', text.substring(0, 100) + '...');
    
    // Copy to clipboard
    navigator.clipboard.writeText(text).then(() => {
        showCopyNotification(`Copied ${cellsArray.length} cell(s) from ${isSingleColumn ? '1 column' : allColIndices.size + ' columns'} - Ready to paste in Excel`);
    }).catch(err => {
        console.error('Failed to copy:', err);
        // Fallback: try using execCommand for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showCopyNotification(`Copied ${cellsArray.length} cell(s) - Ready to paste in Excel`);
        } catch (e) {
            alert('Failed to copy. Please select and copy manually (Ctrl/Cmd+C).');
        }
        document.body.removeChild(textArea);
    });
}

/**
 * Clear selection in a table
 * @param {HTMLElement} table - Table element
 */
function clearSelection(table) {
    table.querySelectorAll('.selected').forEach(el => {
        el.classList.remove('selected');
    });
}

/**
 * Copy cell content to clipboard
 * @param {HTMLElement} cell - Cell element
 */
function copyCellContent(cell) {
    const text = cell.textContent.trim();
    navigator.clipboard.writeText(text).then(() => {
        showCopyNotification(`Copied: ${text.substring(0, 30)}${text.length > 30 ? '...' : ''}`);
    });
}

/**
 * Copy table to clipboard
 * @param {HTMLElement} table - Table element
 */
function copyTableToClipboard(table) {
    const rows = table.querySelectorAll('tr');
    const data = [];
    const tableId = table.dataset.tableId;
    
    rows.forEach(row => {
        const cells = row.querySelectorAll('th, td');
        const rowData = [];
        for (let i = 0; i < cells.length; i++) {
            const cell = cells[i];
            // Use edited value if available, otherwise use cell text
            if (cell.classList.contains('editable-cell') && tableId && editedData[tableId]) {
                const fieldKey = cell.dataset.fieldKey;
                if (fieldKey && editedData[tableId][fieldKey] !== undefined) {
                    rowData.push(editedData[tableId][fieldKey]);
                } else {
                    rowData.push(cell.textContent.trim());
                }
            } else {
                rowData.push(cell.textContent.trim());
            }
        }
        data.push(rowData.join('\t'));
    });
    
    const text = data.join('\n');
    navigator.clipboard.writeText(text).then(() => {
        showCopyNotification('Table copied to clipboard (tab-separated)');
    }).catch(err => {
        console.error('Failed to copy:', err);
        alert('Failed to copy to clipboard. Please select and copy manually.');
    });
}

/**
 * Update save button state based on whether there are unsaved changes
 */
function updateSaveButtonState() {
    const saveBtn = document.getElementById('saveChangesBtn');
    if (!saveBtn) return;
    
    // Check if any table has edited data
    let hasChanges = false;
    for (const tableId in editedData) {
        if (Object.keys(editedData[tableId]).length > 0) {
            hasChanges = true;
            break;
        }
    }
    
    saveBtn.disabled = !hasChanges;
    if (hasChanges) {
        saveBtn.classList.add('has-changes');
    } else {
        saveBtn.classList.remove('has-changes');
    }
}

/**
 * Get all edited data for a specific table
 * @param {string} tableId - Table ID
 * @returns {Object} Edited data object
 */
function getEditedDataForTable(tableId) {
    return editedData[tableId] || {};
}

/**
 * Clear edited data for a table
 * @param {string} tableId - Table ID
 */
function clearEditedDataForTable(tableId) {
    if (editedData[tableId]) {
        delete editedData[tableId];
    }
    updateSaveButtonState();
}


