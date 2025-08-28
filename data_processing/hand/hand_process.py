import os
import numpy as np
import cv2
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

def preprocess_image(image):
    """
    Preprocess the image to improve OCR accuracy for poorly handwritten text.
    """
    # Convert PIL image to OpenCV format
    open_cv_image = np.array(image)
    # Convert to grayscale
    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
    # Apply Otsu's thresholding
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Denoise with median blur
    denoised = cv2.medianBlur(thresh, 3)
    # Convert back to PIL image
    return Image.fromarray(denoised)

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF using OCR, with preprocessing for handwritten content.
    """
    try:
        images = convert_from_path(pdf_path)
        text = ''
        for i, image in enumerate(images, start=1):
            preprocessed = preprocess_image(image)
            page_text = pytesseract.image_to_string(preprocessed)
            text += f"--- Page {i} ---\n{page_text}\n\n"
        return text
    except Exception as e:
        return f"Error extracting from {pdf_path}: {str(e)}\n\n"

# Directory containing the PDFs (subfolder 'hr' in the same folder as this script)
input_dir = 'hr'

# Output directory and file (folder above called 'data_processing', file 'hand_written.txt')
output_dir = '../data_processing'
output_file = os.path.join(output_dir, 'hand_written.txt')

# Create output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# Get list of PDF files from 'hr' directory
pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]

# Sort the PDF files by name (assuming date-based naming)
pdf_files.sort()

# Extract text from each PDF and collect all in one string
all_extracted_text = ''
for pdf in pdf_files:
    pdf_path = os.path.join(input_dir, pdf)
    if os.path.exists(pdf_path):
        extracted_text = extract_text_from_pdf(pdf_path)
        all_extracted_text += f"--- Extracted from {pdf} ---\n{extracted_text}\n\n"
        print(f"Extracted data from {pdf}")
    else:
        print(f"File not found: {pdf_path}")
        all_extracted_text += f"File not found: {pdf_path}\n\n"

# Write all extracted text to the single output file
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(all_extracted_text)

print(f"All extracted data saved to {output_file}")