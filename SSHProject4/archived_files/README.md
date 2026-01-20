# Attack Data Analysis Pipeline

Convert 23GB of CSV attack logs to fast Parquet format with IP enrichment for sub-second visualizations.

## 🎯 Goal

Transform your current setup from **30-120 seconds** to **<1 second** for generating 6-12 visualizations, and scale to billions of records.

## 📋 Prerequisites

- **Python 3.10+**
- **~30GB free disk space** (for temporary processing + output)
- Your data:
  - 1 JSON file (~18MB) with IP geolocation/ASN info
  - 69 CSV files (~23GB total) with attack logs

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `pandas` - Data processing
- `pyarrow` - Parquet format support
- `duckdb` - Fast analytical queries
- `tqdm` - Progress bars

### Step 2: Validate Your Setup

Run the validation script to check your files:

```bash
python 00_validate_setup.py
```

This will:
- ✅ Check if your JSON and CSV files exist
- 📊 Show data previews
- ⏱️ Estimate conversion time
- 🧪 Optionally test on 10,000 rows

### Step 3: Configure Paths

Edit `config.ini` with your actual file paths:

```ini
[paths]
json_file = /home/username/data/ip_lookup.json
csv_directory = /home/username/data/csv_files/
output_directory = /home/username/data/parquet_output
duckdb_path = /home/username/data/attacks.db

[processing]
chunk_size = 100000
compression = snappy
```

### Step 4: Convert to Parquet

Run the conversion:

```bash
python convert_to_parquet_v2.py
```

Expected time: **~15-20 minutes** for 23GB of CSV data

What happens:
1. Loads your 18MB JSON with IP lookup data
2. Processes each CSV in 100K row chunks (memory efficient)
3. Enriches each row with geolocation and ASN data
4. Writes partitioned Parquet files by year/month
5. Compresses data (expect ~3-4GB output vs 23GB input)

### Step 5: Set Up DuckDB (Coming Next)

After conversion completes, you'll run:

```bash
python 02_setup_duckdb.py
```

This creates a DuckDB database that can query your data in **milliseconds**.

## 📁 Project Structure

```
.
├── requirements.txt           # Python dependencies
├── config.ini                # Configuration file (EDIT THIS)
├── 00_validate_setup.py      # Validates your data
├── convert_to_parquet_v2.py  # Main conversion script
├── 02_setup_duckdb.py        # DuckDB setup (next step)
├── 03_create_visualizations.py  # Fast viz generation (coming)
└── README.md                 # This file
```

## 📊 Data Flow

```
Input:
  ├── ip_data.json (18MB)
  │   └── IP → {country, lat/lng, ASN, org, ...}
  └── attack_logs/*.csv (23GB, 69 files)
      └── IP, Date, Time, Username, Port, ...

      ↓ CONVERSION (15-20 min)

Output:
  └── parquet_output/
      ├── year=2022/
      │   ├── month=11/
      │   │   └── data_*.parquet
      │   └── month=12/
      └── year=2023/
          └── month=01/

      ↓ QUERY WITH DUCKDB (<1 second)

Visualizations:
  ├── Attacks by country (map)
  ├── Timeline of attacks
  ├── Top attacking IPs
  ├── Username distribution
  └── ... (6-12 total)
```

## 🔍 What Gets Created

### Parquet File Structure

Each row in the output Parquet files contains:

**Original CSV columns:**
- `datetime` - Combined date/time
- `IP` - Attacker IP
- `Node` - Your server node
- `Port` - Attack port
- `PID` - Process ID
- `Username` - Attempted username
- `Tag` - Attack classification
- `Message` - Full log message

**Enriched columns from JSON:**
- `continent` - Continent name
- `country_code` - 2-letter country code
- `country` - Country name
- `latitude` - Geographic latitude
- `longitude` - Geographic longitude
- `asn` - ASN number (e.g., "AS139195")
- `asn_name` - Organization name
- `asn_domain` - Organization domain
- `asn_type` - Type (isp, hosting, etc.)

### Partitioning

Data is automatically partitioned by year and month:
- Enables fast filtering (e.g., "attacks in Jan 2023")
- Smaller files = faster queries
- Only reads relevant partitions

## 💡 Performance Benefits

| Metric | Before (CSV) | After (Parquet + DuckDB) |
|--------|--------------|-------------------------|
| File Size | 23 GB | ~3-4 GB (85% reduction) |
| Query Time | 30-120 sec | <1 second (100x faster) |
| Memory Usage | High (loads all CSVs) | Low (columnar format) |
| Visualization Time | Minutes | Milliseconds |

## 🛠️ Troubleshooting

### "Memory Error"
- Reduce `chunk_size` in config.ini (try 50000 or 25000)
- Close other applications

### "File Not Found"
- Double-check paths in config.ini
- Use absolute paths (e.g., `/home/user/data/` not `~/data/`)
- Ensure no typos

### "Conversion is Slow"
- Normal for first run (15-20 min for 23GB)
- Future incremental updates will be fast
- SSD will be faster than HDD

### "Invalid JSON"
- Ensure your JSON is valid
- Run validation script first: `python 00_validate_setup.py`

## 📈 Scaling to Billions of Records

When you reach 100M+ records:

1. **Switch to ClickHouse** (distributed columnar database)
2. **Use streaming ingestion** (Apache Kafka)
3. **Pre-aggregate more** (hourly, daily summaries)
4. **Implement caching** (Redis for hot data)

But for now, Parquet + DuckDB will handle up to 100M records blazingly fast.

## 🎓 Next Steps After Conversion

1. **Create DuckDB database** - Fast analytical queries
2. **Build pre-aggregated tables** - Even faster visualizations
3. **Generate visualization scripts** - Auto-refresh dashboards
4. **Set up incremental updates** - Process only new CSVs

Stay tuned for the next scripts!

## 📞 Support

If you encounter issues:
1. Run `python 00_validate_setup.py` to diagnose
2. Check file paths in config.ini
3. Ensure sufficient disk space (~30GB free)
4. Verify Python version: `python --version` (need 3.10+)

---

**Current Status:** ✅ Ready for Step 4 (Conversion)
**Next:** 🔜 DuckDB Setup (coming after conversion)
