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
    
    // Add grid lines
    g.append('g')
        .attr('class', 'grid')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x)
            .ticks(data.length)
            .tickSize(-height)
            .tickFormat(''));
    
    g.append('g')
        .attr('class', 'grid')
        .call(d3.axisLeft(y)
            .ticks(5)
            .tickSize(-width)
            .tickFormat(''));
    
    // X-axis with all dates, rotated labels, smaller font
    g.append('g')
        .attr('class', 'axis')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x)
            .ticks(data.length)
            .tickFormat(d3.timeFormat('%m/%d')))
        .selectAll('text')
        .style('text-anchor', 'end')
        .style('font-size', '9px')
        .attr('dx', '-.8em')
        .attr('dy', '.15em')
        .attr('transform', 'rotate(-45)');
    
    // Y-axis
    g.append('g')
        .attr('class', 'axis')
        .call(d3.axisLeft(y)
            .ticks(5)
            .tickFormat(d => d.toLocaleString()));
    
    // Line
    const line = d3.line()
        .x(d => x(d.date))
        .y(d => y(d[options.yKey]));
    
    g.append('path')
        .datum(data)
        .attr('class', 'line')
        .attr('d', line)
        .attr('stroke', options.color || '#7c4dff');
    
    // Add brush BEFORE dots so dots are on top
    if (options.enableBrush) {
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

// Render multi-line chart (used for Charts 2-6)
function renderMultiLineChart(containerId, series, options) {
    const container = d3.select(`#${containerId}`);
    container.selectAll('*').remove();
    
    if (series.length === 0) {
        container.append('div')
            .attr('class', 'loading')
            .text('No data available for current filters');
        return;
    }
    
    // Console log data for debugging
    console.log(`${containerId} data:`, {
        seriesCount: series.length,
        seriesNames: series.map(s => s.key),
        firstSeries: series[0]?.key,
        sampleData: series[0]?.values.slice(0, 3)
    });
    
    const svg = container.append('svg')
        .attr('width', CHART_WIDTH)
        .attr('height', CHART_HEIGHT);
    
    const g = svg.append('g')
        .attr('transform', `translate(${MARGIN.left},${MARGIN.top})`);
    
    const width = CHART_WIDTH - MARGIN.left - MARGIN.right;
    const height = CHART_HEIGHT - MARGIN.top - MARGIN.bottom;
    
    // Parse dates as local dates to avoid timezone shift
    series.forEach(s => {
        s.values.forEach(d => {
            const parts = d.date.split('-');
            d.date = new Date(parts[0], parts[1] - 1, parts[2]);
        });
    });
    
    // Scales
    const x = d3.scaleTime()
        .domain([
            d3.min(series, s => d3.min(s.values, d => d.date)),
            d3.max(series, s => d3.max(s.values, d => d.date))
        ])
        .range([0, width]);
    
    const y = d3.scaleLinear()
        .domain([0, d3.max(series, s => d3.max(s.values, d => d[options.yKey]))])
        .range([height, 0]);
    
    // Add grid lines
    g.append('g')
        .attr('class', 'grid')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x)
            .ticks(d3.max(series, s => s.values.length))
            .tickSize(-height)
            .tickFormat(''));
    
    g.append('g')
        .attr('class', 'grid')
        .call(d3.axisLeft(y)
            .ticks(5)
            .tickSize(-width)
            .tickFormat(''));
    
    // X-axis with all dates, rotated labels, smaller font
    g.append('g')
        .attr('class', 'axis')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x)
            .ticks(d3.max(series, s => s.values.length))
            .tickFormat(d3.timeFormat('%m/%d')))
        .selectAll('text')
        .style('text-anchor', 'end')
        .style('font-size', '9px')
        .attr('dx', '-.8em')
        .attr('dy', '.15em')
        .attr('transform', 'rotate(-45)');
    
    // Y-axis
    g.append('g')
        .attr('class', 'axis')
        .call(d3.axisLeft(y)
            .ticks(5)
            .tickFormat(d => d.toLocaleString()));
    
    // Create or reuse tooltip
    let tooltip = d3.select('body').select('.tooltip');
    if (tooltip.empty()) {
        tooltip = d3.select('body').append('div').attr('class', 'tooltip');
    }
    
    // Lines
    const line = d3.line()
        .x(d => x(d.date))
        .y(d => y(d[options.yKey]));
    
    series.forEach((s, i) => {
        const lineColor = color(s.key);
        
        // Draw line
        g.append('path')
            .datum(s.values)
            .attr('class', 'line')
            .attr('d', line)
            .attr('stroke', lineColor)
            .style('cursor', options.onClick ? 'pointer' : 'default')
            .on('click', function() {
                if (options.onClick) {
                    console.log('Clicked:', s.key);
                    options.onClick(s.key);
                }
            })
            .on('mouseover', function() {
                d3.select(this).attr('stroke-width', 4);
            })
            .on('mouseout', function() {
                d3.select(this).attr('stroke-width', 2);
            });
        
        // Add visible hover points
        g.selectAll(`.dot-${i}`)
            .data(s.values)
            .enter().append('circle')
            .attr('class', `dot-${i}`)
            .attr('cx', d => x(d.date))
            .attr('cy', d => y(d[options.yKey]))
            .attr('r', 2.5)
            .attr('fill', lineColor)
            .attr('opacity', 0.7)
            .attr('stroke', 'white')
            .attr('stroke-width', 1)
            .style('cursor', 'pointer')
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
    
    // Legend
    const legend = g.append('g')
        .attr('transform', `translate(${width + 10}, 0)`);
    
    series.forEach((s, i) => {
        const legendRow = legend.append('g')
            .attr('transform', `translate(0, ${i * 20})`)
            .style('cursor', options.onClick ? 'pointer' : 'default')
            .on('click', function() {
                if (options.onClick) {
                    console.log('Legend clicked:', s.key);
                    options.onClick(s.key);
                }
            });
        
        legendRow.append('rect')
            .attr('width', 15)
            .attr('height', 15)
            .attr('fill', color(s.key));
        
        legendRow.append('text')
            .attr('x', 20)
            .attr('y', 12)
            .attr('font-size', '11px')
            .text(s.key.substring(0, 20));
    });
}
