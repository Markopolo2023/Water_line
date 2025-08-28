import os
import re
from docx import Document
import json
from pathlib import Path

def extract_data(filename):
    doc = Document(filename)
    data = {}
    # Date
    for para in doc.paragraphs:
        match = re.search(r'Date:\s*([\d/-]+)', para.text)
        if match:
            data['date'] = match.group(1)
            break
    # Facility
    for para in doc.paragraphs:
        match = re.search(r'Facility:\s*([^\n]+)', para.text)
        if match:
            data['facility'] = match.group(1).strip()
            break
    # Person
    for i, para in enumerate(doc.paragraphs):
        if 'Signature' in para.text:
            # The next non-empty paragraph is the name
            for j in range(i + 1, len(doc.paragraphs)):
                if doc.paragraphs[j].text.strip():
                    data['person'] = doc.paragraphs[j].text.strip()
                    break
            break
        match = re.search(r'IWT Field Representative:\s*([^\n]+)', para.text)
        if match:
            data['person'] = match.group(1).strip()
            break
    # Find the water samples table
    the_table = None
    for table in doc.tables:
        if len(table.rows) > 1:
            first_cell_text = table.rows[0].cells[0].text.strip()
            if 'GWT Names' in first_cell_text or table.rows[0].cells[1].text.strip().startswith('P Alkalinity'):
                the_table = table
                break
    if not the_table:
        data['measurements'] = 'Not found'
        return data
    # Headers (handle multi-line by joining)
    headers = [cell.text.strip() for cell in the_table.rows[0].cells]
    measurements = []
    for row in the_table.rows[1:]:
        row_data = [cell.text.strip() for cell in row.cells]
        if row_data and row_data[0]:
            measurement = {'distribution': row_data[0]}
            for h, v in zip(headers[1:], row_data[1:]):
                measurement[h] = v
            measurements.append(measurement)
    data['measurements'] = measurements
    return data

# Define directories
input_dir = Path('dr')
output_dir = Path('../data_processing')

# Create output directory if it doesn't exist
output_dir.mkdir(exist_ok=True)

# Process all .docx files in the 'dr' directory
for file_path in input_dir.glob('*.docx'):
    extracted_data = extract_data(file_path)
    # Create output filename (same as input but with .json extension)
    output_file = output_dir / f"{file_path.stem}.json"
    # Save extracted data as JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, indent=2)

# Note: You may need to install python-docx if not installed: pip install python-docx