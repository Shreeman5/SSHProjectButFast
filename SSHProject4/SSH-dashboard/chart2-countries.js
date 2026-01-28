async function loadCountryAttacks() {
    let url = `${API_BASE}/country_attacks?start=${state.startDate}&end=${state.endDate}`;
    
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
}