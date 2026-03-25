// Discovery Dashboard - Core Module
// State management, configuration, and utility functions

const API_BASE = 'http://localhost:5000';

// State
let currentDimension = 'country';
let allData = [];
let filteredData = [];
let currentPage = 1;
let pageSize = 50;

// Progressive loading state
let isLoadingMore = false;
let hasMoreData = true;
let batchSize = 50000;  // Load 50000 at a time

// Multi-column sorting state
let sortColumns = ['total_attacks'];  // Array of columns to sort by
let sortDirection = 'desc';  // Single direction for now (all columns same direction)
let debugRankings = null;  // Store ranking debug info

// Selection state (for countries and ASNs only)
let selectedCountries = new Set();
let selectedASNs = new Set();
const MAX_SELECTED = 10;

// Available optional columns for each dimension
const OPTIONAL_COLUMNS = {
    country: [
        // Default columns (visible by default)
        { key: 'total_attacks', label: 'Total Attacks', tooltip: 'Total attacks across all 69 days', default: true },
        { key: 'avg_daily', label: 'Avg Daily', tooltip: 'Average attacks per day', default: true },
        { key: 'persistence_pct', label: 'Persistence', tooltip: 'Percentage of days active', default: true },
        { key: 'max_absolute_change', label: 'Max Absolute Δ', tooltip: 'Largest day-to-day increase', default: true },
        { key: 'max_pct_change', label: 'Max % Δ', tooltip: 'Largest percentage increase', default: true },
        { key: 'recent_attacks', label: 'Recent (7d)', tooltip: 'Attacks in last 7 days', default: true },
        { key: 'first_seen', label: 'First Seen', tooltip: 'First appearance date', default: true },
        { key: 'last_seen', label: 'Last Seen', tooltip: 'Last appearance date', default: true },
        { key: 'max_daily', label: 'Max Daily', tooltip: 'Highest single-day count', default: true },
        
        // Optional columns (hidden by default)
        { key: 'unique_asns', label: 'Unique ASNs', tooltip: 'Number of distinct ASN organizations attacking from this country', default: false },
        { key: 'unique_ips', label: 'Unique IPs', tooltip: 'Number of distinct IP addresses from this country', default: false },
        { key: 'unique_usernames', label: 'Unique Usernames', tooltip: 'Number of distinct usernames tried from this country', default: false },
        { key: 'asn_stability', label: 'ASN Stability', tooltip: 'Mean Jaccard similarity between consecutive days\' ASN sets (0=volatile, 1=stable). Higher = same ASNs attacking consistently.', default: false },
        { key: 'ip_stability', label: 'IP Stability', tooltip: 'Mean Jaccard similarity between consecutive days\' IP sets (0=volatile, 1=stable). Higher = same IPs attacking consistently.', default: false },
        { key: 'username_stability', label: 'Username Stability', tooltip: 'Mean Jaccard similarity between consecutive days\' username sets (0=volatile, 1=stable). Higher = same credentials targeted consistently.', default: false },
        { key: 'peak_hours', label: 'Peak Attack Hours', tooltip: 'Top 3 hours of day with most attacks (hour + percentage of daily total)', default: false },
        { key: 'peak_minutes', label: 'Peak Attack Minutes', tooltip: 'Top 3 minutes with most attacks (HH:MM + percentage)', default: false },
        { key: 'peak_seconds', label: 'Peak Attack Seconds', tooltip: 'Top 3 seconds with most attacks (HH:MM:SS + percentage)', default: false },
        { key: 'asn_concentration', label: 'ASN Concentration (Top 3)', tooltip: 'Top 3 ASNs and their attack percentages - sortable by top contributor', default: false },
        { key: 'ip_concentration', label: 'IP Concentration (Top 3)', tooltip: 'Top 3 IPs and their attack percentages - sortable by top contributor', default: false },
        { key: 'username_concentration', label: 'Username Concentration (Top 3)', tooltip: 'Top 3 usernames and their attack percentages - sortable by top contributor', default: false },
        { key: 'trend_sparkline', label: 'Trend (7-day)', tooltip: 'Mini chart showing attacks at 7-day intervals (10 points for 69 days)', default: false },
        { key: 'ip_rotation', label: 'IP Rotation Rate', tooltip: 'Average number of unique IPs used per day', default: false },
        { key: 'asn_rotation', label: 'ASN Rotation Rate', tooltip: 'Average number of unique ASNs used per day', default: false },
        { key: 'username_rotation', label: 'Username Rotation Rate', tooltip: 'Average number of unique usernames tried per day', default: false },
        { key: 'burst_intensity', label: 'Burst Intensity', tooltip: 'Ratio of max daily attacks to average daily (higher = more bursty)', default: false }
    ],
    asn: [
        { key: 'total_attacks', label: 'Total Attacks', tooltip: 'Total attacks across all 69 days', default: true },
        { key: 'avg_daily', label: 'Avg Daily', tooltip: 'Average attacks per day', default: true },
        { key: 'persistence_pct', label: 'Persistence', tooltip: 'Percentage of days active', default: true },
        { key: 'max_absolute_change', label: 'Max Absolute Δ', tooltip: 'Largest day-to-day increase', default: true },
        { key: 'max_pct_change', label: 'Max % Δ', tooltip: 'Largest percentage increase', default: true },
        { key: 'recent_attacks', label: 'Recent (7d)', tooltip: 'Attacks in last 7 days', default: true },
        { key: 'first_seen', label: 'First Seen', tooltip: 'First appearance date', default: true },
        { key: 'last_seen', label: 'Last Seen', tooltip: 'Last appearance date', default: true },
        { key: 'max_daily', label: 'Max Daily', tooltip: 'Highest single-day count', default: true },

        // Geographic columns (5)
        { key: 'unique_countries', label: 'Unique Countries', tooltip: 'Number of countries this ASN operates from', default: false },
        { key: 'primary_country', label: 'Primary Country', tooltip: 'Country with most attacks from this ASN', default: false },
        { key: 'country_concentration', label: 'Country Concentration (Top 3)', tooltip: 'Top 3 countries and their attack percentages', default: false },
        { key: 'country_rotation', label: 'Country Rotation Rate', tooltip: 'Average number of countries used per active day', default: false },
        { key: 'country_stability', label: 'Country Stability', tooltip: 'Mean Jaccard similarity between consecutive days\' country sets (0=volatile, 1=stable)', default: false },
        
        // Infrastructure columns (3)
        { key: 'unique_ips', label: 'Unique IPs', tooltip: 'Number of distinct IP addresses used by this ASN', default: false },
        { key: 'ip_concentration', label: 'IP Concentration (Top 3)', tooltip: 'Top 3 IPs and their attack percentages', default: false },
        { key: 'ip_rotation', label: 'IP Rotation Rate', tooltip: 'Average number of unique IPs used per active day', default: false },
        
        // Targeting columns (3)
        { key: 'unique_usernames', label: 'Unique Usernames', tooltip: 'Number of distinct usernames tried by this ASN', default: false },
        { key: 'username_concentration', label: 'Username Concentration (Top 3)', tooltip: 'Top 3 usernames and their attack percentages', default: false },
        { key: 'username_rotation', label: 'Username Rotation Rate', tooltip: 'Average number of unique usernames tried per active day', default: false },
        
        // Stability columns (2)
        { key: 'ip_stability', label: 'IP Stability', tooltip: 'Mean Jaccard similarity between consecutive days\' IP sets (0=volatile, 1=stable)', default: false },
        { key: 'username_stability', label: 'Username Stability', tooltip: 'Mean Jaccard similarity between consecutive days\' username sets (0=volatile, 1=stable)', default: false },
        
        // Other columns (2)
        { key: 'trend_sparkline', label: 'Trend (7-day)', tooltip: 'Mini chart showing attacks at 7-day intervals', default: false },
        { key: 'burst_intensity', label: 'Burst Intensity', tooltip: 'Ratio of max daily attacks to average daily (higher = more bursty)', default: false }
    ],
    ip: [
        // Default columns (visible by default)
        { key: 'total_attacks', label: 'Total Attacks', tooltip: 'Total attacks across all 69 days', default: true },
        { key: 'avg_daily', label: 'Avg Daily', tooltip: 'Average attacks per day', default: true },
        { key: 'persistence_pct', label: 'Persistence', tooltip: 'Percentage of days active', default: true },
        { key: 'max_absolute_change', label: 'Max Absolute Δ', tooltip: 'Largest day-to-day increase', default: true },
        { key: 'max_pct_change', label: 'Max % Δ', tooltip: 'Largest percentage increase', default: true },
        { key: 'recent_attacks', label: 'Recent (7d)', tooltip: 'Attacks in last 7 days', default: true },
        { key: 'first_seen', label: 'First Seen', tooltip: 'First appearance date', default: true },
        { key: 'last_seen', label: 'Last Seen', tooltip: 'Last appearance date', default: true },
        { key: 'max_daily', label: 'Max Daily', tooltip: 'Highest single-day count', default: true },
        
        // Attribution columns (2)
        { key: 'asn_name', label: 'ASN Name', tooltip: 'Organization that owns this IP address', default: false },
        { key: 'country', label: 'Country', tooltip: 'Geographic location of this IP', default: false },
        
        // Targeting columns (4)
        { key: 'unique_usernames', label: 'Unique Usernames', tooltip: 'Number of distinct usernames tried by this IP', default: false },
        { key: 'username_concentration', label: 'Username Concentration (Top 3)', tooltip: 'Top 3 usernames and their attack percentages', default: false },
        { key: 'username_rotation', label: 'Username Rotation Rate', tooltip: 'Average number of unique usernames tried per active day', default: false },
        { key: 'username_stability', label: 'Username Stability', tooltip: 'Mean Jaccard similarity between consecutive days\' username sets (0=volatile, 1=stable)', default: false },
        
        // Attack characteristics (2)
        { key: 'trend_sparkline', label: 'Trend (7-day)', tooltip: 'Mini chart showing attacks at 7-day intervals', default: false },
        { key: 'burst_intensity', label: 'Burst Intensity', tooltip: 'Ratio of max daily attacks to average daily (higher = more bursty)', default: false }
    ],
    username: [
        // Default columns (visible by default)
        { key: 'total_attacks', label: 'Total Attacks', tooltip: 'Total attacks across all 69 days', default: true },
        { key: 'avg_daily', label: 'Avg Daily', tooltip: 'Average attacks per day', default: true },
        { key: 'persistence_pct', label: 'Persistence', tooltip: 'Percentage of days active', default: true },
        { key: 'max_absolute_change', label: 'Max Absolute Δ', tooltip: 'Largest day-to-day increase', default: true },
        { key: 'max_pct_change', label: 'Max % Δ', tooltip: 'Largest percentage increase', default: true },
        { key: 'recent_attacks', label: 'Recent (7d)', tooltip: 'Attacks in last 7 days', default: true },
        { key: 'first_seen', label: 'First Seen', tooltip: 'First appearance date', default: true },
        { key: 'last_seen', label: 'Last Seen', tooltip: 'Last appearance date', default: true },
        { key: 'max_daily', label: 'Max Daily', tooltip: 'Highest single-day count', default: true },
        
        // Attribution columns (6)
        { key: 'unique_countries', label: 'Unique Countries', tooltip: 'Number of countries attacking with this username', default: false },
        { key: 'unique_asns', label: 'Unique ASNs', tooltip: 'Number of ASN organizations attacking with this username', default: false },
        { key: 'unique_ips', label: 'Unique IPs', tooltip: 'Number of distinct IPs attacking with this username', default: false },
        { key: 'country_concentration', label: 'Country Concentration (Top 3)', tooltip: 'Top 3 countries and their attack percentages', default: false },
        { key: 'asn_concentration', label: 'ASN Concentration (Top 3)', tooltip: 'Top 3 ASNs and their attack percentages', default: false },
        { key: 'ip_concentration', label: 'IP Concentration (Top 3)', tooltip: 'Top 3 IPs and their attack percentages', default: false },
        
        // Stability columns (3)
        { key: 'country_stability', label: 'Country Stability', tooltip: 'Mean Jaccard similarity between consecutive days\' country sets (0=volatile, 1=stable)', default: false },
        { key: 'asn_stability', label: 'ASN Stability', tooltip: 'Mean Jaccard similarity between consecutive days\' ASN sets (0=volatile, 1=stable)', default: false },
        { key: 'ip_stability', label: 'IP Stability', tooltip: 'Mean Jaccard similarity between consecutive days\' IP sets (0=volatile, 1=stable)', default: false },
        
        // Rotation columns (3)
        { key: 'country_rotation', label: 'Country Rotation Rate', tooltip: 'Average number of countries attacking per active day', default: false },
        { key: 'asn_rotation', label: 'ASN Rotation Rate', tooltip: 'Average number of ASNs attacking per active day', default: false },
        { key: 'ip_rotation', label: 'IP Rotation Rate', tooltip: 'Average number of IPs attacking per active day', default: false },
        
        // Characteristics (2)
        { key: 'trend_sparkline', label: 'Trend (7-day)', tooltip: 'Mini chart showing attacks at 7-day intervals', default: false },
        { key: 'burst_intensity', label: 'Burst Intensity', tooltip: 'Ratio of max daily attacks to average daily (higher = more bursty)', default: false }
    ]
};

