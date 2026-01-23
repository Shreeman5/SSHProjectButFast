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
    
    const data = await fetch(url).then(r => r.json());
    
    const series = d3.group(data, d => d.username);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    renderMultiLineChart('usernamechart', seriesArray, {
        yKey: 'attacks'
    });
}