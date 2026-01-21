# SSH Attack Data Visualization Dashboard

Real-time visualization dashboard for analyzing 213+ million SSH attack attempts across 69 days from honeypot servers.

## 📊 Overview

This system converts 26GB of CSV data into an interactive D3.js dashboard showing:
- Daily attack volumes with interactive brushing
- Geographic attack distribution (197 countries)
- Top attacking IPs, usernames, and ASNs
- Temporal patterns and trends

**Data Stats:**
- **Total Attacks:** 213,101,672
- **Time Period:** Nov 1, 2022 - Jan 8, 2023 (69 days)
- **Source Files:** 207 CSV files (3 servers: clem, wisc, utah)
- **Countries:** 197
- **Unique IPs:** 91,959

---

## 🏗️ Architecture

```
CSV Files (26GB)
    ↓
[IP Enrichment via ipinfo.json]
    ↓
Parquet Files (7.8GB, 2,229 files)
    ↓
DuckDB Database (summary tables)
    ↓
Flask API (REST endpoints)
    ↓
D3.js Dashboard (6 interactive charts)
```

### Data Flow

1. **CSV → Parquet Conversion** (`convert_to_parquet_FIXED.py`)
   - Reads CSVs in 100K row chunks
   - Enriches each row with geolocation data from `ipinfo.json`
   - Writes to partitioned Parquet files (year/month structure)
   - **Critical:** Preserves DataFrame index during enrichment

2. **Database Creation** (`02_setup_duckdb_NO_VIEW.py`)
   - Processes 2,229 Parquet files individually (avoids file limit issues)
   - Creates 5 pre-aggregated summary tables
   - No view creation (avoids opening all files at once)

3. **Country Table** (`create_country_file_by_file.py`)
   - Builds `daily_country_attacks` table for geographic charts
   - Processes files one-by-one to avoid memory issues
   - Aggregates duplicate date/country entries

4. **API Server** (`api_summary_only.py`)
   - Flask REST API serving 6 endpoints
   - Queries only pre-aggregated tables (fast!)
   - Supports date range filtering and country selection

5. **Dashboard** (`dashboard.html`)
   - Single-page D3.js application
   - 6 interactive charts with tooltips and click interactions
   - URL-based state management for filtering

---

## 📁 Project Structure

```
.
├── config.ini                          # Configuration (paths, settings)
├── ipinfo.json                         # IP geolocation lookup (91,959 IPs)
│
├── csv_files/                          # Source data (26GB)
│   ├── clem/                          # 69 CSV files
│   ├── wisc/                          # 69 CSV files
│   └── utah/                          # 69 CSV files
│
├── parquet_output/                     # Converted data (7.8GB)
│   ├── year=2022/month=11/            # ~501 files
│   ├── year=2022/month=12/            # ~1,387 files
│   └── year=2023/month=01/            # ~341 files
│
├── attack_data.db                      # DuckDB database (summary tables)
│
├── convert_to_parquet_FIXED.py        # Step 1: CSV → Parquet conversion
├── 02_setup_duckdb_NO_VIEW.py         # Step 2: Create database & summary tables
├── create_country_file_by_file.py     # Step 3: Create country table
├── api_summary_only.py                # Step 4: Flask API server
├── dashboard.html                     # Step 5: D3.js visualization
│
├── requirements.txt                    # Python dependencies
└── README.md                          # This file
```

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.8+
pip install -r requirements.txt

# Set file limit (required for database operations)
ulimit -n 4096
```

### Running the Dashboard

**If you already have the database built:**

```bash
# Start API server
ulimit -n 4096
python api_summary_only.py

