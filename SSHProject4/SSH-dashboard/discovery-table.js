// Discovery Dashboard - Table Module
// Table rendering, formatting, and selection functions

// Render table body with current page data
function renderTable() {
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = startIdx + pageSize;
    const pageData = filteredData.slice(startIdx, endIdx);
    
    // Render header
    renderHeader();
    
    // Render body
    const tbody = document.getElementById('table-body');
    
    if (pageData.length === 0) {
        const colspan = (currentDimension === 'country' || currentDimension === 'asn') ? 13 : 12;
        tbody.innerHTML = `<tr><td colspan="${colspan}" style="text-align: center; padding: 40px;">No data found</td></tr>`;
        return;
    }
    
    tbody.innerHTML = pageData.map((item, idx) => {
        const rank = startIdx + idx + 1;
        const entityName = getEntityName(item);
        
        if (currentDimension === 'country') {
            const isSelected = selectedCountries.has(item.country);
            const isDisabled = !isSelected && selectedCountries.size >= MAX_SELECTED;
            
            // Build row HTML dynamically based on visible columns
            // Get attack profile badge
            const profileBadges = {
                'High-Volume Spray': '<span style="background: #3b82f6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 6px;" title="Many IPs, many usernames">🌊 Spray</span>',
                'Targeted Brute Force': '<span style="background: #ef4444; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 6px;" title="Few IPs, many attempts on few usernames">🎯 Brute</span>',
                'Distributed Botnet': '<span style="background: #8b5cf6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 6px;" title="Many ASNs, many IPs">🕸️ Botnet</span>',
                'Single Source': '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 6px;" title="One ASN, few IPs">📍 Single</span>',
                'General Scanning': '<span style="background: #6b7280; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 6px;" title="General attack pattern">🔍 Scan</span>'
            };
            const badge = profileBadges[item.attack_profile] || '';
            
            let rowHTML = `
                <tr>
                    <td style="text-align: center;">
                        <input type="checkbox" 
                               class="country-checkbox" 
                               data-country="${item.country.replace(/"/g, '&quot;')}"
                               ${isSelected ? 'checked' : ''}
                               ${isDisabled ? 'disabled' : ''}
                               style="cursor: ${isDisabled && !isSelected ? 'not-allowed' : 'pointer'}; width: 16px; height: 16px;">
                    </td>
                    <td>${rank}</td>
                    <td><strong>${entityName}</strong>${badge}</td>`;
            
            // Add all visible columns dynamically
            const prefs = columnPreferences[currentDimension];
            const availableCols = OPTIONAL_COLUMNS[currentDimension] || [];
            
            availableCols.forEach(col => {
                if (prefs[col.key]) {
                    rowHTML += renderColumnData(item, col.key);
                }
            });
            
            rowHTML += `</tr>`;
            return rowHTML;
        } else if (currentDimension === 'asn') {
            const isSelected = selectedASNs.has(item.asn_name);
            const isDisabled = !isSelected && selectedASNs.size >= MAX_SELECTED;
            
            return `
                <tr>
                    <td style="text-align: center;">
                        <input type="checkbox" 
                               class="asn-checkbox" 
                               data-asn="${item.asn_name.replace(/"/g, '&quot;')}"
                               ${isSelected ? 'checked' : ''}
                               ${isDisabled ? 'disabled' : ''}
                               style="cursor: ${isDisabled && !isSelected ? 'not-allowed' : 'pointer'}; width: 16px; height: 16px;">
                    </td>
                    <td>${rank}</td>
                    <td><strong>${entityName}</strong></td>
                    <td class="number">${formatNumber(item.total_attacks)}</td>
                    <td class="number">${formatNumber(item.avg_daily)}</td>
                    <td class="number">${formatPercentage(item.persistence_pct || 0)} ${item.active_days ? `(${item.active_days}d)` : ''}</td>
                    <td class="number">${formatNumber(item.max_absolute_change || 0)}</td>
                    <td class="number">${formatPercentage(item.max_pct_change || 0)}</td>
                    <td class="number">${formatNumber(item.recent_attacks || 0)}</td>
                    <td>${formatDate(item.first_seen)}</td>
                    <td>${formatDate(item.last_seen)}</td>
                    <td class="number">${formatNumber(item.max_daily || 0)}</td>
                </tr>
            `;
        } else {
            return `
                <tr>
                    <td>${rank}</td>
                    <td><strong>${entityName}</strong></td>
                    <td class="number">${formatNumber(item.total_attacks)}</td>
                    <td class="number">${formatNumber(item.avg_daily)}</td>
                    <td class="number">${formatPercentage(item.persistence_pct || 0)} ${item.active_days ? `(${item.active_days}d)` : ''}</td>
                    <td class="number">${formatNumber(item.max_absolute_change || 0)}</td>
                    <td class="number">${formatPercentage(item.max_pct_change || 0)}</td>
                    <td class="number">${formatNumber(item.recent_attacks || 0)}</td>
                    <td>${formatDate(item.first_seen)}</td>
                    <td>${formatDate(item.last_seen)}</td>
                    <td class="number">${formatNumber(item.max_daily || 0)}</td>
                </tr>
            `;
        }
    }).join('');
    
    updatePagination();
    
    // Add event listeners for checkboxes
    if (currentDimension === 'country') {
        const checkboxes = document.querySelectorAll('.country-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                toggleCountrySelection(this.getAttribute('data-country'));
            });
        });
    } else if (currentDimension === 'asn') {
        const checkboxes = document.querySelectorAll('.asn-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                toggleASNSelection(this.getAttribute('data-asn'));
            });
        });
    }
}

