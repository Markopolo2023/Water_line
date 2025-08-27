# report_processor.py

import os
import sqlite3
import re
from docx import Document
import PyPDF2
from typing import Dict, Optional


class ReportProcessor:
    def __init__(self, directory: str = 'reports', db_path: str = 'reports.db'):
        self.directory = directory
        self.db_path = db_path
        # Ensure the reports directory exists
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY,
                file_name TEXT,
                site_name TEXT,
                date TEXT,
                technician TEXT
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS systems (
                id INTEGER PRIMARY KEY,
                report_id INTEGER,
                system_type TEXT,
                system_name TEXT,
                comments TEXT,
                FOREIGN KEY (report_id) REFERENCES reports(id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY,
                system_id INTEGER,
                metric_key TEXT,
                metric_value TEXT,
                FOREIGN KEY (system_id) REFERENCES systems(id)
            )
        ''')

        self.conn.commit()

    def extract_text_from_docx(self, file_path: str) -> str:
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

    def extract_text_from_pdf(self, file_path: str) -> str:
        text = ""
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text

    def parse_report_text(self, text: str) -> Dict:
        data = {
            "site_name": None,
            "date": None,
            "technician": None,
            "systems": []  # List of dicts: {"type": str, "name": str, "data": dict}
        }

        # Normalize text: remove extra spaces, newlines
        text = re.sub(r'\s+', ' ', text).strip()

        # Extract site name (common patterns like "Facility: " or "SITE VISITATION REPORT" followed by name)
        site_match = re.search(r'(Facility:|SITE VISITATION REPORT)\s*([^,]+?)(Attention|Date|Systems|$)', text,
                               re.IGNORECASE)
        if site_match:
            data["site_name"] = site_match.group(2).strip()

        # Extract date (patterns like "Date: MM/DD/YY" or "YYYY-MM-DD")
        date_match = re.search(r'Date:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})', text, re.IGNORECASE)
        if date_match:
            data["date"] = date_match.group(1)

        # Extract technician (patterns like "Field Representative:", "Signature", "Field Chemist")
        tech_match = re.search(
            r'(IWT Field Representative:|Signature|Field Chemist|xMatthew Miller|Jeremy Overmann|Albert Rios)\s*([^,]+?)(@|\.|$)',
            text, re.IGNORECASE)
        if tech_match:
            data["technician"] = tech_match.group(2).strip()

        # Extract systems: Look for tables or sections with system names, types, and data
        system_blocks = re.findall(
            r'(Cold Dist|Hot Dist|MTW Nitrite|CW Nitrite|Pool Loop|CLOSED LOOP HEATING SYSTEM|CHILLED WATER SYSTEM|Cooling Tower|Basement Soft\.|Pool BLDG MTW|CW East|RECIRC\. DOMESTIC HOT|CITY WATER)\s*(.*?)(?=(Next System|$))',
            text, re.IGNORECASE | re.DOTALL)

        metrics_pattern = r'(Cond\.|pH|Temp|P Alk|M Alk|Chloride|Hardness|Calcium|PO4|SO2|Mo|NO2|Live ATP|Glycol|Free Chlorine|Total Chlorine|Max Temp\.)\s*[:=]?\s*([\d\.\-%\*/]+|OK|Good|Light Orange|Pink Color|Slight Yellow)'

        for system_type_name, block, _ in system_blocks:
            system_type, system_name = (
                system_type_name.split(maxsplit=1) if ' ' in system_type_name else (system_type_name, ""))
            system_data = {}

            # Extract comments/recommendations if present
            comment_match = re.search(
                r'(Comments and Recommendations:|Comment|Add\. Comments)\s*(.*?)(?=(Next Section|$))', block,
                re.IGNORECASE | re.DOTALL)
            if comment_match:
                system_data["comments"] = comment_match.group(2).strip()

            # Extract metrics
            for metric_match in re.finditer(metrics_pattern, block, re.IGNORECASE):
                key = metric_match.group(1).lower().strip()
                value = metric_match.group(2).strip()
                system_data[key] = value

            data["systems"].append({
                "type": system_type.strip(),
                "name": system_name.strip(),
                "data": system_data
            })

        return data

    def process_file(self, file_path: str) -> Optional[Dict]:
        ext = os.path.splitext(file_path)[1].lower()
        text = ""

        if ext == '.docx':
            text = self.extract_text_from_docx(file_path)
        elif ext == '.pdf':
            text = self.extract_text_from_pdf(file_path)
        else:
            print(f"Unsupported file type: {ext}")
            return None

        return self.parse_report_text(text)

    def insert_into_db(self, file_name: str, parsed_data: Dict):
        # Insert main report info
        self.cursor.execute('''
            INSERT INTO reports (file_name, site_name, date, technician)
            VALUES (?, ?, ?, ?)
        ''', (file_name, parsed_data["site_name"], parsed_data["date"], parsed_data["technician"]))

        report_id = self.cursor.lastrowid

        # Insert systems
        for system in parsed_data["systems"]:
            self.cursor.execute('''
                INSERT INTO systems (report_id, system_type, system_name, comments)
                VALUES (?, ?, ?, ?)
            ''', (report_id, system["type"], system["name"], system["data"].get("comments")))

            system_id = self.cursor.lastrowid

            # Insert metrics as key-value pairs (for flexibility, since metrics vary)
            for key, value in system["data"].items():
                if key != "comments":
                    self.cursor.execute('''
                        INSERT INTO metrics (system_id, metric_key, metric_value)
                        VALUES (?, ?, ?)
                    ''', (system_id, key, value))

        self.conn.commit()

    def process_files(self):
        for file_name in os.listdir(self.directory):
            file_path = os.path.join(self.directory, file_name)
            if os.path.isfile(file_path):
                parsed_data = self.process_file(file_path)
                if parsed_data:
                    self.insert_into_db(file_name, parsed_data)
                    print(f"Processed: {file_name}")

        print(f"Data saved to {self.db_path}.")

    def close(self):
        self.conn.close()