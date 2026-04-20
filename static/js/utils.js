/**
 * Utility functions and constants
 */

// API Configuration
const API_BASE = '/api';

// W-2 numeric formatting helpers
const W2_NUMERIC_LABELS = new Set([
    'wages, tips, other compensation',
    'federal income tax withheld',
    'social security wages',
    'social security tax withheld',
    'medicare wages and tips',
    'medicare tax withheld',
    'social security tips',
    'allocated tips',
    'dependent care benefits',
    'nonqualified plans',
    'amount',
    'state wages, tips, etc.',
    'state income tax',
    'local wages, tips, etc.',
    'local income tax'
]);

function normalizeNumericInput(value) {
    if (value === null || value === undefined) {
        return null;
    }
    if (typeof value === 'number') {
        return Number.isFinite(value) ? value : null;
    }
    if (typeof value !== 'string') {
        return null;
    }
    let cleaned = value.trim();
    if (cleaned === '') {
        return null;
    }
    // Remove commas, spaces, and common currency symbols
    cleaned = cleaned.replace(/[,\s$€£¥]/g, '');
    // Keep only digits, dot, and minus
    cleaned = cleaned.replace(/[^0-9.\-]/g, '');
    if (cleaned === '' || cleaned === '.' || cleaned === '-' || cleaned === '-.') {
        return null;
    }
    // Normalize minus sign
    const isNegative = cleaned.startsWith('-');
    cleaned = cleaned.replace(/-/g, '');
    // Normalize multiple dots (keep the first)
    const parts = cleaned.split('.');
    if (parts.length > 1) {
        cleaned = `${parts[0]}.${parts.slice(1).join('')}`;
    }
    if (isNegative) {
        cleaned = `-${cleaned}`;
    }
    const num = Number(cleaned);
    return Number.isFinite(num) ? num : null;
}

function formatTwoDecimal(value) {
    const num = normalizeNumericInput(value);
    if (num === null) {
        return '0.00';
    }
    return num.toFixed(2);
}

function isW2NumericLabel(label) {
    if (!label) return false;
    return W2_NUMERIC_LABELS.has(label.trim().toLowerCase());
}

function isW2SectionTitle(title) {
    if (!title) return false;
    const normalized = title.trim().toLowerCase();
    return normalized === 'form w-2' || normalized === 'state & local taxes';
}

// Display name mappings
const GROUP_DISPLAY_NAMES = {
    'pages_8_9': 'Form 1120S',
    'pages_12': 'Schedule L',
    'pages_13': 'Schedule M',
    'Form_1065': 'Form 1065',
    'Schedule_M_L': 'Schedule M & L',
    'Form_1120': 'Form 1120',
    'Schedule_M_L_1120': 'Schedule M & L',
    'Form_1040': 'Form 1040',
    'Form_1099DIV': 'Form 1099-DIV',
    'Form_1099INT': 'Form 1099-INT',
    'Form_1099MISC': 'Form 1099-MISC',
    'Form_1099NEC': 'Form 1099-NEC',
    'Form_1099R': 'Form 1099-R',
    'Form_1099SSA': 'Form 1099-SSA',
    'Form_W2': 'Form W-2',
};

const MODEL_DISPLAY_NAMES = {
    'Train_1120s_v2': 'Form 1120S',
    'Train_1120s_scehdule_M1_v2': 'Schedule M-1',
    'Train_1120s_schedule_M2_v3': 'Schedule M-2',
    'Train_1120s_schedule_L_v4': 'Schedule L',
    'Train_1065_schedule_m2_v3': 'Schedule M-2',
    'Train_1065_schedule_m1_v2': 'Schedule M-1',
    'Train_1065_schedule_L_v4': 'Schedule L',
    'Train_model_1065_v4': 'Form 1065',
    'Train_1120_schedule_M2_v3': 'Schedule M-2',
    'Train_1120_schedule_M1_v2': 'Schedule M-1',
    'Train_1120_schedule_L_v3': 'Schedule L',
    'Train_1120_v2': 'Form 1120',
    'prebuilt-tax.us.1040': 'Form 1040',
    'prebuilt-tax.us.1099DIV': 'Form 1099-DIV',
    'prebuilt-tax.us.1099INT': 'Form 1099-INT',
    'prebuilt-tax.us.1099MISC': 'Form 1099-MISC',
    'prebuilt-tax.us.1099NEC': 'Form 1099-NEC',
    'prebuilt-tax.us.1099R': 'Form 1099-R',
    'prebuilt-tax.us.1099SSA': 'Form 1099-SSA',
    'Train_model_w2_v4': 'Form W-2',
    'prebuilt-tax.us.w2': 'Form W-2',
};

/**
 * Show copy notification
 * @param {string} message - Notification message
 */
