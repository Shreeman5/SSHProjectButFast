// Discovery Dashboard - Data Module
// API calls, data loading, filtering, and sorting functions

// Load data for current dimension
async function loadData() {
    try {
        // Reset state
        allData = [];
        hasMoreData = true;
        
        // Fetch total count for debugging
        await fetchTotalCount();
        
        // Initial load - get first batch
        await loadMoreData();
        
        updateQuickStats();
    } catch (error) {
        console.error('Error loading data:', error);
        document.getElementById('table-body').innerHTML = 
            '<tr><td colspan="15" style="text-align: center; padding: 40px; color: red;">Error loading data. The dataset may be too large.</td></tr>';
    }
}

// Fetch total count for current dimension
async function fetchTotalCount() {
    try {
        const response = await fetch(`${API_BASE}/api/${currentDimension}_count?start=2022-11-01&end=2023-01-08`);
        const data = await response.json();
        
        let total = 0;
        let label = '';
        
        if (currentDimension === 'country') {
            total = data.total_countries;
            label = 'countries';
        } else if (currentDimension === 'ip') {
            total = data.total_ips;
            label = 'IPs';
        } else if (currentDimension === 'asn') {
            total = data.total_asns;
            label = 'ASNs';
        } else if (currentDimension === 'username') {
            total = data.total_usernames;
            label = 'usernames';
        }
        
        console.log(`%c[${currentDimension.toUpperCase()}] Total unique ${label}: ${total.toLocaleString()}`, 'color: #667eea; font-weight: bold; font-size: 14px;');
        
    } catch (error) {
        console.error('Error fetching total count:', error);
    }
}

// Load next batch of data
async function loadMoreData() {
    if (isLoadingMore || !hasMoreData) return;
    
    isLoadingMore = true;
    updateLoadingIndicator(true);
    
    try {
        const offset = allData.length;
        const url = `${API_BASE}/api/${currentDimension}_summary?start=2022-11-01&end=2023-01-08&limit=${batchSize}&offset=${offset}`;
        
        console.log(`Fetching: ${url}`);
        
        const response = await fetch(url);
        
        // Check if response is ok
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // Check content type
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            const text = await response.text();
            console.error('Received non-JSON response:', text.substring(0, 500));
            throw new Error(`Expected JSON, got ${contentType}`);
        }
        
        const newData = await response.json();
        
        // Validate data is an array
        if (!Array.isArray(newData)) {
            console.error('Received invalid data:', newData);
            throw new Error('Expected array of data');
        }
        
        if (newData.length === 0) {
            console.log('No more data to load');
            hasMoreData = false;
            updateLoadingIndicator(false);
            
            // If this was the first load and we got no data, show message
            if (offset === 0) {
                document.getElementById('table-body').innerHTML = 
                    '<tr><td colspan="15" style="text-align: center; padding: 40px;">No data found for this dimension.</td></tr>';
            }
            return;
        }
        
        // Append new data
        allData = allData.concat(newData);
        
        // Check if we got less than batch size (means we're done)
        if (newData.length < batchSize) {
            hasMoreData = false;
        }
        
        console.log(`✓ Loaded ${newData.length} ${currentDimension}s (total: ${allData.length})`);
        
        // Default sort by total_attacks descending on first load
        if (offset === 0) {
            sortColumns = ['total_attacks'];
            sortDirection = 'desc';
        }
        
        applyFilters();
        updateLoadMoreButton();
        
    } catch (error) {
        console.error('❌ Error loading batch:', error);
        hasMoreData = false;
        
        // Show error message in table
        if (allData.length === 0) {
            document.getElementById('table-body').innerHTML = 
                `<tr><td colspan="15" style="text-align: center; padding: 40px; color: red;">
                    <strong>Error loading data</strong><br>
                    ${error.message}<br>
                    <small>Check browser console for details</small>
                </td></tr>`;
        }
    } finally {
        isLoadingMore = false;
        updateLoadingIndicator(false);
    }
}

// Update loading indicator
function updateLoadingIndicator(show) {
    const indicator = document.getElementById('loading-indicator');
    if (indicator) {
        indicator.style.display = show ? 'block' : 'none';
    }
}

// Update "Load More" button
function updateLoadMoreButton() {
    const btnContainer = document.getElementById('load-more-container');
    if (!btnContainer) return;
    
    if (hasMoreData) {
        btnContainer.innerHTML = `
            <button onclick="loadMoreData()" style="padding: 12px 24px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: 600;">
                📥 Load More (${allData.length.toLocaleString()} loaded)
            </button>
        `;
        btnContainer.style.display = 'block';
    } else {
        btnContainer.innerHTML = `
            <div style="padding: 12px; color: #666; font-style: italic;">
                ✓ All ${allData.length.toLocaleString()} ${currentDimension}s loaded
            </div>
        `;
        btnContainer.style.display = 'block';
    }
}

