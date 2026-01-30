async function loadASNAttacks() {
    let url = `${API_BASE}/asn_attacks?start=${state.startDate}&end=${state.endDate}`;
    
    // Priority: single country filter > multiple countries > no filter
    if (state.country) {
        url += `&country=${encodeURIComponent(state.country)}`;
    } else if (state.countries && state.countries.length > 0) {
        url += `&countries=${encodeURIComponent(state.countries.join(','))}`;
    }
    
    // Priority: single ASN filter > multiple ASNs > no filter
    if (state.asn) {
        url += `&asn=${encodeURIComponent(state.asn)}`;
    } else if (state.asns && state.asns.length > 0) {
        // Discovery mode - multiple ASNs
        console.log('🐛 chart6 - state.asns type:', typeof state.asns);
        console.log('🐛 chart6 - state.asns is Array?', Array.isArray(state.asns));
        console.log('🐛 chart6 - state.asns:', state.asns);
        const joined = state.asns.join('|||');
        console.log('🐛 chart6 - joined:', joined);
        const encoded = encodeURIComponent(joined);
        console.log('🐛 chart6 - encoded:', encoded);
        url += `&asns=${encoded}`;
    }
    
    if (state.ip) {
        url += `&ip=${encodeURIComponent(state.ip)}`;
    }
    if (state.username) {
        url += `&username=${encodeURIComponent(state.username)}`;
    }
    
    const data = await fetch(url).then(r => r.json());
    const series = d3.group(data, d => d.asn_name);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    renderMultiLineChart('asnchart', seriesArray, {
        yKey: 'attacks',
        onClick: (asnName) => {
            if (state.asn === asnName) {
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