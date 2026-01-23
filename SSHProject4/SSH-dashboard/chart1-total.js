async function loadTotalAttacks() {
    let url = `${API_BASE}/total_attacks?start=${state.startDate}&end=${state.endDate}`;
    let chartData;
    let chartColor = '#7c4dff';  // Default purple
    
    // Add IP filter
    if (state.ip) {
        url += `&ip=${encodeURIComponent(state.ip)}`;
    }
    
    // Add username filter
    if (state.username) {
        url += `&username=${encodeURIComponent(state.username)}`;
    }
    
    // Add ASN filter
    if (state.asn) {
        url += `&asn=${encodeURIComponent(state.asn)}`;
    }
    
    // Add country filter
    if (state.country) {
        url += `&country=${encodeURIComponent(state.country)}`;
    }
    
    // Fetch data
    chartData = await fetch(url).then(r => r.json());
    
    // Set color based on active filter
    if (state.ip) {
        chartColor = '#ff7f0e';  // Orange for IP
    } else if (state.username) {
        chartColor = '#9467bd';  // Purple for username
    } else if (state.asn) {
        chartColor = '#8c564b';  // Brown for ASN
    } else if (state.country) {
        const distinctColors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
        ];
        const colorIndex = Math.abs(state.country.split('').reduce((a,b) => (a<<5)-a+b.charCodeAt(0),0)) % 10;
        chartColor = distinctColors[colorIndex];
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