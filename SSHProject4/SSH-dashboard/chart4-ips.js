async function loadIPAttacks() {
    let url = `${API_BASE}/ip_attacks?start=${state.startDate}&end=${state.endDate}`;
    
    // Priority: single country filter > multiple countries > no filter
    if (state.country) {
        url += `&country=${encodeURIComponent(state.country)}`;
    } else if (state.countries && state.countries.length > 0) {
        url += `&countries=${encodeURIComponent(state.countries.join(','))}`;
    }
    
    console.log('🐛 chart4 - state.asn:', state.asn);
    console.log('🐛 chart4 - state.asns:', state.asns);
    console.log('🐛 chart4 - state.asns length:', state.asns ? state.asns.length : 'null');
    
    if (state.asn) {
        url += `&asn=${encodeURIComponent(state.asn)}`;
    } else if (state.asns && state.asns.length > 0) {
        const joined = Array.isArray(state.asns) ? state.asns.join('|||') : state.asns;
        console.log('🐛 chart4 - joined:', joined);
        url += `&asns=${encodeURIComponent(joined)}`;
    }
    
    console.log('🐛 chart4 - final URL:', url);
    
    if (state.ip) {
        url += `&ip=${encodeURIComponent(state.ip)}`;
    }
    if (state.username) {
        url += `&username=${encodeURIComponent(state.username)}`;
    }
    
    const data = await fetch(url).then(r => r.json());
    console.log('🐛 chart4 - response length:', data.length);
    const series = d3.group(data, d => d.IP);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    renderMultiLineChart('ipchart', seriesArray, {
        yKey: 'attacks',
        onClick: (ip) => {
            if (state.ip === ip) {
                state.ip = null;
            } else {
                state.ip = ip;
            }
            updateURL();
            updateFilterInfo();
            loadAllCharts();
        }
    });
}