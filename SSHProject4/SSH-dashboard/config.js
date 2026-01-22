// Configuration and Global State Management

// Configuration
const API_BASE = 'http://localhost:5000/api';
const CHART_WIDTH = 1800;  // Increased from 1800 to fill more screen space
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
    dateRangeHistory: [],  // Stack of previous date ranges
    crossedOutCountries: [],  // ← ADD THIS LINE
    filteredFromVolatileChart: false  // Track if filter came from volatile chart
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
    
    // Update Go Back button near date chart
    updateGoBackButton();
    
    // Update Restore Countries button near country chart
    updateRestoreCountriesButton();

    updateRestoreASNsButton();  // ← ADD THIS
}

// New function to update Go Back button
function updateGoBackButton() {
    const goBackContainer = document.getElementById('go-back-container');
    if (state.dateRangeHistory.length > 0) {
        goBackContainer.innerHTML = `<button onclick="goBack()" class="filter-btn"> Go Back (${state.dateRangeHistory.length})</button>`;
        goBackContainer.style.display = 'block';
    } else {
        goBackContainer.style.display = 'none';
    }
}

// Update Restore Countries button (appears on both country and volatile charts)
function updateRestoreCountriesButton() {
    const restoreContainerCountry = document.getElementById('restore-countries-container');
    const restoreContainerVolatile = document.getElementById('restore-countries-volatile-container');
    
    if (state.country && !state.filteredFromVolatileChart) {
        // Filtered from country chart - show button on country chart
        restoreContainerCountry.innerHTML = `<button onclick="restoreCountries()" class="restore-btn">Restore All Countries</button>`;
        restoreContainerCountry.style.display = 'inline-block';
        restoreContainerVolatile.style.display = 'none';
    } else if (state.country && state.filteredFromVolatileChart) {
        // Filtered from volatile chart - show button on volatile chart
        restoreContainerVolatile.innerHTML = `<button onclick="restoreCountries()" class="restore-btn">Restore All Countries</button>`;
        restoreContainerVolatile.style.display = 'inline-block';
        restoreContainerCountry.style.display = 'none';
    } else {
        // No filter - hide both buttons
        restoreContainerCountry.style.display = 'none';
        restoreContainerVolatile.style.display = 'none';
    }
}

// Go back to previous date range
function goBack() {
    if (state.dateRangeHistory.length === 0) return;
    
    // Pop the last date range from history
    const previous = state.dateRangeHistory.pop();
    
    // Restore it (without adding to history again)
    state.startDate = previous.startDate;
    state.endDate = previous.endDate;
    
    updateURL();
    updateFilterInfo();
    loadAllCharts();
}

// Restore all countries (clear country filter)
function restoreCountries() {
    state.country = null;
    state.filteredFromVolatileChart = false;  // Clear volatile chart flag
    document.getElementById('chart2').style.display = 'block';  // Show country chart
    document.getElementById('chart3').style.display = 'block';  // Show volatile chart
    updateURL();
    updateFilterInfo();
    loadAllCharts();
}

// Update Restore ASNs button
function updateRestoreASNsButton() {
    const restoreContainer = document.getElementById('restore-asns-container');
    
    if (state.asn) {
        restoreContainer.innerHTML = `<button onclick="restoreASNs()" class="restore-btn">Restore All ASNs</button>`;
        restoreContainer.style.display = 'inline-block';
    } else {
        restoreContainer.style.display = 'none';
    }
}

// Restore all ASNs (clear ASN filter)
function restoreASNs() {
    state.asn = null;
    updateURL();
    updateFilterInfo();
    loadAllCharts();
}

// Reset all filters
function resetFilters() {
    state.startDate = '2022-11-01';
    state.endDate = '2023-01-08';
    state.country = null;
    state.ip = null;
    state.username = null;
    state.asn = null;
    state.dateRangeHistory = [];
    state.crossedOutCountries = [];
    state.filteredFromVolatileChart = false;  // Clear volatile flag
    
    // Show both charts
    document.getElementById('chart2').style.display = 'block';
    document.getElementById('chart3').style.display = 'block';
    
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
    
    const chartsToLoad = [
        loadTotalAttacks(),
        loadIPAttacks(),
        loadUsernameAttacks(),
        loadASNAttacks()
    ];
    
    if (!state.country) {
        // No filter: show both country and volatile charts
        chartsToLoad.push(loadCountryAttacks());
        chartsToLoad.push(loadUnusualCountries());
        document.getElementById('chart2').style.display = 'block';
        document.getElementById('chart3').style.display = 'block';
    } else if (state.filteredFromVolatileChart) {
        // Filtered from volatile chart: hide country chart, keep volatile chart
        chartsToLoad.push(loadUnusualCountries());
        document.getElementById('chart2').style.display = 'none';
        document.getElementById('chart3').style.display = 'block';
    } else {
        // Filtered from country chart: hide volatile chart, keep country chart
        chartsToLoad.push(loadCountryAttacks());
        document.getElementById('chart2').style.display = 'block';
        document.getElementById('chart3').style.display = 'none';
    }
    
    await Promise.all(chartsToLoad);
    console.log('All charts loaded successfully');
}