function showCopyNotification(message) {
    let notification = document.getElementById('copyNotification');
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'copyNotification';
        notification.className = 'selection-info';
        document.body.appendChild(notification);
    }
    notification.textContent = message;
    notification.classList.add('show');
    setTimeout(() => {
        notification.classList.remove('show');
    }, 2000);
}

/**
 * Parse line value for sorting (handles numeric and alphanumeric values)
 * Unified function for all table types
 * @param {string} lineValue - Line value (e.g., "1", "2a", "2b", "3")
 * @returns {Array} [numericPart, letterPart] for sorting
 */
function parseLineValue(lineValue) {
    if (!lineValue || lineValue.trim() === '') {
        return [Infinity, '']; // Empty values go to end
    }
    
    const trimmed = lineValue.trim();
    // Match: optional number, optional letter(s)
    const match = trimmed.match(/^(\d*)([a-z]*)$/i);
    
    if (match) {
        const numericPart = match[1] ? parseInt(match[1], 10) : 0;
        const letterPart = match[2] ? match[2].toLowerCase() : '';
        return [numericPart, letterPart];
    }
    
    // Fallback: try to parse as number
    const num = parseFloat(trimmed);
    if (!isNaN(num)) {
        return [num, ''];
    }
    
    // If can't parse, put at end
    return [Infinity, trimmed.toLowerCase()];
}

/**
 * Unified function to sort table by Line column
 * Works for both data tables (.data-table) and Excel tables (.excel-data-table)
 * @param {HTMLElement} table - Table element
 * @param {HTMLElement} headerCell - Header cell that was clicked (optional for auto-sort)
 */
function sortTableByLine(table, headerCell = null) {
    const tbody = table.querySelector('tbody');
    if (!tbody) return;
    
    // Get only tbody rows (exclude thead)
    const rows = Array.from(tbody.querySelectorAll('tr'));
    if (rows.length === 0) return;
    
    // Get current sort direction
    let currentDirection = table.dataset.sortDirection || 'none';
    
    // Toggle sort direction: none -> asc -> desc -> asc
    // Initial auto-sort starts with ascending (null -> 1 -> 100)
    let newDirection;
    if (currentDirection === 'none' || currentDirection === 'desc') {
        newDirection = 'asc';
    } else {
        newDirection = 'desc';
    }
    
    table.dataset.sortDirection = newDirection;
    
    // Update sort indicator if headerCell is provided
    if (headerCell) {
        const sortIndicator = headerCell.querySelector('.sort-indicator');
        if (sortIndicator) {
            if (newDirection === 'asc') {
                sortIndicator.textContent = ' ↑';
                sortIndicator.style.opacity = '1';
            } else if (newDirection === 'desc') {
                sortIndicator.textContent = ' ↓';
                sortIndicator.style.opacity = '1';
            } else {
                sortIndicator.textContent = ' ↕';
                sortIndicator.style.opacity = '0.5';
            }
        }
    }
    
    // Sort rows (only tbody rows, header stays in thead)
    rows.sort((rowA, rowB) => {
        const cellsA = rowA.querySelectorAll('td');
        const cellsB = rowB.querySelectorAll('td');
        
        if (cellsA.length === 0 || cellsB.length === 0) return 0;
        
        // Get Line column value (first column, index 0)
        const lineValueA = cellsA[0] ? cellsA[0].textContent.trim() : '';
        const lineValueB = cellsB[0] ? cellsB[0].textContent.trim() : '';
        
        // Parse values for comparison
        const [numA, letterA] = parseLineValue(lineValueA);
        const [numB, letterB] = parseLineValue(lineValueB);
        
        // Handle empty/null values - always put them at the beginning regardless of sort direction
        const isEmptyA = numA === Infinity;
        const isEmptyB = numB === Infinity;
        
        if (isEmptyA && isEmptyB) {
            return 0; // Both empty, keep original order
        }
        if (isEmptyA) {
            return -1; // A is empty, put A before B (at beginning)
        }
        if (isEmptyB) {
            return 1; // B is empty, put B before A (at beginning)
        }
        
        let comparison = 0;
        
        // First compare numeric part
        if (numA < numB) {
            comparison = -1;
        } else if (numA > numB) {
            comparison = 1;
        } else {
            // If numeric parts are equal, compare letter parts
            if (letterA < letterB) {
                comparison = -1;
            } else if (letterA > letterB) {
                comparison = 1;
            }
        }
        
        // Reverse if descending
        return newDirection === 'desc' ? -comparison : comparison;
    });
    
    // Re-append sorted rows to tbody (header stays in thead)
    rows.forEach(row => tbody.appendChild(row));
    
    // Update row indices and data attributes
    rows.forEach((row, index) => {
        const cells = row.querySelectorAll('td');
        cells.forEach((cell, colIndex) => {
            cell.dataset.row = index;
        });
    });
    
    console.log(`Table sorted by Line column (${newDirection})`);
}

