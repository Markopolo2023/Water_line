# mssql_exporter.py

import pandas as pd
import sqlite3
from sqlalchemy import create_engine
from typing import Optional


class MSSQLExporter:
    def __init__(self, sqlite_db_path: str = 'reports.db',
                 mssql_connection_string: str = 'mssql+pyodbc://username:password@server/dbname?driver=ODBC+Driver+17+for+SQL+Server'):
        self.sqlite_db_path = sqlite_db_path
        self.mssql_connection_string = mssql_connection_string

    def export_to_mssql(self) -> Optional[str]:
        try:
            # Connect to SQLite
            sqlite_conn = sqlite3.connect(self.sqlite_db_path)

            # Read data from SQLite tables
            reports_df = pd.read_sql_query("SELECT * FROM reports", sqlite_conn)
            systems_df = pd.read_sql_query("SELECT * FROM systems", sqlite_conn)
            metrics_df = pd.read_sql_query("SELECT * FROM metrics", sqlite_conn)

            # Close SQLite connection
            sqlite_conn.close()

            # Connect to MSSQL using SQLAlchemy
            engine = create_engine(self.mssql_connection_string)

            # Write to MSSQL (append to preserve existing data; use 'replace' if you want to overwrite)
            reports_df.to_sql('reports', engine, if_exists='append', index=False)
            systems_df.to_sql('systems', engine, if_exists='append', index=False)
            metrics_df.to_sql('metrics', engine, if_exists='append', index=False)

            return "Data successfully exported to MSSQL."

        except Exception as e:
            return f"Error exporting to MSSQL: {str(e)}"


if __name__ == "__main__":
    # Example usage: Replace with your MSSQL connection string
    exporter = MSSQLExporter(
        sqlite_db_path='reports.db',
        mssql_connection_string='mssql+pyodbc://username:password@server/dbname?driver=ODBC+Driver+17+for+SQL+Server'
    )
    result = exporter.export_to_mssql()
    print(result)