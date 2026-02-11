#!/usr/bin/env python3
"""
Load CSV data from dataset.10 into PostgreSQL database
Based on config.json configuration
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import json
import os
import sys
from datetime import datetime

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

def get_db_connection(config):
    """Create PostgreSQL database connection"""
    pg_config = config['data_source']['postgresql']
    conn = psycopg2.connect(
        host=pg_config['host'],
        port=pg_config['port'],
        database=pg_config['database'],
        user=pg_config['user'],
        password=pg_config['password'],
        sslmode='disable'
    )
    return conn

def clean_dataframe(df):
    """Clean DataFrame for PostgreSQL insertion"""
    # Replace NaN with None for proper NULL handling
    df = df.where(pd.notnull(df), None)

    # Replace empty strings with None
    df = df.replace('', None)

    # Convert boolean columns properly
    for col in df.select_dtypes(include=['bool']).columns:
        df[col] = df[col].astype('bool')

    # Handle date columns and 'NaT' values more aggressively
    for col in df.columns:
        if 'data' in col.lower() or 'date' in col.lower() or 'inizio' in col.lower() or 'fine' in col.lower():
            try:
                # Convert to datetime, replacing errors with None
                df[col] = pd.to_datetime(df[col], errors='coerce')
                # Replace NaT with None
                df[col] = df[col].where(pd.notna(df[col]), None)
            except:
                pass

    # Handle all numeric columns - convert ALL large integers to TEXT for safety
    for col in df.columns:
        if df[col].dtype in ['int64', 'int32', 'float64']:
            try:
                # Check if any values are too large for PostgreSQL INTEGER
                if df[col].dtype == 'int64':
                    max_val = df[col].max() if not df[col].isna().all() else 0
                    min_val = df[col].min() if not df[col].isna().all() else 0

                    # If any value is outside INTEGER range, convert to TEXT
                    if (pd.notna(max_val) and max_val > 2147483647) or (pd.notna(min_val) and min_val < -2147483648):
                        df[col] = df[col].astype(str).replace('nan', None)
            except:
                # If any error, convert to string
                df[col] = df[col].astype(str).replace('nan', None)

    # Quote column names that have special characters or spaces
    df.columns = [f'"{col}"' if (' ' in col or '-' in col) else col for col in df.columns]

    return df

def load_csv_to_table(conn, csv_file, table_name, separator=','):
    """Load CSV file to PostgreSQL table"""
    print(f"Loading {csv_file} into {table_name}...")

    try:
        # Read CSV with proper separator
        df = pd.read_csv(csv_file, sep=separator, low_memory=False)
        print(f"  Read {len(df)} rows from {csv_file}")

        # Clean data
        df = clean_dataframe(df)

        # Additional cleaning for specific problematic values
        for col in df.columns:
            if df[col].dtype == 'object':
                # Replace 'NaT' strings with None
                df[col] = df[col].replace('NaT', None)
                # Replace 'NaN' strings with None
                df[col] = df[col].replace('NaN', None)
                # Replace 'nan' strings with None
                df[col] = df[col].replace('nan', None)

        # Get column names (excluding id which is auto-generated)
        columns = [col for col in df.columns]
        placeholders = ','.join(['%s'] * len(columns))

        # Create INSERT query
        query = f"""
        INSERT INTO {table_name} ({','.join(columns)})
        VALUES ({placeholders})
        """

        # Convert DataFrame to list of tuples, handling None values properly
        data = []
        for _, row in df.iterrows():
            row_data = []
            for val in row:
                if pd.isna(val) or val == 'NaT' or val == 'NaN' or val == 'nan':
                    row_data.append(None)
                else:
                    row_data.append(val)
            data.append(tuple(row_data))

        # Execute batch insert
        cursor = conn.cursor()
        execute_batch(cursor, query, data, page_size=1000)
        conn.commit()
        cursor.close()

        print(f"  ✅ Loaded {len(data)} rows into {table_name}")

    except Exception as e:
        print(f"  ❌ Error loading {csv_file}: {e}")
        conn.rollback()
        return False

    return True

def main():
    """Main data loading function"""
    print("🗄️ GiAs-llm Data Loader")
    print("=" * 50)

    # Load configuration
    config = load_config()
    csv_config = config['data_source']['csv']
    pg_config = config['data_source']['postgresql']

    # Check if dataset directory exists
    dataset_dir = csv_config['directory']
    if not os.path.exists(dataset_dir):
        print(f"❌ Dataset directory {dataset_dir} not found")
        sys.exit(1)

    # Connect to database
    try:
        conn = get_db_connection(config)
        print(f"✅ Connected to PostgreSQL database: {pg_config['database']}")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("Make sure PostgreSQL is running and database is created")
        sys.exit(1)

    # File mappings from config.json
    file_mappings = [
        (csv_config['files']['piani'], pg_config['tables']['piani'], ','),
        (csv_config['files']['attivita'], pg_config['tables']['attivita'], ','),
        (csv_config['files']['controlli'], pg_config['tables']['controlli'], ','),
        (csv_config['files']['osa_mai_controllati'], pg_config['tables']['osa_mai_controllati'], ','),
        (csv_config['files']['ocse'], pg_config['tables']['ocse'], csv_config['ocse_separator']),
        (csv_config['files']['diff_prog_eseg'], pg_config['tables']['diff_prog_eseg'], ','),
        (csv_config['files']['personale'], pg_config['tables']['personale'], csv_config['personale_separator'])
    ]

    # Load each file
    success_count = 0
    total_count = len(file_mappings)

    for csv_file, table_name, separator in file_mappings:
        csv_path = os.path.join(dataset_dir, csv_file)

        if not os.path.exists(csv_path):
            print(f"⚠️  File not found: {csv_path}")
            continue

        if load_csv_to_table(conn, csv_path, table_name, separator):
            success_count += 1

    # Close connection
    conn.close()

    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Data Loading Summary:")
    print(f"   Successfully loaded: {success_count}/{total_count} tables")

    if success_count == total_count:
        print("   ✅ All data loaded successfully!")

        # Update config.json to enable PostgreSQL
        config['data_source']['postgresql']['enabled'] = True
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)
        print("   🔧 PostgreSQL data source enabled in config.json")

    else:
        print("   ⚠️  Some tables failed to load")

    print("=" * 50)

if __name__ == "__main__":
    main()