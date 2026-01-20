# Step 2: DuckDB Setup - Quick Guide

## 🎯 Goal
Set up DuckDB for lightning-fast analytical queries on your 213M attack records.

## 📥 What You Got
1. **02_setup_duckdb.py** - Main setup script
2. **example_queries.py** - Demo queries to see the speed

## 🚀 Run It

```bash
python 02_setup_duckdb.py
```

## ⏱️ What Happens (Takes ~5-10 minutes)

1. **Creates DuckDB database** 
   - Connects to your Parquet files
   - Creates a view over all 213M rows

2. **Tests query performance**
   - Runs sample queries
   - Shows you the speed (milliseconds!)

3. **Creates pre-aggregated tables**
   - `daily_stats` - Attacks per day
   - `country_stats` - Attacks per country  
   - `top_ips` - Top 10,000 attacking IPs
   - `username_stats` - Top 10,000 usernames
   - `hourly_patterns` - 24-hour attack patterns

4. **Shows summary**
   - Total attacks
   - Date ranges
   - Top countries

## 💡 Why This Works

**DuckDB is perfect for analytics because:**
- Reads Parquet files directly (no import needed)
- Columnar execution (only reads needed columns)
- Parallel processing (uses all CPU cores)
- Pre-aggregated tables = instant results

## 🧪 Test It

After setup completes, run:

```bash
python example_queries.py
```

This demonstrates 10 different analytical queries that run in **<1 second** each on 213M rows!

## 📊 What You Can Query

After setup, you'll have:

**Main View:**
- `attacks` - All 213M rows with full details

**Summary Tables (pre-computed):**
- `daily_stats` - Daily attack counts and unique IPs
- `country_stats` - Per-country statistics
- `top_ips` - Top attacking IPs with details
- `username_stats` - Most common usernames
- `hourly_patterns` - Hourly attack distribution

## 🎨 Next Step

After DuckDB setup, we'll create:
- **Step 3**: Visualization generation scripts
- Generate 6-12 charts in under 1 second
- Interactive dashboards

## 💾 Database Location

Your DuckDB database will be saved at:
```
./attack_data.db
```

This is a single file (~few hundred MB) that contains:
- Views over Parquet files
- Pre-aggregated summary tables
- Query indexes and metadata

---

**Ready? Run:** `python 02_setup_duckdb.py`
