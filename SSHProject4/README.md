# SSH Attack Analysis Dashboard - Development Log

## 📊 Project Overview

Interactive web dashboard for analyzing SSH attack patterns from honeypot data. Built with D3.js, Flask API, and DuckDB for real-time analysis of 213M+ attacks across 69 days (Nov 1, 2022 - Jan 8, 2023).

---

## 🎯 Dashboard Structure

### Chart Layout (Top to Bottom)

1. **Total Attacks Over Time** - Temporal overview with date range brushing
2. **Top 20 Attacking Countries** - Geographic distribution with filtering
3. **Top 20 Most Volatile Countries** - Countries with biggest day-to-day swings
4. **Top 20 Attacking ASN Organizations** - Network operators behind attacks
5. **Top 20 Attacking IPs** - Specific attacking machines
6. **Top 20 Attacking Usernames** - Credentials being targeted

**Data Hierarchy:** Time → Geography → Network (ASN) → Machine (IP) → Credential (Username)

---

## ✨ Major Features Implemented

### 1. Interactive Date Range Brushing
**Location:** Chart 1 (Date Chart)

**Features:**
- Brush over chart to zoom into specific date ranges
- Brush history with "Go Back" button (undo stack)
- Automatic brush disabling when ≤ 2 dates remain
- Visual feedback when at minimum range
- Button positioned next to chart title

**User Flow:**
```
1. Full range (69 days) → Brush to 31 days → [Go Back (1)]
2. Brush to 10 days → [Go Back (2)]
3. Click Go Back → Returns to 31 days → [Go Back (1)]
4. Click Reset All Filters → Returns to full 69 days
```

---

### 2. Advanced Country Chart Interactions
**Location:** Chart 2 (Country Chart)

**Visual Design:**
- Top legend grid (5 columns × 2 rows)
- Countries ordered by total attacks (descending)
- Distinct color palette (10 unique colors)
- Legend shows: `Country (Total Attacks)` format
  - Example: `China (28.3M)`, `United States (44.5M)`

**Interactive Features:**

| Action | Behavior |
|--------|----------|
| **Hover legend** | Highlight that country's line, grey out all others |
| **Left-click legend/line** | Filter all charts to that country only |
| **Right-click legend** | Cross out country (hide line completely) |
| **Right-click again** | Restore country |
| **Click filtered country** | Toggle off filter (unfilter) |

**When Country Selected:**
- Date chart shows only that country's attacks (in country's color)
- Country chart shows only that country
- Volatile chart hidden
- IP/Username/ASN charts filtered to that country
- "Restore All Countries" button appears (styled purple button)

**Right-Click Rescaling:**
- When you hide a high-value country (e.g., United States with 1.8M max)
- Y-axis automatically rescales to next highest country (e.g., China at 1.4M)
- Other countries become more visible with smooth 500ms transition

**Code Location:** `chart2-countries.js`, `chart-renderers.js`

---

### 3. Volatile Countries Chart Interactivity
**Location:** Chart 3 (Volatile Chart)

**Purpose:** Shows countries with the highest day-to-day attack variance

**Interactive Features:**
- Same interactions as Country Chart (hover, left-click, right-click)
- Shows top 20 countries by maximum percentage change

**When Volatile Country Selected:**
- Date chart shows only that country's attacks
- Country chart hidden (volatile chart stays visible)
- IP/Username/ASN charts filtered to that country
- "Restore All Countries" button appears on volatile chart

**Difference from Country Chart:**
- Filtering from volatile chart hides country chart, keeps volatile chart
- Filtering from country chart hides volatile chart, keeps country chart
- Both use same "Restore All Countries" button functionality

**Code Location:** `chart3-volatile.js`

---

### 4. ASN Chart Interactivity
**Location:** Chart 4 (ASN Chart)

**Interactive Features:**
- Hover legend to highlight
- Left-click to filter by ASN
- Right-click to cross out ASN
- "Restore All ASNs" button appears when filtered

**When ASN Selected:**
- Date chart shows only that ASN's attacks (brown color)
- Country chart stays visible (ASNs operate globally)
- Volatile chart stays visible
- ASN chart shows only that ASN
- IP chart shows top 20 IPs from that ASN
- Username chart shows top 20 usernames from that ASN

**Rationale:** ASNs (Autonomous System Numbers) are global network operators that can have IP addresses in multiple countries. Keeping country/volatile charts visible shows geographic distribution of the ASN.

**Code Location:** `chart6-asn.js`

---

### 5. Zero-Filling for Continuous Lines
**Problem:** When an entity (country/IP/username/ASN) had 0 attacks on a day, the database had no row, causing lines to disappear.

