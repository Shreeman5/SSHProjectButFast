// Chart 7: "How buried is it?"
// Shown only when the dashboard is opened from the IP similarity window with a
// searched IP (?searched=...&ips=...). Data comes from /api/burial, which ranks
// everything by total attacks in the date range -- the same rule the Top 10
// charts use to decide what is visible.
//
// Part 1 -- burial ladder: the searched IP, its ASN and its country, each as a
//           share of ALL attacks on a log scale, with the Top-10 cutoff marked.
// Part 2 -- rank strip: every IP that was sent, placed by its global rank.
//
// Built as plain SVG markup (no d3) so it renders the same everywhere.

const BURIAL_COLORS = {
    all: '#d1d5db', country: '#c4b5fd', asn: '#a78bfa', ip: '#7c3aed',
    cutoff: '#dc2626', top10Band: '#dcfce7', other: '#6b7280', text: '#111827', muted: '#6b7280',
};

function burialEsc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function burialCount(n) {
    if (n === null || n === undefined) return '—';
    if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return String(n);
}

// Two significant figures for small percentages, never scientific notation.
function burialPct(p) {
    if (!p) return '0%';
    if (p >= 10) return p.toFixed(1) + '%';
    if (p >= 1) return p.toFixed(2) + '%';
    return p.toFixed(Math.min(10, 1 - Math.floor(Math.log10(p)))) + '%';
}

function burialInt(n) { return n === null || n === undefined ? '—' : n.toLocaleString(); }

// Log scale helper: maps [lo, hi] onto [x0, x1].
function burialLog(lo, hi, x0, x1) {
    const a = Math.log10(lo), b = Math.log10(hi);
    return v => x0 + (Math.log10(Math.max(v, lo)) - a) / (b - a) * (x1 - x0);
}

async function loadBurialChart() {
    const section = document.getElementById('chart7');
    const target = document.getElementById('burialchart');
    if (!section || !target) return;
    if (!state.searched) {
        section.style.display = 'none';
        return;
    }
    section.style.display = 'block';

    const ips = (state.ips || []).join('|||');
    const url = `${API_BASE}/burial?start=${state.startDate}&end=${state.endDate}` +
                `&searched=${encodeURIComponent(state.searched)}&ips=${encodeURIComponent(ips)}`;
    let data;
    try {
        const r = await fetch(url);
        data = await r.json();
        if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    } catch (e) {
        target.innerHTML = `<div style="padding: 16px; color: #b91c1c;">Could not load the burial chart: ${burialEsc(e.message)}</div>`;
        return;
    }
    target.innerHTML = renderBurialChart(data, typeof CHART_WIDTH === 'number' ? CHART_WIDTH : 1800);
}

// "✓ big enough" / "✗ 300× too small" for one level.
function burialVerdict(lvl, N) {
    if (lvl.in_top10) return { ok: true, text: `✓ Big enough to appear in the default Top ${N}` };
    if (!lvl.share || !lvl.top10_share) return { ok: false, text: `✗ Not in the default Top ${N}` };
    const f = lvl.top10_share / lvl.share;
    const times = f < 10 ? f.toFixed(1) : Math.round(f).toLocaleString();
    return { ok: false, text: `✗ ${times}× too small to appear in the default Top ${N}` };
}

