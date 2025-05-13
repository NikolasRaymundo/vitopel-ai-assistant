# ingest_docs.py

# ——— Imports ———
import os
import fitz  # PyMuPDF – PDF parsing (native & OCR fallback)
import pytesseract  # OCR engine (Tesseract)
import pillow_heif  # Adds HEIC support to Pillow
pillow_heif.register_heif_opener()  # Enables PIL.Image.open() to read HEIC
from PIL import Image  # Image handling for OCR
from docx import Document  # DOCX parsing
import pandas as pd  # Excel/CSV parsing
import json  # Save processed outputs as JSON
import hashlib  # Generate unique file hash
from pptx import Presentation  # PPTX parsing
import zipfile  # ZIP file extraction
import subprocess  # Run LibreOffice conversions
import unicodedata  # Normalize filenames (accents, symbols)
import shutil  # Clean up temp folders

# ——— Folder configuration ———
RAW_FOLDER = "data/raw_docs"
OUT_FOLDER = "data/processed_texts"
TEMP_FOLDER = "data/temp_extracted"

# ——— Conversion helpers for legacy Office formats ———

def convert_ppt_to_pptx(path):
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pptx", path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        converted = os.path.splitext(path)[0] + ".pptx"
        return converted if os.path.exists(converted) else None
    except Exception as e:
        print(f"[fail] PPT conversion error: {path}: {e}")
        return None

def convert_doc_to_docx(path):
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "docx", path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        converted = os.path.splitext(path)[0] + ".docx"
        return converted if os.path.exists(converted) else None
    except Exception as e:
        print(f"[fail] DOC conversion error: {path}: {e}")
        return None

def convert_xls_to_xlsx(path):
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "xlsx", path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        converted = os.path.splitext(path)[0] + ".xlsx"
        return converted if os.path.exists(converted) else None
    except Exception as e:
        print(f"[fail] XLS conversion error: {path}: {e}")
        return None

# ——— Utility: File hasher ———
def hash_file(filepath):
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

# ——— Parsers for different file types ———

def parse_pdf(path):
    text = ""
    try:
        doc = fitz.open(path)
        for page in doc:
            page_text = page.get_text()
            if page_text.strip():
                text += page_text + "\n"
        if text.strip():
            return text
        else:
            raise ValueError("PDF has no text — fallback to OCR")
    except:
        # Fallback: OCR each page
        try:
            text = ""
            doc = fitz.open(path)
            for i in range(len(doc)):
                pix = doc[i].get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_text = pytesseract.image_to_string(img, lang="por+eng")
                text += ocr_text + "\n"
            return text if text.strip() else None
        except Exception as e:
            print(f"[OCR FAIL] {path}: {e}")
            return None

def parse_docx(path):
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)

def parse_excel(path):
    try:
        df = pd.read_excel(path)
        return df.to_string(index=False)
    except Exception as e:
        print(f"[XLS FAIL] {path}: {e}")
        return None

def parse_csv(path):
    try:
        df = pd.read_csv(path)
        return df.to_string(index=False)
    except Exception as e:
        print(f"[CSV FAIL] {path}: {e}")
        return None

def parse_image(path):
    try:
        img = Image.open(path)
        print(f"[debug] Opened image: {path}, format: {img.format}, mode: {img.mode}")
        if img.format.lower() in ["heif", "webp"]:
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img, lang="por+eng")
        return text if text.strip() else None
    except Exception as e:
        print(f"[IMG FAIL] {path}: {type(e).__name__}: {e}")
        return None

