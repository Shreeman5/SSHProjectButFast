async function loadASNAttacks() {
    const showVolatile = state.asnViewMode === 'volatile';
    const endpoint = showVolatile ? 'asn_attacks_volatile' : 'asn_attacks';
    let url = `${API_BASE}/${endpoint}?start=${state.startDate}&end=${state.endDate}`;
    
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
    
    updateASNToggleButton();
}

function toggleASNView() {
    state.asnViewMode = state.asnViewMode === 'volatile' ? 'attacking' : 'volatile';
    loadASNAttacks();
}

function updateASNToggleButton() {
    const toggleBtn = document.getElementById('asn-toggle-btn');
    if (state.asnViewMode === 'volatile') {
        toggleBtn.textContent = 'Show Attacking ASNs';
        toggleBtn.className = 'toggle-btn toggle-attacking';
    } else {
        toggleBtn.textContent = 'Show Volatile ASNs';
        toggleBtn.className = 'toggle-btn toggle-volatile';
    }
}
