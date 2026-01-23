"""
Database connection utilities
"""

import duckdb
from flask import request
from .config import DB_PATH


def get_db():
    """Get database connection"""
    return duckdb.connect(str(DB_PATH), read_only=True)


def parse_date_params():
    """Parse date range from query parameters"""
    start = request.args.get('start', '2022-11-01')
    end = request.args.get('end', '2023-01-08')
    return start, end
