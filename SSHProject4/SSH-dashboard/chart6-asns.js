async function loadASNAttacks() {
    let url = `${API_BASE}/asn_attacks?start=${state.startDate}&end=${state.endDate}`;
    
    // Filter by country if selected
    if (state.country) {
        url += `&country=${encodeURIComponent(state.country)}`;
    }
    
    // Filter by ASN if selected
    if (state.asn) {
        url += `&asn=${encodeURIComponent(state.asn)}`;
    }
    
    // Add IP filter to show which ASN this IP belongs to
    if (state.ip) {
        url += `&ip=${encodeURIComponent(state.ip)}`;
    }
    
    const data = await fetch(url).then(r => r.json());
    
    const series = d3.group(data, d => d.asn_name);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    renderMultiLineChart('asnchart', seriesArray, {
        yKey: 'attacks',
        onClick: (asnName) => {
            // Left click: toggle filter to this ASN
            if (state.asn === asnName) {
                // Click again to unfilter
                state.asn = null;
            } else {
                state.asn = asnName;
            }
            updateURL();
            updateFilterInfo();
            loadAllCharts();
        }
    });
}