# Open dashboard.html in browser
# Navigate to: http://127.0.0.1:5000 or open dashboard.html directly
```

---

## 🔧 Full Setup (From Scratch)

### Step 1: Convert CSVs to Parquet (~45 min)

```bash
python convert_to_parquet_FIXED.py
```

**What it does:**
- Loads 91,959 IP addresses from `ipinfo.json`
- Processes 207 CSV files in 100K row chunks
- Enriches each row with country, ASN, lat/lng
- Writes 2,229 partitioned Parquet files
- **Output:** `parquet_output/` directory (7.8GB)

**Key Fix:** Preserves DataFrame index during enrichment to avoid data duplication

---

### Step 2: Create Database (~15 min)

```bash
ulimit -n 4096
python 02_setup_duckdb_NO_VIEW.py
```

**What it does:**
- Processes 2,229 Parquet files one-by-one
- Creates 5 summary tables:
  - `daily_stats` - Daily attack totals
  - `country_stats` - Per-country aggregates
  - `top_ips` - Top 10K attacking IPs
  - `username_stats` - Top 10K attempted usernames
  - `hourly_patterns` - Attack patterns by hour
- **Output:** `attack_data.db` file

**No view creation** - API only needs summary tables, skipping view avoids "too many open files" errors

---

### Step 3: Create Country Table (~15 min)

```bash
python create_country_file_by_file.py
```

**What it does:**
- Builds `daily_country_attacks` table
- Processes files individually to avoid memory issues
- Aggregates data by (date, country)
- **Output:** 13,593 rows (69 days × ~197 countries)

---

### Step 4: Start API

```bash
ulimit -n 4096
python api_summary_only.py
```

**Endpoints:**
- `GET /api/total_attacks` - Daily totals
- `GET /api/country_attacks` - Country breakdown
- `GET /api/unusual_countries` - Volatile countries
- `GET /api/ip_attacks` - Top IPs
- `GET /api/username_attacks` - Top usernames
- `GET /api/asn_attacks` - Top ASNs

**Query Parameters:**
- `start` - Start date (YYYY-MM-DD)
- `end` - End date (YYYY-MM-DD)
- `country` - Filter by country

---

### Step 5: Open Dashboard

Open `dashboard.html` in a web browser.

**Features:**
- **Chart 1:** Total attacks timeline with brush-to-zoom
- **Chart 2:** Top 10 countries (click to filter)
- **Chart 3:** Volatile countries
- **Chart 4:** Top attacking IPs
- **Chart 5:** Most attempted usernames
- **Chart 6:** Top attacking ASNs

**Interactions:**
- Brush Chart 1 to zoom date range
- Click country lines to filter other charts
- Hover for tooltips with details

---

## 📊 Database Schema

### daily_stats
| Column | Type | Description |
|--------|------|-------------|
| date | DATE | Day of attacks |
| total_attacks | BIGINT | Total attacks that day |
| unique_ips | BIGINT | Unique IPs that day |
| unique_countries | BIGINT | Countries attacking |
| unique_usernames | BIGINT | Usernames attempted |

### country_stats
| Column | Type | Description |
|--------|------|-------------|
| country | VARCHAR | Country name |
| country_code | VARCHAR | ISO code (US, CN, etc) |
| continent | VARCHAR | Continent |
| total_attacks | BIGINT | Total attacks from country |
| unique_ips | BIGINT | Unique IPs from country |
| avg_latitude | DOUBLE | Average latitude |
| avg_longitude | DOUBLE | Average longitude |

### daily_country_attacks
| Column | Type | Description |
|--------|------|-------------|
| date | DATE | Day of attacks |
| country | VARCHAR | Country name |
| attacks | BIGINT | Attacks that day from country |

### top_ips
| Column | Type | Description |
|--------|------|-------------|
| IP | VARCHAR | IP address |
| country | VARCHAR | Source country |
| asn | VARCHAR | ASN number |
| asn_name | VARCHAR | ASN organization |
| attack_count | BIGINT | Total attacks |
| first_seen | TIMESTAMP | First attack |
| last_seen | TIMESTAMP | Last attack |

---

## 🐛 Common Issues & Solutions

### "Too many open files" error

**Problem:** DuckDB tries to open too many Parquet files simultaneously

**Solution:**
```bash
ulimit -n 4096  # Increase file limit before running scripts
```

### Dashboard shows flat lines for countries

**Problem:** Only first chunk per CSV was enriched (index mismatch bug)

**Solution:** Use `convert_to_parquet_FIXED.py` which preserves DataFrame index:
```python
enrichment_df = pd.DataFrame(ip_enrichment.tolist(), index=chunk.index)
```

### Memory issues during conversion

**Problem:** Processing too many files at once

**Solution:** All scripts now process files one-by-one to stay within memory limits

### Country data is NULL in Parquet files

**Problem:** Enrichment not being written to files

**Solution:** The index preservation fix in `convert_to_parquet_FIXED.py` solves this

---

## 📈 Performance

- **CSV → Parquet:** ~45 min (207 files, 213M rows)
- **Database Setup:** ~15 min (2,229 files)
- **Country Table:** ~15 min (2,229 files)
- **API Response Time:** <100ms (all endpoints)
- **Dashboard Load:** <1 second (6 charts)

**Why so fast?**
- Pre-aggregated summary tables (no raw data scans)
- DuckDB's columnar storage
- File-by-file processing (predictable memory usage)

---

## 🔍 Data Quality

**Enrichment Coverage:**
- IPs in lookup file: 91,959 (100% of unique IPs)
- Attacks with country data: 213,101,672 (100%)
- Countries identified: 197

**Top 5 Attack Sources:**
1. United States: 44,530,934 (20.9%)
2. China: 28,315,120 (13.3%)
3. Singapore: 13,887,671 (6.5%)
4. India: 12,868,517 (6.0%)
5. Russia: 11,945,417 (5.6%)

---

## 🛠️ Troubleshooting

### Verify Parquet Enrichment

```bash
python3 << 'EOF'
import duckdb
from pathlib import Path

