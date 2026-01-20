# Quick Start Guide - Attack Data Pipeline

## 🚀 Get Started in 3 Commands

```bash
# 1. Install dependencies
python setup.py

# 2. Edit config.ini with your paths
nano config.ini

# 3. Run conversion
python convert_to_parquet_v2.py
```

## 📝 What You Need to Edit

Open `config.ini` and update these lines:

```ini
json_file = /home/youruser/path/to/ip_data.json
csv_directory = /home/youruser/path/to/csv_files/
output_directory = /home/youruser/path/to/output/
```

Replace `/home/youruser/path/to/...` with your actual paths.

## ⏱️ Timeline

1. **Setup** (5 minutes)
   - Run `python setup.py`
   - Edit config.ini

2. **Validation** (1 minute)
   - Run `python 00_validate_setup.py`
   - Preview your data

3. **Conversion** (15-20 minutes)
   - Run `python convert_to_parquet_v2.py`
   - Watch the progress bar
   - Get coffee ☕

4. **Result**
   - 23GB CSV → 3-4GB Parquet
   - Data enriched with IP info
   - Ready for sub-second queries

## 🎯 What This Achieves

- **85% size reduction** (23GB → 3-4GB)
- **100x faster queries** (minutes → milliseconds)
- **IP enrichment** (country, ASN, org added to every row)
- **Partitioned data** (query only what you need)
- **Ready for visualization** (next step: DuckDB)

## 🆘 Troubleshooting

**Problem:** "File not found"
**Solution:** Check paths in config.ini, use absolute paths

**Problem:** "Memory error"
**Solution:** Reduce chunk_size in config.ini to 50000

**Problem:** "Takes too long"
**Solution:** This is normal for first run (15-20 min). Future updates will be fast.

## 📞 Questions?

Check the full README.md for detailed information.

---

**You are here:** Step 1 - Data Conversion
**Next:** Step 2 - DuckDB Setup (coming after conversion)