**Example Bug:**
- Haiti had 148 attacks on Nov 29
- 0 attacks Nov 30 - Dec 4 (no database rows)
- Line disappeared from Nov 29 onwards ❌

**Solution:** Generate complete date grid for all entities, fill missing dates with 0 attacks.

**Implementation:** SQL query uses:
```sql
WITH date_range AS (
    SELECT UNNEST(generate_series(DATE 'start', DATE 'end', INTERVAL 1 DAY))::DATE as date
),
complete_grid AS (
    SELECT d.date, t.entity FROM date_range d CROSS JOIN top_entities t
)
SELECT g.date, g.entity, COALESCE(d.attacks, 0) as attacks
FROM complete_grid g LEFT JOIN actual_data d ON ...
```

**Applied to:** All 5 multi-line charts (Country, Volatile, ASN, IP, Username) + Date chart when filtered

**Code Location:** All API endpoints (`api_summary_only.py`), `chart1-total.js`

---

### 6. Database Schema Updates

#### Rebuilt Tables with Country Column

**Before:**
```sql
daily_username_attacks (date, username, attacks)
daily_asn_attacks (date, asn, asn_name, attacks)
```

**After:**
```sql
daily_username_attacks (date, username, country, attacks)
daily_asn_attacks (date, asn, asn_name, country, attacks)
```

**Impact:**
- Username table: ~50K rows → ~1.2M rows (24x larger)
- ASN table: ~150K rows → ~980K rows (6.5x larger)
- Enables country filtering for username and ASN charts

**Why?** Each username/ASN now has one row per country per day, allowing proper filtering when a country is selected.

**Scripts:** 
- `rebuild_username_with_country_FIXED.py`
- `create_asn_table_with_country.py`

---

## 🎨 Visual Improvements

### Chart Sizing
- Chart width: 1800px → **2200px** (fills screen better)
- Legend height: 70px for all multi-line charts (prevents overlap)
- Consistent margins across all charts

### Font Improvements
| Element | Before | After |
|---------|--------|-------|
| X-axis dates | 9px | 12px |
| Y-axis numbers | 11px | 15px |
| Top Y-axis value | 15px | 18px bold |
| Legend labels | 11px | 12px |

### Date Format
- Before: `11/18` (MM/DD)
- After: `Nov 18` (human-readable)

### Number Format
- Before: `8,000` (full number)
- After: `8k` (compact)
- Format: 1.5M (millions), 12k (thousands), 567 (hundreds)

### Y-Axis Improvements
- Always exactly 5 ticks: 0%, 25%, 50%, 75%, 100% of max value
- All values rounded to integers (no decimals like 905.25)
- Top value emphasized (18px bold)

---

## 🔧 Technical Fixes

### 1. Fixed API Date Range Filtering
**Problem:** Charts 2-6 showed top 20 entities from ALL dates, not filtered date range.

**Example Bug:**
- Brush to Nov 15 - Dec 15
- Country chart showed top 20 countries from all 69 days ❌
- Should show top 20 countries from Nov 15 - Dec 15 only ✅

**Fix:** Added date filter to top 20 selection in CTE:
```sql
WITH top_items AS (
    SELECT item FROM table
    WHERE date BETWEEN 'start' AND 'end'  -- Added this
    GROUP BY item ORDER BY SUM(attacks) DESC LIMIT 20
)
```

**Affected endpoints:** All 5 multi-line chart endpoints

---

### 2. Fixed Duplicate Date Ticks
**Problem:** Brushing to exactly 2 dates showed 3 ticks with phantom middle tick.

**Cause:** `.ticks(data.length)` is a suggestion; D3 adds "nice" intervals.

**Fix:** Use `.tickValues(actualDates)` to force exact dates:
```javascript
const actualDates = data.map(d => d.date);
.call(d3.axisBottom(x).tickValues(actualDates).tickFormat(...))
```

**Code Location:** `chart-renderers.js` (both rendering functions)

---

### 3. Fixed Inconsistent Y-Axis Ticks
**Problem:** Different charts showed different numbers of y-axis ticks despite both using `.ticks(5)`.

**Fix:** Force exactly 5 ticks with `.tickValues()`:
```javascript
const yMax = d3.max(...);
const tickValues = [
    0,
    Math.round(yMax * 0.25),
    Math.round(yMax * 0.5),
    Math.round(yMax * 0.75),
    Math.round(yMax)
];
.tickValues(tickValues)
```

---

### 4. Fixed Date Chart Missing Jan 8
**Problem:** When filtering by country, date chart showed 68 days instead of 69 (missing Jan 8).

