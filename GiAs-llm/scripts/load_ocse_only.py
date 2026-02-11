#!/usr/bin/env python3
"""
Load only the OCSE table that's still missing
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import json

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

def main():
    """Load only OCSE data"""
    print("🗄️ Loading OCSE Data Only")
    print("=" * 50)

    config = load_config()
    conn = get_db_connection(config)

    csv_file = "dataset.10/isp_sempl_in_chiaro_2016_2025.csv"
    separator = "$"

    try:
        # Read CSV with $ separator
        df = pd.read_csv(csv_file, sep=separator, low_memory=False)
        print(f"Read {len(df)} rows from {csv_file}")

        # Clean problematic values
        df = df.where(pd.notnull(df), None)
        df = df.replace('', None)
        df = df.replace('NaT', None)
        df = df.replace('NaN', None)
        df = df.replace('nan', None)

        # Handle date column
        if 'data_inizio_attivita' in df.columns:
            df['data_inizio_attivita'] = pd.to_datetime(df['data_inizio_attivita'], errors='coerce')
            df['data_inizio_attivita'] = df['data_inizio_attivita'].where(pd.notna(df['data_inizio_attivita']), None)

        # Get columns
        columns = list(df.columns)
        placeholders = ','.join(['%s'] * len(columns))

        # Create INSERT query
        query = f"""
        INSERT INTO ocse_isp_semp_2025 ({','.join(columns)})
        VALUES ({placeholders})
        """

        # Convert to tuples with proper None handling
        data = []
        for _, row in df.iterrows():
            row_data = []
            for val in row:
                if pd.isna(val) or val == 'NaT' or val == 'NaN' or val == 'nan':
                    row_data.append(None)
                else:
                    row_data.append(val)
            data.append(tuple(row_data))

        print(f"Inserting {len(data)} rows...")

        # Execute in smaller batches
        cursor = conn.cursor()
        batch_size = 500
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            execute_batch(cursor, query, batch, page_size=100)
            if i % 10000 == 0:
                print(f"  Processed {i}/{len(data)} rows...")

        conn.commit()
        cursor.close()
        conn.close()

        print(f"✅ Successfully loaded {len(data)} rows into ocse_isp_semp_2025")

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        conn.close()

if __name__ == "__main__":
    main()