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
    countryViewMode: 'attacking'
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
    
    let html = `<strong>Active Filters:</strong>`;
    html += `<div class="filter-items">`;
    
    // Filter order: Date, Country, ASN, IP, Username (matching chart order)
    
    // 1. Date (always present)
    html += `
        <div class="filter-item">
            <span class="filter-item-label">Date:</span>
            <span class="filter-item-value">${state.startDate} to ${state.endDate}</span>
        </div>
    `;
    
    // 2. Country
    if (state.country) {
        html += `
            <div class="filter-item">
                <span class="filter-item-label">Country:</span>
                <span class="filter-item-value">${state.country}</span>
            </div>
        `;
    }
    
    // 3. ASN
    if (state.asn) {
        html += `
            <div class="filter-item">
                <span class="filter-item-label">ASN:</span>
                <span class="filter-item-value">${state.asn}</span>
            </div>
        `;
    }
    
    // 4. IP
    if (state.ip) {
        html += `
            <div class="filter-item">
                <span class="filter-item-label">IP:</span>
                <span class="filter-item-value">${state.ip}</span>
            </div>
        `;
    }
    
    // 5. Username
    if (state.username) {
        html += `
            <div class="filter-item">
                <span class="filter-item-label">Username:</span>
                <span class="filter-item-value">${state.username}</span>
            </div>
        `;
    }
    
    html += `</div>`;
    
    // Reset button on the right
    html += `<button onclick="resetFilters()" class="reset-btn">Reset All Filters</button>`;
    
    filterInfo.innerHTML = html;
    filterInfo.style.display = 'flex';
    
    updateGoBackButton();
    updateRestoreCountriesButton();
    updateRestoreASNsButton();
    updateRestoreIPsButton();
    updateRestoreUsernamesButton();
}

function updateGoBackButton() {
    const goBackContainer = document.getElementById('go-back-container');
    if (state.dateRangeHistory.length > 0) {
        goBackContainer.innerHTML = `<button onclick="goBack()" class="filter-btn">🔙 Go Back (${state.dateRangeHistory.length})</button>`;
        goBackContainer.style.display = 'block';
    } else {
        goBackContainer.style.display = 'none';
    }
}

async function updateRestoreCountriesButton() {
    const restoreContainer = document.getElementById('restore-countries-container');
    
    if (state.country) {
        // Check if IP or ASN filter constrains to only 1 country
        let disabled = false;
        let title = '';
        
        // Check IP constraint
        if (state.ip) {
            console.log(`Checking if IP ${state.ip} should disable "Restore Countries" button...`);
            try {
                const uniqueCountries = await getUniqueCountriesForIP(state.ip);
                if (uniqueCountries === 1) {
                    disabled = true;
                    title = 'This IP only attacks from one country';
                    console.log('Button will be DISABLED (IP constraint)');
                }
            } catch (error) {
                console.error('Error checking countries for IP:', error);
            }
        }
        
        // Check ASN constraint (if not already disabled by IP)
        if (!disabled && state.asn) {
            console.log(`Checking if ASN ${state.asn} should disable "Restore Countries" button...`);
            try {
                const uniqueCountries = await getUniqueCountriesForASN(state.asn);
                if (uniqueCountries === 1) {
                    disabled = true;
                    title = 'This ASN only operates in one country';
                    console.log('Button will be DISABLED (ASN constraint)');
                } else {
                    console.log(`Button will be ENABLED (${uniqueCountries} countries)`);
                }
            } catch (error) {
                console.error('Error checking countries for ASN:', error);
            }
        }
        
        const disabledAttr = disabled ? 'disabled' : '';
        const titleAttr = title ? `title="${title}"` : '';
        const buttonClass = disabled ? 'restore-btn restore-btn-disabled' : 'restore-btn';
        
        restoreContainer.innerHTML = `<button onclick="restoreCountries()" class="${buttonClass}" ${disabledAttr} ${titleAttr}>Restore All Countries</button>`;
        restoreContainer.style.display = 'inline-block';
    } else {
        restoreContainer.style.display = 'none';
    }
}

