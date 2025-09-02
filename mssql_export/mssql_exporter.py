import os
import json
import sqlite3
import pyodbc
from dateutil.parser import parse as parse_date
from datetime import datetime

# Define directories (relative to the script location in mssql_export)
hr_dir = os.path.abspath(os.path.join('..', 'data_processing', 'data_processing'))
pr_dir = os.path.abspath(os.path.join('..', 'data_processing', 'data_processing'))

# Function to clean column names for SQL
def clean_column(name):
    if name is None:
        return None
    name = name.replace("\n", " ").replace("µ", "u").replace(".", "").replace("°", "").strip()
    name = ''.join(c if c.isalnum() or c == ' ' else '' for c in name)
    name = name.replace(" ", "_")
    return name

# Function to standardize date format
def standardize_date(date_str):
    if not date_str or date_str.strip() == "":
        return None
    try:
        parsed_date = parse_date(date_str, fuzzy=True)
        return parsed_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError) as e:
        print(f"Error parsing date '{date_str}': {e}")
        return None

# Standard column mapping for similar measurements
column_mapping = {
    'P_Alkalinity_CaCO3_mgL': 'p_alkalinity',
    'P_Alk': 'p_alkalinity',
    'M_Alkalinity_CaCO3_mgL': 'm_alkalinity',
    'M_Alk': 'm_alkalinity',
    'Cl_mgL': 'chloride',
    'Chloride': 'chloride',
    'Hardness_CaCO3_mgL': 'hardness',
    'Hardness': 'hardness',
    'Ca_CaCO3_mgL': 'calcium',
    'Calcium': 'calcium',
    'Cond_uScm': 'conductivity',
    'Cond': 'conductivity',
    'pH': 'ph',
    'Temp_C': 'temperature',
    'Temp': 'temperature',
    'NO2_mgL': 'no2',
    'NO2': 'no2',
    'FREE_CHLORINE_ppm': 'free_chlorine',
    'Free_Chlorine': 'free_chlorine',
    'TOTAL_CHLORINE_ppm': 'total_chlorine',
    'Total_Chlorine': 'total_chlorine',
    'Susp_Solids': 'susp_solids',
    'PO4': 'po4',
    'SO2': 'so2',
    'Mo': 'mo',
    'Live_ATP': 'live_atp',
    'Glycol': 'glycol',
    'Max_Temp': 'max_temperature'
}

# Collect all unique standardized parameter names
params_set = set()
for directory in [hr_dir, pr_dir]:
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.json'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if "systems" in data and isinstance(data["systems"], list):
                        for sys in data["systems"]:
                            for key in sys:
                                if key not in ["#", "System Type", "System Name"]:
                                    cleaned = clean_column(key)
                                    standard = column_mapping.get(cleaned, cleaned.lower())
                                    params_set.add(standard)
                    elif "measurements" in data and isinstance(data["measurements"], list):
                        for meas in data["measurements"]:
                            for key in meas:
                                if key != "distribution":
                                    cleaned = clean_column(key)
                                    standard = column_mapping.get(cleaned, cleaned.lower())
                                    params_set.add(standard)
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")

if not params_set:
    print("Warning: No parameters found in JSON files. Check file contents or directories.")
params = sorted(params_set)

# Create SQLite database
sqlite_db = 'combined.db'
conn = sqlite3.connect(sqlite_db)
cur = conn.cursor()

# Create documents table
cur.execute('''
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    filename TEXT
)
''')

# Create data table with dynamic columns
base_columns = '''
id INTEGER PRIMARY KEY,
document_id INTEGER,
facility_name TEXT,
date TEXT,
chemist TEXT,
system_type TEXT,
system_name TEXT
'''
data_columns = ', '.join([f'"{cp}" TEXT' for cp in params]) if params else ''
create_table_query = f'''
CREATE TABLE IF NOT EXISTS data (
    {base_columns}
    {',' + data_columns if data_columns else ''}
)
'''.strip()
try:
    cur.execute(create_table_query)
except sqlite3.OperationalError as e:
    print(f"Error creating data table: {e}")
    print(f"Query: {create_table_query}")
    raise

# Check existing columns in the data table and add new ones
cur.execute("PRAGMA table_info(data)")
existing_columns = {row[1] for row in cur.fetchall()} - {'id', 'document_id', 'facility_name', 'date', 'chemist', 'system_type', 'system_name'}
for param in params:
    if param not in existing_columns:
        try:
            cur.execute(f'ALTER TABLE data ADD COLUMN "{param}" TEXT')
            print(f"Added new column: {param}")
        except sqlite3.OperationalError as e:
            print(f"Error adding column {param}: {e}")
conn.commit()

