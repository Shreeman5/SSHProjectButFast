"""
Country Summary Endpoint
Returns comprehensive data for all countries with discovery metrics
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_country_summary(app):
    """Register country summary endpoint for discovery tables"""
    
    @app.route('/api/country_summary', methods=['GET'])
    def get_country_summary():
        """Get comprehensive summary data for all countries"""
        start, end = parse_date_params()
        limit = request.args.get('limit', type=int, default=None)
        offset = request.args.get('offset', type=int, default=0)
        
        conn = get_db()
        
        query = f"""
            WITH date_range AS (
                -- Generate all dates in the range
                SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
            ),
            country_list AS (
                -- Get all unique countries
                SELECT DISTINCT country
                FROM daily_country_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND country != 'Unknown'
            ),
            complete_grid AS (
                -- Create complete date x country grid
                SELECT d.date, c.country
                FROM date_range d
                CROSS JOIN country_list c
            ),
            daily_data AS (
                -- Join with actual data, filling missing days with 0
                SELECT 
                    g.date,
                    g.country,
                    COALESCE(d.attacks, 0) as attacks,
                    CASE WHEN d.attacks IS NOT NULL THEN 1 ELSE 0 END as was_present
                FROM complete_grid g
                LEFT JOIN daily_country_attacks d 
                    ON g.date = d.date AND g.country = d.country
            ),
            country_stats AS (
                SELECT 
                    country,
                    SUM(attacks) as total_attacks,
                    AVG(CASE WHEN was_present = 1 THEN attacks ELSE NULL END) as avg_daily,
                    SUM(was_present) as active_days,
                    MIN(CASE WHEN was_present = 1 THEN date ELSE NULL END) as first_seen,
                    MAX(CASE WHEN was_present = 1 THEN date ELSE NULL END) as last_seen,
                    MAX(attacks) as max_daily
                FROM daily_data
                GROUP BY country
            ),
            day_over_day AS (
                -- Calculate day-over-day changes for volatility metrics
                SELECT 
                    country,
                    date,
                    attacks,
                    attacks - LAG(attacks) OVER (PARTITION BY country ORDER BY date) as absolute_change,
                    CASE 
                        WHEN LAG(attacks) OVER (PARTITION BY country ORDER BY date) = 0 
                        THEN (attacks - 1.0) / 1.0 * 100  -- Use 1 as denominator when previous day was 0
                        ELSE (attacks - LAG(attacks) OVER (PARTITION BY country ORDER BY date)) 
                             / LAG(attacks) OVER (PARTITION BY country ORDER BY date) * 100
                    END as pct_change
                FROM daily_data
            ),
            volatility_metrics AS (
                SELECT 
                    country,
                    MAX(absolute_change) as max_absolute_change,
                    MAX(pct_change) as max_pct_change
                FROM day_over_day
                WHERE absolute_change IS NOT NULL  -- Skip first day which has no previous day
                GROUP BY country
            ),
            last_7_days AS (
                -- Calculate attacks in last 7 days
                SELECT 
                    country,
                    SUM(attacks) as recent_attacks
                FROM daily_data
                WHERE date > (SELECT MAX(date) FROM daily_data) - INTERVAL 7 DAY
                GROUP BY country
            ),
            unique_asns_by_country AS (
                -- Count unique ASNs per country
                SELECT 
                    country,
                    COUNT(DISTINCT asn_name) as unique_asns
                FROM daily_asn_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND country != 'Unknown'
                GROUP BY country
            ),
            unique_ips_by_country AS (
                -- Count unique IPs per country
                SELECT 
                    country,
                    COUNT(DISTINCT ip) as unique_ips
                FROM daily_ip_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND country != 'Unknown'
                GROUP BY country
            ),
            unique_usernames_by_country AS (
                -- Count unique usernames per country
                SELECT 
                    country,
                    COUNT(DISTINCT username) as unique_usernames
                FROM daily_ip_username_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND country != 'Unknown'
                GROUP BY country
            ),
            asn_concentration_by_country AS (
                -- Get top 3 ASNs per country with percentages and structured data
                SELECT 
                    country,
                    STRING_AGG(
                        asn_name || ' (' || ROUND((asn_attacks::FLOAT / country_total * 100), 1) || '%)',
                        '|||'
                        ORDER BY asn_attacks DESC
                    ) as asn_concentration,
                    MAX(CASE WHEN rn = 1 THEN ROUND((asn_attacks::FLOAT / country_total * 100), 1) ELSE 0 END) as asn_top1_pct,
                    STRING_AGG(
                        '{{"name":"' || asn_name || '","pct":' || ROUND((asn_attacks::FLOAT / country_total * 100), 1) || '}}',
                        ','
                        ORDER BY asn_attacks DESC
                    ) as asn_top3_json
                FROM (
                    SELECT 
                        da.country,
                        da.asn_name,
                        SUM(da.attacks) as asn_attacks,
                        SUM(SUM(da.attacks)) OVER (PARTITION BY da.country) as country_total,
                        ROW_NUMBER() OVER (PARTITION BY da.country ORDER BY SUM(da.attacks) DESC) as rn
                    FROM daily_asn_attacks da
                    WHERE da.date BETWEEN '{start}' AND '{end}'
                      AND da.country != 'Unknown'
                    GROUP BY da.country, da.asn_name
                ) ranked
                WHERE rn <= 3
                GROUP BY country
            ),
            ip_concentration_by_country AS (
                -- Get top 3 IPs per country with percentages and structured data
                SELECT 
                    country,
                    STRING_AGG(
                        ip || ' (' || ROUND((ip_attacks::FLOAT / country_total * 100), 1) || '%)',
                        ', '
                        ORDER BY ip_attacks DESC
                    ) as ip_concentration,
                    MAX(CASE WHEN rn = 1 THEN ROUND((ip_attacks::FLOAT / country_total * 100), 1) ELSE 0 END) as ip_top1_pct,
                    STRING_AGG(
                        '{{"name":"' || ip || '","pct":' || ROUND((ip_attacks::FLOAT / country_total * 100), 1) || '}}',
                        ','
                        ORDER BY ip_attacks DESC
                    ) as ip_top3_json
                FROM (
                    SELECT 
                        di.country,
                        di.ip,
                        SUM(di.attacks) as ip_attacks,
                        SUM(SUM(di.attacks)) OVER (PARTITION BY di.country) as country_total,
                        ROW_NUMBER() OVER (PARTITION BY di.country ORDER BY SUM(di.attacks) DESC) as rn
                    FROM daily_ip_attacks di
                    WHERE di.date BETWEEN '{start}' AND '{end}'
                      AND di.country != 'Unknown'
                    GROUP BY di.country, di.ip
                ) ranked
                WHERE rn <= 3
                GROUP BY country
            ),
            username_concentration_by_country AS (
                -- Get top 3 usernames per country with percentages and structured data
                SELECT 
                    country,
                    STRING_AGG(
                        username || ' (' || ROUND((username_attacks::FLOAT / country_total * 100), 1) || '%)',
                        ', '
                        ORDER BY username_attacks DESC
                    ) as username_concentration,
                    MAX(CASE WHEN rn = 1 THEN ROUND((username_attacks::FLOAT / country_total * 100), 1) ELSE 0 END) as username_top1_pct,
                    STRING_AGG(
                        '{{"name":"' || username || '","pct":' || ROUND((username_attacks::FLOAT / country_total * 100), 1) || '}}',
                        ','
                        ORDER BY username_attacks DESC
                    ) as username_top3_json
                FROM (
                    SELECT 
                        diu.country,
                        diu.username,
                        SUM(diu.attacks) as username_attacks,
                        SUM(SUM(diu.attacks)) OVER (PARTITION BY diu.country) as country_total,
                        ROW_NUMBER() OVER (PARTITION BY diu.country ORDER BY SUM(diu.attacks) DESC) as rn
                    FROM daily_ip_username_attacks diu
                    WHERE diu.date BETWEEN '{start}' AND '{end}'
                      AND diu.country != 'Unknown'
                    GROUP BY diu.country, diu.username
                ) ranked
                WHERE rn <= 3
                GROUP BY country
            ),
            sparkline_data AS (
                -- Get attack counts at 7-day intervals for sparkline
                SELECT 
                    country,
                    STRING_AGG(
                        CAST(total_attacks AS VARCHAR),
                        ','
                        ORDER BY week_num
                    ) as sparkline_values
                FROM (
                    SELECT 
                        dd.country,
                        FLOOR((dd.date - DATE '{start}') / 7) as week_num,
                        SUM(dd.attacks) as total_attacks
                    FROM daily_data dd
                    GROUP BY dd.country, week_num
                ) intervals
                GROUP BY country
            ),
            total_days AS (
                -- Count total days in range
                SELECT COUNT(*) as total_day_count
                FROM date_range
            )
            SELECT 
                cs.country,
                cs.total_attacks,
                ROUND(cs.avg_daily, 2) as avg_daily,
                cs.first_seen::VARCHAR as first_seen,
                cs.last_seen::VARCHAR as last_seen,
                cs.max_daily,
                COALESCE(ROUND(vm.max_absolute_change, 2), 0) as max_absolute_change,
                COALESCE(ROUND(vm.max_pct_change, 2), 0) as max_pct_change,
                ROUND((cs.active_days::FLOAT / td.total_day_count) * 100, 1) as persistence_pct,
                COALESCE(l7.recent_attacks, 0) as recent_attacks,
                cs.active_days as active_days,
                COALESCE(ua.unique_asns, 0) as unique_asns,
                COALESCE(ui.unique_ips, 0) as unique_ips,
                COALESCE(uu.unique_usernames, 0) as unique_usernames,
                ac.asn_concentration,
                COALESCE(ac.asn_top1_pct, 0) as asn_top1_pct,
                ac.asn_top3_json,
                ic.ip_concentration,
                COALESCE(ic.ip_top1_pct, 0) as ip_top1_pct,
                ic.ip_top3_json,
                uc.username_concentration,
                COALESCE(uc.username_top1_pct, 0) as username_top1_pct,
                uc.username_top3_json,
                CASE WHEN cs.active_days > 0 THEN ROUND(COALESCE(ua.unique_asns, 0)::FLOAT / cs.active_days, 1) ELSE 0 END as asn_rotation,
                CASE WHEN cs.active_days > 0 THEN ROUND(COALESCE(ui.unique_ips, 0)::FLOAT / cs.active_days, 1) ELSE 0 END as ip_rotation,
                CASE WHEN cs.active_days > 0 THEN ROUND(COALESCE(uu.unique_usernames, 0)::FLOAT / cs.active_days, 1) ELSE 0 END as username_rotation,
                CASE WHEN cs.avg_daily > 0 THEN ROUND(cs.max_daily::FLOAT / cs.avg_daily, 1) ELSE 0 END as burst_intensity,
                sd.sparkline_values,
                CASE 
                    WHEN COALESCE(ui.unique_ips, 0) > 1000 AND COALESCE(uu.unique_usernames, 0) > 100 THEN 'High-Volume Spray'
                    WHEN COALESCE(ui.unique_ips, 0) < 50 AND COALESCE(uu.unique_usernames, 0) / NULLIF(cs.active_days, 0) > 10 THEN 'Targeted Brute Force'
                    WHEN COALESCE(ua.unique_asns, 0) > 20 AND COALESCE(ui.unique_ips, 0) > 500 THEN 'Distributed Botnet'
                    WHEN COALESCE(ua.unique_asns, 0) <= 2 AND COALESCE(ui.unique_ips, 0) < 20 THEN 'Single Source'
                    ELSE 'General Scanning'
                END as attack_profile,
                sm.asn_stability,
                sm.ip_stability,
                sm.username_stability,
                sm.peak_hours
            FROM country_stats cs
            CROSS JOIN total_days td
            LEFT JOIN volatility_metrics vm ON cs.country = vm.country
            LEFT JOIN last_7_days l7 ON cs.country = l7.country
            LEFT JOIN unique_asns_by_country ua ON cs.country = ua.country
            LEFT JOIN unique_ips_by_country ui ON cs.country = ui.country
            LEFT JOIN unique_usernames_by_country uu ON cs.country = uu.country
            LEFT JOIN asn_concentration_by_country ac ON cs.country = ac.country
            LEFT JOIN ip_concentration_by_country ic ON cs.country = ic.country
            LEFT JOIN username_concentration_by_country uc ON cs.country = uc.country
            LEFT JOIN sparkline_data sd ON cs.country = sd.country
            LEFT JOIN country_stability_metrics sm ON cs.country = sm.country
            ORDER BY cs.total_attacks DESC
            {f'LIMIT {limit}' if limit else ''}
            {f'OFFSET {offset}' if offset > 0 else ''}
        """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{
            'country': row[0],
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
            'unique_asns': row[11],
            'unique_ips': row[12],
            'unique_usernames': row[13],
            'asn_concentration': row[14],
            'asn_top1_pct': row[15],
            'asn_top3_json': row[16],
            'ip_concentration': row[17],
            'ip_top1_pct': row[18],
            'ip_top3_json': row[19],
            'username_concentration': row[20],
            'username_top1_pct': row[21],
            'username_top3_json': row[22],
            'asn_rotation': row[23],
            'ip_rotation': row[24],
            'username_rotation': row[25],
            'burst_intensity': row[26],
            'sparkline_values': row[27],
            'attack_profile': row[28],
            'asn_stability': round(row[29], 3) if row[29] is not None else None,
            'ip_stability': round(row[30], 3) if row[30] is not None else None,
            'username_stability': round(row[31], 3) if row[31] is not None else None,
            'peak_hours': row[32]
        } for row in result]
        
        return jsonify(data)