conn = duckdb.connect(':memory:')
files = list(Path('./parquet_output').glob("**/data_*.parquet"))

for file in files[:3]:
    result = conn.execute(f"""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN country IS NOT NULL THEN 1 ELSE 0 END) as enriched
        FROM read_parquet('{file}')
    """).fetchone()
    pct = (result[1]/result[0]*100) if result[0] > 0 else 0
    print(f"{file.name}: {result[1]:,}/{result[0]:,} ({pct:.1f}%)")
EOF
```

### Check Database Tables

```bash
python3 << 'EOF'
import duckdb
conn = duckdb.connect('./attack_data.db', read_only=True)

tables = conn.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'main' AND table_type = 'BASE TABLE'
""").fetchall()

for table in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
    print(f"{table[0]}: {count:,} rows")
EOF
```

### Verify Country Data

```bash
python3 << 'EOF'
import duckdb
conn = duckdb.connect('./attack_data.db', read_only=True)

total = conn.execute("SELECT SUM(attacks) FROM daily_country_attacks").fetchone()[0]
expected = conn.execute("SELECT SUM(total_attacks) FROM daily_stats").fetchone()[0]

print(f"Country table total: {total:,}")
print(f"Expected total: {expected:,}")
print(f"Match: {'✅ YES' if abs(total - expected) < 1000 else '❌ NO'}")
EOF
```

---

## 📝 Notes

- **File Limit:** Always set `ulimit -n 4096` before running scripts
- **No View:** Database doesn't have `attacks` view - API only uses summary tables
- **Index Preservation:** Critical for enrichment - don't remove `index=chunk.index`
- **One File at a Time:** All scripts process files individually to avoid memory/file limit issues

---

## 🎯 Future Enhancements

Potential improvements:
- Consolidate Parquet files (2,229 → 3) to avoid file limit issues entirely
- Add geographic heatmap visualization
- Real-time streaming from live honeypots
- Machine learning for attack pattern detection
- Export functionality for reports

---

## 📜 License

This project analyzes honeypot attack data for research purposes.

---

## 🙏 Acknowledgments

- **Data Sources:** clem, wisc, utah honeypot servers
- **IP Enrichment:** ipinfo.json (91,959 IPs with geolocation)
- **Technologies:** DuckDB, Flask, D3.js, Pandas, PyArrow

---

**Built with:** Python 3.11, DuckDB 0.9.2, Flask 3.0.0, D3.js v7

**Last Updated:** January 2026