// Apply filters
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
            
            // If we're back to 1 column, hide debug and clear rankings
            if (sortColumns.length === 1) {
                debugRankings = null;
                const debugSection = document.getElementById('debug-section');
                if (debugSection && debugSection.style.display !== 'none') {
                    toggleDebug();
                }
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
        
        // Clear debug rankings and hide section
        debugRankings = null;
        const debugSection = document.getElementById('debug-section');
        if (debugSection && debugSection.style.display !== 'none') {
            toggleDebug();
        }
    }
    
    sortData();
    renderTable();
}

// Calculate ranks for each column (with tie handling)
function calculateRanks(data, column) {
    // Determine sort direction based on column type
    let sortAscending = false;
    
    if (column === 'first_seen') {
        sortAscending = true;
    } else if (column === 'last_seen') {
        sortAscending = false;
    } else if (column === 'country' || column === 'ip' || column === 'asn_name' || column === 'username') {
        sortAscending = true;
    }
    
    // Sort by column value
    const sorted = [...data].sort((a, b) => {
        let aVal = a[column] ?? (sortAscending ? Infinity : -Infinity);
        let bVal = b[column] ?? (sortAscending ? Infinity : -Infinity);
        
        if (column === 'first_seen' || column === 'last_seen') {
            aVal = new Date(aVal);
            bVal = new Date(bVal);
        }
        
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
    
    const getEntityId = (item) => {
        if (currentDimension === 'country') return item.country;
        if (currentDimension === 'ip') return item.ip;
        if (currentDimension === 'asn') return item.asn_name;
        if (currentDimension === 'username') return item.username;
        return item.country;
    };
    
    sorted.forEach((item, index) => {
        let value = item[column];
        let valueStr;
        
        if (column === 'first_seen' || column === 'last_seen') {
            valueStr = new Date(value).getTime().toString();
        } else {
            valueStr = String(value);
        }
        
        if (valueStr === previousValueStr) {
            // Same value, same rank (tie)
        } else {
            currentRank = index + 1;
        }
        
        ranks.set(getEntityId(item), currentRank);
        previousValueStr = valueStr;
    });
    
    return ranks;
}

// Sort data based on current sortColumns
function sortData() {
    // Helper function to map concentration display columns to sortable numeric fields
    const getSortKey = (column) => {
        const concentrationMap = {
            'asn_concentration': 'asn_top1_pct',
            'ip_concentration': 'ip_top1_pct',
            'username_concentration': 'username_top1_pct'
        };
        return concentrationMap[column] || column;
    };
    
    if (sortColumns.length === 1) {
        // Single column sort
        debugRankings = null;
        
        const sortKey = getSortKey(sortColumns[0]);
        
        filteredData.sort((a, b) => {
            let aVal = a[sortKey];
            let bVal = b[sortKey];
            
            if (aVal === null || aVal === undefined) aVal = sortDirection === 'desc' ? -Infinity : Infinity;
            if (bVal === null || bVal === undefined) bVal = sortDirection === 'desc' ? -Infinity : Infinity;
            
            if (sortColumns[0] === 'first_seen' || sortColumns[0] === 'last_seen') {
                aVal = new Date(aVal);
                bVal = new Date(bVal);
            }
            
            if (sortColumns[0] === 'country' || sortColumns[0] === 'ip' || sortColumns[0] === 'asn_name' || sortColumns[0] === 'username') {
                aVal = aVal.toLowerCase();
                bVal = bVal.toLowerCase();
            }
            
            if (sortDirection === 'desc') {
                return bVal > aVal ? 1 : bVal < aVal ? -1 : 0;
            } else {
                return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
            }
        });
    } else {
        // Multi-column sort - average ranking method
        const rankMaps = sortColumns.map(col => calculateRanks(filteredData, getSortKey(col)));
        const columnLabels = sortColumns.map(col => getColumnLabel(col));
        
        const avgRanks = filteredData.map(item => {
            const entityId = getEntityId(item);
            const ranks = rankMaps.map(rankMap => rankMap.get(entityId));
            const avgRank = ranks.reduce((sum, rank) => sum + rank, 0) / ranks.length;
            return { item, avgRank, ranks };
        });
        
        function getEntityId(item) {
            if (currentDimension === 'country') return item.country;
            if (currentDimension === 'ip') return item.ip;
            if (currentDimension === 'asn') return item.asn_name;
            if (currentDimension === 'username') return item.username;
            return item.country;
        }
        
        avgRanks.sort((a, b) => {
            if (sortDirection === 'desc') {
                return a.avgRank - b.avgRank;
            } else {
                return b.avgRank - a.avgRank;
            }
        });
        
        debugRankings = { rankMaps, avgRanks, columnLabels };
        
        if (document.getElementById('debug-section').style.display !== 'none') {
            updateDebugView();
        }
        
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