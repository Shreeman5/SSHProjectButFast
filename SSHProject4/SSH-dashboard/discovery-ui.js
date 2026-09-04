// Discovery Dashboard - UI Module
// UI interactions, column selector, dimension switching, debug view

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
    
    // Build table showing top 20 entities with their ranks
    let html = '<table style="width: 100%; border-collapse: collapse;">';
    html += '<thead><tr style="background: #f5f5f5;">';
    html += '<th style="padding: 8px; border: 1px solid #ddd;">Final Rank</th>';
    html += '<th style="padding: 8px; border: 1px solid #ddd;">Entity</th>';
    html += '<th style="padding: 8px; border: 1px solid #ddd;">Avg Rank</th>';
    
    columnLabels.forEach(label => {
        html += `<th style="padding: 8px; border: 1px solid #ddd;">${label} Rank</th>`;
    });
    
    html += '</tr></thead><tbody>';
    
    avgRanks.slice(0, 20).forEach((entry, finalRank) => {
        html += '<tr>';
        html += `<td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">${finalRank + 1}</td>`;
        html += `<td style="padding: 8px; border: 1px solid #ddd;">${getEntityName(entry.item)}</td>`;
        html += `<td style="padding: 8px; border: 1px solid #ddd;">${entry.avgRank.toFixed(2)}</td>`;
        
        entry.ranks.forEach(rank => {
            html += `<td style="padding: 8px; border: 1px solid #ddd;">${rank}</td>`;
        });
        
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    html += '<p style="margin-top: 16px; color: #666; font-size: 13px;">Showing top 20. Each entity ranked independently on each column, then averaged.</p>';
    
    debugContent.innerHTML = html;
}

// Toggle column selector dropdown
function toggleColumnSelector() {
    const dropdown = document.getElementById('column-selector-dropdown');
    if (dropdown.style.display === 'none') {
        dropdown.style.display = 'block';
        renderColumnOptions();
        setTimeout(() => {
            document.addEventListener('click', closeColumnSelectorOnClickOutside);
        }, 0);
    } else {
        dropdown.style.display = 'none';
        document.removeEventListener('click', closeColumnSelectorOnClickOutside);
    }
}

// Close column selector when clicking outside
function closeColumnSelectorOnClickOutside(event) {
    const dropdown = document.getElementById('column-selector-dropdown');
    const button = document.getElementById('column-selector-btn');
    
    // Check if click is outside both the button and dropdown
    if (!dropdown.contains(event.target) && !button.contains(event.target)) {
        dropdown.style.display = 'none';
        document.removeEventListener('click', closeColumnSelectorOnClickOutside);
    }
}

// Render column options based on current dimension
function renderColumnOptions() {
    const container = document.getElementById('column-checkboxes');
    const optionalCols = OPTIONAL_COLUMNS[currentDimension] || [];
    
    if (optionalCols.length === 0) {
        container.innerHTML = '<div style="padding: 12px; text-align: center; color: #999;">No additional columns available for this dimension</div>';
        return;
    }
    
    const prefs = columnPreferences[currentDimension];
    
    container.innerHTML = optionalCols.map(col => `
        <div class="column-option">
            <input type="checkbox" 
                   id="col-${col.key}" 
                   ${prefs[col.key] ? 'checked' : ''}
                   onchange="toggleColumn('${col.key}')">
            <label for="col-${col.key}" class="column-option-label">
                ${col.label}
                <span class="column-option-tooltip" title="${col.tooltip}">ⓘ</span>
            </label>
        </div>
    `).join('');
}

// Toggle individual column
function toggleColumn(columnKey) {
    const prefs = columnPreferences[currentDimension];
    const wasVisible = prefs[columnKey];
    prefs[columnKey] = !prefs[columnKey];
    saveColumnPreferences(currentDimension, prefs);
    
    // If hiding a column that's currently in the sort list, remove it
    if (wasVisible && sortColumns.includes(columnKey)) {
        const index = sortColumns.indexOf(columnKey);
        sortColumns.splice(index, 1);
        
        // If we removed all columns from sort, default to total_attacks
        if (sortColumns.length === 0) {
            sortColumns = ['total_attacks'];
        }
        
        // Clear debug rankings if we're back to single column
        if (sortColumns.length === 1) {
            debugRankings = null;
        }
        
        // Re-sort with remaining columns
        applyFilters();
    } else {
        // Just re-render without re-sorting
        renderHeader();
        renderTable();
    }
}

// Select all columns
function selectAllColumns() {
    const prefs = columnPreferences[currentDimension];
    const optionalCols = OPTIONAL_COLUMNS[currentDimension] || [];
    
    optionalCols.forEach(col => {
        prefs[col.key] = true;
    });
    
    saveColumnPreferences(currentDimension, prefs);
    renderColumnOptions();
    renderHeader();
    renderTable();
}

// Deselect all columns
function deselectAllColumns() {
    const prefs = columnPreferences[currentDimension];
    const optionalCols = OPTIONAL_COLUMNS[currentDimension] || [];
    
    // Track which columns are being hidden
    const columnsBeingHidden = [];
    
    optionalCols.forEach(col => {
        if (prefs[col.key]) {
            columnsBeingHidden.push(col.key);
        }
        prefs[col.key] = false;
    });
    
    // Remove any hidden columns from sort list
    sortColumns = sortColumns.filter(col => !columnsBeingHidden.includes(col));
    
    // If we removed all columns from sort, default to total_attacks
    if (sortColumns.length === 0) {
        sortColumns = ['total_attacks'];
    }
    
    // Clear debug rankings if we're back to single column
    if (sortColumns.length === 1) {
        debugRankings = null;
    }
    
    saveColumnPreferences(currentDimension, prefs);
    renderColumnOptions();
    
    // Re-sort with remaining columns
    applyFilters();
}

// Switch dimension
function switchDimension(dimension) {
    currentDimension = dimension;
    
    // Update active button
    document.querySelectorAll('.dim-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    
    // Clear selection state
    selectedCountries.clear();
    selectedASNs.clear();
    
    // Close column dropdown when switching dimensions
    const dropdown = document.getElementById('column-selector-dropdown');
    if (dropdown) {
        dropdown.style.display = 'none';
    }
    
    // Show/hide similar IPs search (only for IP dimension)
    const similarSearch = document.getElementById('similar-ips-search');
    if (similarSearch) {
        similarSearch.style.display = (dimension === 'ip') ? 'block' : 'none';
        
        // Clear search when switching away from IP
        if (dimension !== 'ip') {
            clearSimilarSearch();
        }
    }
    
    // Show/hide IP cluster builder (only for IP dimension)
    const clusterBuilder = document.getElementById('ip-cluster-builder');
    if (clusterBuilder) {
        clusterBuilder.style.display = (dimension === 'ip') ? 'block' : 'none';
        
        // Clear cluster when switching away from IP
        if (dimension !== 'ip' && typeof clearCluster === 'function') {
            clearCluster();
        }
    }
    
    // Show/hide similar usernames search (only for username dimension)
    const similarUsernameSearch = document.getElementById('similar-usernames-search');
    if (similarUsernameSearch) {
        similarUsernameSearch.style.display = (dimension === 'username') ? 'block' : 'none';
        
        // Clear search when switching away from username, so results from one
        // dimension are never left on screen under another dimension's heading
        if (dimension !== 'username' && typeof clearSimilarUsernameSearch === 'function') {
            clearSimilarUsernameSearch();
        }
    }
    
    // Show/hide tag manager (R4). Currently wired for the username dimension;
    // the API is dimension-scoped, so extending it to ip/asn/country is a
    // matter of widening this condition once those tabs have tag columns.
    const tagManager = document.getElementById('tag-manager');
    if (tagManager) {
        tagManager.style.display = (dimension === 'username') ? 'block' : 'none';
        
        if (dimension === 'username' && typeof loadTags === 'function') {
            document.getElementById('operator-name').textContent =
                localStorage.getItem('discovery_operator') || 'not set';
            loadTags();
        }
    }
    
    // Load data for new dimension
    loadData();
    renderHeader();
    
    // Show/hide "Analyze Selected" button based on dimension
    const analyzeBtn = document.getElementById('analyze-selected-btn');
    if (analyzeBtn) {
        if (dimension === 'country' || dimension === 'asn') {
            analyzeBtn.style.display = 'inline-block';
            updateSelectedCount();
        } else {
            analyzeBtn.style.display = 'none';
        }
    }
}

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
    loadData();
    renderHeader();
});