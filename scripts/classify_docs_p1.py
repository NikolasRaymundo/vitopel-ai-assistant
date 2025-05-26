# scripts/classify_docs_p1.py

import os
import json
# We will add the google.generativeai import in the next step
import google.generativeai as genai # For Gemini API
from dotenv import load_dotenv
import time
from datetime import datetime
import hashlib

# --- Configuration ---
# First, establish the project root based on the script's location
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

PROCESSED_TEXTS_FOLDER = os.path.join(project_root, "data", "processed_texts")
CLASSIFIED_OUTPUT_FOLDER = os.path.join(project_root, "data", "classified_texts_p1")
CLASSIFICATION_MANIFEST_FILE = os.path.join(project_root, "data", "classification_p1_manifest.json")
GOOGLE_API_KEY_NAME = "GOOGLE_API_KEY" # Name of the key in your .env file

# Ensure the output folder exists
os.makedirs(CLASSIFIED_OUTPUT_FOLDER, exist_ok=True)

# Load environment variables (like your API key from .env file in the project root)
# Construct the absolute path to the .env file in the project's root directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=dotenv_path)

# Configure the Gemini API client
try:
    google_api_key = os.getenv(GOOGLE_API_KEY_NAME)
    if not google_api_key:
        raise ValueError(f"'{GOOGLE_API_KEY_NAME}' not found. \n"
                         f"Ensure it's in your .env file located at: {dotenv_path}\n"
                         f"And that the .env file has the line: GOOGLE_API_KEY=your_actual_key")
    genai.configure(api_key=google_api_key)
    print("✅ Google AI SDK configured successfully.")
except Exception as e:
    print(f"❌ Error configuring Google AI SDK: {e}")
    print("   Please ensure your GOOGLE_API_KEY is correctly set in a .env file in the project root.")
    exit() # Critical to have API access

print("-" * 30) # Separator

# --- P1 Lite Classification Schema (Our Target Output from LLM) ---
# This is a reference for the structure we want the LLM to generate.
# We will build a prompt to ask the LLM to fill these fields based on document text.
P1_LITE_SCHEMA_EXAMPLE = {
    "primary_category": "Maintenance", # Example: "Maintenance", "Operations", "Safety", "Quality", "Logistics", "General Procedure", "Technical Document"
    "document_type_tags": ["SOP", "Manual"], # Example: ["SOP", "Manual"], ["Report", "Log"], ["Policy"]
    "target_roles": ["Technician", "Engineer"], # Example: ["Operator", "Technician", "Engineer", "All Employees"]
    "relevant_plant_areas_or_equipment": ["Linha 5", "Cortadeira M5"], # Example: ["Linha 5", "Chill Roll", "General Plant"]
    "is_safety_critical": False, # Boolean
    "detected_language": "pt", # "pt", "en", "mixed"
    "brief_summary": "This document outlines the standard operating procedure for the M5 tensioner unit.", # 1-2 sentence summary
    "key_entities_simple": { # Simple, high-value entity extraction
        "machines_components": ["M5 Tensioner", "Control Panel X2"], # Specific machine names or components
        "materials_products": [] # Specific material codes, product names
    },
    "llm_notes_or_confidence": "High confidence on category and type." # Optional: LLM's own notes about its classification or confidence
}
print("ℹ️ P1 Lite Classification Schema defined (for reference).")
print("-" * 30)

# (This should be after your P1_LITE_SCHEMA_EXAMPLE block)

