// Chart 4: Top 10 Attacking IPs

async function loadIPAttacks() {
    let url = `${API_BASE}/ip_attacks?start=${state.startDate}&end=${state.endDate}`;
    if (state.country) url += `&country=${state.country}`;
    
    const data = await fetch(url).then(r => r.json());
    
    const nested = d3.group(data, d => d.IP);
    const series = Array.from(nested, ([key, values]) => ({key, values}));
    
    renderMultiLineChart('ipchart', series, {
        xKey: 'date',
        yKey: 'attacks'
    });
}
