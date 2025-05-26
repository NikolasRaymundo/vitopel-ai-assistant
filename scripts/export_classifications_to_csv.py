# scripts/export_classifications_to_csv.py

import os
import json
import csv
from datetime import datetime

# --- Configuration ---
# Establish the project root based on this script's location
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

CLASSIFIED_JSON_FOLDER = os.path.join(project_root, "data", "classified_texts_p1")
CSV_OUTPUT_FOLDER = os.path.join(project_root, "data", "review_exports") # New folder for CSVs
# Let's make the CSV filename timestamped to keep versions if you run it multiple times
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_FILENAME = f"classification_review_{timestamp}.csv"

# Define the keys from P1_LITE_SCHEMA we want as columns in the CSV
# This also helps define the order of columns for these fields
P1_LITE_CLASSIFICATION_KEYS = [
    "primary_category",
    "document_type_tags",
    "target_roles",
    "relevant_plant_areas_or_equipment",
    "is_safety_critical",
    "detected_language",
    "brief_summary",
    # For nested key_entities_simple, we'll flatten them
    "machines_components", # from key_entities_simple.machines_components
    "materials_products",  # from key_entities_simple.materials_products
    "llm_notes_or_confidence"
]

def main():
    print(f"🚀 Starting Classification Export to CSV...")
    
    # Ensure CSV output folder exists
    os.makedirs(CSV_OUTPUT_FOLDER, exist_ok=True)
    
    csv_output_path = os.path.join(CSV_OUTPUT_FOLDER, CSV_FILENAME)
    
    print(f"📂 Reading classified JSON files from: {CLASSIFIED_JSON_FOLDER}")
    print(f"💾 Exporting CSV to: {csv_output_path}")
    print("-" * 30)

    if not os.path.isdir(CLASSIFIED_JSON_FOLDER):
        print(f"❌ Error: Source folder for classified JSONs not found: {CLASSIFIED_JSON_FOLDER}")
        print("   Please ensure the path is correct and that classify_docs_p1.py has produced output.")
        return

    all_rows_data = [] # To store dictionaries, each representing a row in the CSV

    # Define the full list of headers for the CSV
    # We'll have some standard columns, then the classification keys
    csv_headers = [
        "source_json_filename",       # e.g., MyDoc.pdf.HASH123.json
        "original_document_name",     # e.g., MyDoc_normalized.pdf (from within the JSON)
        "ingestion_timestamp",      # e.g., 2023-10-01T12:00:00Z (from the JSON)
        "classification_status",      # e.g., success, llm_processing_error
    ] + P1_LITE_CLASSIFICATION_KEYS   # Add all the keys from our schema list
    # We can add more specific error message columns if needed later

    # === Loop through classified JSON files ===
    file_count = 0
    for json_filename in os.listdir(CLASSIFIED_JSON_FOLDER):
        if json_filename.endswith(".json"):
            file_count += 1
            print(f"  Processing classified file ({file_count}): {json_filename}")
            file_path = os.path.join(CLASSIFIED_JSON_FOLDER, json_filename)
            
            row_data = {} # Initialize a dictionary for the current CSV row
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    document_data = json.load(f)

                # Populate standard columns
                row_data["source_json_filename"] = json_filename
                # Use normalized_identifier if present, else file_name from the JSON content
                row_data["original_document_name"] = document_data.get("normalized_identifier", document_data.get("file_name", "Unknown"))
                row_data["ingestion_timestamp"] = document_data.get("ingestion_timestamp", "")
                row_data["classification_status"] = document_data.get("classification_p1_lite_status", "status_unknown")

                classifications = document_data.get("classifications_p1_lite")

                if isinstance(classifications, dict) and "error" not in classifications:
                    for key in P1_LITE_CLASSIFICATION_KEYS:
                        if key == "machines_components":
                            value = classifications.get("key_entities_simple", {}).get("machines_components", [])
                        elif key == "materials_products":
                            value = classifications.get("key_entities_simple", {}).get("materials_products", [])
                        else:
                            value = classifications.get(key)

                        # Convert lists to comma-separated strings for CSV readability
                        if isinstance(value, list):
                            row_data[key] = ", ".join(str(v) for v in value) if value else ""
                        elif isinstance(value, bool):
                            row_data[key] = str(value) # "True" or "False"
                        elif value is None:
                            row_data[key] = "" # Empty string for None
                        else:
                            row_data[key] = str(value) # Ensure it's a string
                
                elif isinstance(classifications, dict) and "error" in classifications:
                    # If an error was stored in classifications_p1_lite
                    row_data["primary_category"] = f"ERROR: {classifications.get('error')}"
                    # Fill other classification keys with empty strings or a note
                    for key in P1_LITE_CLASSIFICATION_KEYS:
                        if key not in row_data: # Avoid overwriting primary_category if it was the error field
                            row_data[key] = "N/A due to LLM/parsing error"
                    # You could also add a specific column for "raw_llm_error_response" if classifications.get('raw_response') exists
                
                else: # classifications_p1_lite is missing or not a dict
                    print(f"    [warn] 'classifications_p1_lite' data missing or not a dict in {json_filename}")
                    for key in P1_LITE_CLASSIFICATION_KEYS:
                        row_data[key] = "Data missing"
                
                all_rows_data.append(row_data)

            except json.JSONDecodeError:
                print(f"    [error] Failed to decode JSON from: {json_filename}")
                row_data = {"source_json_filename": json_filename, "classification_status": "json_decode_error"}
                for key in P1_LITE_CLASSIFICATION_KEYS: row_data[key] = "JSON Decode Error"
                all_rows_data.append(row_data)
            except Exception as e:
                print(f"    [error] Unexpected error processing file {json_filename}: {e}")
                row_data = {"source_json_filename": json_filename, "classification_status": "script_processing_error"}
                for key in P1_LITE_CLASSIFICATION_KEYS: row_data[key] = f"Script Error: {e}"
                all_rows_data.append(row_data)
    # === End of Loop ===

    # === Write data to CSV ===
    if all_rows_data: # Check if there's any data to write
        try:
            with open(csv_output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=csv_headers, extrasaction='ignore')
                # extrasaction='ignore' means if a row_data dict has more keys than csv_headers, those extra keys are ignored.
                # This shouldn't happen if we populate row_data carefully based on csv_headers.

                writer.writeheader() # Write the header row
                writer.writerows(all_rows_data) # Write all the data rows
            print(f"    Successfully wrote {len(all_rows_data)} rows to {csv_output_path}")
        except IOError:
            print(f"    [error] I/O error writing to CSV file: {csv_output_path}")
        except Exception as e:
            print(f"    [error] Unexpected error writing CSV file: {e}")
    else:
        print("    [info] No data was prepared for CSV export. CSV file not created.")
    # === End of CSV Writing ===

    print("-" * 30)
    print(f"✅ CSV export completed: {csv_output_path}")
    print(f"Total documents processed into CSV: {len(all_rows_data)}")
    print("🏁 Script finished.")

if __name__ == "__main__":
    main()