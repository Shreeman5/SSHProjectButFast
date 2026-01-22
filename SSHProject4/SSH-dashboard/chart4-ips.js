async function loadIPAttacks() {
    let url = `${API_BASE}/ip_attacks?start=${state.startDate}&end=${state.endDate}`;
    
    if (state.country) {
        url += `&country=${encodeURIComponent(state.country)}`;
    }
    
    // Add ASN filter
    if (state.asn) {
        url += `&asn=${encodeURIComponent(state.asn)}`;
    }
    
    const data = await fetch(url).then(r => r.json());
    
    const series = d3.group(data, d => d.IP);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    renderMultiLineChart('ipchart', seriesArray, {
        yKey: 'attacks'
    });
}