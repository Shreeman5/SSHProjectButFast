async function loadCountryAttacks() {
    let url = `${API_BASE}/country_attacks?start=${state.startDate}&end=${state.endDate}`;
    
    // Priority: single country filter > multiple countries > no filter
    if (state.country) {
        // Drilling down to single country (even if in discovery mode)
        url += `&country=${encodeURIComponent(state.country)}`;
    } else if (state.countries && state.countries.length > 0) {
        // Discovery mode - multiple countries
        url += `&countries=${encodeURIComponent(state.countries.join(','))}`;
    }

    if (state.asn) {
        url += `&asn=${encodeURIComponent(state.asn)}`;
    } else if (state.asns && state.asns.length > 0) {
        url += `&asns=${encodeURIComponent(state.asns.join(','))}`;
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
            // When in discovery mode (multiple countries), clicking filters to just that country
            // but keeps state.countries so "Restore" goes back to discovery mode
            if (state.countries && state.countries.length > 0) {
                // Drill down to single country (but preserve state.countries)
                if (state.country === country) {
                    // Clicking same country = restore to all discovery countries
                    state.country = null;
                } else {
                    // Click different country = filter to that country
                    state.country = country;
                }
            } else if (state.country === country) {
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