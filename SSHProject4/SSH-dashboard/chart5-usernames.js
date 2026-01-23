async function loadUsernameAttacks() {
    let url = `${API_BASE}/username_attacks?start=${state.startDate}&end=${state.endDate}`;
    
    if (state.country) {
        url += `&country=${encodeURIComponent(state.country)}`;
    }
    
    // Add ASN filter
    if (state.asn) {
        url += `&asn=${encodeURIComponent(state.asn)}`;
    }
    
    // Add IP filter
    if (state.ip) {
        url += `&ip=${encodeURIComponent(state.ip)}`;
    }
    
    // Add username filter
    if (state.username) {
        url += `&username=${encodeURIComponent(state.username)}`;
    }
    
    const data = await fetch(url).then(r => r.json());
    
    const series = d3.group(data, d => d.username);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    renderMultiLineChart('usernamechart', seriesArray, {
        yKey: 'attacks',
        onClick: (username) => {
            // Toggle username filter
            if (state.username === username) {
                state.username = null;  // Click again to unfilter
            } else {
                state.username = username;
            }
            updateURL();
            updateFilterInfo();
            loadAllCharts();
        }
    });
}