async function loadUsernameAttacks() {
    let url = `${API_BASE}/username_attacks?start=${state.startDate}&end=${state.endDate}`;
    
    console.log('🐛 chart5 - state.asns:', state.asns);
    console.log('🐛 chart5 - is Array?', Array.isArray(state.asns));
    
    // Priority: single country filter > multiple countries > no filter
    if (state.country) {
        url += `&country=${encodeURIComponent(state.country)}`;
    } else if (state.countries && state.countries.length > 0) {
        url += `&countries=${encodeURIComponent(state.countries.join(','))}`;
    }
    
    if (state.asn) {
        url += `&asn=${encodeURIComponent(state.asn)}`;
    } else if (state.asns && state.asns.length > 0) {
        const joined = Array.isArray(state.asns) ? state.asns.join('|||') : state.asns;
        console.log('🐛 chart5 - joined:', joined);
        url += `&asns=${encodeURIComponent(joined)}`;
    }
    
    console.log('🐛 chart5 - final URL:', url);
    
    if (state.ip) {
        url += `&ip=${encodeURIComponent(state.ip)}`;
    }
    if (state.username) {
        url += `&username=${encodeURIComponent(state.username)}`;
    }
    
    const data = await fetch(url).then(r => r.json());
    const series = d3.group(data, d => d.username);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    renderMultiLineChart('usernamechart', seriesArray, {
        yKey: 'attacks',
        onClick: (username) => {
            if (state.username === username) {
                state.username = null;
            } else {
                state.username = username;
            }
            updateURL();
            updateFilterInfo();
            loadAllCharts();
        }
    });
}