// Chart 2: Top 10 Attacking Countries

async function loadCountryAttacks() {
    let url = `${API_BASE}/country_attacks?start=${state.startDate}&end=${state.endDate}`;
    
    // If country is selected, only show that country
    if (state.country) {
        url += `&country=${encodeURIComponent(state.country)}`;
    }
    
    const data = await fetch(url).then(r => r.json());
    
    const series = d3.group(data, d => d.country);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    renderMultiLineChart('countrychart', seriesArray, {
        yKey: 'attacks',
        onClick: (country) => {
            // Left click: toggle filter to this country
            if (state.country === country) {
                // Click again to unfilter
                state.country = null;
            } else {
                state.country = country;
            }
            updateURL();
            updateFilterInfo();
            loadAllCharts();
        }
    });
}