# Process directories with enhanced validation
for directory in [hr_dir, pr_dir]:
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.json'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        jsondata = json.load(f)
                    # Insert into documents
                    cur.execute('INSERT INTO documents (filename) VALUES (?)', (file,))
                    doc_id = cur.lastrowid
                    facility = jsondata.get("facility_name") or jsondata.get("facility")
                    if facility is None or facility.strip() == "":
                        print(f"Warning: Skipping file {file_path} due to missing or empty facility_name or facility")
                        continue
                    # Standardize the date
                    raw_date = jsondata.get("date")
                    date = standardize_date(raw_date)
                    chemist = jsondata.get("field_chemist") or jsondata.get("person")
                    chemist = chemist.replace("Page 1 of 1 ", "").strip() if chemist else None
                    inserted = False
                    if "systems" in jsondata and isinstance(jsondata["systems"], list):
                        for sys in jsondata["systems"]:
                            # Skip invalid or header rows
                            sys_type = sys.get("System Type")
                            sys_name = sys.get("System Name")
                            if sys.get("#") == "#" or '\n' in str(sys_type) or '\n' in str(sys_name) or sys_type == "-" or sys_type is None or sys_name is None:
                                print(f"Warning: Skipping invalid system in {file_path}: System Type={sys_type}, System Name={sys_name}")
                                continue
                            # Standardize parameters
                            standard_dict = {}
                            for raw_key in sys:
                                if raw_key not in ["#", "System Type", "System Name"]:
                                    cleaned = clean_column(raw_key)
                                    standard = column_mapping.get(cleaned, cleaned.lower())
                                    val = sys.get(raw_key)
                                    standard_dict[standard] = str(val) if val is not None else None
                            values = [doc_id, facility, date, chemist, sys_type, sys_name] + [standard_dict.get(p, None) for p in params]
                            placeholders = ','.join(['?'] * len(values))
                            columns = 'document_id, facility_name, date, chemist, system_type, system_name' + (', ' + ', '.join([f'"{p}"' for p in params]) if params else '')
                            cur.execute(f'INSERT INTO data ({columns}) VALUES ({placeholders})', values)
                            inserted = True
                    elif "measurements" in jsondata:
                        measurements = jsondata["measurements"]
                        if measurements != "Not found" and isinstance(measurements, list):
                            for meas in measurements[1:]:  # Skip header
                                sys_type = None
                                sys_name = meas.get("distribution")
                                if sys_name is None or "Water Samples" in sys_name or sys_name.strip() == "":
                                    print(f"Warning: Skipping invalid measurement in {file_path}: distribution={sys_name}")
                                    continue
                                # Standardize parameters
                                standard_dict = {}
                                for raw_key in meas:
                                    if raw_key != "distribution":
                                        cleaned = clean_column(raw_key)
                                        standard = column_mapping.get(cleaned, cleaned.lower())
                                        val = meas.get(raw_key)
                                        standard_dict[standard] = str(val) if val and val != '' else None
                                values = [doc_id, facility, date, chemist, sys_type, sys_name] + [standard_dict.get(p, None) for p in params]
                                placeholders = ','.join(['?'] * len(values))
                                columns = 'document_id, facility_name, date, chemist, system_type, system_name' + (', ' + ', '.join([f'"{p}"' for p in params]) if params else '')
                                cur.execute(f'INSERT INTO data ({columns}) VALUES ({placeholders})', values)
                                inserted = True
                    if inserted:
                        conn.commit()
                    else:
                        print(f"Warning: No valid data inserted from {file_path}")
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

# Close SQLite connection
conn.close()

# Export to MSSQL
server = 'your_server_name'
database = 'your_database_name'
username = 'your_username'
password = 'your_password'
driver = '{ODBC Driver 17 for SQL Server}'
conn_str = f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}'

try:
    mssql_conn = pyodbc.connect(conn_str)
    mssql_cur = mssql_conn.cursor()

    # Create documents table in MSSQL
    mssql_cur.execute('''
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='documents' AND xtype='U')
    CREATE TABLE documents (
        id INT PRIMARY KEY IDENTITY,
        filename VARCHAR(255)
    )
    ''')

    # Create data table in MSSQL with dynamic columns
    data_columns_mssql = ', '.join([f'[{cp}] VARCHAR(MAX)' for cp in params]) if params else ''
    mssql_create_query = f'''
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='data' AND xtype='U')
    CREATE TABLE data (
        id INT PRIMARY KEY IDENTITY,
        document_id INT,
        facility_name VARCHAR(255),
        date VARCHAR(50),
        chemist VARCHAR(255),
        system_type VARCHAR(255),
        system_name VARCHAR(255)
        {',' + data_columns_mssql if data_columns_mssql else ''}
    )
    '''.strip()
    try:
        mssql_cur.execute(mssql_create_query)
    except pyodbc.Error as e:
        print(f"Error creating MSSQL data table: {e}")
        print(f"Query: {mssql_create_query}")
        raise

    # Check and add new columns to MSSQL data table
    mssql_cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'data'")
    existing_mssql_columns = {row[0] for row in mssql_cur.fetchall()} - {'id', 'document_id', 'facility_name', 'date', 'chemist', 'system_type', 'system_name'}
    for param in params:
        if param not in existing_mssql_columns:
            try:
                mssql_cur.execute(f'ALTER TABLE data ADD [{param}] VARCHAR(MAX)')
                print(f"Added new column to MSSQL: {param}")
            except pyodbc.Error as e:
                print(f"Error adding column {param} to MSSQL: {e}")
    mssql_conn.commit()

    # Reopen SQLite to fetch data
    conn = sqlite3.connect(sqlite_db)
    cur = conn.cursor()

    # Export documents
    docs = cur.execute('SELECT id, filename FROM documents').fetchall()
    for row in docs:
        mssql_cur.execute('INSERT INTO documents (filename) VALUES (?)', (row[1],))

    # Export data
    data_cols = ['document_id', 'facility_name', 'date', 'chemist', 'system_type', 'system_name'] + params
    data_cols_str = ', '.join(data_cols)
    placeholders_mssql = ','.join(['?'] * len(data_cols))
    rows = cur.execute(f'SELECT {data_cols_str} FROM data').fetchall()
    for row in rows:
        mssql_cur.execute(
            f'INSERT INTO data ({", ".join([f"[{c}]" for c in data_cols])}) VALUES ({placeholders_mssql})',
            row
        )
    mssql_conn.commit()
    print("Data exported to MSSQL successfully.")
except Exception as e:
    print("Error exporting to MSSQL:", str(e))
finally:
    if 'mssql_conn' in locals():
        mssql_conn.close()
    if 'conn' in locals():
        conn.close()