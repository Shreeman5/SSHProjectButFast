// Configuration and Global State Management

// Configuration
const API_BASE = 'http://localhost:5000/api';
const CHART_WIDTH = 1800;
const CHART_HEIGHT = 370;
const MARGIN = {top: 20, right: 120, bottom: 90, left: 80};

// Global state
let state = {
    startDate: '2022-11-01',
    endDate: '2023-01-08',
    country: null,
    ip: null,
    username: null,
    asn: null
};

// Color scale
const color = d3.scaleOrdinal(d3.schemeCategory10);

// Initialize state from URL parameters
function initState() {
    const params = new URLSearchParams(window.location.search);
    state.startDate = params.get('start') || state.startDate;
    state.endDate = params.get('end') || state.endDate;
    state.country = params.get('country') || null;
}

// Update filter info display
function updateFilterInfo() {
    const filterInfo = document.getElementById('filter-info');
    const filterText = document.getElementById('filter-text');
    
    let filters = [];
    if (state.startDate && state.endDate) {
        filters.push(`Date: ${state.startDate} to ${state.endDate}`);
    }
    if (state.country) filters.push(`Country: ${state.country}`);
    if (state.ip) filters.push(`IP: ${state.ip}`);
    if (state.username) filters.push(`Username: ${state.username}`);
    if (state.asn) filters.push(`ASN: ${state.asn}`);
    
    if (filters.length > 0) {
        filterText.textContent = 'Active Filters: ' + filters.join(' | ');
        filterInfo.style.display = 'block';
    } else {
        filterInfo.style.display = 'none';
    }
}

// Reset all filters
function resetFilters() {
    state.startDate = '2022-11-01';
    state.endDate = '2023-01-08';
    state.country = null;
    state.ip = null;
    state.username = null;
    state.asn = null;
    
    updateURL();
    updateFilterInfo();
    loadAllCharts();
}

// Update URL with current state
function updateURL() {
    const params = new URLSearchParams();
    params.set('start', state.startDate);
    params.set('end', state.endDate);
    if (state.country) params.set('country', state.country);
    
    window.history.pushState({}, '', `?${params.toString()}`);
}

// Load all charts
async function loadAllCharts() {
    console.log('Loading all charts with state:', state);
    await Promise.all([
        loadTotalAttacks(),
        loadCountryAttacks(),
        loadUnusualCountries(),
        loadIPAttacks(),
        loadUsernameAttacks(),
        loadASNAttacks()
    ]);
    console.log('All charts loaded successfully');
}
