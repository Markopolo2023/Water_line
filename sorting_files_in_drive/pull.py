import os
import shutil


def extract_reports(root_dir, dest_dir):
    # Create the destination directory if it doesn't exist
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    copied_files = 0
    target_name = "***your target directory here***".lower()

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Check if the current directory is named "Site Visit Reports" (case-insensitive)
        if os.path.basename(dirpath).lower() == target_name:
            print(f"Found folder: {dirpath}")
            # Now recursively walk this "Site Visit Reports" folder and its subfolders
            for subpath, _, subfiles in os.walk(dirpath):
                print(f"Processing subpath: {subpath}")
                for filename in subfiles:
                    # Check for PDF or DOCX files (case-insensitive)
                    if filename.lower().endswith(('.pdf', '.docx')):
                        source_path = os.path.join(subpath, filename)
                        dest_path = os.path.join(dest_dir, filename)

                        # If a file with the same name exists, append a number to avoid overwriting
                        if os.path.exists(dest_path):
                            base, extension = os.path.splitext(filename)
                            counter = 1
                            while os.path.exists(os.path.join(dest_dir, f"{base}_{counter}{extension}")):
                                counter += 1
                            dest_path = os.path.join(dest_dir, f"{base}_{counter}{extension}")

                        # Copy the file
                        try:
                            shutil.copy(source_path, dest_path)
                            copied_files += 1
                            print(f"Copied: {source_path} to {dest_path}")
                        except Exception as e:
                            print(f"Error copying {source_path}: {e}")

    print(f"Extraction complete. Copied {copied_files} files to {dest_dir}.")


# Example usage - replace with your actual paths
root_directory = r'C:'  # Path to your root folder
usb_directory = r'D:'  # Path to your USB folder (using drive letter D:)
extract_reports(root_directory, usb_directory)