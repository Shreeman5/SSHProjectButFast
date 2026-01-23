async function loadUnusualCountries() {
    let url = `${API_BASE}/unusual_countries?start=${state.startDate}&end=${state.endDate}`;
    
    if (state.country && state.filteredFromVolatileChart) {
        url += `&country=${encodeURIComponent(state.country)}`;
    }

    // Add ASN filter to show which countries this ASN operates in
    if (state.asn) {
        url += `&asn=${encodeURIComponent(state.asn)}`;
    }
    
    // console.log('🟢 Volatile API URL:', url);  // ← ADD THIS
    
    const data = await fetch(url).then(r => r.json());
    
    // console.log('🟢 Volatile API Response:', data);  // ← ADD THIS
    
    const series = d3.group(data, d => d.country);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    renderMultiLineChart('volatilechart', seriesArray, {
        yKey: 'attacks',
        onClick: (country) => {
            if (state.country === country && state.filteredFromVolatileChart) {
                state.country = null;
                state.filteredFromVolatileChart = false;
            } else {
                state.country = country;
                state.filteredFromVolatileChart = true;
            }
            updateURL();
            updateFilterInfo();
            loadAllCharts();
        }
    });
}