// Load column preferences from localStorage
function loadColumnPreferences(dimension) {
    const PREFS_VERSION = 9; // Increment this when you change column structure
    const versionKey = `${dimension}ColumnPrefsVersion`;
    const savedVersion = localStorage.getItem(versionKey);
    
    // If version doesn't match, clear old preferences
    if (savedVersion !== String(PREFS_VERSION)) {
        localStorage.removeItem(`${dimension}ColumnPreferences`);
        localStorage.setItem(versionKey, String(PREFS_VERSION));
    }
    
    const saved = localStorage.getItem(`${dimension}ColumnPreferences`);
    if (saved) {
        return JSON.parse(saved);
    }
    
    // Default: use the 'default' property from column definitions
    const prefs = {};
    (OPTIONAL_COLUMNS[dimension] || []).forEach(col => {
        prefs[col.key] = col.default !== undefined ? col.default : false;
    });
    return prefs;
}

// Column preferences (for customizable columns)
let columnPreferences = {
    country: loadColumnPreferences('country'),
    asn: loadColumnPreferences('asn'),
    ip: loadColumnPreferences('ip'),
    username: loadColumnPreferences('username')
};

// Save column preferences to localStorage
function saveColumnPreferences(dimension, prefs) {
    localStorage.setItem(`${dimension}ColumnPreferences`, JSON.stringify(prefs));
    columnPreferences[dimension] = prefs;
}

// Update quick stats display
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
        updatePagination();
    }
}

function nextPage() {
    const totalPages = Math.ceil(filteredData.length / pageSize);
    if (currentPage < totalPages) {
        currentPage++;
        renderTable();
        updatePagination();
    }
}

function changePageSize() {
    const select = document.getElementById('page-size');
    pageSize = parseInt(select.value);
    currentPage = 1;
    renderTable();
    updatePagination();
}