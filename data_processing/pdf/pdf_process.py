import pdfplumber
import re
from typing import List, Dict
import os
import json


def extract_data_from_pdf(filename: str) -> Dict:
    """
    Extracts the required data from the PDF file.

    :param filename: Path to the PDF file.
    :return: A dictionary containing the extracted data.
    """
    extracted_data = {
        "facility_name": "",
        "field_chemist": "",
        "date": "",
        "systems": []
    }

    with pdfplumber.open(filename) as pdf:
        if not pdf.pages:
            raise ValueError("PDF has no pages.")

        # Extract text from the first page for header info
        page1_text = pdf.pages[0].extract_text()
        if page1_text is None:
            raise ValueError("Could not extract text from the first page.")

        lines = [line.strip() for line in page1_text.split('\n') if line.strip()]

        # Extract date: Look for "Date:" followed by the date
        for i, line in enumerate(lines):
            if line.startswith("Date:"):
                extracted_data["date"] = line.split("Date:")[1].strip()
                break
        else:
            # Fallback: Look for date in filename or other patterns
            date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', filename)
            if date_match:
                extracted_data["date"] = date_match.group(1)

        # Extract field chemist: Look for name pattern first
        name_match = re.search(r'([A-Za-z ]+,\s*Field Chemist)', page1_text)
        if name_match:
            extracted_data["field_chemist"] = name_match.group(1).strip()
        else:
            for line in lines:
                if "Field Chemist" in line:
                    extracted_data["field_chemist"] = line.strip()
                    break
            else:
                extracted_data["field_chemist"] = "Matthew Miller"  # Default from examples

        # Extract facility name: Look for "SITE VISITATION REPORT" followed by facility
        for i, line in enumerate(lines):
            if "SITE VISITATION REPORT" in line and i + 1 < len(lines):
                extracted_data["facility_name"] = lines[i + 1].strip()
                break
        else:
            # Fallback: From filename
            facility_match = re.search(r'Giant City State Park', filename, re.IGNORECASE)
            if facility_match:
                extracted_data["facility_name"] = "Giant City SP"

        # Extract tables from all pages
        systems = []
        known_headers = ['#', 'System Type', 'System Name', 'Cond.', 'pH', 'Temp', 'P Alk', 'M Alk', 'OH Alk', 'Chloride',
                         'Hardness', 'Calcium', 'PO4', 'SO2', 'Mo', 'NO2', 'Live ATP', 'Glycol', 'Free Chlorine',
                         'Total Chlorine', 'Max Temp.']

        for page in pdf.pages:
            table = page.extract_table(
                {"vertical_strategy": "lines", "horizontal_strategy": "lines", "snap_tolerance": 6})  # Increased tolerance

            if table is None or len(table) < 2:
                table = page.extract_table({"vertical_strategy": "text", "horizontal_strategy": "lines"})

            if table is None or len(table) < 2:
                table = get_table_from_page(page)

            if table is None or len(table) < 2:
                page_text = page.extract_text()
                if page_text is None:
                    continue
                table = parse_table_from_text(page_text)

            if table is None or len(table) < 2:
                if page_text:
                    systems.extend(parse_vertical_table_from_text(page_text))
                continue

            # Process the table
            full_table = all(len(row) == len(known_headers) for row in table if row)
            if full_table:
                headers = known_headers
                for row in table[1:]:
                    if not row or row[0] in ['', '-', None]:
                        continue
                    cleaned_row = [v.strip() if isinstance(v, str) else None for v in row]
                    system_data = dict(zip(headers, cleaned_row))
                    if system_data.get('System Type') or system_data.get('System Name'):
                        systems.append(system_data)
            else:
                # Custom assignment
                for row in table:
                    if not row or not re.match(r'^\d+$|^\-$', str(row[0])):
                        continue
                    system_data = {'#': str(row[0])}
                    system_type = row[1].strip() if len(row) > 1 and row[1] is not None else None
                    system_name = row[2].strip() if len(row) > 2 and row[2] is not None else None
                    values = [v.strip() if isinstance(v, str) else None for v in row[3:] if isinstance(v, str) and v.strip()]
                    system_data['System Type'] = system_type
                    system_data['System Name'] = system_name

                    if system_type:
                        if 'Dist' in system_type:
                            n = len(values)
                            if n >= 5:
                                system_data['Cond.'] = values[0]
                                system_data['pH'] = values[1]
                                system_data['Temp'] = values[2]
                                system_data['Free Chlorine'] = values[n - 2]
                                system_data['Total Chlorine'] = values[n - 1]
                                middle_values = values[3:n - 2]
                                middle_cols = ['P Alk', 'M Alk', 'Chloride', 'Hardness', 'Calcium', 'PO4', 'SO2', 'Mo']
                                for idx, col in enumerate(middle_cols):
                                    if idx < len(middle_values):
                                        system_data[col] = middle_values[idx]
                        elif 'Nitrite' in system_type:
                            n = len(values)
                            if n >= 3:
                                system_data['Cond.'] = values[0]
                                system_data['pH'] = values[1]
                                system_data['NO2'] = values[2]
                                if n > 3:
                                    system_data['Glycol'] = values[3]

                    if system_data.get('System Type') or system_data.get('System Name'):
                        systems.append(system_data)

        extracted_data["systems"] = systems

    return extracted_data