**Cause:** `new Date('2023-01-08')` can be parsed as UTC midnight, becoming Jan 7 in local timezone.

**Fix:** Parse dates explicitly as local:
```javascript
const parts = '2023-01-08'.split('-');
new Date(parts[0], parts[1] - 1, parts[2])  // Local date
```

---

### 5. Changed Top 10 to Top 20
All multi-line charts now show top 20 entities instead of top 10:
- More comprehensive view
- Better for analysis
- 10 columns × 2 rows legend layout

**Code:** Changed `LIMIT 10` → `LIMIT 20` in all API endpoints

---

## 🎛️ UI/UX Enhancements

### Filter Bar
**Location:** Top of dashboard

**Displays:**
- Active Filters: Date range, Country, ASN
- "Reset All Filters" button (blue, always visible)

**Features:**
- Updates in real-time as filters change
- Clear visual feedback of active filters

---

### Button System

| Button | Location | Appearance | Action |
|--------|----------|------------|--------|
| **Go Back (n)** | Next to Date Chart title | Purple, shows count | Undo date range brush |
| **Reset All Filters** | Filter bar (top) | Blue | Clear all filters & history |
| **Restore All Countries** | Country or Volatile Chart title | Purple | Clear country filter |
| **Restore All ASNs** | ASN Chart title | Purple | Clear ASN filter |

**Button Styling:**
```css
background-color: #7c4dff;  /* Purple */
padding: 5px 12px;
border-radius: 4px;
font-size: 12px;
transition: all 0.2s ease;
box-shadow: 0 1px 3px rgba(0,0,0,0.12);
```

**Hover effect:** Darker purple, scale(1.05), enhanced shadow

---

### Chart Subtitles
Consistent interaction instructions across all charts:

- **Date Chart:** `Brush to zoom (disabled when ≤ 2 dates)`
- **Multi-line Charts:** `Hover legend to highlight | Left-click to filter | Right-click to cross out`

---

## 📁 File Structure

### Frontend Files
```
dashboard-modular.html         # Main HTML with all charts
config.js                      # State management, URL handling, filter functions
chart-renderers.js             # D3 rendering functions (single & multi-line)
chart1-total.js               # Date chart with brushing
chart2-countries.js           # Country chart with interactions
chart3-volatile.js            # Volatile countries chart
chart4-ips.js                 # IP addresses chart
chart5-usernames.js           # Usernames chart
chart6-asn.js                 # ASN organizations chart
```

### Backend Files
```
api_summary_only.py           # Flask API with all endpoints
attack_data.db                # DuckDB database
rebuild_username_with_country_FIXED.py  # Rebuild username table
create_asn_table_with_country.py        # Rebuild ASN table
```

### Data Tables
```sql
daily_stats                   # Aggregated daily totals
daily_country_attacks         # Country × Date × Attacks
daily_ip_attacks             # IP × Date × Country × ASN × Attacks
daily_username_attacks       # Username × Date × Country × Attacks
daily_asn_attacks           # ASN × Date × Country × Attacks
```

---

## 🔗 Data Relationships

### Entity Hierarchy
```
Time (Date)
  └─ Country (Geographic Location)
      └─ ASN (Network Operator)
          └─ IP Address (Specific Machine)
              └─ Username (Credential Attempt)
```

### Filtering Cascade
```
Select Country → Filters: ASN, IP, Username (shows only from that country)
Select ASN → Filters: IP, Username (shows only from that ASN)
            → Keeps: Country, Volatile (ASNs operate globally)
```

### Database Joins
```
IP Address: 61.177.173.49
  ├─ ASN: CHINANET-BACKBONE (IP belongs to ASN)
  ├─ Country: China (IP geolocated to country)
  └─ Username: root (credential attempted from this IP)
```

**Key Insight:** ASNs own IP blocks, IPs are geolocated to countries. ASNs can have IPs in multiple countries (e.g., CHINANET mostly in China, but may have IPs elsewhere for data centers/peering).

---

## 🎯 User Workflows

### Workflow 1: Explore Geographic Patterns
1. View Country Chart → See United States dominates
2. Right-click United States → Hide to focus on others
3. China becomes more visible
4. Click China → Filter all charts to China
5. See top Chinese ASNs, IPs, usernames

### Workflow 2: Investigate Time Patterns
1. Notice spike on Dec 3 in Date Chart
2. Brush around Dec 1-5 to zoom in
3. See which countries caused the spike in Country Chart
4. Click volatile country (e.g., Sri Lanka) to investigate

