async function loadUsernameAttacks() {
    let url = `${API_BASE}/username_attacks?start=${state.startDate}&end=${state.endDate}`;
    
    if (state.country) {
        url += `&country=${encodeURIComponent(state.country)}`;
    }
    
    // Add ASN filter
    if (state.asn) {
        url += `&asn=${encodeURIComponent(state.asn)}`;
    }
    
    // DEBUG: Log the constructed URL
    console.log('=== USERNAME CHART DEBUG ===');
    console.log('State object:', state);
    console.log('Constructed URL:', url);
    
    const data = await fetch(url).then(r => r.json());
    
    // DEBUG: Log the raw data received from API
    console.log('Raw data from API (first 5 rows):', data.slice(0, 5));
    console.log('Total rows received:', data.length);
    
    // DEBUG: Log unique usernames in the data
    const uniqueUsernames = [...new Set(data.map(d => d.username))];
    console.log('Number of unique usernames:', uniqueUsernames.length);
    console.log('Unique usernames:', uniqueUsernames);
    
    const series = d3.group(data, d => d.username);
    const seriesArray = Array.from(series, ([key, values]) => ({ key, values }));
    
    // DEBUG: Log the series array structure
    console.log('Series array (first 3):', seriesArray.slice(0, 3).map(s => ({
        key: s.key,
        valueCount: s.values.length,
        firstValue: s.values[0]
    })));
    console.log('============================');
    
    renderMultiLineChart('usernamechart', seriesArray, {
        yKey: 'attacks'
    });
}