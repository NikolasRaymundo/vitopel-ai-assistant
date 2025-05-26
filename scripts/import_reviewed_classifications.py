import os
import json
import csv
from datetime import datetime
import argparse

# --- Configuration ---
# Establish the project root based on this script's location
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

CLASSIFIED_JSON_SRC_FOLDER = os.path.join(PROJECT_ROOT, "data", "classified_texts_p1")
REVIEWED_JSON_DEST_FOLDER = os.path.join(PROJECT_ROOT, "data", "classified_texts_p1_reviewed")
DEFAULT_INPUT_CSV_DIR = os.path.join(PROJECT_ROOT, "data", "review_exports")

# Define the keys from P1_LITE_SCHEMA that are expected in the CSV
# These are the fields that can be updated from the CSV.
P1_LITE_CLASSIFICATION_KEYS = [
    "primary_category",
    "document_type_tags",
    "target_roles",
    "relevant_plant_areas_or_equipment",
    "is_safety_critical",
    "detected_language",
    "brief_summary",
    "machines_components", # from key_entities_simple.machines_components
    "materials_products",  # from key_entities_simple.materials_products
    "llm_notes_or_confidence"
]

# Keys that represent lists of strings and are stored as comma-separated strings in the CSV
LIST_KEYS = [
    "document_type_tags",
    "target_roles",
    "relevant_plant_areas_or_equipment",
    "machines_components",
    "materials_products"
]

# Keys that represent boolean values
BOOLEAN_KEYS = [
    "is_safety_critical"
]

def parse_list_from_csv_string(csv_string):
    """Converts a comma-separated string from CSV into a list of strings."""
    if not csv_string or csv_string.strip() == "":
        return []
    return [item.strip() for item in csv_string.split(',')]

def parse_boolean_from_csv_string(csv_string):
    """Converts a string like 'True' or 'False' from CSV into a boolean."""
    if isinstance(csv_string, bool): # Already a boolean
        return csv_string
    if csv_string is None:
        return None # Or False, depending on desired behavior for empty/None
    return csv_string.strip().lower() == 'true'

