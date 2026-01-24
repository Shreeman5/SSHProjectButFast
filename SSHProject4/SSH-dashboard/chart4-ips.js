async function loadIPAttacks() {
    const showVolatile = state.ipViewMode === 'volatile';
    const endpoint = showVolatile ? 'ip_attacks_volatile' : 'ip_attacks';
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
    
    updateIPToggleButton();
}

function toggleIPView() {
    state.ipViewMode = state.ipViewMode === 'volatile' ? 'attacking' : 'volatile';
    loadIPAttacks();
}

function updateIPToggleButton() {
    const toggleBtn = document.getElementById('ip-toggle-btn');
    if (state.ipViewMode === 'volatile') {
        toggleBtn.textContent = 'Show Attacking IPs';
        toggleBtn.className = 'toggle-btn toggle-attacking';
    } else {
        toggleBtn.textContent = 'Show Volatile IPs';
        toggleBtn.className = 'toggle-btn toggle-volatile';
    }
}
