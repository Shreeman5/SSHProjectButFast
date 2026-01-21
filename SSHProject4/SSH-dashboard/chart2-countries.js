// Chart 2: Top 10 Attacking Countries

async function loadCountryAttacks() {
    let url = `${API_BASE}/country_attacks?start=${state.startDate}&end=${state.endDate}`;
    if (state.country) url += `&country=${state.country}`;
    
    const data = await fetch(url).then(r => r.json());

    console.log('Country data raw:', data);
    console.log('Total attacks in country data:', data.reduce((sum, d) => sum + d.attacks, 0));
    console.log('Unique countries:', [...new Set(data.map(d => d.country))]);
    
    const nested = d3.group(data, d => d.country);
    const series = Array.from(nested, ([key, values]) => ({key, values}));
    
    renderMultiLineChart('countrychart', series, {
        xKey: 'date',
        yKey: 'attacks',
        onClick: (country) => {
            state.country = country;
            updateURL();
            updateFilterInfo();
            loadAllCharts();
        }
    });
}
