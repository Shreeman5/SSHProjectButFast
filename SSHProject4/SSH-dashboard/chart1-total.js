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
    
    // Add ASN filter (single or multiple)
    if (state.asn) {
        url += `&asn=${encodeURIComponent(state.asn)}`;
    } else if (state.asns && state.asns.length > 0) {
        // Discovery mode - multiple ASNs
        console.log('🐛 chart1 - state.asns:', state.asns);
        console.log('🐛 chart1 - is Array?', Array.isArray(state.asns));
        const joined = Array.isArray(state.asns) ? state.asns.join('|||') : state.asns;
        console.log('🐛 chart1 - joined:', joined);
        const encoded = encodeURIComponent(joined);
        console.log('🐛 chart1 - encoded:', encoded);
        url += `&asns=${encoded}`;
        chartColor = '#f59e0b';  // Orange for multi-ASN discovery mode
    }
    
    // Add country filter (single or multiple)
    if (state.country) {
        // Drilling down to single country (even if in discovery mode)
        url += `&country=${encodeURIComponent(state.country)}`;
    } else if (state.countries && state.countries.length > 0) {
        // Discovery mode - multiple countries
        url += `&countries=${encodeURIComponent(state.countries.join(','))}`;
        chartColor = '#10b981';  // Green for multi-country discovery mode
    }
    
    // Fetch data
    console.log('🐛 chart1 - full URL:', url);
    chartData = await fetch(url).then(r => r.json());
    console.log('🐛 chart1 - response length:', chartData.length);
    console.log('🐛 chart1 - first 3 records:', chartData.slice(0, 3));
    
    // Set color based on active filter (only if not in multi-country/asn mode)
    if ((!state.countries || state.countries.length === 0) && (!state.asns || state.asns.length === 0)) {
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