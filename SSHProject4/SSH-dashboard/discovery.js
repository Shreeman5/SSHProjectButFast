// Discovery Dashboard JavaScript

const API_BASE = 'http://localhost:5000';

// State
let currentDimension = 'country';
let allData = [];
let filteredData = [];
let currentPage = 1;
let pageSize = 50;

// Multi-column sorting state
let sortColumns = ['total_attacks'];  // Array of columns to sort by
let sortDirection = 'desc';  // Single direction for now (all columns same direction)
let debugRankings = null;  // Store ranking debug info

// Toggle debug view
function toggleDebug() {
    const debugSection = document.getElementById('debug-section');
    const showBtn = document.getElementById('show-debug-btn');
    
    if (debugSection.style.display === 'none') {
        debugSection.style.display = 'block';
        showBtn.style.display = 'none';
        updateDebugView();
    } else {
        debugSection.style.display = 'none';
        showBtn.style.display = 'block';
    }
}

// Update debug view with current ranking info
function updateDebugView() {
    const debugContent = document.getElementById('debug-content');
    
    if (!debugRankings) {
        debugContent.innerHTML = '<p>No multi-column sort active. Select 2+ columns to see ranking breakdown.</p>';
        return;
    }
    
    const { rankMaps, avgRanks, columnLabels } = debugRankings;
    
    // Create header
    let html = '<div style="margin-bottom: 15px; padding: 10px; background: #f8f9fa; border-radius: 4px;">';
    html += `<strong>Sorting by ${sortColumns.length} columns:</strong> ${columnLabels.join(', ')}<br>`;
    html += `<strong>Direction:</strong> ${sortDirection === 'desc' ? 'Best to Worst' : 'Worst to Best'}`;
    html += '</div>';
    
    // Create table
    html += '<table style="width: 100%; border-collapse: collapse; background: white;">';
    html += '<thead style="background: #e9ecef; position: sticky; top: 0;">';
    html += '<tr>';
    html += '<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Final Rank</th>';
    html += '<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Country</th>';
    
    columnLabels.forEach(label => {
        html += `<th style="padding: 8px; border: 1px solid #ddd; text-align: center;">${label}<br>Rank</th>`;
    });
    
    html += '<th style="padding: 8px; border: 1px solid #ddd; text-align: center; background: #fff3cd;">Avg Rank</th>';
    html += '</tr>';
    html += '</thead>';
    html += '<tbody>';
    
    // Show top 50 countries
    const topCountries = avgRanks.slice(0, 50);
    
    topCountries.forEach((entry, idx) => {
        const { item, avgRank, ranks } = entry;
        const finalRank = idx + 1;
        
        html += '<tr>';
        html += `<td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">#${finalRank}</td>`;
        html += `<td style="padding: 8px; border: 1px solid #ddd;"><strong>${item.country}</strong></td>`;
        
        ranks.forEach(rank => {
            html += `<td style="padding: 8px; border: 1px solid #ddd; text-align: center;">${rank}</td>`;
        });
        
        html += `<td style="padding: 8px; border: 1px solid #ddd; text-align: center; background: #fff3cd; font-weight: bold;">${avgRank.toFixed(2)}</td>`;
        html += '</tr>';
    });
    
    html += '</tbody>';
    html += '</table>';
    
    if (avgRanks.length > 50) {
        html += `<p style="margin-top: 10px; color: #666; font-style: italic;">Showing top 50 of ${avgRanks.length} countries</p>`;
    }
    
    debugContent.innerHTML = html;
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadData();
});

// Load data for current dimension
async function loadData() {
    try {
        const response = await fetch(`${API_BASE}/api/${currentDimension}_summary?start=2022-11-01&end=2023-01-08`);
        allData = await response.json();
        
        // Default sort by total_attacks descending
        sortColumns = ['total_attacks'];
        sortDirection = 'desc';
        
        applyFilters();
        updateQuickStats();
    } catch (error) {
        console.error('Error loading data:', error);
        document.getElementById('table-body').innerHTML = 
            '<tr><td colspan="15" style="text-align: center; padding: 40px; color: red;">Error loading data</td></tr>';
    }
}

