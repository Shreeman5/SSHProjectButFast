"""
ASN Summary Endpoint
Returns comprehensive data for all ASNs with discovery metrics + stability metrics
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_asn_summary(app):
    """Register ASN summary endpoint for discovery tables"""
    
    @app.route('/api/asn_summary', methods=['GET'])
    def get_asn_summary():
        """Get comprehensive summary data for all ASNs"""
        start, end = parse_date_params()
        limit = request.args.get('limit', type=int, default=None)
        offset = request.args.get('offset', type=int, default=0)
        
        conn = get_db()
        
        query = f"""
            WITH date_range AS (
                -- Generate all dates in the range
                SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
            ),
            asn_list AS (
                -- Get all unique ASNs
                SELECT DISTINCT asn_name
                FROM daily_asn_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
            ),
            complete_grid AS (
                -- Create complete date x ASN grid
                SELECT d.date, a.asn_name
                FROM date_range d
                CROSS JOIN asn_list a
            ),
            daily_data AS (
                -- Join with actual data, filling missing days with 0
                SELECT 
                    g.date,
                    g.asn_name,
                    COALESCE(d.attacks, 0) as attacks,
                    d.country,
                    CASE WHEN d.attacks IS NOT NULL THEN 1 ELSE 0 END as was_present
                FROM complete_grid g
                LEFT JOIN daily_asn_attacks d 
                    ON g.date = d.date AND g.asn_name = d.asn_name
            ),
            asn_stats AS (
                SELECT 
                    asn_name,
                    SUM(attacks) as total_attacks,
                    AVG(CASE WHEN was_present = 1 THEN attacks ELSE NULL END) as avg_daily,
                    COUNT(DISTINCT CASE WHEN was_present = 1 THEN date ELSE NULL END) as active_days,
                    MIN(CASE WHEN was_present = 1 THEN date ELSE NULL END) as first_seen,
                    MAX(CASE WHEN was_present = 1 THEN date ELSE NULL END) as last_seen,
                    MAX(attacks) as max_daily,
                    COUNT(DISTINCT country) as country_count
                FROM daily_data
                GROUP BY asn_name
            ),
            day_over_day AS (
                -- Calculate day-over-day changes for volatility metrics
                SELECT 
                    asn_name,
                    date,
                    attacks,
                    attacks - LAG(attacks) OVER (PARTITION BY asn_name ORDER BY date) as absolute_change,
                    CASE 
                        WHEN LAG(attacks) OVER (PARTITION BY asn_name ORDER BY date) = 0 
                        THEN (attacks - 1.0) / 1.0 * 100
                        ELSE (attacks - LAG(attacks) OVER (PARTITION BY asn_name ORDER BY date)) 
                             / LAG(attacks) OVER (PARTITION BY asn_name ORDER BY date) * 100
                    END as pct_change
                FROM daily_data
            ),
            volatility_metrics AS (
                SELECT 
                    asn_name,
                    MAX(absolute_change) as max_absolute_change,
                    MAX(pct_change) as max_pct_change
                FROM day_over_day
                WHERE absolute_change IS NOT NULL
                GROUP BY asn_name
            ),
            last_7_days AS (
                -- Calculate attacks in last 7 days
                SELECT 
                    asn_name,
                    SUM(attacks) as recent_attacks
                FROM daily_data
                WHERE date > (SELECT MAX(date) FROM daily_data) - INTERVAL 7 DAY
                GROUP BY asn_name
            ),
            sparkline_data AS (
                -- Get attack counts at 7-day intervals for sparkline
                SELECT 
                    asn_name,
                    STRING_AGG(
                        CAST(total_attacks AS VARCHAR),
                        ','
                        ORDER BY week_num
                    ) as sparkline_values
                FROM (
                    SELECT 
                        dd.asn_name,
                        FLOOR((dd.date - DATE '{start}') / 7) as week_num,
                        SUM(dd.attacks) as total_attacks
                    FROM daily_data dd
                    GROUP BY dd.asn_name, week_num
                ) intervals
                GROUP BY asn_name
            ),
            total_days AS (
                -- Count total days in range
                SELECT COUNT(*) as total_day_count
                FROM date_range
            )
            SELECT 
                s.asn_name,
                s.total_attacks,
                ROUND(s.avg_daily, 2) as avg_daily,
                s.first_seen::VARCHAR as first_seen,
                s.last_seen::VARCHAR as last_seen,
                s.max_daily,
                COALESCE(ROUND(vm.max_absolute_change, 2), 0) as max_absolute_change,
                COALESCE(ROUND(vm.max_pct_change, 2), 0) as max_pct_change,
                ROUND((s.active_days::FLOAT / td.total_day_count) * 100, 1) as persistence_pct,
                COALESCE(l7.recent_attacks, 0) as recent_attacks,
                s.active_days as active_days,
                CASE WHEN s.avg_daily > 0 THEN ROUND(s.max_daily::FLOAT / s.avg_daily, 1) ELSE 0 END as burst_intensity,
                sd.sparkline_values,
                
                -- Stability metrics from asn_stability_metrics table
                sm.unique_countries,
                sm.primary_country,
                sm.unique_ips,
                sm.unique_usernames,
                sm.country_concentration,
                sm.country_top1_pct,
                sm.ip_concentration,
                sm.ip_top1_pct,
                sm.username_concentration,
                sm.username_top1_pct,
                sm.country_rotation,
                sm.ip_rotation,
                sm.username_rotation,
                sm.country_stability,
                sm.ip_stability,
                sm.username_stability,
                sm.peak_hours,
                sm.peak_hour_1_pct,
                sm.peak_minutes,
                sm.peak_minute_1_pct,
                sm.peak_seconds,
                sm.peak_second_1_pct
                
            FROM asn_stats s
            CROSS JOIN total_days td
            LEFT JOIN volatility_metrics vm ON s.asn_name = vm.asn_name
            LEFT JOIN last_7_days l7 ON s.asn_name = l7.asn_name
            LEFT JOIN sparkline_data sd ON s.asn_name = sd.asn_name
            LEFT JOIN asn_stability_metrics sm ON s.asn_name = sm.asn_name
            ORDER BY s.total_attacks DESC
            {f'LIMIT {limit}' if limit else ''}
            {f'OFFSET {offset}' if offset > 0 else ''}
        """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{
            'asn_name': row[0],
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
            'burst_intensity': row[11],
            'sparkline_values': row[12],
            
            # Stability metrics (15 fields available, 3 peak time fields will be NULL)
            'unique_countries': row[13],
            'primary_country': row[14],
            'unique_ips': row[15],
            'unique_usernames': row[16],
            'country_concentration': row[17],
            'country_top1_pct': round(row[18], 1) if row[18] is not None else None,
            'ip_concentration': row[19],
            'ip_top1_pct': round(row[20], 1) if row[20] is not None else None,
            'username_concentration': row[21],
            'username_top1_pct': round(row[22], 1) if row[22] is not None else None,
            'country_rotation': round(row[23], 1) if row[23] is not None else None,
            'ip_rotation': round(row[24], 1) if row[24] is not None else None,
            'username_rotation': round(row[25], 1) if row[25] is not None else None,
            'country_stability': round(row[26], 3) if row[26] is not None else None,
            'ip_stability': round(row[27], 3) if row[27] is not None else None,
            'username_stability': round(row[28], 3) if row[28] is not None else None,
            'peak_hours': row[29],
            'peak_hour_1_pct': round(row[30], 1) if row[30] is not None else None,
            'peak_minutes': row[31],
            'peak_minute_1_pct': round(row[32], 1) if row[32] is not None else None,
            'peak_seconds': row[33],
            'peak_second_1_pct': round(row[34], 1) if row[34] is not None else None
        } for row in result]
        
        return jsonify(data)