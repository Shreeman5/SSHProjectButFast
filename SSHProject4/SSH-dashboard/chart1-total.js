// Chart 1: Total Attacks Over Time

async function loadTotalAttacks() {
    let url = `${API_BASE}/total_attacks?start=${state.startDate}&end=${state.endDate}`;
    let chartData;
    let chartColor = '#7c4dff';  // Default purple
    
    // If country is selected, get that country's data
    if (state.country) {
        url = `${API_BASE}/country_attacks?start=${state.startDate}&end=${state.endDate}&country=${encodeURIComponent(state.country)}`;
        const data = await fetch(url).then(r => r.json());
        
        // Aggregate by date
        const dateMap = new Map();
        data.forEach(d => {
            if (dateMap.has(d.date)) {
                dateMap.set(d.date, dateMap.get(d.date) + d.attacks);
            } else {
                dateMap.set(d.date, d.attacks);
            }
        });
        chartData = Array.from(dateMap, ([date, attacks]) => ({ date, attacks }));
        
        // Use country-specific color matching the country chart
        const distinctColors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
        ];
        // Simple hash to pick consistent color
        const colorIndex = Math.abs(state.country.split('').reduce((a,b) => (a<<5)-a+b.charCodeAt(0),0)) % 10;
        chartColor = distinctColors[colorIndex];
    } else {
        chartData = await fetch(url).then(r => r.json());
    }
    
    renderLineChart('datechart', chartData, {
        xKey: 'date',
        yKey: 'attacks',
        color: chartColor,
        enableBrush: true,
        onBrush: (start, end) => {
            state.dateRangeHistory.push({
                startDate: state.startDate,
                endDate: state.endDate
            });
            
            state.startDate = start;
            state.endDate = end;
            
            updateURL();
            updateFilterInfo();
            loadAllCharts();
        }
    });
}