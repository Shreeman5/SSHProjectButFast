"""
Build per-IP username vectors for username-overlap similarity between IPs.

Creates three tables used by utils/username_similarity.py:

    username_idf        (username, ip_count, idf)
    ip_username_tfidf   (ip, username, weight)
    ip_username_norm    (ip, norm, n_usernames)

HOW THE SCORE WORKS
-------------------
Each IP becomes a vector over usernames. The weight of username u for IP i is

    weight(i, u) = tf(i, u) * idf(u)
    tf(i, u)     = ln(1 + attacks by IP i on username u)
    idf(u)       = ln(N / number of IPs that tried u)       N = total IPs

and the similarity of two IPs is the cosine of their vectors (0 to 1).

  * tf is logged so that hammering one username a million times does not
    swamp the rest of the IP's username list: what matters is WHICH usernames
    an IP tries, with volume as a secondary signal.
  * idf makes common usernames nearly worthless and rare ones decisive. A
    username tried by every IP gets idf = 0 and is dropped; `root` and `admin`
    end up close to it. Two IPs sharing only `root` therefore score ~0, while
    two IPs that both try the same handful of unusual usernames score high.

Uses all dates in daily_ip_username_attacks. Re-run whenever that table changes.

MEMORY: the (IP, username) matrix is large (~19M pairs on the full data), so
DuckDB is capped at --memory-limit and spills to a temp folder on disk beyond
it, instead of claiming most of the machine's RAM. Lower the limit if the
computer still struggles; it only makes the run slower.

USAGE (stop Flask first -- DuckDB allows only one writer):
    python summary_tables_code/create_ip_username_vectors.py
    python summary_tables_code/create_ip_username_vectors.py --memory-limit 1GB --threads 1
    python summary_tables_code/create_ip_username_vectors.py path/to/other.db
"""

import argparse
import os
import shutil
import time
import duckdb


def parse_args():
    ap = argparse.ArgumentParser(description='Build per-IP username vectors.')
    ap.add_argument('db_path', nargs='?', default='attack_data.db')
    ap.add_argument('--memory-limit', default='2GB',
                    help="DuckDB memory cap, e.g. 1GB, 2GB, 4GB (default 2GB)")
    ap.add_argument('--threads', type=int, default=2,
                    help="worker threads; each holds its own buffers (default 2)")
    return ap.parse_args()


def main():
    args = parse_args()
    t0 = time.time()
    spill_dir = os.path.join(os.path.dirname(os.path.abspath(args.db_path)), '.duckdb_spill')
    os.makedirs(spill_dir, exist_ok=True)

    con = duckdb.connect(args.db_path)
    con.execute(f"SET memory_limit = '{args.memory_limit}'")
    con.execute(f"SET threads = {int(args.threads)}")
    con.execute(f"SET temp_directory = '{spill_dir}'")
    con.execute("SET preserve_insertion_order = false")  # lets large inserts stream
    print(f"Building username vectors in {args.db_path} "
          f"(memory limit {args.memory_limit}, {args.threads} threads, spilling to {spill_dir})")

    print("  1/4 Summing attacks per (IP, username)...")
    # A regular table, not TEMP: temp tables live in memory.
    con.execute("""
        CREATE OR REPLACE TABLE ip_username_counts AS
        SELECT IP AS ip, username, SUM(attacks) AS attacks
        FROM daily_ip_username_attacks
        GROUP BY IP, username
    """)
    n_ips = con.execute("SELECT COUNT(DISTINCT ip) FROM ip_username_counts").fetchone()[0]
    n_pairs = con.execute("SELECT COUNT(*) FROM ip_username_counts").fetchone()[0]
    print(f"      {n_ips:,} IPs, {n_pairs:,} (IP, username) pairs")

    print("  2/4 Computing IDF per username...")
    con.execute(f"""
        CREATE OR REPLACE TABLE username_idf AS
        SELECT username,
               COUNT(*) AS ip_count,
               LN(CAST({n_ips} AS DOUBLE) / COUNT(*)) AS idf
        FROM ip_username_counts
        GROUP BY username
    """)

    print("  3/4 Computing TF-IDF weights...")
    # No ORDER BY and no index here: on ~19M rows both need memory that cannot
    # spill to disk, and a plain scan of this table is fast enough per request.
    con.execute("""
        CREATE OR REPLACE TABLE ip_username_tfidf AS
        SELECT c.ip, c.username, LN(1 + c.attacks) * i.idf AS weight
        FROM ip_username_counts c
        JOIN username_idf i USING (username)
        WHERE i.idf > 0
    """)
    con.execute("DROP TABLE ip_username_counts")

    print("  4/4 Computing vector norms...")
    con.execute("""
        CREATE OR REPLACE TABLE ip_username_norm AS
        SELECT ip, SQRT(SUM(weight * weight)) AS norm, COUNT(*) AS n_usernames
        FROM ip_username_tfidf
        GROUP BY ip
    """)

    # A few reference points, useful when describing the weighting in a paper.
    print("\nMost common usernames (lowest weight):")
    for u, n, idf in con.execute("""
        SELECT username, ip_count, idf FROM username_idf ORDER BY ip_count DESC LIMIT 5
    """).fetchall():
        print(f"    {u!r:20} tried by {n:>9,} IPs ({100 * n / n_ips:5.1f}%)  idf {idf:.3f}")

    kept = con.execute("SELECT COUNT(*) FROM ip_username_tfidf").fetchone()[0]
    con.execute("CHECKPOINT")
    con.close()
    shutil.rmtree(spill_dir, ignore_errors=True)
    print(f"\nDone in {time.time() - t0:.1f}s: {kept:,} weighted (IP, username) pairs "
          f"({n_pairs - kept:,} dropped as tried by every IP).")


if __name__ == '__main__':
    main()