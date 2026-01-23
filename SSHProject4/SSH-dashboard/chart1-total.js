async function loadTotalAttacks() {
    let url = `${API_BASE}/total_attacks?start=${state.startDate}&end=${state.endDate}`;
    let chartData;
    let chartColor = '#7c4dff';  // Default purple
    
    // Check for IP filter first (highest priority)
    if (state.ip) {
        // If IP is selected, get that IP's data
        url = `${API_BASE}/ip_attacks?start=${state.startDate}&end=${state.endDate}&ip=${encodeURIComponent(state.ip)}`;
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
        
        // ZERO-FILL: Generate all dates in range
        const startParts = state.startDate.split('-');
        const endParts = state.endDate.split('-');
        const start = new Date(startParts[0], startParts[1] - 1, startParts[2]);
        const end = new Date(endParts[0], endParts[1] - 1, endParts[2]);
        chartData = [];
        
        for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
            const year = d.getFullYear();
            const month = String(d.getMonth() + 1).padStart(2, '0');
            const day = String(d.getDate()).padStart(2, '0');
            const dateStr = `${year}-${month}-${day}`;
            
            chartData.push({
                date: dateStr,
                attacks: dateMap.get(dateStr) || 0
            });
        }
        
        // Use IP-specific color (orange)
        chartColor = '#ff7f0e';
    }
    // Check for BOTH ASN and Country (combined filter)
    else if (state.asn && state.country) {
        // Send both parameters to total_attacks endpoint
        url += `&asn=${encodeURIComponent(state.asn)}&country=${encodeURIComponent(state.country)}`;
        chartData = await fetch(url).then(r => r.json());
        
        // Use combined filter color (purple - same as ASN)
        chartColor = '#8c564b';
    }
    // Check for Country only
    else if (state.country) {
        // Send only country parameter
        url += `&country=${encodeURIComponent(state.country)}`;
        chartData = await fetch(url).then(r => r.json());
        
        // Use country-specific color
        const distinctColors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
        ];
        const colorIndex = Math.abs(state.country.split('').reduce((a,b) => (a<<5)-a+b.charCodeAt(0),0)) % 10;
        chartColor = distinctColors[colorIndex];
    }
    // Check for ASN only
    else if (state.asn) {
        // Send only ASN parameter
        url += `&asn=${encodeURIComponent(state.asn)}`;
        chartData = await fetch(url).then(r => r.json());
        
        // Use ASN-specific color (brownish)
        chartColor = '#8c564b';
    }
    // No filters
    else {
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