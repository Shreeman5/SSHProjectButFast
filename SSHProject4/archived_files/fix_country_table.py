#!/usr/bin/env python3
"""
Fix daily_country_attacks - one-time consolidation.

THE BUG
    create_country_file_by_file.py loops over ~1000 parquet files and runs
    INSERT ... GROUP BY date, country once PER FILE. The GROUP BY only ever
    spans a single file, so a country appearing in 24 files produces 24 rows
    for the same day. Currently 263,584 rows for 11,012 real country-days,
    with one country-day spread across 96 rows.

WHY IT WENT UNNOTICED
    The script's own verification compares SUM(attacks) against daily_stats and
    reports "PERFECT MATCH". That check is blind to this bug: the partial sums
    add up to the correct total no matter how many rows they are split across.
    It validates the total and never the row count.

WHY SUM IS THE RIGHT FIX
    attacks is COUNT(*) per file, so the rows are partial counts, not repeated
    copies. Adding them is exactly right. And create_country_file_by_file.py
    unconditionally DROPs the table before its loop, so a double run cannot have
    left true duplicates behind.

WHAT IT FIXES
    - Chart 2 (Top 10 Attacking Countries) stops drawing a sawtooth
    - country_summary.py starts reporting correct Avg Daily / Max Daily /
      Max Absolute Delta / Max % Delta, with no code change: once there is one
      row per country-day, its AVG and MAX are per-day by construction
    - 263,584 rows collapse to ~11,012, so both get faster too

Run from the project root:  python3 fix_country_table.py
Takes a few seconds. Stop the API server first.
"""

import duckdb
import sys

DB_PATH = './attack_data.db'
TABLE = 'daily_country_attacks'


def main():
    print("=" * 72)
    print(f"CONSOLIDATE {TABLE}")
    print("=" * 72)

    conn = duckdb.connect(DB_PATH)

    # ---- before -------------------------------------------------------
    rows = conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
    pairs = conn.execute(
        f"SELECT COUNT(*) FROM (SELECT DISTINCT date, country FROM {TABLE})").fetchone()[0]
    total = conn.execute(f"SELECT SUM(attacks) FROM {TABLE}").fetchone()[0]
    worst = conn.execute(f"""
        SELECT MAX(n) FROM (SELECT COUNT(*) n FROM {TABLE} GROUP BY date, country)
    """).fetchone()[0]

    print(f"\nBefore")
    print(f"  rows                  : {rows:,}")
    print(f"  distinct country-days : {pairs:,}")
    print(f"  duplication ratio     : {rows / pairs:.2f}x")
    print(f"  worst country-day     : {worst} rows")
    print(f"  total attacks         : {total:,}")

    if rows == pairs:
        print("\nAlready consolidated. Nothing to do.")
        conn.close()
        return

    # ---- sanity: schema must be exactly the three known columns -------
    cols = [r[0] for r in conn.execute(f"DESCRIBE {TABLE}").fetchall()]
    if cols != ['date', 'country', 'attacks']:
        print(f"\nERROR: unexpected schema {cols}")
        print("Expected ['date', 'country', 'attacks']. If extra columns exist they")
        print("may be a real key (as in daily_asn_attacks, where asn/country make")
        print("multiple rows per asn_name legitimate). Aborting rather than")
        print("collapsing a dimension that matters.")
        conn.close()
        sys.exit(1)

    print(f"\nConsolidating...")
    conn.execute(f"DROP TABLE IF EXISTS {TABLE}__new")
    conn.execute(f"""
        CREATE TABLE {TABLE}__new AS
        SELECT date, country, SUM(attacks)::BIGINT AS attacks
        FROM {TABLE}
        GROUP BY date, country
    """)

    # ---- verify BEFORE destroying anything ----------------------------
    new_rows = conn.execute(f"SELECT COUNT(*) FROM {TABLE}__new").fetchone()[0]
    new_total = conn.execute(f"SELECT SUM(attacks) FROM {TABLE}__new").fetchone()[0]

    ok = (new_rows == pairs) and (new_total == total)
    print(f"  new rows              : {new_rows:,}   (expected {pairs:,})")
    print(f"  new total attacks     : {new_total:,}   (expected {total:,})")

    if not ok:
        print("\nERROR: verification failed. Original table untouched.")
        print(f"Inspect {TABLE}__new manually, or drop it.")
        conn.close()
        sys.exit(1)

    conn.execute(f"DROP TABLE {TABLE}")
    conn.execute(f"ALTER TABLE {TABLE}__new RENAME TO {TABLE}")
    print("  swapped in")

    # ---- after --------------------------------------------------------
    print(f"\nAfter")
    print(f"  rows                  : {new_rows:,}  ({rows / new_rows:.1f}x smaller)")
    print(f"  total attacks         : {new_total:,}  (unchanged)")

    print(f"\nSpot check - United States, first 5 days")
    for d, c, a in conn.execute(f"""
        SELECT date, country, attacks FROM {TABLE}
        WHERE country = 'United States' ORDER BY date LIMIT 5
    """).fetchall():
        print(f"  {d}  {a:>12,}")

    # cross-check against a table that was never affected
    try:
        ip_total = conn.execute("SELECT SUM(attacks) FROM daily_ip_attacks").fetchone()[0]
        print(f"\nCross-check")
        print(f"  daily_country_attacks : {new_total:,}")
        print(f"  daily_ip_attacks      : {ip_total:,}")
        diff = abs(new_total - ip_total)
        pct = diff / ip_total * 100 if ip_total else 0
        print(f"  difference            : {diff:,} ({pct:.2f}%)")
        if pct > 1:
            print("  note: some rows have no country attribution, so a small gap is normal")
    except Exception:
        pass

    conn.close()

    print("\n" + "=" * 72)
    print("Done. Restart the API and hard refresh.")
    print("Chart 2 should now draw one point per day per country.")
    print("The Countries discovery tab's Avg Daily / Max Daily are also now")
    print("correct - same class of correction as root going 840.96 -> 1.41M.")
    print("=" * 72)


if __name__ == "__main__":
    main()
