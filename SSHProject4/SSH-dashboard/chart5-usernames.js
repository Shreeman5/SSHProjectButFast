// Chart 5: Top 10 Attacking Usernames

async function loadUsernameAttacks() {
    let url = `${API_BASE}/username_attacks?start=${state.startDate}&end=${state.endDate}`;
    if (state.country) url += `&country=${state.country}`;
    
    const data = await fetch(url).then(r => r.json());
    
    const nested = d3.group(data, d => d.username);  // lowercase 'username'
    const series = Array.from(nested, ([key, values]) => ({key, values}));
    
    renderMultiLineChart('usernamechart', series, {
        xKey: 'date',
        yKey: 'attacks'
    });
}
