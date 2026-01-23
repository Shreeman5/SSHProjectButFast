async function loadIPAttacks() {
    let url = `${API_BASE}/ip_attacks?start=${state.startDate}&end=${state.endDate}`;
    
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
    
    const series = d3.group(data, d => d.IP);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    renderMultiLineChart('ipchart', seriesArray, {
        yKey: 'attacks',
        onClick: (ipAddress) => {
            // Left click: toggle filter to this IP
            if (state.ip === ipAddress) {
                // Click again to unfilter
                state.ip = null;
            } else {
                state.ip = ipAddress;
            }
            updateURL();
            updateFilterInfo();
            loadAllCharts();
        }
    });
}