// Chart Rendering Functions

// Render single line chart (used for Chart 1: Total Attacks)
function renderLineChart(containerId, data, options) {
    const container = d3.select(`#${containerId}`);
    container.selectAll('*').remove();
    
    // Console log data for debugging
    console.log(`${containerId} data:`, {
        rows: data.length,
        firstRow: data[0],
        lastRow: data[data.length - 1],
        sample: data.slice(0, 5)
    });
    
    const svg = container.append('svg')
        .attr('width', CHART_WIDTH)
        .attr('height', CHART_HEIGHT);
    
    const g = svg.append('g')
        .attr('transform', `translate(${MARGIN.left},${MARGIN.top})`);
    
    const width = CHART_WIDTH - MARGIN.left - MARGIN.right;
    const height = CHART_HEIGHT - MARGIN.top - MARGIN.bottom;
    
    // Parse dates as local dates (not UTC) to avoid timezone shift
    data.forEach(d => {
        const parts = d.date.split('-');
        d.date = new Date(parts[0], parts[1] - 1, parts[2]);
    });
    
    // Scales
    const x = d3.scaleTime()
        .domain(d3.extent(data, d => d.date))
        .range([0, width]);
    
    const y = d3.scaleLinear()
        .domain([0, d3.max(data, d => d[options.yKey])])
        .range([height, 0]);
    
    // Extract actual dates for exact tick placement
    const actualDates = data.map(d => d.date);
    
    // Add grid lines - use tickValues to force exact dates
    g.append('g')
        .attr('class', 'grid')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x)
            .tickValues(actualDates)
            .tickSize(-height)
            .tickFormat(''));
    
    g.append('g')
        .attr('class', 'grid')
        .call(d3.axisLeft(y)
            .ticks(5)
            .tickSize(-width)
            .tickFormat(''));
    
    // X-axis with all dates, rotated labels, LARGER font, human-readable format
    g.append('g')
        .attr('class', 'axis')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x)
            .tickValues(actualDates)
            .tickFormat(d3.timeFormat('%b %d')))  // Nov 18 instead of 11/18
        .selectAll('text')
        .style('text-anchor', 'end')
        .style('font-size', '15px')  // Increased from 9px
        .attr('dx', '-.8em')
        .attr('dy', '.15em')
        .attr('transform', 'rotate(-45)');
    
    // Y-axis with human-readable format (8k instead of 8000) and larger font
    const yAxis = g.append('g')
        .attr('class', 'axis')
        .call(d3.axisLeft(y)
            .ticks(5)
            .tickFormat(d => {
                if (d >= 1000000) return (d / 1000000).toFixed(1) + 'M';
                if (d >= 1000) return (d / 1000).toFixed(0) + 'k';
                return d;
            }));
    
    // Increase font size for all y-axis labels
    yAxis.selectAll('text')
        .style('font-size', '15px');
    
    // Make the top y-axis value much bigger
    const ticks = yAxis.selectAll('.tick');
    const tickCount = ticks.size();
    ticks.each(function(d, i) {
        if (i === tickCount - 1) {  // Last tick (top value)
            d3.select(this).select('text')
                .style('font-size', '18px')
                .style('font-weight', 'bold');
        }
    });
    
    // Line
    const line = d3.line()
        .x(d => x(d.date))
        .y(d => y(d[options.yKey]));
    
    g.append('path')
        .datum(data)
        .attr('class', 'line')
        .attr('d', line)
        .attr('stroke', options.color || '#7c4dff');
    
    // Add brush BEFORE dots so dots are on top (only if more than 2 dates)
    if (options.enableBrush && data.length > 2) {
        const brush = d3.brushX()
            .extent([[0, 0], [width, height]])
            .on('end', brushed);
        
        const brushGroup = g.append('g')
            .attr('class', 'brush')
            .call(brush);
        
        brushGroup.select('.overlay')
            .style('pointer-events', 'all');
        
        brushGroup.select('.selection')
            .style('pointer-events', 'none');
        
        function brushed(event) {
            if (!event.selection) return;
            const [x0, x1] = event.selection.map(x.invert);
            const start = d3.timeFormat('%Y-%m-%d')(x0);
            const end = d3.timeFormat('%Y-%m-%d')(x1);
            console.log('Brushed date range:', start, 'to', end);
            options.onBrush(start, end);
        }
    } else if (options.enableBrush && data.length <= 2) {
        // Show visual indicator that brushing is disabled
        g.append('text')
            .attr('x', width / 2)
            .attr('y', -5)
            .attr('text-anchor', 'middle')
            .attr('font-size', '11px')
            .attr('fill', '#999')
            .text('(Brushing disabled - minimum date range reached)');
    }
    
    // Create or reuse tooltip
    let tooltip = d3.select('body').select('.tooltip');
    if (tooltip.empty()) {
        tooltip = d3.select('body').append('div').attr('class', 'tooltip');
    }
    
    // Add larger invisible hit areas
    g.selectAll('.dot-hitarea')
        .data(data)
        .enter().append('circle')
        .attr('class', 'dot-hitarea')
        .attr('cx', d => x(d.date))
        .attr('cy', d => y(d[options.yKey]))
        .attr('r', 8)
        .attr('fill', 'transparent')
        .style('cursor', 'pointer')
        .style('pointer-events', 'all')
        .on('mouseover', function(event, d) {
            d3.select(this.parentNode).selectAll('.dot')
                .filter(dd => dd.date.getTime() === d.date.getTime())
                .attr('r', 6).attr('opacity', 1);
            
            tooltip.transition().duration(200).style('opacity', 1);
            tooltip.html(`
                    <strong>Date:</strong> ${d3.timeFormat('%Y-%m-%d')(d.date)}<br>
                    <strong>Attacks:</strong> ${d[options.yKey].toLocaleString()}
                `)
                .style('left', (event.pageX + 10) + 'px')
                .style('top', (event.pageY - 10) + 'px');
        })
        .on('mouseout', function(event, d) {
            d3.select(this.parentNode).selectAll('.dot')
                .filter(dd => dd.date.getTime() === d.date.getTime())
                .attr('r', 3).attr('opacity', 0.7);
            
            tooltip.transition().duration(200).style('opacity', 0);
        });
    
    // Add visible dots on top
    g.selectAll('.dot')
        .data(data)
        .enter().append('circle')
        .attr('class', 'dot')
        .attr('cx', d => x(d.date))
        .attr('cy', d => y(d[options.yKey]))
        .attr('r', 3)
        .attr('fill', options.color || '#7c4dff')
        .attr('opacity', 0.7)
        .attr('stroke', 'white')
        .attr('stroke-width', 1)
        .style('pointer-events', 'none');
}