### Workflow 3: Drill Down by Network
1. View ASN Chart → See CHINANET-BACKBONE is top attacker
2. Click CHINANET → Filter to this network
3. Country Chart shows CHINANET operates in China, Singapore, etc.
4. IP Chart shows specific CHINANET machines attacking
5. Username Chart shows what credentials they're trying

### Workflow 4: Undo Exploration
1. Brush multiple times to zoom in
2. Click "Go Back (3)" to undo brushes one by one
3. Click "Reset All Filters" to start over
4. All charts return to initial state

---

## 📊 Performance Metrics

### Data Scale
- **Total attacks:** 213,101,672
- **Date range:** 69 days (Nov 1, 2022 - Jan 8, 2023)
- **Unique IPs:** ~45,000
- **Unique countries:** ~180
- **Unique ASNs:** ~5,273
- **Unique usernames:** ~45,678

### Database Size
- **daily_stats:** ~69 rows
- **daily_country_attacks:** ~12,000 rows
- **daily_ip_attacks:** ~3.1M rows
- **daily_username_attacks:** ~1.2M rows (with country)
- **daily_asn_attacks:** ~980K rows (with country)

### Query Performance
- **API response time:** <500ms for most queries
- **Chart rendering:** <300ms with D3.js transitions
- **Zero-filling queries:** ~200-400ms (generates date grid)

---

## 🚀 Deployment Notes

### Prerequisites
- Python 3.8+
- Flask
- DuckDB
- D3.js v7 (loaded via CDN)

### Setup
```bash
# Install dependencies
pip install flask duckdb

# Build database tables
python3 rebuild_username_with_country_FIXED.py
python3 create_asn_table_with_country.py

# Start API server
python3 api_summary_only.py

# Open dashboard
# Navigate to localhost:5000 in browser
```

### Configuration
- **Chart width:** `CHART_WIDTH = 2200` in `config.js`
- **Chart height:** `CHART_HEIGHT = 370` in `config.js`
- **API base URL:** `API_BASE = 'http://localhost:5000/api'` in `config.js`
- **Default date range:** Nov 1, 2022 - Jan 8, 2023

---

## 🎓 Key Learnings

### D3.js Insights
1. **`.ticks(n)` is a suggestion** - Use `.tickValues([...])` for exact control
2. **Date parsing matters** - Local vs UTC can cause off-by-one errors
3. **CROSS JOIN for zero-filling** - Essential for continuous lines
4. **`.datum()` vs `.data()`** - Use `.datum()` for single line, `.data()` for points
5. **Event handling** - Separate line events from dot events for better UX

### SQL Optimization
1. **CTEs for readability** - WITH clauses make complex queries maintainable
2. **COALESCE for zero-fill** - `COALESCE(d.attacks, 0)` fills missing data
3. **Date filtering in CTEs** - Filter before aggregation for performance
4. **LEFT JOIN for completeness** - Ensures all dates appear even with 0 attacks

### UX Principles
1. **Progressive disclosure** - Show details on hover, commit on click
2. **Undo capability** - Go Back button prevents dead ends
3. **Visual feedback** - Button state, hover effects, transitions
4. **Consistent interactions** - Same gestures across all charts
5. **Contextual controls** - Buttons appear near relevant charts

---

## 📝 Development Timeline

### Phase 1: Foundation (Completed)
- ✅ Basic chart rendering
- ✅ API endpoint creation
- ✅ Database schema

### Phase 2: Interactivity (Completed)
- ✅ Date range brushing with history
- ✅ Country chart filtering
- ✅ Volatile chart filtering
- ✅ ASN chart filtering
- ✅ Right-click to hide/cross out

### Phase 3: Polish (Completed)
- ✅ Zero-filling for continuous lines
- ✅ Visual improvements (fonts, colors, layout)
- ✅ Button styling and placement
- ✅ Y-axis rounding and formatting
- ✅ Chart reordering (logical hierarchy)

### Phase 4: Data Enhancement (Completed)
- ✅ Rebuild username table with country
- ✅ Rebuild ASN table with country
- ✅ Update all API endpoints for filtering

### Phase 5: Future (Potential)
- ⏳ IP chart interactivity
- ⏳ Username chart interactivity
- ⏳ Export functionality
- ⏳ Real-time updates

---

## 🙏 Credits

**Dashboard Design & Development:** Collaborative effort
**Data Source:** SSH honeypot logs (Nov 1, 2022 - Jan 8, 2023)
**Technologies:**
- D3.js v7 - Data visualization
- Flask - API backend
- DuckDB - Analytics database
- Python 3 - Data processing

---

**Last Updated:** January 21, 2026
**Version:** 2.0
**Status:** Feature-complete
