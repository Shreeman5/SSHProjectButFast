// Chart 3: Top 10 Most Volatile Countries

async function loadUnusualCountries() {
    const url = `${API_BASE}/unusual_countries?start=${state.startDate}&end=${state.endDate}`;
    const data = await fetch(url).then(r => r.json());
    
    const nested = d3.group(data, d => d.country);
    const series = Array.from(nested, ([key, values]) => ({key, values}));
    
    renderMultiLineChart('unusualchart', series, {
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