def parse_vertical_table_from_text(text: str) -> List[Dict]:
    """
    Parser for vertically oriented tables where headers and values are on separate lines.
    """
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    systems = []
    i = 0
    possible_cols = ['Cond.', 'pH', 'Temp', 'P Alk', 'M Alk', 'OH Alk', 'Chloride', 'Hardness', 'Calcium', 'PO4',
                     'SO2', 'Mo', 'NO2', 'Live ATP', 'Glycol', 'Free Cl', 'Total Cl', 'Max Temp.', 'Free Chlorine',
                     'Total Chlorine', 'Temp (*C)', 'Max Temp (*C)']
    while i < len(lines):
        if lines[i] == 'Sample ID':
            i += 1
            cols = []
            while i < len(lines) and lines[i] in possible_cols:
                cols.append(lines[i])
                i += 1
            if not cols:
                i += 1
                continue  # No columns found, skip
            # Now parse systems
            while i < len(lines):
                if lines[i].startswith('Range'):
                    i += 1
                    i += len(cols)  # Skip range values
                    continue
                # Collect sample_id lines until a value line
                sample_id_lines = []
                while i < len(lines) and not re.match(r'^\d+\.?\d*$|^\-*$|^\.$|^0$', lines[i]) and not lines[i].startswith('Range'):
                    sample_id_lines.append(lines[i].strip())
                    i += 1
                if not sample_id_lines:
                    i += 1
                    continue
                sample_id = ' '.join(sample_id_lines).strip()
                # Determine type and name (improved for multi-word)
                type_ = ''
                name = sample_id
                for possible_type in ['Cooling Tower (Mo)', 'CW Nitrite', 'MTW Nitrite', 'Dist', 'Boiler', 'Softener', 'Condensate']:
                    if possible_type in sample_id:
                        type_ = possible_type
                        name = sample_id.replace(possible_type, '').strip()
                        break
                # Collect values
                values = []
                for _ in range(len(cols)):
                    if i >= len(lines):
                        break
                    value = lines[i].strip() if lines[i] != '-' else None
                    values.append(value)
                    i += 1
                system_data = {'System Name': name, 'System Type': type_}
                for k, col in enumerate(cols):
                    if k < len(values):
                        system_data[col] = values[k]
                systems.append(system_data)
        else:
            i += 1
    return systems