async function updateRestoreASNsButton() {
    const restoreContainer = document.getElementById('restore-asns-container');
    
    if (state.asn) {
        // Check if IP or Country filter constrains to only 1 ASN
        let disabled = false;
        let title = '';
        
        // Check IP constraint
        if (state.ip) {
            console.log(`Checking if IP ${state.ip} should disable "Restore ASNs" button...`);
            try {
                const uniqueASNs = await getUniqueASNsForIP(state.ip);
                if (uniqueASNs === 1) {
                    disabled = true;
                    title = 'This IP only uses one ASN';
                    console.log('Button will be DISABLED (IP constraint)');
                }
            } catch (error) {
                console.error('Error checking ASNs for IP:', error);
            }
        }
        
        // Check Country constraint (if not already disabled by IP)
        if (!disabled && state.country) {
            console.log(`Checking if Country ${state.country} should disable "Restore ASNs" button...`);
            try {
                const uniqueASNs = await getUniqueASNsForCountry(state.country);
                if (uniqueASNs === 1) {
                    disabled = true;
                    title = 'This country only has one ASN';
                    console.log('Button will be DISABLED (Country constraint)');
                } else {
                    console.log(`Button will be ENABLED (${uniqueASNs} ASNs)`);
                }
            } catch (error) {
                console.error('Error checking ASNs for Country:', error);
            }
        }
        
        const disabledAttr = disabled ? 'disabled' : '';
        const titleAttr = title ? `title="${title}"` : '';
        const buttonClass = disabled ? 'restore-btn restore-btn-disabled' : 'restore-btn';
        
        restoreContainer.innerHTML = `<button onclick="restoreASNs()" class="${buttonClass}" ${disabledAttr} ${titleAttr}>Restore All ASNs</button>`;
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

// Helper function to check unique countries for an IP
async function getUniqueCountriesForIP(ip) {
    try {
        let url = `${API_BASE}/country_attacks?ip=${encodeURIComponent(ip)}&start=${state.startDate}&end=${state.endDate}`;
        const data = await fetch(url).then(r => r.json());
        const uniqueCountries = new Set(data.map(d => d.country));
        console.log(`IP ${ip} has ${uniqueCountries.size} unique countries:`, Array.from(uniqueCountries));
        return uniqueCountries.size;
    } catch (error) {
        console.error('Error fetching countries for IP:', error);
        return 1; // Default to disabled on error for safety
    }
}

// Helper function to check unique countries for an ASN
async function getUniqueCountriesForASN(asn) {
    try {
        let url = `${API_BASE}/country_attacks?asn=${encodeURIComponent(asn)}&start=${state.startDate}&end=${state.endDate}`;
        const data = await fetch(url).then(r => r.json());
        const uniqueCountries = new Set(data.map(d => d.country));
        console.log(`ASN ${asn} has ${uniqueCountries.size} unique countries:`, Array.from(uniqueCountries));
        return uniqueCountries.size;
    } catch (error) {
        console.error('Error fetching countries for ASN:', error);
        return 1; // Default to disabled on error for safety
    }
}

// Helper function to check unique ASNs for an IP
async function getUniqueASNsForIP(ip) {
    try {
        let url = `${API_BASE}/asn_attacks?ip=${encodeURIComponent(ip)}&start=${state.startDate}&end=${state.endDate}`;
        const asnData = await fetch(url).then(r => r.json());
        const uniqueASNs = new Set(asnData.map(d => d.asn_name));
        console.log(`IP ${ip} has ${uniqueASNs.size} unique ASNs:`, Array.from(uniqueASNs));
        return uniqueASNs.size;
    } catch (error) {
        console.error('Error fetching ASNs for IP:', error);
        return 1; // Default to disabled on error for safety
    }
}

// Helper function to check unique ASNs for a country
async function getUniqueASNsForCountry(country) {
    try {
        let url = `${API_BASE}/asn_attacks?country=${encodeURIComponent(country)}&start=${state.startDate}&end=${state.endDate}`;
        const asnData = await fetch(url).then(r => r.json());
        const uniqueASNs = new Set(asnData.map(d => d.asn_name));
        console.log(`Country ${country} has ${uniqueASNs.size} unique ASNs:`, Array.from(uniqueASNs));
        return uniqueASNs.size;
    } catch (error) {
        console.error('Error fetching ASNs for Country:', error);
        return 1; // Default to disabled on error for safety
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