def main(input_csv_file):
    print(f"🚀 Starting Import of Reviewed Classifications...")
    print(f"📂 Input CSV file: {input_csv_file}")
    print(f"📁 Source JSONs from: {CLASSIFIED_JSON_SRC_FOLDER}")
    print(f"💾 Destination for reviewed JSONs: {REVIEWED_JSON_DEST_FOLDER}")
    print("-" * 30)

    # Ensure output directory exists
    os.makedirs(REVIEWED_JSON_DEST_FOLDER, exist_ok=True)

    if not os.path.isfile(input_csv_file):
        print(f"❌ Error: Input CSV file not found: {input_csv_file}")
        return

    if not os.path.isdir(CLASSIFIED_JSON_SRC_FOLDER):
        print(f"❌ Error: Source folder for classified JSONs not found: {CLASSIFIED_JSON_SRC_FOLDER}")
        return

    processed_rows_count = 0
    updated_files_count = 0
    error_count = 0

    # === Read CSV and Process Rows ===
    try:
        with open(input_csv_file, 'r', encoding='utf-8', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Check if all expected classification keys are in the CSV header
            # This is a soft check; missing keys in CSV will result in those fields not being updated.
            csv_fieldnames = reader.fieldnames if reader.fieldnames else []
            missing_keys_in_csv = [key for key in P1_LITE_CLASSIFICATION_KEYS if key not in csv_fieldnames]
            if missing_keys_in_csv:
                print(f"    [info] The following classification keys are not present in the CSV header and will not be updated: {', '.join(missing_keys_in_csv)}")

            if "source_json_filename" not in csv_fieldnames:
                print(f"❌ Error: Crucial column 'source_json_filename' not found in CSV header. Cannot proceed.")
                return

            for row_index, row in enumerate(reader):
                processed_rows_count += 1
                source_json_filename = row.get("source_json_filename")

                if not source_json_filename:
                    print(f"    [warn] Row {row_index + 2}: Missing 'source_json_filename'. Skipping row.")
                    error_count +=1
                    continue

                source_json_path = os.path.join(CLASSIFIED_JSON_SRC_FOLDER, source_json_filename)
                dest_json_path = os.path.join(REVIEWED_JSON_DEST_FOLDER, source_json_filename)

                print(f"  Processing row {row_index + 2} for: {source_json_filename}")

                if not os.path.exists(source_json_path):
                    print(f"    [error] Source JSON file not found: {source_json_path}. Skipping.")
                    error_count += 1
                    continue
                
                try:
                    with open(source_json_path, 'r', encoding='utf-8') as f_json:
                        document_data = json.load(f_json)
                    
                    # Ensure 'classifications_p1_lite' exists
                    if "classifications_p1_lite" not in document_data or not isinstance(document_data["classifications_p1_lite"], dict):
                        document_data["classifications_p1_lite"] = {} # Initialize if missing or wrong type
                    
                    # Remove any previous error field to ensure updates take precedence
                    if "error" in document_data["classifications_p1_lite"]:
                        del document_data["classifications_p1_lite"]["error"]
                    
                    # Ensure 'key_entities_simple' exists if we have keys that map to it
                    if any(key in P1_LITE_CLASSIFICATION_KEYS for key in ["machines_components", "materials_products"]):
                         if "key_entities_simple" not in document_data["classifications_p1_lite"] or \
                            not isinstance(document_data["classifications_p1_lite"]["key_entities_simple"], dict):
                            document_data["classifications_p1_lite"]["key_entities_simple"] = {}


                    # --- TODO: Implement the detailed update logic here. ---
                    # For each key in P1_LITE_CLASSIFICATION_KEYS:
                    #   1. Get the value from the CSV row using row.get(key).
                    #      Handle cases where a key might be missing in the CSV row (e.g. if the CSV is older/different).
                    #   2. If the key is in LIST_KEYS, parse it using parse_list_from_csv_string.
                    #   3. Else if the key is in BOOLEAN_KEYS, parse it using parse_boolean_from_csv_string.
                    #   4. For 'machines_components' and 'materials_products':
                    #      Store the parsed value in document_data["classifications_p1_lite"]["key_entities_simple"][key].
                    #   5. For other keys:
                    #      Store the parsed/original value in document_data["classifications_p1_lite"][key].
                    #   6. Handle None values from CSV appropriately (e.g., store as None, empty string, or skip update).
                    #      The current parse functions handle empty strings to empty lists/None for booleans.
                    # ----------------------------------------------------------
                    
                    # Placeholder for where the loop and update logic will go:
                    for key in P1_LITE_CLASSIFICATION_KEYS:
                        if key in row: # Check if the key exists in the CSV row
                            csv_value = row[key]
                            parsed_value = None

                            if key in LIST_KEYS:
                                parsed_value = parse_list_from_csv_string(csv_value)
                            elif key in BOOLEAN_KEYS:
                                parsed_value = parse_boolean_from_csv_string(csv_value)
                            else:
                                # For other string fields, or if it's a number that should remain string
                                # (like detected_language which could be 'en', 'pt', or brief_summary)
                                # We store it as is, or empty string if None/empty
                                parsed_value = csv_value if csv_value is not None else ""

                            # Assign to the correct place in the JSON structure
                            if key == "machines_components":
                                document_data["classifications_p1_lite"]["key_entities_simple"]["machines_components"] = parsed_value
                            elif key == "materials_products":
                                document_data["classifications_p1_lite"]["key_entities_simple"]["materials_products"] = parsed_value
                            else:
                                document_data["classifications_p1_lite"][key] = parsed_value
                        # else:
                            # print(f"    [info] Key '{key}' not found in CSV row for {source_json_filename}. Field will not be updated.")


                    # Add/update review metadata
                    document_data["review_metadata"] = {
                        "reviewed_by_script": os.path.basename(__file__),
                        "review_timestamp": datetime.now().isoformat(),
                        "review_input_csv": os.path.basename(input_csv_file),
                        "manual_review_status": "completed_from_csv_import" 
                        # Consider adding a CSV column like 'review_disposition' or 'reviewer_notes'
                        # and pulling that into this metadata.
                    }

                    # Write the updated JSON to the destination folder
                    os.makedirs(os.path.dirname(dest_json_path), exist_ok=True) # Should be redundant due to earlier makedirs
                    with open(dest_json_path, 'w', encoding='utf-8') as f_out_json:
                        json.dump(document_data, f_out_json, indent=4, ensure_ascii=False)
                    
                    updated_files_count +=1
                    # print(f"    Successfully updated and saved: {dest_json_path}") # Covered by summary

                except json.JSONDecodeError:
                    print(f"    [error] Failed to decode JSON from: {source_json_path}. Skipping.")
                    error_count += 1
                except KeyError as e:
                    print(f"    [error] KeyError while processing {source_json_filename} (likely missing key in CSV or JSON structure): {e}. Skipping.")
                    error_count += 1
                except Exception as e:
                    print(f"    [error] Unexpected error processing file {source_json_filename}: {type(e).__name__} - {e}. Skipping.")
                    error_count += 1
                    
    except FileNotFoundError:
        print(f"❌ Error: Input CSV file not found at path: {input_csv_file}")
        return # Exit main if CSV not found
    except Exception as e:
        print(f"❌ Error: Failed to read or process CSV file {input_csv_file}: {type(e).__name__} - {e}")
        return # Exit main for other CSV errors

    print("-" * 30)
    print(f"✅ CSV Import Process Completed.")
    print(f"Total rows processed from CSV: {processed_rows_count}")
    print(f"JSON files successfully updated and saved: {updated_files_count}")
    print(f"Errors encountered (see logs above): {error_count}")
    if error_count > 0:
        print(f"⚠️ Please review the errors listed above for files that were not updated.")
    print(f"Reviewed JSONs are in: {REVIEWED_JSON_DEST_FOLDER}")
    print("🏁 Script finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import reviewed classifications from a CSV file and update corresponding JSON files.",
        epilog=f"If no input_csv is provided, the script attempts to find the latest 'classification_review_*.csv' file in {DEFAULT_INPUT_CSV_DIR}."
    )
    parser.add_argument(
        "input_csv",
        nargs='?', # Makes the argument optional
        default=None, # Default value if no argument is provided
        help="Path to the input CSV file containing reviewed classifications."
    )
    # Example for future:
    # parser.add_argument("--source-dir", default=CLASSIFIED_JSON_SRC_FOLDER, help="Override source JSON directory.")
    # parser.add_argument("--dest-dir", default=REVIEWED_JSON_DEST_FOLDER, help="Override destination JSON directory.")

    args = parser.parse_args()
    
    input_csv_to_process = args.input_csv

    if not input_csv_to_process:
        print(f"ℹ️ No input CSV file provided. Attempting to find the latest CSV in {DEFAULT_INPUT_CSV_DIR}...")
        if not os.path.isdir(DEFAULT_INPUT_CSV_DIR):
            print(f"❌ Error: Default CSV directory not found: {DEFAULT_INPUT_CSV_DIR}")
            print(f"   Please create it or provide an explicit path to a CSV file.")
            exit(1) 

        try:
            csv_files = [
                os.path.join(DEFAULT_INPUT_CSV_DIR, f) 
                for f in os.listdir(DEFAULT_INPUT_CSV_DIR) 
                if f.startswith("classification_review_") and f.endswith(".csv") and \
                   os.path.isfile(os.path.join(DEFAULT_INPUT_CSV_DIR, f))
            ]
            if not csv_files:
                print(f"❌ Error: No 'classification_review_*.csv' files found in {DEFAULT_INPUT_CSV_DIR}.")
                exit(1)
            
            # Sort files by modification time to get the latest
            # This is more robust than sorting by filename if timestamps aren't perfectly sortable strings
            latest_csv_file = max(csv_files, key=os.path.getmtime)
            input_csv_to_process = latest_csv_file
            print(f"👍 Found latest CSV (by modification time): {input_csv_to_process}")
        except Exception as e:
            print(f"❌ Error: Could not automatically find the latest CSV: {e}")
            exit(1)

    main(input_csv_to_process)