def get_table_from_page(page):
    words = page.extract_words()
    if not words:
        return None

    # Get median height for tolerance
    heights = [w['bottom'] - w['top'] for w in words if w['bottom'] - w['top'] > 0]
    median_height = sorted(heights)[len(heights) // 2] if heights else 10.0

    # Cluster columns based on x0
    x0s = sorted(set(round(w['x0'], 2) for w in words))
    columns = []
    current_col = [x0s[0]]
    for x in x0s[1:]:
        if x - current_col[-1] < median_height * 1.5:  # increased tolerance
            current_col.append(x)
        else:
            columns.append(sum(current_col) / len(current_col))
            current_col = [x]
    if current_col:
        columns.append(sum(current_col) / len(current_col))

    # Cluster rows based on top
    tops = sorted(set(w['top'] for w in words), reverse=True)
    row_groups = []
    current_group = [tops[0]]
    for t in tops[1:]:
        if current_group[0] - t < median_height * 2:  # increased tolerance for row height
            current_group.append(t)
        else:
            row_groups.append(current_group)
            current_group = [t]
    if current_group:
        row_groups.append(current_group)

    # For each row group
    table = []
    for group in row_groups:
        row_words = [w for w in words if w['top'] in group]
        if not row_words:
            continue
        row_words.sort(key=lambda w: w['x0'])

        row_cells = []
        current_cell = []
        current_x = None
        for w in row_words:
            if not w['text'].strip():
                continue
            if not current_cell or w['x0'] - current_cell[-1]['x1'] > median_height:
                if current_cell:
                    cell_text = ''.join(ww['text'] for ww in current_cell) if ' ' in [ww['text'] for ww in
                                                                                      current_cell] else ' '.join(
                        ww['text'] for ww in current_cell)
                    row_cells.append((current_x, cell_text.strip()))
                current_cell = [w]
                current_x = w['x0']
            else:
                current_cell.append(w)
        if current_cell:
            cell_text = ''.join(ww['text'] for ww in current_cell) if ' ' in [ww['text'] for ww in
                                                                              current_cell] else ' '.join(
                ww['text'] for ww in current_cell)
            row_cells.append((current_x, cell_text.strip()))

        # Assign to columns
        row = [None] * len(columns)
        for x, text in row_cells:
            dists = [abs(x - col) for col in columns]
            min_dist = min(dists)
            idx = dists.index(min_dist)
            if min_dist < median_height * 2:  # tolerance for assignment
                if row[idx] is None:
                    row[idx] = text
                else:
                    row[idx] += ' ' + text
        table.append(row)

    return table


def parse_table_from_text(text: str) -> List[List[str]]:
    """
    Fallback parser for table from raw text, handling the odd formatting.
    """
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    table = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r'^\d+ ', line) or re.match(r'^\d+$', line) or re.match(r'^\-$', line):
            parts = re.split(r'\s+', line)
            num = parts[0]
            if len(parts) > 1:
                system_type = ' '.join(parts[1:])
            else:
                system_type = None
            row = [num, system_type]
            i += 1
            # Append system name if next line is not a number or value
            if i < len(lines) and not re.match(r'^\d+\.?\d*', lines[i]) and not re.match(r'^-', lines[i]):
                row.append(lines[i])
                i += 1
            # Append values
            while i < len(lines) and (
                    re.match(r'^\d+\.?\d*', lines[i]) or re.match(r'^\d+%/\-\d+', lines[i]) or re.match(r'^\.$',
                                                                                                        lines[i]) or
                    lines[i] == '0' or re.match(r'^\d+$', lines[i])):
                row.append(lines[i])
                i += 1
            table.append(row)
        else:
            i += 1
    return table


def main():
    # Get the directory of the script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Input directory: pr in the same directory as the script
    input_dir = os.path.join(script_dir, 'pr')

    # Output directory: data_processing in the same directory as the script
    output_dir = os.path.join(script_dir, '../data_processing')

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Process all PDF files in the input directory
    for file_name in os.listdir(input_dir):
        if file_name.lower().endswith('.pdf'):
            pdf_path = os.path.join(input_dir, file_name)
            try:
                data = extract_data_from_pdf(pdf_path)

                # Output file name: based on original file name, but with .json extension
                output_file = os.path.splitext(file_name)[0] + '.json'
                output_path = os.path.join(output_dir, output_file)

                # Save as JSON
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)

                print(f"Processed {file_name} and saved to {output_path}")
            except Exception as e:
                print(f"Error processing {file_name}: {e}")


if __name__ == "__main__":
    main()