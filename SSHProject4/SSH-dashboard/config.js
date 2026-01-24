// Configuration and Global State Management

// Configuration
const API_BASE = 'http://localhost:5000/api';
const CHART_WIDTH = 1800;
const CHART_HEIGHT = 370;
const MARGIN = {top: 20, right: 40, bottom: 50, left: 50};

// Global state
let state = {
    startDate: '2022-11-01',
    endDate: '2023-01-08',
    country: null,
    ip: null,
    username: null,
    asn: null,
    dateRangeHistory: [],
    countryViewMode: 'attacking',
    ipViewMode: 'attacking',           // ← ADD THIS
    usernameViewMode: 'attacking',     // ← ADD THIS
    asnViewMode: 'attacking'           // ← ADD THIS
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

function updateFilterInfo() {
    const filterInfo = document.getElementById('filter-info');
    
    let html = `<strong>Active Filters:</strong> `;
    html += `Date: ${state.startDate} to ${state.endDate}`;
    
    if (state.country) html += ` | Country: ${state.country}`;
    if (state.ip) html += ` | IP: ${state.ip}`;
    if (state.username) html += ` | Username: ${state.username}`;
    if (state.asn) html += ` | ASN: ${state.asn}`;
    
    html += ` <button onclick="resetFilters()" class="reset-btn">Reset All Filters</button>`;
    
    filterInfo.innerHTML = html;
    filterInfo.style.display = 'block';
    
    updateGoBackButton();
    updateRestoreCountriesButton();
    updateRestoreASNsButton();
    updateRestoreIPsButton();
    updateRestoreUsernamesButton();
}

function updateGoBackButton() {
    const goBackContainer = document.getElementById('go-back-container');
    if (state.dateRangeHistory.length > 0) {
        goBackContainer.innerHTML = `<button onclick="goBack()" class="filter-btn"> Go Back (${state.dateRangeHistory.length})</button>`;
        goBackContainer.style.display = 'block';
    } else {
        goBackContainer.style.display = 'none';
    }
}

function updateRestoreCountriesButton() {
    const restoreContainer = document.getElementById('restore-countries-container');
    
    if (state.country) {
        restoreContainer.innerHTML = `<button onclick="restoreCountries()" class="restore-btn">Restore All Countries</button>`;
        restoreContainer.style.display = 'inline-block';
    } else {
        restoreContainer.style.display = 'none';
    }
}

function updateRestoreASNsButton() {
    const restoreContainer = document.getElementById('restore-asns-container');
    
    if (state.asn) {
        restoreContainer.innerHTML = `<button onclick="restoreASNs()" class="restore-btn">Restore All ASNs</button>`;
        restoreContainer.style.display = 'inline-block';
    } else {
        restoreContainer.style.display = 'none';
    }
}

function updateRestoreIPsButton() {
    const restoreContainer = document.getElementById('restore-ips-container');
    
    if (state.ip) {
        restoreContainer.innerHTML = `<button onclick="restoreIPs()" class="restore-btn">Restore All IPs</button>`;
        restoreContainer.style.display = 'inline-block';
    } else {
        restoreContainer.style.display = 'none';
    }
}

function updateRestoreUsernamesButton() {
    const restoreContainer = document.getElementById('restore-usernames-container');
    
    if (state.username) {
        restoreContainer.innerHTML = `<button onclick="restoreUsernames()" class="restore-btn">Restore All Usernames</button>`;
        restoreContainer.style.display = 'inline-block';
    } else {
        restoreContainer.style.display = 'none';
    }
}

function goBack() {
    if (state.dateRangeHistory.length === 0) return;
    
    const previous = state.dateRangeHistory.pop();
    state.startDate = previous.startDate;
    state.endDate = previous.endDate;
    
    updateURL();
    updateFilterInfo();
    loadAllCharts();
}

function restoreCountries() {
    state.country = null;
    updateURL();
    updateFilterInfo();
    loadAllCharts();
}

function restoreASNs() {
    state.asn = null;
    updateURL();
    updateFilterInfo();
    loadAllCharts();
}

function restoreIPs() {
    state.ip = null;
    updateURL();
    updateFilterInfo();
    loadAllCharts();
}

function restoreUsernames() {
    state.username = null;
    updateURL();
    updateFilterInfo();
    loadAllCharts();
}

function resetFilters() {
    state.startDate = '2022-11-01';
    state.endDate = '2023-01-08';
    state.country = null;
    state.ip = null;
    state.username = null;
    state.asn = null;
    state.dateRangeHistory = [];
    
    updateURL();
    updateFilterInfo();
    loadAllCharts();
}

function updateURL() {
    const params = new URLSearchParams();
    params.set('start', state.startDate);
    params.set('end', state.endDate);
    if (state.country) params.set('country', state.country);
    
    window.history.pushState({}, '', `?${params.toString()}`);
}

async function loadAllCharts() {
    const chartsToLoad = [
        loadTotalAttacks(),
        loadCountryAttacks(),
        loadIPAttacks(),
        loadUsernameAttacks(),
        loadASNAttacks()
    ];
    
    await Promise.all(chartsToLoad);
}