# --- Manifest Handling Functions ---
def load_classification_manifest():
    """Loads the classification manifest if it exists and is valid JSON."""
    if os.path.exists(CLASSIFICATION_MANIFEST_FILE):
        try:
            with open(CLASSIFICATION_MANIFEST_FILE, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
                print(f"[info] Loaded existing classification manifest from {CLASSIFICATION_MANIFEST_FILE}")
                return manifest_data
        except json.JSONDecodeError:
            print(f"[warn] Classification manifest file {CLASSIFICATION_MANIFEST_FILE} is corrupted. Starting with a new one.")
            return {} 
        except Exception as e:
            print(f"[warn] Could not load classification manifest file {CLASSIFICATION_MANIFEST_FILE}: {e}. Starting new.")
            return {}
    else:
        print(f"[info] No classification manifest file found at {CLASSIFICATION_MANIFEST_FILE}. A new one will be created.")
        return {}

def save_classification_manifest(manifest_data):
    """Saves the provided manifest data to the classification manifest file."""
    try:
        # Ensure the 'data' directory (or whatever parent dir CLASSIFICATION_MANIFEST_FILE is in) exists
        os.makedirs(os.path.dirname(CLASSIFICATION_MANIFEST_FILE), exist_ok=True) 
        with open(CLASSIFICATION_MANIFEST_FILE, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, indent=4, ensure_ascii=False) # Use indent=4 for readability
        print(f"[info] Classification manifest saved to {CLASSIFICATION_MANIFEST_FILE}")
    except Exception as e:
        print(f"[error] Could not save classification manifest to {CLASSIFICATION_MANIFEST_FILE}: {e}")

def cleanup_orphaned_classified_files(classified_folder_path, active_manifest):
    """
    Deletes JSON files from classified_folder_path that are not listed as
    'output_classified_filename' in the active_manifest.
    """
    print("--- Starting Cleanup of Orphaned Classified JSON Files ---")
    if not active_manifest:
        print("    [info] Classification manifest is empty. No cleanup performed (or all files would be considered orphaned).")
        return

    active_classified_filenames = set()
    for manifest_key, entry_data in active_manifest.items():
        if isinstance(entry_data, dict) and "output_classified_filename" in entry_data:
            active_classified_filenames.add(entry_data["output_classified_filename"])
        else:
            # This might happen if an entry was for a skipped_no_text file and we didn't give it an output_classified_filename
            # or if an error entry was made without it.
            print(f"    [info] Manifest entry for key '{manifest_key}' is missing 'output_classified_filename' or not a dict, skipping for active file list. Value: {entry_data}")

    if not active_classified_filenames:
        print("    [info] No active classified filenames found in manifest. No cleanup performed.")
        return

    deleted_count = 0
    found_json_files_in_folder = 0
    try:
        if not os.path.isdir(classified_folder_path):
            print(f"    [warn] Classified output folder {classified_folder_path} not found. No cleanup performed.")
            return

        for filename in os.listdir(classified_folder_path):
            if filename.endswith(".json"): # Only consider JSON files
                found_json_files_in_folder += 1
                if filename not in active_classified_filenames:
                    fpath_to_delete = os.path.join(classified_folder_path, filename)
                    try:
                        os.remove(fpath_to_delete)
                        print(f"    [cleanup] Deleted orphaned classified JSON: {filename}")
                        deleted_count += 1
                    except Exception as e:
                        print(f"    [warn] Could not delete orphaned classified JSON '{filename}': {e}")
    except Exception as e:
        print(f"    [error] An error occurred listing files for cleanup in {classified_folder_path}: {e}")

    print(f"--- Finished Cleanup: Found {found_json_files_in_folder} JSON files in '{os.path.basename(classified_folder_path)}', deleted {deleted_count} orphaned files. ---")

def hash_text_content(text_content: str) -> str:
    """Computes a SHA256 hash of the given text content."""
    if text_content is None: # Should not happen if we check before calling, but good for robustness
        return "" 
    return hashlib.sha256(text_content.encode('utf-8')).hexdigest()

# --- Function to Get Classifications from Gemini API ---
def get_document_classifications(doc_text_content, model_name='gemini-1.5-flash-latest'):
    """
    Sends document text to a Gemini model and asks for classifications
    based on the P1 Lite Schema.

    Args:
        doc_text_content (str): The text content of the document to classify.
        model_name (str): The Gemini model to use.

    Returns:
        dict or None: A dictionary with the classifications if successful and JSON parsing works,
                      a dictionary with an error message if JSON parsing fails,
                      or None if the API call itself fails or returns no text.
    """
    print(f"📄 Attempting to classify document content (first 100 chars): '{doc_text_content[:100].replace('\n', ' ')}...'")
    
    try:
        model = genai.GenerativeModel(model_name)

        # Define the structure we want for the JSON output, using our schema as a guide
        json_structure_guidance = """
        {
            "primary_category": "string (e.g., Maintenance, Operations, Safety, Quality, Logistics, General Procedure, Technical Document)",
            "document_type_tags": ["string", "string"],
            "target_roles": ["string", "string"],
            "relevant_plant_areas_or_equipment": ["string", "string"],
            "is_safety_critical": "boolean (true or false)",
            "detected_language": "string (e.g., pt, en, mixed)",
            "brief_summary": "string (1-2 sentence summary)",
            "key_entities_simple": {
                "machines_components": ["string", "string"],
                "materials_products": ["string", "string"]
            },
            "llm_notes_or_confidence": "string (any notes on confidence or ambiguity)"
        }
        """

        # Truncate doc_text_content if it's excessively long for this initial document-level classification.
        max_text_chars = 28000 # Approx 7000 tokens, leaving room for the rest of the prompt.
        truncated_info = ""
        if len(doc_text_content) > max_text_chars:
            doc_text_content_for_prompt = doc_text_content[:max_text_chars]
            truncated_info = "\n[INFO: Document text was truncated for this analysis due to length.]"
        else:
            doc_text_content_for_prompt = doc_text_content

        # Construct the single prompt string asking for JSON
        prompt = (
            f"Analyze the following document text and return a single, valid JSON object"
            f" containing classifications based on the structure and examples provided below. "
            f"Do not include any explanatory text or markdown formatting (like ```json or ```) before or after the JSON object.\n\n"
            f"Desired JSON Structure and examples:\n{json_structure_guidance}\n\n"
            f"Document Text:\n"
            f"---------------------\n"
            f"{doc_text_content_for_prompt}\n"
            f"---------------------\n"
            f"Provide your classifications as a single, valid JSON object only:{truncated_info}"
        )
        
        print(f"   Sending prompt to {model_name} (prompt text approx length: {len(prompt)} chars)...")
        
        response = model.generate_content(prompt) # Use the single 'prompt' string
            
        time.sleep(1) # Polite delay

        if response.text:
            print(f"✅ Raw classification text received from {model_name}.")
            clean_text = response.text.strip()
            # Attempt to remove markdown backticks if the model still adds them
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            
            clean_text = clean_text.strip() # Strip again after potential ``` removal

            try:
                classified_data = json.loads(clean_text)
                print(f"   Successfully parsed JSON classification.")
                return classified_data 
            except json.JSONDecodeError as json_e:
                print(f"   [WARN] Failed to parse LLM response as JSON: {json_e}")
                print(f"   Raw LLM Text was: '{response.text}'") # Show the problematic text
                return {"error": "Failed to parse LLM response as JSON", "raw_response": response.text}
            except Exception as e: # Catch any other unexpected parsing error
                print(f"   [WARN] An unexpected error occurred during JSON parsing: {e}")
                print(f"   Raw LLM Text was: '{response.text}'")
                return {"error": "Unexpected error during JSON parsing", "raw_response": response.text}
        else:
            print(f"⚠️ Classification attempt for document SUCCEEDED, but got an empty text response from {model_name}.")
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                print(f"   Prompt Feedback: {response.prompt_feedback}")
            return {"error": "Empty response from LLM"}

    except Exception as e: # Catch errors from the model instantiation or generate_content call
        print(f"❌ Classification attempt FAILED for document: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'):
             print(f"   Prompt Feedback from error: {e.response.prompt_feedback}")
        elif hasattr(e, 'message'): # Some Google API errors have a 'message' attribute
             print(f"   Error message: {e.message}")
        return None # Indicates a failure in the API call itself
    finally:
        print("-" * 30)


# --- Function to Test Gemini API Connection ---
def test_gemini_connection():
    """
    Sends a simple test prompt to the configured Gemini model to verify connection.
    """
    print("🧪 Testing Gemini API connection...")
    try:
        # Model choice: 'gemini-1.0-pro-latest' is a balanced option.
        # 'gemini-1.5-flash-latest' is faster & cheaper for simpler tasks.
        # 'gemini-1.5-pro-latest' is most capable but potentially more expensive.
        # See available models: https://ai.google.dev/models/gemini
        model_name = 'gemini-1.5-flash-latest' # can be changed later
        model = genai.GenerativeModel(model_name)
        print(f"   Using model: {model_name}")

        prompt = "Hello! Briefly introduce yourself as an AI model from Google, and state your model name."
        response = model.generate_content(prompt)

        if response.text:
            print("✅ Gemini API Connection Test SUCCESSFUL!")
            print(f"   Model's response: {response.text[:150]}...") # Print first 150 chars
        else:
            print("⚠️ Gemini API Connection Test SUCCEEDED, but got an empty response.")
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                print(f"   Prompt Feedback: {response.prompt_feedback}")
            else:
                print(f"   No text in response and no specific prompt feedback.")

    except Exception as e:
        print(f"❌ Gemini API Connection Test FAILED: {e}")
        # Attempt to print more detailed error information if available
        if hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'):
             print(f"   Prompt Feedback from error: {e.response.prompt_feedback}")
        elif hasattr(e, 'message'): # Some Google API errors have a 'message' attribute
             print(f"   Error message: {e.message}")

    print("-" * 30)

# --- Main execution block ---
if __name__ == "__main__":
    print(f"🚀 Starting {os.path.basename(__file__)}...")
    print(f"📂 Looking for processed JSON files in: {PROCESSED_TEXTS_FOLDER}")
    print(f"💾 Classified files will be saved to: {CLASSIFIED_OUTPUT_FOLDER}")
    print(f"📖 Using manifest file: {CLASSIFICATION_MANIFEST_FILE}")
    print("-" * 30)

    # Load the classification manifest
    classification_manifest = load_classification_manifest()
    new_classification_manifest = {} # To build the manifest for the current run

    # Counters for summary
    total_files_found = 0
    processed_this_run_count = 0
    skipped_count = 0
    failed_classification_count = 0
    skipped_no_text_count = 0

    if not os.path.isdir(PROCESSED_TEXTS_FOLDER):
        print(f"❌ Error: Source folder for processed texts not found: {PROCESSED_TEXTS_FOLDER}")
        print("   Please ensure the path is correct and the Phase 1 output (ingested JSONs) exists.")
        exit()

    # Iterate through files in the processed_texts folder
    for filename in os.listdir(PROCESSED_TEXTS_FOLDER):
        if filename.endswith(".json"):
            total_files_found += 1
            print(f"\n📄 Considering file #{total_files_found}: {filename}...")
            
            source_file_path = os.path.join(PROCESSED_TEXTS_FOLDER, filename)
            # Output filename for the classified JSON is the same as the input JSON filename
            # but in the CLASSIFIED_OUTPUT_FOLDER
            output_file_path = os.path.join(CLASSIFIED_OUTPUT_FOLDER, filename) 
            
            manifest_key = filename # Use the filename from processed_texts as the key

            try:
                with open(source_file_path, 'r', encoding='utf-8') as f:
                    document_data = json.load(f)
                
                doc_text = document_data.get("text")

                if not doc_text or not isinstance(doc_text, str) or not doc_text.strip():
                    print(f"   ⚠️ Skipping classification for {filename}: No valid text content found.")
                    document_data["classification_p1_lite_status"] = "skipped_no_text_content"
                    # Save the JSON with the status even if skipped
                    with open(output_file_path, 'w', encoding='utf-8') as f_out:
                        json.dump(document_data, f_out, indent=4, ensure_ascii=False)
                    skipped_no_text_count += 1
                    # Add to new manifest with a specific status if desired, or omit
                    # For now, we'll omit from manifest if no text to classify.
                    continue

                current_text_hash = hash_text_content(doc_text)

                # Manifest Check:
                # Skip if:
                # 1. Key is in manifest
                # 2. Stored text hash matches current text hash
                # 3. The output classified file (referenced in manifest) actually exists
                entry_in_manifest = classification_manifest.get(manifest_key)
                output_file_should_exist = False
                if entry_in_manifest and entry_in_manifest.get("source_text_hash") == current_text_hash:
                    # Check if the output file from the manifest still exists
                    # The manifest stores the output filename which is same as manifest_key
                    expected_output_classified_file = os.path.join(CLASSIFIED_OUTPUT_FOLDER, entry_in_manifest.get("output_classified_filename", manifest_key))
                    if os.path.exists(expected_output_classified_file):
                        output_file_should_exist = True

                if output_file_should_exist:
                    print(f"   [skip] Content of '{filename}' is unchanged and output file exists (manifest).")
                    new_classification_manifest[manifest_key] = entry_in_manifest # Carry over old entry
                    skipped_count += 1
                    continue # Skip to the next file
                
                # If not skipped, proceed with classification
                if entry_in_manifest and entry_in_manifest.get("source_text_hash") == current_text_hash and not output_file_should_exist:
                    print(f"   [process] Content of '{filename}' is unchanged but output file was missing. Re-classifying.")
                else: # New file or changed content
                    print(f"   [process] New or changed content for '{filename}'. Classifying...")

                classification_result = get_document_classifications(doc_text) # API call

                if classification_result:
                    if "error" not in classification_result:
                        document_data["classifications_p1_lite"] = classification_result
                        document_data["classification_p1_lite_status"] = "success"
                        
                        # Save enriched JSON to CLASSIFIED_OUTPUT_FOLDER
                        with open(output_file_path, 'w', encoding='utf-8') as f_out:
                            json.dump(document_data, f_out, indent=4, ensure_ascii=False)
                        print(f"   ✅ Successfully classified and saved: {output_file_path}")
                        
                        new_classification_manifest[manifest_key] = {
                            "source_text_hash": current_text_hash,
                            "output_classified_filename": filename, # filename in CLASSIFIED_OUTPUT_FOLDER
                            "classified_at": datetime.now().isoformat(),
                            "status": "classified"
                        }
                        processed_this_run_count += 1
                    else: # Error dictionary from get_document_classifications (e.g., JSON parse error)
                        document_data["classifications_p1_lite"] = classification_result # Store error info
                        document_data["classification_p1_lite_status"] = "llm_processing_error"
                        with open(output_file_path, 'w', encoding='utf-8') as f_out:
                            json.dump(document_data, f_out, indent=4, ensure_ascii=False)
                        print(f"   🟡 Classification for {filename} resulted in an error structure from LLM: {classification_result.get('error')}")
                        failed_classification_count += 1
                else: # API call itself failed (get_document_classifications returned None)
                    document_data["classification_p1_lite_status"] = "api_call_failed"
                    with open(output_file_path, 'w', encoding='utf-8') as f_out:
                        json.dump(document_data, f_out, indent=4, ensure_ascii=False)
                    print(f"   ❌ Classification API call failed for: {filename}")
                    failed_classification_count += 1

            except FileNotFoundError:
                print(f"   ❌ Error: Source JSON file not found {source_file_path}. Might have been moved/deleted.")
                failed_classification_count += 1 # Count as a failure for this file
            except json.JSONDecodeError:
                print(f"   ❌ Error: Could not decode JSON from {source_file_path}.")
                failed_classification_count += 1
            except Exception as e:
                print(f"   ❌ An unexpected error occurred processing {filename}: {e}")
                failed_classification_count += 1
                # Optionally, attempt to save an error status to the output file
                try:
                    error_data_structure = {"error_processing_file": str(e), "classification_p1_lite_status": "script_error"}
                    # If document_data was loaded, add error to it, else create new
                    if 'document_data' in locals():
                        document_data["classification_p1_lite_error"] = str(e)
                        document_data["classification_p1_lite_status"] = "script_error"
                        data_to_write = document_data
                    else:
                        data_to_write = error_data_structure
                    with open(output_file_path, 'w', encoding='utf-8') as f_out:
                        json.dump(data_to_write, f_out, indent=4, ensure_ascii=False)
                except Exception as e_save:
                    print(f"      Additionally, failed to save error file for {filename}: {e_save}")

    # Save the new manifest for this run
    save_classification_manifest(new_classification_manifest)
    # Clean up orphaned classified JSON files from CLASSIFIED_OUTPUT_FOLDER
    cleanup_orphaned_classified_files(CLASSIFIED_OUTPUT_FOLDER, new_classification_manifest)
   
    print("-" * 30)
    print("📊 Classification Run Summary:")
    print(f"  Total JSON files found in '{PROCESSED_TEXTS_FOLDER}': {total_files_found}")
    print(f"  Processed and classified this run: {processed_this_run_count}")
    print(f"  Skipped (unchanged, output exists): {skipped_count}")
    print(f"  Skipped (no text content): {skipped_no_text_count}")
    if failed_classification_count > 0:
        print(f"  Failed classification attempts: {failed_classification_count}")
    print("🏁 Script finished.")