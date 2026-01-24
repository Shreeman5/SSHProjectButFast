// Discovery Dashboard JavaScript

const API_BASE = 'http://localhost:5000';

// State
let currentDimension = 'country';
let currentTab = 'most-active';
let allData = [];
let filteredData = [];
let currentPage = 1;
let pageSize = 50;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadData();
});

// Load data for current dimension
async function loadData() {
    try {
        const response = await fetch(`${API_BASE}/api/${currentDimension}_summary?start=2022-11-01&end=2023-01-08`);
        allData = await response.json();
        applyFilters();
        updateQuickStats();
    } catch (error) {
        console.error('Error loading data:', error);
        document.getElementById('table-body').innerHTML = 
            '<tr><td colspan="10" style="text-align: center; padding: 40px; color: red;">Error loading data</td></tr>';
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

// Switch tab
function switchTab(tab) {
    currentTab = tab;
    currentPage = 1;
    
    // Update active tab
    document.querySelectorAll('.tab').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    
    applyFilters();
}

// Apply filters and sorting
function applyFilters() {
    const minAttacks = parseInt(document.getElementById('min-attacks').value) || 0;
    const searchTerm = document.getElementById('search-box').value.toLowerCase();
    
    // Filter data
    filteredData = allData.filter(item => {
        const matchesMin = item.total_attacks >= minAttacks;
        const matchesSearch = !searchTerm || getEntityName(item).toLowerCase().includes(searchTerm);
        return matchesMin && matchesSearch;
    });
    
    // Sort by current tab
    sortData();
    
    // Reset to page 1
    currentPage = 1;
    
    // Render table
    renderTable();
}

// Sort data based on current tab
function sortData() {
    switch (currentTab) {
        case 'most-active':
            filteredData.sort((a, b) => b.total_attacks - a.total_attacks);
            break;
        case 'most-volatile':
            filteredData.sort((a, b) => b.volatility - a.volatility);
            break;
        case 'recently-active':
            filteredData.sort((a, b) => new Date(b.last_seen) - new Date(a.last_seen));
            break;
        case 'new-threats':
            filteredData.sort((a, b) => new Date(b.first_seen) - new Date(a.first_seen));
            break;
        case 'persistent':
            filteredData.sort((a, b) => b.persistence_pct - a.persistence_pct);
            break;
    }
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
        tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 40px;">No data found</td></tr>';
        return;
    }
    
    tbody.innerHTML = pageData.map((item, idx) => {
        const rank = startIdx + idx + 1;
        const badges = getBadges(item, rank);
        
        return `
            <tr>
                <td>${rank}</td>
                <td><strong>${getEntityName(item)}</strong> ${badges}</td>
                ${currentDimension === 'ip' ? `<td>${item.country || 'Unknown'}</td>` : ''}
                ${currentDimension === 'ip' ? `<td>${truncate(item.asn_name, 30)}</td>` : ''}
                ${['asn', 'username'].includes(currentDimension) ? `<td>${item.countries}</td>` : ''}
                <td class="number">${formatNumber(item.total_attacks)}</td>
                <td class="number">${formatNumber(item.avg_daily)}</td>
                <td>${item.active_days}</td>
                <td>${item.first_seen}</td>
                <td>${item.last_seen}</td>
                <td class="number">${item.volatility}%</td>
                <td class="number">${item.persistence_pct}%</td>
            </tr>
        `;
    }).join('');
    
    // Update pagination
    updatePagination();
}

// Render table header
function renderHeader() {
    const header = document.getElementById('table-header');
    
    let columns = [
        'Rank',
        getDimensionLabel()
    ];
    
    if (currentDimension === 'ip') {
        columns.push('Country', 'ASN');
    }
    
    if (currentDimension === 'asn' || currentDimension === 'username') {
        columns.push('Countries');
    }
    
    columns.push(
        'Total Attacks',
        'Avg Daily',
        'Active Days',
        'First Seen',
        'Last Seen',
        'Volatility',
        'Persistence'
    );
    
    header.innerHTML = columns.map(col => `<th>${col}</th>`).join('');
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

// Get badges for entity
function getBadges(item, rank) {
    const badges = [];
    
    if (rank <= 10) {
        badges.push('<span class="badge badge-top10">🔥 TOP 10</span>');
    }
    
    if (item.volatility > 100) {
        badges.push('<span class="badge badge-volatile">⚡ VOLATILE</span>');
    }
    
    const daysSinceFirstSeen = Math.floor((new Date() - new Date(item.first_seen)) / (1000 * 60 * 60 * 24));
    if (daysSinceFirstSeen <= 7) {
        badges.push('<span class="badge badge-new">🆕 NEW</span>');
    }
    
    if (item.persistence_pct >= 80) {
        badges.push('<span class="badge badge-persistent">🔄 PERSISTENT</span>');
    }
    
    return badges.join(' ');
}

// Update quick stats
function updateQuickStats() {
    const totalEntities = allData.length;
    
    // Calculate top 10 percentage
    const top10Total = allData.slice(0, 10).reduce((sum, item) => sum + item.total_attacks, 0);
    const grandTotal = allData.reduce((sum, item) => sum + item.total_attacks, 0);
    const top10Pct = grandTotal > 0 ? ((top10Total / grandTotal) * 100).toFixed(1) : 0;
    
    // Count active in last 7 days
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    const activeRecent = allData.filter(item => new Date(item.last_seen) >= sevenDaysAgo).length;
    
    // Count new in last 7 days
    const newThreats = allData.filter(item => {
        const daysSince = Math.floor((new Date() - new Date(item.first_seen)) / (1000 * 60 * 60 * 24));
        return daysSince <= 7;
    }).length;
    
    document.getElementById('total-entities').textContent = formatNumber(totalEntities);
    document.getElementById('top10-pct').textContent = top10Pct + '%';
    document.getElementById('active-recent').textContent = formatNumber(activeRecent);
    document.getElementById('new-threats').textContent = formatNumber(newThreats);
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
    document.getElementById('min-attacks').value = 0;
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
