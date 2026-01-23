"""
Configuration loader for the API
"""

import configparser

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')
DB_PATH = config['paths']['duckdb_path']