// Render header (continued in next part due to size)
function renderHeader() {
    const header = document.getElementById('table-header');
    
    if (currentDimension === 'country') {
        // Start with fixed columns (checkbox, rank, country name)
        const columns = [
            { label: '', key: null, tooltip: 'Select for analysis', sortable: false, isCheckbox: true },
            { label: 'Rank', key: null, tooltip: 'Position in the current sorted list', sortable: false },
            { label: 'Country', key: 'country', tooltip: 'Country where attacks originated', sortable: false }
        ];
        
        // Add columns based on user preferences
        const prefs = columnPreferences[currentDimension];
        const availableCols = OPTIONAL_COLUMNS[currentDimension] || [];
        
        availableCols.forEach(col => {
            if (prefs[col.key]) {
                columns.push({
                    label: col.label,
                    key: col.key,
                    tooltip: col.tooltip,
                    sortable: true
                });
            }
        });
        
        header.innerHTML = columns.map(col => {
            if (col.isCheckbox) {
                return `<th style="width: 40px;" title="${col.tooltip}">
                    <input type="checkbox" id="select-all" onchange="toggleSelectAll()" 
                           style="cursor: pointer; width: 16px; height: 16px;">
                </th>`;
            }
            
            if (!col.sortable) {
                return `<th title="${col.tooltip}">${col.label}</th>`;
            }
            
            const sortClass = getSortClass(col.key);
            const indicator = getSortIndicator(col.key);
            
            return `<th class="${sortClass}" onclick="sortByColumn('${col.key}', event)" style="cursor: pointer; user-select: none;" title="${col.tooltip}">${col.label}${indicator}</th>`;
        }).join('');
    } else if (currentDimension === 'asn') {
        const columns = [
            { label: '', key: null, tooltip: 'Select for analysis', sortable: false, isCheckbox: true },
            { label: 'Rank', key: null, tooltip: 'Position in sorted list', sortable: false },
            { label: 'ASN', key: 'asn_name', tooltip: 'ASN organization name', sortable: false },
            { label: 'Total Attacks', key: 'total_attacks', tooltip: 'Total attacks', sortable: true },
            { label: 'Avg Daily', key: 'avg_daily', tooltip: 'Average per day', sortable: true },
            { label: 'Persistence', key: 'persistence_pct', tooltip: 'Percentage of days active', sortable: true },
            { label: 'Max Absolute Δ', key: 'max_absolute_change', tooltip: 'Largest increase', sortable: true },
            { label: 'Max % Δ', key: 'max_pct_change', tooltip: 'Largest % increase', sortable: true },
            { label: 'Recent (7d)', key: 'recent_attacks', tooltip: 'Last 7 days', sortable: true },
            { label: 'First Seen', key: 'first_seen', tooltip: 'First date', sortable: true },
            { label: 'Last Seen', key: 'last_seen', tooltip: 'Last date', sortable: true },
            { label: 'Max Daily', key: 'max_daily', tooltip: 'Highest daily', sortable: true }
        ];
        
        header.innerHTML = columns.map(col => {
            if (col.isCheckbox) {
                return `<th style="width: 40px;" title="${col.tooltip}">
                    <input type="checkbox" id="select-all" onchange="toggleSelectAllASN()" 
                           style="cursor: pointer; width: 16px; height: 16px;">
                </th>`;
            }
            
            if (!col.sortable) {
                return `<th title="${col.tooltip}">${col.label}</th>`;
            }
            
            const sortClass = getSortClass(col.key);
            const indicator = getSortIndicator(col.key);
            
            return `<th class="${sortClass}" onclick="sortByColumn('${col.key}', event)" style="cursor: pointer; user-select: none;" title="${col.tooltip}">${col.label}${indicator}</th>`;
        }).join('');
    } else {
        const columns = [
            { label: 'Rank', key: null, tooltip: 'Position', sortable: false },
            { label: getDimensionLabel(), key: getDimensionKey(), tooltip: `The ${currentDimension}`, sortable: false },
            { label: 'Total Attacks', key: 'total_attacks', tooltip: 'Total', sortable: true },
            { label: 'Avg Daily', key: 'avg_daily', tooltip: 'Average', sortable: true },
            { label: 'Persistence', key: 'persistence_pct', tooltip: '% of days', sortable: true },
            { label: 'Max Absolute Δ', key: 'max_absolute_change', tooltip: 'Max increase', sortable: true },
            { label: 'Max % Δ', key: 'max_pct_change', tooltip: 'Max %', sortable: true },
            { label: 'Recent (7d)', key: 'recent_attacks', tooltip: 'Last 7d', sortable: true },
            { label: 'First Seen', key: 'first_seen', tooltip: 'First', sortable: true },
            { label: 'Last Seen', key: 'last_seen', tooltip: 'Last', sortable: true },
            { label: 'Max Daily', key: 'max_daily', tooltip: 'Max', sortable: true }
        ];
        
        header.innerHTML = columns.map(col => {
            if (!col.sortable) {
                return `<th title="${col.tooltip}">${col.label}</th>`;
            }
            
            const sortClass = getSortClass(col.key);
            const indicator = getSortIndicator(col.key);
            
            return `<th class="${sortClass}" onclick="sortByColumn('${col.key}', event)" style="cursor: pointer; user-select: none;" title="${col.tooltip}">${col.label}${indicator}</th>`;
        }).join('');
    }
}

