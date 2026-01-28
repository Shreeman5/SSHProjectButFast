async function loadASNAttacks() {
    let url = `${API_BASE}/asn_attacks?start=${state.startDate}&end=${state.endDate}`;
    
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