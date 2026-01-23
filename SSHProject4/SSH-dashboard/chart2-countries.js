async function loadCountryAttacks() {
    // Check if we should show volatile view
    const showVolatile = state.countryViewMode === 'volatile';
    
    // Use the appropriate endpoint
    const endpoint = showVolatile ? 'unusual_countries' : 'country_attacks';
    let url = `${API_BASE}/${endpoint}?start=${state.startDate}&end=${state.endDate}`;
    
    if (state.country) {
        url += `&country=${encodeURIComponent(state.country)}`;
    }

    if (state.asn) {
        url += `&asn=${encodeURIComponent(state.asn)}`;
    }
    
    if (state.ip) {
        url += `&ip=${encodeURIComponent(state.ip)}`;
    }
    
    if (state.username) {
        url += `&username=${encodeURIComponent(state.username)}`;
    }
    
    const data = await fetch(url).then(r => r.json());
    
    const series = d3.group(data, d => d.country);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    renderMultiLineChart('countrychart', seriesArray, {
        yKey: 'attacks',
        onClick: (country) => {
            if (state.country === country) {
                state.country = null;
            } else {
                state.country = country;
            }
            updateURL();
            updateFilterInfo();
            loadAllCharts();
        }
    });
    
    // Update the toggle button text
    updateCountryToggleButton();
}

function toggleCountryView() {
    // Toggle between 'attacking' and 'volatile'
    state.countryViewMode = state.countryViewMode === 'volatile' ? 'attacking' : 'volatile';
    
    // Reload the country chart
    loadCountryAttacks();
}

function updateCountryToggleButton() {
    const toggleBtn = document.getElementById('country-toggle-btn');
    if (state.countryViewMode === 'volatile') {
        toggleBtn.textContent = 'Show Attacking Countries';
        toggleBtn.className = 'toggle-btn toggle-attacking';
    } else {
        toggleBtn.textContent = 'Show Volatile Countries';
        toggleBtn.className = 'toggle-btn toggle-volatile';
    }
}