import os
import shutil
from PyPDF2 import PdfReader


def classify_pdf(pdf_path):
    """
    Classifies a PDF into one of three categories:
    - 'handwritten': No extractable text (likely scanned/image-based).
    - 'excel_table': Extractable text and metadata indicates origin from Excel (e.g., producer/creator contains 'excel'), or fallback based on content.
    - 'docx_to_pdf': Extractable text and metadata indicates origin from Word (e.g., producer/creator contains 'word'), or fallback based on content.
    Prints metadata for diagnosis.
    Returns None on error.
    """
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted
        text = text.strip()

        print(f"Classifying {pdf_path}")

        category = None
        metadata = reader.metadata
        producer = 'None'
        creator = 'None'
        if metadata:
            producer = str(metadata.get('/Producer', 'None'))
            creator = str(metadata.get('/Creator', 'None'))
            producer_lower = producer.lower()
            creator_lower = creator.lower()

            if any(k in producer_lower or k in creator_lower for k in ['excel', 'calc', 'spreadsheet', 'xls']):
                category = "excel_table"
            elif any(k in producer_lower or k in creator_lower for k in ['word', 'writer', 'docx']):
                category = "docx_to_pdf"

        print(f"Producer: {producer}")
        print(f"Creator: {creator}")

        if len(text) == 0:
            category = "handwritten"
        elif category is None:
            # Fallback based on content analysis
            if "Comments and Recommendations:" in text:
                category = "docx_to_pdf"
            else:
                category = "excel_table"

        print(f"Category: {category}\n")

        return category

    except Exception as e:
        print(f"Error classifying {pdf_path}: {e}")
        return None


def sort_files(directory, recursive=False):
    """
    Sorts files in the given directory (and subdirectories if recursive=True) into four subfolders at the root:
    - handwritten: PDFs with no extractable text (likely handwritten/scanned)
    - excel_table: PDFs with extractable text and Excel metadata or content
    - docx_to_pdf: PDFs with extractable text and Word metadata or content
    - docx: All .docx files

    Creates the folders at the root if they don't exist.
    Skips non-PDF/DOCX files, Recycle Bin, and handles errors gracefully.
    """
    # Check if directory exists
    if not os.path.exists(directory):
        print(f"Error: Directory '{directory}' does not exist or is not accessible.")
        return

    handwritten_dir = os.path.join(directory, "handwritten")
    excel_dir = os.path.join(directory, "excel_table")
    docx_to_pdf_dir = os.path.join(directory, "docx_to_pdf")
    docx_dir = os.path.join(directory, "docx")

    try:
        os.makedirs(handwritten_dir, exist_ok=True)
        os.makedirs(excel_dir, exist_ok=True)
        os.makedirs(docx_to_pdf_dir, exist_ok=True)
        os.makedirs(docx_dir, exist_ok=True)
    except PermissionError as e:
        print(f"Error: Permission denied when creating folders in '{directory}': {e}")
        return
    except Exception as e:
        print(f"Error creating folders in '{directory}': {e}")
        return

    if recursive:
        for root, dirs, files in os.walk(directory):
            # Skip Recycle Bin and output folders
            if '$RECYCLE.BIN' in root.upper() or root in [handwritten_dir, excel_dir, docx_to_pdf_dir, docx_dir]:
                continue
            for filename in files:
                filepath = os.path.join(root, filename)
                process_file(filepath, handwritten_dir, excel_dir, docx_to_pdf_dir, docx_dir, filename)
    else:
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                process_file(filepath, handwritten_dir, excel_dir, docx_to_pdf_dir, docx_dir, filename)


def process_file(filepath, handwritten_dir, excel_dir, docx_to_pdf_dir, docx_dir, filename):
    try:
        if filename.lower().endswith('.docx'):
            dest_path = os.path.join(docx_dir, filename)
            if os.path.exists(dest_path):
                print(f"Filename conflict: {filename} already exists in docx folder. Skipping.")
            else:
                shutil.move(filepath, dest_path)
                print(f"Moved {filename} to docx folder")
        elif filename.lower().endswith('.pdf'):
            category = classify_pdf(filepath)
            if category == "excel_table":
                dest_path = os.path.join(excel_dir, filename)
                if os.path.exists(dest_path):
                    print(f"Filename conflict: {filename} already exists in excel_table folder. Skipping.")
                else:
                    shutil.move(filepath, dest_path)
                    print(f"Moved {filename} to excel_table folder")
            elif category == "handwritten":
                dest_path = os.path.join(handwritten_dir, filename)
                if os.path.exists(dest_path):
                    print(f"Filename conflict: {filename} already exists in handwritten folder. Skipping.")
                else:
                    shutil.move(filepath, dest_path)
                    print(f"Moved {filename} to handwritten folder")
            elif category == "docx_to_pdf":
                dest_path = os.path.join(docx_to_pdf_dir, filename)
                if os.path.exists(dest_path):
                    print(f"Filename conflict: {filename} already exists in docx_to_pdf folder. Skipping.")
                else:
                    shutil.move(filepath, dest_path)
                    print(f"Moved {filename} to docx_to_pdf folder")
            else:
                print(f"Skipping {filename}: Could not classify PDF (possible corruption).")
    except PermissionError as e:
        print(f"Error moving {filename}: Permission denied - {e}")
    except Exception as e:
        print(f"Error moving {filename}: {e}")


# Example usage for drive G:
sort_files('G:\\', recursive=True)