// Switch dimension
function switchDimension(dimension) {
    currentDimension = dimension;
    currentPage = 1;
    
    // Update active button
    document.querySelectorAll('.dim-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    
    loadData();
}

// Apply filters and sorting
function applyFilters() {
    const searchTerm = document.getElementById('search-box').value.toLowerCase();
    
    // Filter data
    filteredData = allData.filter(item => {
        const matchesSearch = !searchTerm || getEntityName(item).toLowerCase().includes(searchTerm);
        return matchesSearch;
    });
    
    // Sort by current column(s) and direction
    sortData();
    
    // Reset to page 1
    currentPage = 1;
    
    // Render table
    renderTable();
}

// Toggle column in sort list
function sortByColumn(column, event) {
    // Check for Ctrl/Cmd key for multi-column sorting
    const isMultiSelect = event.ctrlKey || event.metaKey;
    
    if (isMultiSelect) {
        // Multi-column mode: add/remove column from list
        const index = sortColumns.indexOf(column);
        if (index > -1) {
            // Column already in list, remove it
            sortColumns.splice(index, 1);
            
            // If we removed the last column, add back total_attacks as default
            if (sortColumns.length === 0) {
                sortColumns = ['total_attacks'];
            }
        } else {
            // Add column to sort list
            sortColumns.push(column);
        }
    } else {
        // Single-column mode: replace sort list with this column
        if (sortColumns.length === 1 && sortColumns[0] === column) {
            // Same column, toggle direction
            sortDirection = sortDirection === 'desc' ? 'asc' : 'desc';
        } else {
            // New column(s), reset to descending
            sortColumns = [column];
            sortDirection = 'desc';
        }
    }
    
    sortData();
    renderTable();
}

// Calculate ranks for each column (with tie handling)
function calculateRanks(data, column) {
    // Determine sort direction based on column type
    // For most metrics: higher value = better (rank 1)
    // For dates: depends on semantic meaning
    let sortAscending = false;
    
    if (column === 'first_seen') {
        // Earlier first_seen = better (lower rank) - older/more established threats
        sortAscending = true;
    } else if (column === 'last_seen') {
        // More recent last_seen = better (lower rank) - currently active threats
        sortAscending = false;
    } else if (column === 'country' || column === 'ip' || column === 'asn_name' || column === 'username') {
        // For entity names, alphabetical A-Z = better (subjective, but consistent)
        sortAscending = true;
    }
    // All other numeric columns: higher value = better (lower rank)
    
    // Sort by column value
    const sorted = [...data].sort((a, b) => {
        let aVal = a[column] ?? (sortAscending ? Infinity : -Infinity);
        let bVal = b[column] ?? (sortAscending ? Infinity : -Infinity);
        
        // Handle date strings
        if (column === 'first_seen' || column === 'last_seen') {
            aVal = new Date(aVal);
            bVal = new Date(bVal);
        }
        
        // Handle string comparison
        if (column === 'country' || column === 'ip' || column === 'asn_name' || column === 'username') {
            aVal = aVal.toString().toLowerCase();
            bVal = bVal.toString().toLowerCase();
        }
        
        if (sortAscending) {
            return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
        } else {
            return bVal > aVal ? 1 : bVal < aVal ? -1 : 0;
        }
    });
    
    // Assign ranks with tie handling
    const ranks = new Map();
    let currentRank = 1;
    let previousValueStr = null;
    
    // Get entity identifier based on dimension
    const getEntityId = (item) => {
        if (currentDimension === 'country') return item.country;
        if (currentDimension === 'ip') return item.ip;
        if (currentDimension === 'asn') return item.asn_name;
        if (currentDimension === 'username') return item.username;
        return item.country; // fallback
    };
    
    sorted.forEach((item, index) => {
        let value = item[column];
        let valueStr;
        
        // Convert to comparable string for tie detection
        if (column === 'first_seen' || column === 'last_seen') {
            valueStr = new Date(value).getTime().toString();
        } else {
            valueStr = String(value);
        }
        
        if (valueStr === previousValueStr) {
            // Same value as previous, same rank (tie)
            // Don't increment currentRank
        } else {
            // New value, set rank to current position (1-indexed)
            currentRank = index + 1;
        }
        
        ranks.set(getEntityId(item), currentRank);
        previousValueStr = valueStr;
    });
    
    return ranks;
}

// Sort data based on current sortColumns (average ranking method)
function sortData() {
    if (sortColumns.length === 1) {
        // Single column sort - simple
        debugRankings = null;  // Clear debug info
        
        filteredData.sort((a, b) => {
            let aVal = a[sortColumns[0]];
            let bVal = b[sortColumns[0]];
            
            // Handle null/undefined values
            if (aVal === null || aVal === undefined) aVal = sortDirection === 'desc' ? -Infinity : Infinity;
            if (bVal === null || bVal === undefined) bVal = sortDirection === 'desc' ? -Infinity : Infinity;
            
            // Handle date strings
            if (sortColumns[0] === 'first_seen' || sortColumns[0] === 'last_seen') {
                aVal = new Date(aVal);
                bVal = new Date(bVal);
            }
            
            // Handle string comparison (for entity names)
            if (sortColumns[0] === 'country' || sortColumns[0] === 'ip' || sortColumns[0] === 'asn_name' || sortColumns[0] === 'username') {
                aVal = aVal.toLowerCase();
                bVal = bVal.toLowerCase();
            }
            
            // Compare
            if (sortDirection === 'desc') {
                return bVal > aVal ? 1 : bVal < aVal ? -1 : 0;
            } else {
                return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
            }
        });
    } else {
        // Multi-column sort - average ranking method
        // Step 1: Calculate ranks for each column
        const rankMaps = sortColumns.map(col => calculateRanks(filteredData, col));
        
        // Get column labels for debug
        const columnLabels = sortColumns.map(col => getColumnLabel(col));
        
        // Step 2: Calculate average rank for each entity
        const avgRanks = filteredData.map(item => {
            const entityId = getEntityId(item);
            const ranks = rankMaps.map(rankMap => rankMap.get(entityId));
            const avgRank = ranks.reduce((sum, rank) => sum + rank, 0) / ranks.length;
            return { item, avgRank, ranks };  // Store individual ranks for debug
        });
        
        // Helper function to get entity ID
        function getEntityId(item) {
            if (currentDimension === 'country') return item.country;
            if (currentDimension === 'ip') return item.ip;
            if (currentDimension === 'asn') return item.asn_name;
            if (currentDimension === 'username') return item.username;
            return item.country; // fallback
        }
        
        // Step 3: Sort by average rank
        avgRanks.sort((a, b) => {
            if (sortDirection === 'desc') {
                return a.avgRank - b.avgRank;  // Lower average rank = better
            } else {
                return b.avgRank - a.avgRank;  // Higher average rank = better
            }
        });
        
        // Store debug info
        debugRankings = { rankMaps, avgRanks, columnLabels };
        
        // Update debug view if it's visible
        if (document.getElementById('debug-section').style.display !== 'none') {
            updateDebugView();
        }
        
        // Update filteredData with sorted order
        filteredData = avgRanks.map(x => x.item);
    }
}

// Get human-readable label for column
function getColumnLabel(column) {
    const labels = {
        'country': 'Country',
        'total_attacks': 'Total Attacks',
        'avg_daily': 'Avg Daily',
        'persistence_pct': 'Persistence %',
        'max_absolute_change': 'Max Absolute Δ',
        'max_pct_change': 'Max % Δ',
        'recent_attacks': 'Recent (7d)',
        'first_seen': 'First Seen',
        'last_seen': 'Last Seen',
        'max_daily': 'Max Daily'
    };
    return labels[column] || column;
}

// Get entity name based on dimension
function getEntityName(item) {
    switch (currentDimension) {
        case 'country': return item.country;
        case 'ip': return item.ip;
        case 'asn': return item.asn_name;
        case 'username': return item.username;
    }
}

// Render table
function renderTable() {
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = startIdx + pageSize;
    const pageData = filteredData.slice(startIdx, endIdx);
    
    // Render header
    renderHeader();
    
    // Render body
    const tbody = document.getElementById('table-body');
    
    if (pageData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" style="text-align: center; padding: 40px;">No data found</td></tr>';
        return;
    }
    
    tbody.innerHTML = pageData.map((item, idx) => {
        const rank = startIdx + idx + 1;
        const entityName = getEntityName(item);
        
        // Use same columns for all dimensions
        return `
            <tr>
                <td>${rank}</td>
                <td><strong>${entityName}</strong></td>
                <td class="number">${formatNumber(item.total_attacks)}</td>
                <td class="number">${formatNumber(item.avg_daily)}</td>
                <td class="number">${item.persistence_pct || 0}% ${item.active_days ? `(${item.active_days}d)` : ''}</td>
                <td class="number">${formatNumber(item.max_absolute_change || 0)}</td>
                <td class="number">${formatNumber(item.max_pct_change || 0)}%</td>
                <td class="number">${formatNumber(item.recent_attacks || 0)}</td>
                <td>${item.first_seen || '-'}</td>
                <td>${item.last_seen || '-'}</td>
                <td class="number">${formatNumber(item.max_daily || 0)}</td>
            </tr>
        `;
    }).join('');
    
    // Update pagination
    updatePagination();
}

// Render table header with sort indicators
function renderHeader() {
    const header = document.getElementById('table-header');
    
    if (currentDimension === 'country') {
        const columns = [
            { label: 'Rank', key: null, tooltip: 'Position in the current sorted list' },
            { label: 'Country', key: 'country', tooltip: 'Country where the attacks originated' },
            { label: 'Total Attacks', key: 'total_attacks', tooltip: 'Total number of attacks across all 69 days' },
            { label: 'Avg Daily', key: 'avg_daily', tooltip: 'Average attacks per day (only counting days with activity)' },
            { label: 'Persistence', key: 'persistence_pct', tooltip: 'Percentage of days this country appeared in logs (e.g., 95% = 65 out of 69 days)' },
            { label: 'Max Absolute Δ', key: 'max_absolute_change', tooltip: 'Largest day-to-day increase in attacks (e.g., went from 100 to 5,000 = Δ4,900)' },
            { label: 'Max % Δ', key: 'max_pct_change', tooltip: 'Largest day-to-day percentage increase (e.g., went from 100 to 500 = 400%)' },
            { label: 'Recent (7d)', key: 'recent_attacks', tooltip: 'Total attacks in the last 7 days of the dataset' },
            { label: 'First Seen', key: 'first_seen', tooltip: 'First date this country appeared in the logs (earlier = more established threat)' },
            { label: 'Last Seen', key: 'last_seen', tooltip: 'Last date this country appeared in the logs (more recent = currently active threat)' },
            { label: 'Max Daily', key: 'max_daily', tooltip: 'Highest single-day attack count' }
        ];
        
        header.innerHTML = columns.map(col => {
            if (!col.key) {
                return `<th title="${col.tooltip}">${col.label}</th>`;
            }
            
            const isInSortList = sortColumns.includes(col.key);
            const sortIndex = sortColumns.indexOf(col.key);
            const indicator = isInSortList ? 
                (sortColumns.length === 1 ? 
                    (sortDirection === 'desc' ? ' ▼' : ' ▲') : 
                    ` [${sortIndex + 1}]`) : 
                '';
            const sortClass = isInSortList ? 'sorted' : '';
            
            return `<th class="${sortClass}" onclick="sortByColumn('${col.key}', event)" style="cursor: pointer; user-select: none;" title="${col.tooltip}">${col.label}${indicator}</th>`;
        }).join('');
    } else {
        // Use same column structure for all dimensions
        const columns = [
            { label: 'Rank', key: null, tooltip: 'Position in the current sorted list' },
            { label: getDimensionLabel(), key: getDimensionKey(), tooltip: `The ${currentDimension} identifier` },
            { label: 'Total Attacks', key: 'total_attacks', tooltip: 'Total number of attacks across all 69 days' },
            { label: 'Avg Daily', key: 'avg_daily', tooltip: 'Average attacks per day (only counting days with activity)' },
            { label: 'Persistence', key: 'persistence_pct', tooltip: 'Percentage of days this entity appeared in logs' },
            { label: 'Max Absolute Δ', key: 'max_absolute_change', tooltip: 'Largest day-to-day increase in attacks' },
            { label: 'Max % Δ', key: 'max_pct_change', tooltip: 'Largest day-to-day percentage increase' },
            { label: 'Recent (7d)', key: 'recent_attacks', tooltip: 'Total attacks in the last 7 days of the dataset' },
            { label: 'First Seen', key: 'first_seen', tooltip: 'First date this entity appeared in the logs' },
            { label: 'Last Seen', key: 'last_seen', tooltip: 'Last date this entity appeared in the logs' },
            { label: 'Max Daily', key: 'max_daily', tooltip: 'Highest single-day attack count' }
        ];
        
        header.innerHTML = columns.map(col => {
            if (!col.key) {
                return `<th title="${col.tooltip}">${col.label}</th>`;
            }
            
            const isInSortList = sortColumns.includes(col.key);
            const sortIndex = sortColumns.indexOf(col.key);
            const indicator = isInSortList ? 
                (sortColumns.length === 1 ? 
                    (sortDirection === 'desc' ? ' ▼' : ' ▲') : 
                    ` [${sortIndex + 1}]`) : 
                '';
            const sortClass = isInSortList ? 'sorted' : '';
            
            return `<th class="${sortClass}" onclick="sortByColumn('${col.key}', event)" style="cursor: pointer; user-select: none;" title="${col.tooltip}">${col.label}${indicator}</th>`;
        }).join('');
    }
}

// Get dimension key for entity name column
function getDimensionKey() {
    const keys = {
        'country': 'country',
        'ip': 'ip',
        'asn': 'asn_name',
        'username': 'username'
    };
    return keys[currentDimension];
}

// Get dimension label
function getDimensionLabel() {
    const labels = {
        'country': 'Country',
        'ip': 'IP Address',
        'asn': 'ASN Name',
        'username': 'Username'
    };
    return labels[currentDimension];
}

// Update quick stats
function updateQuickStats() {
    const totalEntities = allData.length;
    document.getElementById('total-entities').textContent = formatNumber(totalEntities);
}

// Pagination functions
function updatePagination() {
    const totalPages = Math.ceil(filteredData.length / pageSize);
    
    document.getElementById('page-info').textContent = `Page ${currentPage} of ${totalPages}`;
    document.getElementById('prev-btn').disabled = currentPage === 1;
    document.getElementById('next-btn').disabled = currentPage === totalPages || totalPages === 0;
}

function previousPage() {
    if (currentPage > 1) {
        currentPage--;
        renderTable();
        window.scrollTo(0, 0);
    }
}

function nextPage() {
    const totalPages = Math.ceil(filteredData.length / pageSize);
    if (currentPage < totalPages) {
        currentPage++;
        renderTable();
        window.scrollTo(0, 0);
    }
}

function changePageSize() {
    pageSize = parseInt(document.getElementById('page-size').value);
    currentPage = 1;
    renderTable();
}

// Reset filters
function resetFilters() {
    document.getElementById('search-box').value = '';
    applyFilters();
}

// Utility functions
function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    return num.toLocaleString();
}

function truncate(str, maxLen) {
    if (!str) return '-';
    return str.length > maxLen ? str.substring(0, maxLen) + '...' : str;
}