function renderBurialChart(d, W) {
    const L = d.levels, N = d.top_n;
    const ip = L.ip;
    const sel = d.selected_ips || [];
    const ranked = sel.filter(s => s.rank !== null);
    const missing = sel.length - ranked.length;

    // ---- summary -------------------------------------------------------------
    const summary = `
        <div style="font-size: 16px; line-height: 1.5; margin: 4px 0 14px; color: ${BURIAL_COLORS.text};">
            <strong>${d.selected_in_top10} of ${sel.length}</strong> IP${sel.length === 1 ? '' : 's'} sent here would appear in the default
            Top ${N} IPs chart. The searched IP <strong style="font-family: monospace;">${burialEsc(d.searched)}</strong>
            ranks <strong>#${burialInt(ip.rank)} of ${burialInt(ip.of)}</strong> IPs by attack volume
            ${ip.rank ? `(${burialPct(100 * (ip.rank - 1) / ip.of)} of IPs attacked more)` : ''}
            and accounts for <strong>${burialPct(ip.share)}</strong> of all ${burialCount(d.total_attacks)} attacks
            between ${burialEsc(d.start)} and ${burialEsc(d.end)}.
            ${missing ? `<span style="color: ${BURIAL_COLORS.muted};">(${missing} sent IP${missing === 1 ? ' has' : 's have'} no attacks in this range.)</span>` : ''}
        </div>`;

    // ---- Part 1: burial ladder ----------------------------------------------
    const levelRow = (label, lvl, color, unit, mono) => ({
        label, share: lvl.share, cutoff: lvl.top10_share, color, mono, verdict: burialVerdict(lvl, N),
        info: [
            `${burialCount(lvl.total)} attacks · ${burialPct(lvl.share)} of all`,
            `rank #${burialInt(lvl.rank)} of ${burialInt(lvl.of)} ${unit}`,
            ...(lvl.within ? [`in ${lvl.within.parent}: #${burialInt(lvl.within.rank)} of ${burialInt(lvl.within.of)} ${unit}, ${burialPct(lvl.within.share_of_parent)} of its attacks`] : []),
        ],
    });
    const rows = [
        { label: 'All attacks', share: 100, color: BURIAL_COLORS.all, info: [`${burialCount(d.total_attacks)} attacks`] },
        levelRow(`Country: ${L.country.name}`, L.country, BURIAL_COLORS.country, 'countries'),
        levelRow(`ASN: ${L.asn.name}`, L.asn, BURIAL_COLORS.asn, 'ASNs'),
        levelRow(`IP: ${d.searched}`, ip, BURIAL_COLORS.ip, 'IPs', true),
    ];
    const smallest = Math.min(...rows.map(r => r.share || 100), ...rows.filter(r => r.cutoff).map(r => r.cutoff));
    const lo = Math.pow(10, Math.floor(Math.log10(Math.max(smallest, 1e-9) / 2)));
    const labelW = 330, infoW = 560, x0 = labelW, x1 = W - infoW - 30, rowH = 84, top = 62;
    const xs = burialLog(lo, 100, x0, x1);
    const h1 = top + rows.length * rowH + 40;

    let svg1 = `<svg width="${W}" height="${h1}" style="font-family: sans-serif;">`;
    svg1 += `<text x="0" y="18" font-size="15" font-weight="600" fill="${BURIAL_COLORS.text}">Share of all attacks (log scale: each gridline is 10× bigger than the one before)</text>`;
    // plain-language key for the red line
    svg1 += `<line x1="0" y1="38" x2="0" y2="52" stroke="${BURIAL_COLORS.cutoff}" stroke-width="2.5" stroke-dasharray="4,3" transform="translate(6,0)"/>`;
    svg1 += `<text x="18" y="50" font-size="14" fill="${BURIAL_COLORS.text}"><tspan font-weight="700" fill="${BURIAL_COLORS.cutoff}">Top ${N} line</tspan>` +
            ` = the size of the ${N}th-biggest country, ASN or IP. A bar has to reach its red line to show up in the dashboard's default Top ${N} charts; the further left it stops, the more buried it is.</text>`;
    for (let p = Math.log10(lo); p <= 2; p++) {
        const v = Math.pow(10, p), x = xs(v);
        svg1 += `<line x1="${x}" y1="${top}" x2="${x}" y2="${top + rows.length * rowH}" stroke="#e5e7eb"/>`;
        svg1 += `<text x="${x}" y="${top + rows.length * rowH + 22}" font-size="13" fill="${BURIAL_COLORS.muted}" text-anchor="middle">${v >= 1 ? v : v.toFixed(-p)}%</text>`;
    }
    rows.forEach((r, i) => {
        const y = top + i * rowH, bh = 30, by = y + 24;
        const name = r.label.length > 38 ? r.label.slice(0, 37) + '…' : r.label;
        svg1 += `<g><title>${burialEsc(r.label)}</title><text x="${labelW - 14}" y="${by + bh / 2 + 5}" font-size="15" text-anchor="end" fill="${BURIAL_COLORS.text}"${r.mono ? ' font-family="monospace" font-weight="700"' : ''}>${burialEsc(name)}</text></g>`;
        const xe = xs(r.share || lo);
        svg1 += `<rect x="${x0}" y="${by}" width="${Math.max(2, xe - x0)}" height="${bh}" rx="3" fill="${r.color}"><title>${burialEsc(r.label)}: ${burialPct(r.share)} of all attacks</title></rect>`;
        if (r.cutoff) {
            const xc = xs(r.cutoff);
            svg1 += `<line x1="${xc}" y1="${by - 8}" x2="${xc}" y2="${by + bh + 6}" stroke="${BURIAL_COLORS.cutoff}" stroke-width="2.5" stroke-dasharray="4,3"><title>Top ${N} line: the ${N}th-biggest has ${burialPct(r.cutoff)} of all attacks</title></line>`;
            svg1 += `<text x="${xc}" y="${by - 12}" font-size="12" font-weight="600" fill="${BURIAL_COLORS.cutoff}" text-anchor="middle">Top ${N} line</text>`;
        }
        if (r.verdict) {
            svg1 += `<text x="${x1 + 30}" y="${y + 20}" font-size="14" font-weight="700" fill="${r.verdict.ok ? '#15803d' : BURIAL_COLORS.cutoff}">${burialEsc(r.verdict.text)}</text>`;
        }
        r.info.forEach((t, k) => {
            const yy = y + (r.verdict ? 40 : 20) + k * 18;
            svg1 += `<text x="${x1 + 30}" y="${yy}" font-size="13" fill="${k === 0 && !r.verdict ? BURIAL_COLORS.text : BURIAL_COLORS.muted}"${k === 0 && !r.verdict ? ' font-weight="600"' : ''}>${burialEsc(t)}</text>`;
        });
    });
    svg1 += `</svg>`;

    // ---- Part 2: rank strip ---------------------------------------------------
    const n = Math.max(ip.of, 2);
    const sx0 = 40, sx1 = W - 40, xr = burialLog(1, n, sx0, sx1);
    const R = 7, RS = 10;
    // stack dots into lanes (upwards from the axis) so close ranks don't hide each other
    const lanes = [];
    const placed = ranked.slice().sort((a, b) => a.rank - b.rank).map(s => {
        const x = xr(s.rank);
        let lane = lanes.findIndex(last => x - last >= 2 * RS + 2);
        if (lane === -1) { lane = lanes.length; lanes.push(x); } else lanes[lane] = x;
        return { ...s, x, lane };
    });
    const laneH = 2 * RS + 4;
    const headerH = 70;                                   // title + legend row
    const plotTop = headerH + 10;
    const plotH = Math.max(2, lanes.length) * laneH + 20;
    const axisY = plotTop + plotH;
    const h2 = axisY + 64;
    const searchedDot = placed.find(s => s.searched);

    let svg2 = `<svg width="${W}" height="${h2}" style="font-family: sans-serif;">`;
    svg2 += `<text x="0" y="18" font-size="15" font-weight="600" fill="${BURIAL_COLORS.text}">Where every IP sent here ranks among all ${burialInt(ip.of)} IPs</text>`;
    svg2 += `<text x="0" y="38" font-size="13" fill="${BURIAL_COLORS.muted}">Ranked by total attacks, #1 = most. Log scale: each gridline is 10× further down the list.</text>`;

    // legend, top right -- the searched IP is named here, not next to its dot
    const lgX = W - 40;
    let lg = '';
    if (searchedDot) {
        lg += `<circle cx="${lgX - 470}" cy="18" r="${RS}" fill="${BURIAL_COLORS.ip}" stroke="white" stroke-width="2"/>`;
        lg += `<text x="${lgX - 454}" y="23" font-size="14" fill="${BURIAL_COLORS.text}">Searched IP <tspan font-family="monospace" font-weight="700" fill="${BURIAL_COLORS.ip}">${burialEsc(searchedDot.ip)}</tspan> · rank #${burialInt(searchedDot.rank)}</text>`;
    }
    lg += `<circle cx="${lgX - 470}" cy="46" r="${R}" fill="${BURIAL_COLORS.other}" fill-opacity="0.85"/>`;
    lg += `<text x="${lgX - 454}" y="51" font-size="14" fill="${BURIAL_COLORS.text}">Other IPs you sent (${ranked.length - (searchedDot ? 1 : 0)})</text>`;
    lg += `<rect x="${lgX - 230}" y="38" width="16" height="16" rx="2" fill="${BURIAL_COLORS.top10Band}" stroke="#86efac"/>`;
    lg += `<text x="${lgX - 208}" y="51" font-size="14" fill="${BURIAL_COLORS.text}">Default Top ${N} IPs chart</text>`;
    svg2 += lg;

    // plot area background + decade gridlines
    svg2 += `<rect x="${sx0}" y="${plotTop}" width="${sx1 - sx0}" height="${plotH}" fill="#fafafa" stroke="#e5e7eb"/>`;
    const xTop = xr(N + 0.5);
    svg2 += `<rect x="${sx0}" y="${plotTop}" width="${xTop - sx0}" height="${plotH}" fill="${BURIAL_COLORS.top10Band}"/>`;
    svg2 += `<text x="${(sx0 + xTop) / 2}" y="${plotTop + plotH / 2 + 5}" font-size="13" font-weight="600" fill="#15803d" text-anchor="middle">Visible in the default Top ${N}</text>`;
    svg2 += `<line x1="${xTop}" y1="${plotTop}" x2="${xTop}" y2="${axisY}" stroke="${BURIAL_COLORS.cutoff}" stroke-width="2.5" stroke-dasharray="4,3"><title>Top ${N} line</title></line>`;
    for (let v = 1; v <= n; v *= 10) {
        const x = xr(v);
        if (v > 1) svg2 += `<line x1="${x}" y1="${plotTop}" x2="${x}" y2="${axisY}" stroke="#e5e7eb"/>`;
        svg2 += `<line x1="${x}" y1="${axisY}" x2="${x}" y2="${axisY + 7}" stroke="#6b7280"/>`;
        svg2 += `<text x="${x}" y="${axisY + 24}" font-size="13" fill="${BURIAL_COLORS.muted}" text-anchor="middle">#${burialInt(v)}</text>`;
        for (let m = 2; m <= 9; m++) {                     // minor ticks
            const vm = v * m;
            if (vm > n) break;
            const xm = xr(vm);
            svg2 += `<line x1="${xm}" y1="${axisY}" x2="${xm}" y2="${axisY + 4}" stroke="#9ca3af"/>`;
        }
    }
    svg2 += `<line x1="${sx0}" y1="${axisY}" x2="${sx1}" y2="${axisY}" stroke="#6b7280"/>`;
    svg2 += `<text x="${sx1}" y="${axisY + 42}" font-size="13" fill="${BURIAL_COLORS.muted}" text-anchor="end">#${burialInt(n)} (last)</text>`;

    const dotY = s => axisY - 14 - s.lane * laneH;
    const tip = s => `${burialEsc(s.ip)}${s.searched ? ' (searched)' : ''} · rank #${burialInt(s.rank)} · ${burialCount(s.total)} attacks · ${burialEsc(s.asn_name || 'Unknown ASN')} · ${burialEsc(s.country || 'Unknown')}`;
    placed.filter(s => !s.searched).forEach(s => {
        svg2 += `<circle cx="${s.x}" cy="${dotY(s)}" r="${R}" fill="${s.in_top10 ? '#16a34a' : BURIAL_COLORS.other}" fill-opacity="0.85" stroke="white" stroke-width="1.5"><title>${tip(s)}</title></circle>`;
    });
    if (searchedDot) {                                    // drawn last so it is on top
        const s = searchedDot, y = dotY(s);
        svg2 += `<line x1="${s.x}" y1="${y}" x2="${s.x}" y2="${axisY}" stroke="${BURIAL_COLORS.ip}" stroke-width="1.5" stroke-opacity="0.5"/>`;
        svg2 += `<circle cx="${s.x}" cy="${y}" r="${RS + 4}" fill="none" stroke="${BURIAL_COLORS.ip}" stroke-opacity="0.35" stroke-width="3"/>`;
        svg2 += `<circle cx="${s.x}" cy="${y}" r="${RS}" fill="${BURIAL_COLORS.ip}" stroke="white" stroke-width="2"><title>${tip(s)}</title></circle>`;
    }
    const ranks = ranked.map(s => s.rank).sort((a, b) => a - b);
    if (ranks.length) {
        const med = ranks[Math.floor((ranks.length - 1) / 2)];
        svg2 += `<text x="${sx0}" y="${axisY + 42}" font-size="13" fill="${BURIAL_COLORS.muted}">` +
                `${ranks.length} ranked IP${ranks.length === 1 ? '' : 's'} · best #${burialInt(ranks[0])} · median #${burialInt(med)} · worst #${burialInt(ranks[ranks.length - 1])} · hover a dot for details</text>`;
    }
    svg2 += `</svg>`;

    return summary + svg1 + `<div style="height: 18px;"></div>` + svg2;
}