// Render multi-line chart with TOP LEGEND and interactions
function renderMultiLineChart(containerId, series, options) {
    const container = d3.select(`#${containerId}`);
    container.selectAll('*').remove();
    
    if (series.length === 0) {
        container.append('div')
            .attr('class', 'loading')
            .text('No data available for current filters');
        return;
    }
    
    // Calculate total attacks per series for ordering
    const seriesWithTotals = series.map(s => ({
        ...s,
        total: d3.sum(s.values, d => d[options.yKey])
    }));
    
    // Sort by total attacks (descending)
    seriesWithTotals.sort((a, b) => b.total - a.total);
    
    console.log(`${containerId} data:`, {
        seriesCount: seriesWithTotals.length,
        seriesNames: seriesWithTotals.map(s => s.key),
        topCountry: seriesWithTotals[0]?.key
    });
    
    // Distinct color palette
    const distinctColors = [
        '#1f77b4', // blue
        '#ff7f0e', // orange
        '#2ca02c', // green
        '#d62728', // red
        '#9467bd', // purple
        '#8c564b', // brown
        '#e377c2', // pink
        '#7f7f7f', // gray
        '#bcbd22', // olive
        '#17becf'  // cyan
    ];
    const countryColor = d3.scaleOrdinal()
        .domain(seriesWithTotals.map(s => s.key))
        .range(distinctColors);
    
    // Always give space for top legend (FIXED: was only for country chart)
    const legendHeight = 70;
    
    const svg = container.append('svg')
        .attr('width', CHART_WIDTH)
        .attr('height', CHART_HEIGHT + legendHeight);
    
    const width = CHART_WIDTH - MARGIN.left - MARGIN.right;
    const height = CHART_HEIGHT - MARGIN.top - MARGIN.bottom;
    
    // Main chart group
    const g = svg.append('g')
        .attr('transform', `translate(${MARGIN.left},${MARGIN.top + legendHeight})`);
    
    // Parse dates
    seriesWithTotals.forEach(s => {
        s.values.forEach(d => {
            const parts = d.date.split('-');
            d.date = new Date(parts[0], parts[1] - 1, parts[2]);
        });
    });
    
    // Scales
    const x = d3.scaleTime()
        .domain([
            d3.min(seriesWithTotals, s => d3.min(s.values, d => d.date)),
            d3.max(seriesWithTotals, s => d3.max(s.values, d => d.date))
        ])
        .range([0, width]);
    
    const y = d3.scaleLinear()
        .domain([0, d3.max(seriesWithTotals, s => d3.max(s.values, d => d[options.yKey]))])
        .range([height, 0]);
    
    // Extract dates for ticks
    const allDates = [...new Set(seriesWithTotals.flatMap(s => s.values.map(v => v.date.getTime())))].sort();
    const actualDates = allDates.map(t => new Date(t));
    
    // Grid lines
    g.append('g')
        .attr('class', 'grid')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x)
            .tickValues(actualDates)
            .tickSize(-height)
            .tickFormat(''));
    
    const yMax = d3.max(seriesWithTotals, s => d3.max(s.values, d => d[options.yKey]));
    const tickValues = [0, yMax * 0.25, yMax * 0.5, yMax * 0.75, yMax];
    
    g.append('g')
        .attr('class', 'grid')
        .call(d3.axisLeft(y)
            .tickValues(tickValues)
            .tickSize(-width)
            .tickFormat(''));
    
    // X-axis
    g.append('g')
        .attr('class', 'axis')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x)
            .tickValues(actualDates)
            .tickFormat(d3.timeFormat('%b %d')))
        .selectAll('text')
        .style('text-anchor', 'end')
        .style('font-size', '12px')
        .attr('dx', '-.8em')
        .attr('dy', '.15em')
        .attr('transform', 'rotate(-45)');
    
    // Y-axis
    const yAxis = g.append('g')
        .attr('class', 'axis')
        .call(d3.axisLeft(y)
            .tickValues(tickValues)
            .tickFormat(d => {
                if (d >= 1000000) return (d / 1000000).toFixed(1) + 'M';
                if (d >= 1000) return (d / 1000).toFixed(0) + 'k';
                return d;
            }));
    
    yAxis.selectAll('text').style('font-size', '15px');
    
    const ticks = yAxis.selectAll('.tick');
    const tickCount = ticks.size();
    ticks.each(function(d, i) {
        if (i === tickCount - 1) {
            d3.select(this).select('text')
                .style('font-size', '18px')
                .style('font-weight', 'bold');
        }
    });
    
    // Tooltip
    let tooltip = d3.select('body').select('.tooltip');
    if (tooltip.empty()) {
        tooltip = d3.select('body').append('div').attr('class', 'tooltip');
    }
    
    // Line generator
    const line = d3.line()
        .x(d => x(d.date))
        .y(d => y(d[options.yKey]));
    
    // Track crossed-out items
    const crossedOut = new Set();
    
    // Pre-declare legendG for reference in event handlers
    let legendG = null;
    
    // Draw lines (simple, no click handlers on lines)
    seriesWithTotals.forEach((s, i) => {
        const lineColor = countryColor(s.key);
        
        g.append('path')
            .datum(s.values)
            .attr('class', `line line-${i}`)
            .attr('data-key', s.key)
            .attr('d', line)
            .attr('stroke', lineColor)
            .attr('stroke-width', 2)
            .attr('fill', 'none')
            .style('cursor', 'default')
            .on('mouseover', function() {
                if (!crossedOut.has(s.key)) {
                    d3.select(this).attr('stroke-width', 4);
                }
            })
            .on('mouseout', function() {
                d3.select(this).attr('stroke-width', 2);
            });
        
        // Dots with tooltip
        g.selectAll(`.dot-${i}`)
            .data(s.values)
            .enter().append('circle')
            .attr('class', `dot-${i}`)
            .attr('data-key', s.key)
            .attr('cx', d => x(d.date))
            .attr('cy', d => y(d[options.yKey]))
            .attr('r', 2.5)
            .attr('fill', lineColor)
            .attr('opacity', 0.7)
            .attr('stroke', 'white')
            .attr('stroke-width', 1)
            .style('cursor', 'pointer')
            .style('pointer-events', 'all')
            .on('mouseover', function(event, d) {
                d3.select(this).attr('r', 5).attr('opacity', 1);
                tooltip.transition().duration(200).style('opacity', 1);
                tooltip.html(`
                    <strong>${s.key}</strong><br>
                    <strong>Date:</strong> ${d3.timeFormat('%Y-%m-%d')(d.date)}<br>
                    <strong>Attacks:</strong> ${d[options.yKey].toLocaleString()}
                `)
                .style('left', (event.pageX + 10) + 'px')
                .style('top', (event.pageY - 10) + 'px');
            })
            .on('mouseout', function() {
                d3.select(this).attr('r', 2.5).attr('opacity', 0.7);
                tooltip.transition().duration(200).style('opacity', 0);
            });
    });
    
    // TOP LEGEND (5×2 grid for all charts)
    legendG = svg.append('g')
        .attr('transform', `translate(${MARGIN.left}, 10)`);
    
    const cols = 5;
    const cellWidth = width / cols;
    
    seriesWithTotals.forEach((s, i) => {
        const row = Math.floor(i / cols);
        const col = i % cols;
        
        const legendItem = legendG.append('g')
            .attr('transform', `translate(${col * cellWidth}, ${row * 30})`)
            .attr('class', 'legend-item')
            .attr('data-key', s.key)
            .style('cursor', 'pointer')
            .on('mouseover', function() {
                // Highlight this line
                g.selectAll('.line').style('opacity', 0.1);
                g.selectAll(`.line[data-key="${s.key}"]`)
                    .style('opacity', 1)
                    .attr('stroke-width', 4);
                
                d3.select(this).select('rect')
                    .attr('stroke', '#000')
                    .attr('stroke-width', 2);
            })
            .on('mouseout', function() {
                // Restore all lines (check if crossed out)
                g.selectAll('.line').each(function() {
                    const key = d3.select(this).attr('data-key');
                    d3.select(this)
                        .style('opacity', crossedOut.has(key) ? 0.3 : 1)
                        .attr('stroke-width', 2);
                });
                
                d3.select(this).select('rect')
                    .attr('stroke', 'none');
            })
            .on('click', function(event) {
                if (options.onClick) {
                    event.preventDefault();
                    options.onClick(s.key);
                }
            })
            .on('contextmenu', function(event) {
                event.preventDefault();
    
                // Toggle crossed-out state
                if (crossedOut.has(s.key)) {
                    // Restore
                    crossedOut.delete(s.key);
                    
                    // Show line and dots
                    g.selectAll(`.line[data-key="${s.key}"]`)
                        .style('display', 'block')
                        .style('opacity', 1)
                        .attr('stroke-dasharray', 'none');
                    
                    g.selectAll(`[class^="dot-"][data-key="${s.key}"]`)
                        .style('display', 'block');
                    
                    // Restore legend
                    d3.select(this).style('opacity', 1);
                    d3.select(this).select('text').style('text-decoration', 'none');
                } else {
                    // Cross out = HIDE completely
                    crossedOut.add(s.key);
                    
                    // Hide line and dots completely
                    g.selectAll(`.line[data-key="${s.key}"]`)
                        .style('display', 'none');
                    
                    g.selectAll(`[class^="dot-"][data-key="${s.key}"]`)
                        .style('display', 'none');
                    
                    // Cross out legend
                    d3.select(this).style('opacity', 0.5);
                    d3.select(this).select('text').style('text-decoration', 'line-through');
                }
                
                // Rescale chart based on visible series
                rescaleChart();  // ← ADD THIS LINE
            });
        
        legendItem.append('rect')
            .attr('width', 18)
            .attr('height', 18)
            .attr('fill', countryColor(s.key))
            .attr('stroke', 'none');
        
        // Format total attacks for display
        const totalFormatted = s.total >= 1000000 
            ? (s.total / 1000000).toFixed(1) + 'M'
            : s.total >= 1000 
            ? (s.total / 1000).toFixed(0) + 'k'
            : s.total.toLocaleString();
        
        // Show name + total attacks in legend
        const legendText = s.key.length > 12 
            ? s.key.substring(0, 10) + '..' 
            : s.key;
        
        legendItem.append('text')
            .attr('x', 24)
            .attr('y', 13)
            .attr('font-size', '12px')
            .style('user-select', 'none')
            .text(`${legendText} (${totalFormatted})`);
    });

    // Function to rescale chart when series are hidden
    function rescaleChart() {
        // Get visible series only
        const visibleSeries = seriesWithTotals.filter(s => !crossedOut.has(s.key));
        
        if (visibleSeries.length === 0) return;
        
        // Recalculate y-axis domain based on visible series only
        const newYMax = d3.max(visibleSeries, s => d3.max(s.values, d => d[options.yKey]));
        y.domain([0, newYMax]);
        
        // Update y-axis with new scale
        const newTickValues = [0, newYMax * 0.25, newYMax * 0.5, newYMax * 0.75, newYMax];
        
        yAxis.transition().duration(500)
            .call(d3.axisLeft(y)
                .tickValues(newTickValues)
                .tickFormat(d => {
                    if (d >= 1000000) return (d / 1000000).toFixed(1) + 'M';
                    if (d >= 1000) return (d / 1000).toFixed(0) + 'k';
                    return d;
                }));
        
        // Re-style tick labels
        yAxis.selectAll('text').style('font-size', '15px');
        const ticks = yAxis.selectAll('.tick');
        const tickCount = ticks.size();
        ticks.each(function(d, i) {
            if (i === tickCount - 1) {
                d3.select(this).select('text')
                    .style('font-size', '18px')
                    .style('font-weight', 'bold');
            } else {
                d3.select(this).select('text')
                    .style('font-size', '15px')
                    .style('font-weight', 'normal');
            }
        });
        
        // Update grid lines
        g.select('.grid').filter(function() {
            return d3.select(this).attr('transform') !== `translate(0,${height})`;
        })
        .transition().duration(500)
        .call(d3.axisLeft(y)
            .tickValues(newTickValues)
            .tickSize(-width)
            .tickFormat(''));
        
        // Reposition all visible lines and dots
        seriesWithTotals.forEach((s, i) => {
            const lineGen = d3.line()
                .x(d => x(d.date))
                .y(d => y(d[options.yKey]));
            
            g.selectAll(`.line[data-key="${s.key}"]`)
                .transition().duration(500)
                .attr('d', lineGen);
            
            g.selectAll(`[class^="dot-"][data-key="${s.key}"]`)
                .transition().duration(500)
                .attr('cy', d => y(d[options.yKey]));
        });
    }
}