// Chart 1: Total Attacks Over Time

async function loadTotalAttacks() {
    const url = `${API_BASE}/total_attacks?start=${state.startDate}&end=${state.endDate}`;
    const data = await fetch(url).then(r => r.json());
    
    renderLineChart('datechart', data, {
        xKey: 'date',
        yKey: 'attacks',
        color: '#7c4dff', // Purple color
        enableBrush: true,
        onBrush: (start, end) => {
            // Save current range to history before changing
            state.dateRangeHistory.push({
                startDate: state.startDate,
                endDate: state.endDate
            });
            
            // Apply new range
            state.startDate = start;
            state.endDate = end;
            
            updateURL();
            updateFilterInfo();
            loadAllCharts();
        }
    });
}