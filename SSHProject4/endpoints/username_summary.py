"""
Username Summary Endpoint
Returns comprehensive data for all usernames with discovery metrics + stability metrics
OPTIMIZED: Only processes the usernames that will be returned

--------------------------------------------------------------------------------
AGGREGATION NOTE -- READ BEFORE EDITING
--------------------------------------------------------------------------------
`daily_username_attacks` is keyed on (date, username, country, asn_name), NOT on
(date, username). A single username-day is split across many rows -- roughly 1,680
of them per day for 'root', which has 192 countries and 4,506 ASNs.

That makes any per-row aggregate over the raw table a FRAGMENT statistic, not a
daily one:

    AVG(attacks)  -> mean over country-ASN fragments, not over days
    MAX(attacks)  -> largest single fragment, not the busiest day
    LAG(attacks) OVER (PARTITION BY username ORDER BY date)
                  -> compares two fragments that are usually from the SAME date,
                     in arbitrary order, because date has ~1,680 ties

Everything below therefore rolls up to one row per (username, date) FIRST, in the
`username_daily` CTE, and every downstream metric reads from that.

Safe on the raw table: SUM(attacks), COUNT(DISTINCT date), COUNT(DISTINCT country),
MIN(date), MAX(date).
--------------------------------------------------------------------------------
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_username_summary(app):
    """Register username summary endpoint for discovery tables"""

    @app.route('/api/username_count', methods=['GET'])
    def get_username_count():
        """Get total count of unique usernames (for debugging)"""
        start, end = parse_date_params()

        conn = get_db()

        query = f"""
            SELECT COUNT(DISTINCT username) as total_usernames
            FROM daily_username_attacks
            WHERE date BETWEEN '{start}' AND '{end}'
        """

        result = conn.execute(query).fetchone()
        conn.close()

        total = result[0]
        print(f"[USERNAME_COUNT] Total unique usernames: {total:,}")

        return jsonify({
            'total_usernames': total,
            'date_range': {
                'start': start,
                'end': end
            }
        })

    @app.route('/api/username_summary', methods=['GET'])
    def get_username_summary():
        """Get comprehensive summary data for all usernames"""
        start, end = parse_date_params()
        limit = request.args.get('limit', type=int, default=1000)
        offset = request.args.get('offset', type=int, default=0)

        conn = get_db()

        # DEBUG: Get total count of unique usernames
        count_query = f"""
            SELECT COUNT(DISTINCT username) as total_usernames
            FROM daily_username_attacks
            WHERE date BETWEEN '{start}' AND '{end}'
        """
        total_count = conn.execute(count_query).fetchone()[0]
        print(f"[USERNAME_SUMMARY] Total unique usernames in dataset: {total_count:,}")
        print(f"[USERNAME_SUMMARY] Requested limit={limit}, offset={offset}")
        print(f"[USERNAME_SUMMARY] Will return usernames {offset + 1} to {offset + limit}")

        # Step 1: Get the top N usernames by total attacks
        # SUM is fragment-safe, so this ordering was already correct.
        top_query = f"""
            SELECT username
            FROM daily_username_attacks
            WHERE date BETWEEN '{start}' AND '{end}'
            GROUP BY username
            ORDER BY SUM(attacks) DESC
            LIMIT {limit}
            OFFSET {offset}
        """

        top_result = conn.execute(top_query).fetchall()
        print(f"[USERNAME_SUMMARY] Retrieved {len(top_result)} usernames from offset {offset}")

        if not top_result:
            conn.close()
            print(f"[USERNAME_SUMMARY] No usernames found at offset {offset}")
            return jsonify([])

        # Get list of usernames
        usernames = [row[0] for row in top_result]

        # Create placeholder string for parameterized query
        placeholders = ', '.join(['?' for _ in usernames])

        # Step 2: Calculate stats only for these usernames
        #
        # NOTE: this query now has TWO `username IN (...)` clauses, not four.
        # `username_daily` is the single entry point for all day-level metrics,
        # so day_over_day / last_7_days / sparkline_data all read from it rather
        # than re-scanning the raw table. See `params` below.
        stats_query = f"""
            WITH username_daily AS (
                -- Collapse country/ASN fragments into ONE row per username-day.
                -- Every day-level metric below depends on this.
                SELECT
                    username,
                    date,
                    SUM(attacks) as attacks
                FROM daily_username_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND username IN ({placeholders})
                GROUP BY username, date
            ),
            username_agg AS (
                -- Renamed from `username_stats` to avoid shadowing the real
                -- `username_stats` table that exists in the database.
                SELECT
                    username,
                    SUM(attacks) as total_attacks,
                    AVG(attacks) as avg_daily,
                    COUNT(DISTINCT date) as active_days,
                    MIN(date) as first_seen,
                    MAX(date) as last_seen,
                    MAX(attacks) as max_daily
                FROM username_daily
                GROUP BY username
            ),
            country_counts AS (
                -- Must read the RAW table: country is collapsed away above.
                SELECT
                    username,
                    COUNT(DISTINCT country) as country_count
                FROM daily_username_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND username IN ({placeholders})
                GROUP BY username
            ),
            day_over_day AS (
                -- LAG is only meaningful once `date` is unique per username.
                SELECT
                    username,
                    attacks - LAG(attacks) OVER (PARTITION BY username ORDER BY date) as absolute_change,
                    CASE
                        WHEN LAG(attacks) OVER (PARTITION BY username ORDER BY date) = 0
                        THEN (attacks - 1.0) / 1.0 * 100
                        ELSE (attacks - LAG(attacks) OVER (PARTITION BY username ORDER BY date))
                             / LAG(attacks) OVER (PARTITION BY username ORDER BY date) * 100
                    END as pct_change
                FROM username_daily
            ),
            volatility_metrics AS (
                SELECT
                    username,
                    MAX(absolute_change) as max_absolute_change,
                    MAX(pct_change) as max_pct_change
                FROM day_over_day
                WHERE absolute_change IS NOT NULL
                GROUP BY username
            ),
            last_7_days AS (
                SELECT
                    username,
                    SUM(attacks) as recent_attacks
                FROM username_daily
                WHERE date BETWEEN (DATE '{end}' - INTERVAL 6 DAY) AND DATE '{end}'
                GROUP BY username
            ),
            sparkline_data AS (
                -- Get attack counts at 7-day intervals for sparkline
                SELECT
                    username,
                    STRING_AGG(
                        CAST(total_attacks AS VARCHAR),
                        ','
                        ORDER BY week_num
                    ) as sparkline_values
                FROM (
                    SELECT
                        username,
                        FLOOR((date - DATE '{start}') / 7) as week_num,
                        SUM(attacks) as total_attacks
                    FROM username_daily
                    GROUP BY username, week_num
                ) intervals
                GROUP BY username
            )
            SELECT
                s.username,
                s.total_attacks,
                ROUND(s.avg_daily, 2) as avg_daily,
                s.first_seen::VARCHAR as first_seen,
                s.last_seen::VARCHAR as last_seen,
                s.max_daily,
                COALESCE(ROUND(vm.max_absolute_change, 2), 0) as max_absolute_change,
                COALESCE(ROUND(vm.max_pct_change, 2), 0) as max_pct_change,
                ROUND((s.active_days::FLOAT / 69.0) * 100, 1) as persistence_pct,
                COALESCE(l7.recent_attacks, 0) as recent_attacks,
                s.active_days,
                COALESCE(cc.country_count, 0) as country_count,
                CASE WHEN s.avg_daily > 0 THEN ROUND(s.max_daily::FLOAT / s.avg_daily, 1) ELSE 0 END as burst_intensity,
                sd.sparkline_values,

                -- Stability metrics from username_stability_metrics table
                sm.unique_countries,
                sm.unique_asns,
                sm.unique_ips,
                sm.country_concentration,
                sm.country_top1_pct,
                sm.asn_concentration,
                sm.asn_top1_pct,
                sm.ip_concentration,
                sm.ip_top1_pct,
                sm.country_stability,
                sm.asn_stability,
                sm.ip_stability,
                sm.country_rotation,
                sm.asn_rotation,
                sm.ip_rotation

            FROM username_agg s
            LEFT JOIN country_counts cc ON s.username = cc.username
            LEFT JOIN volatility_metrics vm ON s.username = vm.username
            LEFT JOIN last_7_days l7 ON s.username = l7.username
            LEFT JOIN sparkline_data sd ON s.username = sd.username
            LEFT JOIN username_stability_metrics sm ON s.username = sm.username
            ORDER BY s.total_attacks DESC
        """

        # Two IN clauses now: username_daily and country_counts.
        # (Was four. If you edit the CTEs, keep this count in sync.)
        params = usernames + usernames
        result = conn.execute(stats_query, params).fetchall()
        conn.close()

        print(f"[USERNAME_SUMMARY] Processed {len(result)} usernames successfully")
        print(f"[USERNAME_SUMMARY] Progress: {offset + len(result):,} / {total_count:,} ({((offset + len(result)) / total_count * 100):.1f}%)")

        data = [{
            'username': row[0],
            'total_attacks': row[1],
            'avg_daily': row[2],
            'first_seen': row[3],
            'last_seen': row[4],
            'max_daily': row[5],
            'max_absolute_change': row[6],
            'max_pct_change': row[7],
            'persistence_pct': row[8],
            'recent_attacks': row[9],
            'active_days': row[10],
            'countries': row[11],
            'burst_intensity': row[12],
            'sparkline_values': row[13],

            # Stability metrics (14 new fields)
            'unique_countries': row[14],
            'unique_asns': row[15],
            'unique_ips': row[16],
            'country_concentration': row[17],
            'country_top1_pct': round(row[18], 1) if row[18] is not None else None,
            'asn_concentration': row[19],
            'asn_top1_pct': round(row[20], 1) if row[20] is not None else None,
            'ip_concentration': row[21],
            'ip_top1_pct': round(row[22], 1) if row[22] is not None else None,
            'country_stability': round(row[23], 3) if row[23] is not None else None,
            'asn_stability': round(row[24], 3) if row[24] is not None else None,
            'ip_stability': round(row[25], 3) if row[25] is not None else None,
            'country_rotation': round(row[26], 1) if row[26] is not None else None,
            'asn_rotation': round(row[27], 1) if row[27] is not None else None,
            'ip_rotation': round(row[28], 1) if row[28] is not None else None
        } for row in result]

        return jsonify(data)