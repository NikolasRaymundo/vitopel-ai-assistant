# ingest_docs.py

"""
Document ingestion script for Vitopel AI Assistant.
Parses PDFs, DOCX, PPTX, Excel, and images into clean text chunks.
Adds visual flags and prepares content for GPT classification.
"""

import os

def parse_pdf(file_path):
    # placeholder function
    print(f"Parsing PDF: {file_path}")

def parse_docx(file_path):
    # placeholder function
    print(f"Parsing Word doc: {file_path}")

def ingest_folder(folder_path):
    for file in os.listdir(folder_path):
        if file.endswith(".pdf"):
            parse_pdf(file)
        elif file.endswith(".docx"):
            parse_docx(file)
        else:
            print(f"Skipping unsupported file: {file}")

if __name__ == "__main__":
    ingest_folder("data/raw_docs/")