function getDimensionKey() {
    return {'country': 'country', 'ip': 'ip', 'asn': 'asn_name', 'username': 'username'}[currentDimension];
}

function getDimensionLabel() {
    return {'country': 'Country', 'ip': 'IP Address', 'asn': 'ASN Name', 'username': 'Username'}[currentDimension];
}

// Formatting
function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toLocaleString();
}

function formatPercentage(num) {
    if (num === null || num === undefined) return '-';
    if (num >= 1000000) return (num / 1000000).toFixed(2) + 'M%';
    if (num >= 10000) return (num / 1000).toFixed(2) + 'K%';
    return num.toFixed(2) + '%';
}

function formatDate(dateStr) {
    if (!dateStr || dateStr === '-') return '-';
    const parts = dateStr.split('-');
    const year = parseInt(parts[0]);
    const month = parseInt(parts[1]) - 1;
    const day = parseInt(parts[2].split('T')[0]);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${months[month]} ${day}, ${year}`;
}

function truncate(str, maxLen) {
    if (!str) return '-';
    return str.length > maxLen ? str.substring(0, maxLen) + '...' : str;
}

// Country selection
function toggleCountrySelection(country) {
    if (selectedCountries.has(country)) {
        selectedCountries.delete(country);
    } else {
        if (selectedCountries.size < MAX_SELECTED) {
            selectedCountries.add(country);
        }
    }
    updateSelectedCount();
    renderTable();
}

function toggleSelectAll() {
    const checkbox = document.getElementById('select-all');
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = startIdx + pageSize;
    const pageData = filteredData.slice(startIdx, endIdx);
    
    if (checkbox.checked) {
        for (const item of pageData) {
            if (selectedCountries.size >= MAX_SELECTED) break;
            selectedCountries.add(item.country);
        }
    } else {
        for (const item of pageData) {
            selectedCountries.delete(item.country);
        }
    }
    updateSelectedCount();
    renderTable();
}

function updateSelectedCount() {
    const span = document.getElementById('selected-count');
    if (span) span.textContent = selectedCountries.size;
    
    const btn = document.getElementById('analyze-selected-btn');
    if (btn && currentDimension === 'country') {
        btn.style.opacity = selectedCountries.size === 0 ? '0.5' : '1';
        btn.style.cursor = selectedCountries.size === 0 ? 'not-allowed' : 'pointer';
    }
}

// ASN selection
function toggleASNSelection(asnName) {
    if (selectedASNs.has(asnName)) {
        selectedASNs.delete(asnName);
    } else {
        if (selectedASNs.size < MAX_SELECTED) {
            selectedASNs.add(asnName);
        }
    }
    updateSelectedCountASN();
    renderTable();
}

function toggleSelectAllASN() {
    const checkbox = document.getElementById('select-all');
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = startIdx + pageSize;
    const pageData = filteredData.slice(startIdx, endIdx);
    
    if (checkbox.checked) {
        for (const item of pageData) {
            if (selectedASNs.size >= MAX_SELECTED) break;
            selectedASNs.add(item.asn_name);
        }
    } else {
        for (const item of pageData) {
            selectedASNs.delete(item.asn_name);
        }
    }
    updateSelectedCountASN();
    renderTable();
}

function updateSelectedCountASN() {
    const span = document.getElementById('selected-count');
    if (span) span.textContent = selectedASNs.size;
    
    const btn = document.getElementById('analyze-selected-btn');
    if (btn && currentDimension === 'asn') {
        btn.style.opacity = selectedASNs.size === 0 ? '0.5' : '1';
        btn.style.cursor = selectedASNs.size === 0 ? 'not-allowed' : 'pointer';
    }
}

// Analyze
function analyzeSelected() {
    if (selectedCountries.size === 0 && selectedASNs.size === 0) {
        alert('Please select at least one country or ASN to analyze.');
        return;
    }
    
    let url = 'http://127.0.0.1:5500/SSH-dashboard/dashboard.html?';
    
    if (selectedCountries.size > 0) {
        const countries = Array.from(selectedCountries);
        url += `countries=${encodeURIComponent(countries.join(','))}`;
    } else if (selectedASNs.size > 0) {
        const asns = Array.from(selectedASNs);
        url += `asns=${encodeURIComponent(asns.join('|||'))}`;
    }
    
    window.open(url, '_blank');
}

// Render column data for any column type
function renderColumnData(item, columnKey) {
    const value = item[columnKey];
    
    // Check if this column is currently being sorted
    const isSorted = sortColumns.includes(columnKey);
    
    const sortedClass = isSorted ? ' sorted-col' : '';
    
    // Handle different column types
    switch(columnKey) {
        // Numeric columns
        case 'total_attacks':
        case 'avg_daily':
        case 'max_absolute_change':
        case 'recent_attacks':
        case 'max_daily':
        case 'unique_asns':
        case 'unique_ips':
        case 'unique_usernames':
            return `<td class="number${sortedClass}">${formatNumber(value || 0)}</td>`;
        
        // Stability columns (0.000-1.000 with color coding)
        case 'asn_stability':
        case 'ip_stability':
        case 'username_stability':
            if (value === null || value === undefined) {
                return `<td class="number${sortedClass}">N/A</td>`;
            }
            // Color code: green = stable (>0.7), yellow = moderate (0.3-0.7), red = volatile (<0.3)
            let stabilityColor = '';
            if (value >= 0.7) {
                stabilityColor = ' style="color: #2d7f3f;"'; // Green
            } else if (value >= 0.3) {
                stabilityColor = ' style="color: #d4a506;"'; // Yellow/Gold
            } else {
                stabilityColor = ' style="color: #c53030;"'; // Red
            }
            return `<td class="number${sortedClass}"${stabilityColor}>${value.toFixed(3)}</td>`;
        
        // Peak hours column
        case 'peak_hours':
            if (!value) {
                return `<td class="text${sortedClass}">N/A</td>`;
            }
            // Value format: "14:00 (25.3%), 15:00 (18.7%), 02:00 (12.1%)"
            // Wrap in small font and break into multiple lines for readability
            const formattedHours = value.split(', ').map(hour => {
                return `<div style="font-size: 0.85em; white-space: nowrap;">${hour}</div>`;
            }).join('');
            return `<td class="text${sortedClass}" style="line-height: 1.4;">${formattedHours}</td>`;
        
        // Percentage columns
        case 'max_pct_change':
            return `<td class="number${sortedClass}">${formatPercentage(value || 0)}</td>`;
        
        // Persistence (percentage + days)
        case 'persistence_pct':
            return `<td class="number${sortedClass}">${formatPercentage(value || 0)} ${item.active_days ? `(${item.active_days}d)` : ''}</td>`;
        
        // Date columns
        case 'first_seen':
        case 'last_seen':
            return `<td class="${sortedClass.trim()}">${formatDate(value)}</td>`;
        
        // Concentration columns (show top 3 with visual formatting)
        case 'asn_concentration':
            if (!value) return `<td class="${sortedClass.trim()}" style="text-align: center;">-</td>`;
            
            // ASN names can contain commas, so we use ||| as delimiter
            const asnItems = value.split('|||');
            const asnFormatted = asnItems.map((item, idx) => {
                const rank = idx + 1;
                const emoji = rank === 1 ? '🥇' : rank === 2 ? '🥈' : '🥉';
                return `<div style="padding: 2px 0;">${emoji} ${item}</div>`;
            }).join('');
            
            return `<td class="${sortedClass.trim()}" style="font-size: 11px; line-height: 1.4;">${asnFormatted}</td>`;
        
        case 'ip_concentration':
        case 'username_concentration':
            if (!value) return `<td class="${sortedClass.trim()}" style="text-align: center;">-</td>`;
            
            // IPs and usernames use standard comma delimiter
            const items = value.split(', ');
            const formatted = items.map((item, idx) => {
                const rank = idx + 1;
                const emoji = rank === 1 ? '🥇' : rank === 2 ? '🥈' : '🥉';
                return `<div style="padding: 2px 0;">${emoji} ${item}</div>`;
            }).join('');
            
            return `<td class="${sortedClass.trim()}" style="font-size: 11px; line-height: 1.4;">${formatted}</td>`;
        
        // Sparkline - mini line chart
        case 'trend_sparkline':
            const sparklineData = item.sparkline_values;
            if (!sparklineData) return `<td style="text-align: center;">-</td>`;
            
            const values = sparklineData.split(',').map(v => parseInt(v) || 0);
            if (values.length === 0) return `<td style="text-align: center;">-</td>`;
            
            const width = 80;
            const height = 25;
            const padding = 2;
            const max = Math.max(...values, 1);
            const min = Math.min(...values);
            const range = max - min || 1;
            
            // Generate SVG path points
            const points = values.map((val, idx) => {
                const x = padding + (idx / (values.length - 1)) * (width - 2 * padding);
                const y = height - padding - ((val - min) / range) * (height - 2 * padding);
                return `${x},${y}`;
            }).join(' ');
            
            const svg = `
                <svg width="${width}" height="${height}" style="display: block;">
                    <polyline 
                        points="${points}" 
                        fill="none" 
                        stroke="#667eea" 
                        stroke-width="1.5"
                        stroke-linejoin="round"
                    />
                    ${values.map((val, idx) => {
                        const x = padding + (idx / (values.length - 1)) * (width - 2 * padding);
                        const y = height - padding - ((val - min) / range) * (height - 2 * padding);
                        return `<circle cx="${x}" cy="${y}" r="2" fill="#667eea" style="cursor: pointer;">
                            <title>Week ${idx + 1}: ${formatNumber(val)} attacks</title>
                        </circle>`;
                    }).join('')}
                </svg>
            `;
            
            return `<td class="${sortedClass.trim()}" style="padding: 4px;">${svg}</td>`;
        
        
        
        // Rotation rates (decimal)
        case 'ip_rotation':
        case 'asn_rotation':
        case 'username_rotation':
            return `<td class="number${sortedClass}">${typeof value === 'number' ? value.toFixed(1) : '-'}</td>`;
        
        // Burst intensity (ratio)
        case 'burst_intensity':
            return `<td class="number${sortedClass}">${typeof value === 'number' ? value.toFixed(1) + 'x' : '-'}</td>`;
        
        default:
            return `<td class="number${sortedClass}">${formatNumber(value || 0)}</td>`;
    }
}

// Get sort CSS class for a column
function getSortClass(columnKey) {
    const isInSortList = sortColumns.includes(columnKey);
    
    if (!isInSortList) return '';
    
    if (sortColumns.length === 1) {
        // Single column sort - use colored arrow classes
        return sortDirection === 'desc' ? 'sorted-desc' : 'sorted-asc';
    } else {
        // Multi-column sort - use purple class
        return 'sorted-multi';
    }
}

// Get sort indicator text (only for multi-column)
function getSortIndicator(columnKey) {
    const isInSortList = sortColumns.includes(columnKey);
    
    if (!isInSortList || sortColumns.length === 1) return '';
    
    const sortIndex = sortColumns.indexOf(columnKey);
    return ` [${sortIndex + 1}]`;
}