async function loadUsernameAttacks() {
    const showVolatile = state.usernameViewMode === 'volatile';
    const endpoint = showVolatile ? 'username_attacks_volatile' : 'username_attacks';
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
    const series = d3.group(data, d => d.username);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    renderMultiLineChart('usernamechart', seriesArray, {
        yKey: 'attacks',
        onClick: (username) => {
            if (state.username === username) {
                state.username = null;
            } else {
                state.username = username;
            }
            updateURL();
            updateFilterInfo();
            loadAllCharts();
        }
    });
    
    updateUsernameToggleButton();
}

function toggleUsernameView() {
    state.usernameViewMode = state.usernameViewMode === 'volatile' ? 'attacking' : 'volatile';
    loadUsernameAttacks();
}

function updateUsernameToggleButton() {
    const toggleBtn = document.getElementById('username-toggle-btn');
    if (state.usernameViewMode === 'volatile') {
        toggleBtn.textContent = 'Show Attacking Usernames';
        toggleBtn.className = 'toggle-btn toggle-attacking';
    } else {
        toggleBtn.textContent = 'Show Volatile Usernames';
        toggleBtn.className = 'toggle-btn toggle-volatile';
    }
}