// Chart 6: Top 10 Attacking ASN Organizations

async function loadASNAttacks() {
    let url = `${API_BASE}/asn_attacks?start=${state.startDate}&end=${state.endDate}`;
    if (state.country) url += `&country=${state.country}`;
    
    const data = await fetch(url).then(r => r.json());
    
    const nested = d3.group(data, d => d.asn_name);
    const series = Array.from(nested, ([key, values]) => ({key, values}));
    
    renderMultiLineChart('asnchart', series, {
        xKey: 'date',
        yKey: 'attacks'
    });
}