def parse_txt(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        print(f"[TXT FAIL] {path}: {e}")
        return None

def parse_pptx(path):
    try:
        prs = Presentation(path)
        text = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text.append(shape.text)
        return "\n".join(text) if text else None
    except Exception as e:
        print(f"[PPTX FAIL] {path}: {e}")
        return None

# ——— Save parsed output as .json ———
def save_json(filename, data):
    out_path = os.path.join(OUT_FOLDER, filename + ".json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ——— Normalize weird filenames from ZIP extractions ———
def normalize_filename(name):
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")

# ——— Unzip and sanitize ZIP files ———
def extract_zip(path):
    extracted_paths = []
    try:
        temp_dir = TEMP_FOLDER
        os.makedirs(temp_dir, exist_ok=True)

        with zipfile.ZipFile(path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.startswith("._") or "__MACOSX" in root:
                    continue

                original_path = os.path.join(root, file)
                clean_name = normalize_filename(file)
                clean_path = os.path.join(root, clean_name)

                if original_path != clean_path:
                    try:
                        os.rename(original_path, clean_path)
                    except Exception as e:
                        print(f"[rename fail] Could not rename {original_path}: {e}")
                        continue

                print(f"[debug] Found file after rename: {clean_path}")
                extracted_paths.append(clean_path)

        return extracted_paths

    except Exception as e:
        print(f"[ZIP FAIL] {path}: {e}")
        return []

# ——— Registry that maps extensions to handlers ———
EXTENSION_PARSERS = {
    "pdf": parse_pdf,
    "docx": parse_docx,
    "xlsx": parse_excel,
    "csv": parse_csv,
    "png": parse_image,
    "jpg": parse_image,
    "jpeg": parse_image,
    "heic": parse_image,
    "tif": parse_image,
    "tiff": parse_image,
    "txt": parse_txt,
    "pptx": parse_pptx,
}

# ——— Master file handler ———
def process_file(path, fname_prefix=""):
    if not os.path.exists(path):
        print(f"[skip] Missing file: {path}")
        return

    ext = os.path.splitext(path)[1].lower().lstrip(".")

    legacy_conversion_map = {
        "ppt": "pptx",
        "doc": "docx",
        "xls": "xlsx"
    }

    if ext in legacy_conversion_map:
        target_ext = legacy_conversion_map[ext]
        new_path = os.path.splitext(path)[0] + f".{target_ext}"
        try:
            subprocess.run([
                "/Applications/LibreOffice.app/Contents/MacOS/soffice",
                "--headless",
                "--convert-to", target_ext,
                path,
                "--outdir", RAW_FOLDER
            ], check=True)
            print(f"[convert] {os.path.basename(path)} → {target_ext}")
            path = new_path
            ext = target_ext
        except Exception as e:
            print(f"[fail] Could not convert .{ext}: {path}")
            return

    parser = EXTENSION_PARSERS.get(ext)
    if not parser:
        print(f"[skip] Unsupported file: {os.path.basename(path)}")
        return

    try:
        parsed_text = parser(path)
        if not parsed_text:
            print(f"[fail] Empty or unreadable content: {os.path.basename(path)}")
            return
        file_hash = hash_file(path)
        outname = fname_prefix + os.path.basename(path) + "." + file_hash[:8]
        save_json(outname, {
            "file_name": os.path.basename(path),
            "file_type": ext,
            "text": parsed_text,
            "hash": file_hash,
            "source_path": path,
        })
        print(f"[ok] {outname}")
    except Exception as e:
        print(f"[error] Failed to process {path}: {e}")

# ——— Orchestrator ———
def main():
    os.makedirs(OUT_FOLDER, exist_ok=True)
    file_count = 0

    for fname in os.listdir(RAW_FOLDER):
        fpath = os.path.join(RAW_FOLDER, fname)

        if fname.lower().endswith(".zip"):
            print(f"[zip] Extracting: {fname}")
            for extracted_file in extract_zip(fpath):
                process_file(extracted_file, fname_prefix=fname + "_")
                file_count += 1
            continue

        process_file(fpath)
        file_count += 1

    # Clean up temp extracted files
    if os.path.exists(TEMP_FOLDER):
        shutil.rmtree(TEMP_FOLDER, ignore_errors=True)

    print(f"\n🎯 Ingestion complete. {file_count} files attempted.")

if __name__ == "__main__":
    main()
