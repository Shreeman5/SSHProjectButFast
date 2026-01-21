async function loadUnusualCountries() {
    let url = `${API_BASE}/unusual_countries?start=${state.startDate}&end=${state.endDate}`;
    
    // If country is selected and filtered from volatile chart, show only that country
    if (state.country && state.filteredFromVolatileChart) {
        url += `&country=${encodeURIComponent(state.country)}`;
    }
    
    const data = await fetch(url).then(r => r.json());
    
    const series = d3.group(data, d => d.country);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    renderMultiLineChart('volatilechart', seriesArray, {
        yKey: 'attacks',
        onClick: (country) => {
            // Left click: filter to this country from volatile chart
            if (state.country === country && state.filteredFromVolatileChart) {
                // Click again to unfilter
                state.country = null;
                state.filteredFromVolatileChart = false;
            } else {
                state.country = country;
                state.filteredFromVolatileChart = true;  // Mark as filtered from volatile
            }
            updateURL();
            updateFilterInfo();
            loadAllCharts();
        }
    });
}