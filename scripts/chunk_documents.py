import os
import json
# import re # Removed as not currently used
import argparse
# import uuid # Removed as not currently used
import hashlib
from datetime import datetime # Moved to top-level imports

# --- Configuration ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Default input, can be overridden by command-line arg
DEFAULT_CLASSIFIED_JSON_INPUT_FOLDER = os.path.join(PROJECT_ROOT, "data", "classified_texts_p1_reviewed")
# Alternative input folder (if reviewed data isn't available yet)
FALLBACK_CLASSIFIED_JSON_INPUT_FOLDER = os.path.join(PROJECT_ROOT, "data", "classified_texts_p1")

CHUNK_OUTPUT_FOLDER = os.path.join(PROJECT_ROOT, "data", "document_chunks")
CHUNK_MANIFEST_FILE = os.path.join(CHUNK_OUTPUT_FOLDER, "_manifest.json") # Manifest file

# Parameters for text-based chunking
TEXT_CHUNK_SIZE = 1000  # Target characters
TEXT_CHUNK_OVERLAP = 150 # Characters overlap

# Parameters for table-based chunking
TABLE_TEXT_SINGLE_CHUNK_THRESHOLD = 2000 # Characters
TABLE_ROWS_PER_CHUNK = 10 # Default rows per chunk for large tables

# Define file types
TEXT_FILE_TYPES = ["pdf", "docx", "pptx", "txt", "md", "html", "xml", "json", "py", "js", "java", "c", "cpp", "h"] # Expanded list
TABLE_FILE_TYPES = ["xlsx", "csv", "ods"]

# --- Manifest Helper Functions ---
def load_manifest(manifest_path):
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"    [warn] Manifest file {manifest_path} is corrupted. Starting with a new one.")
            return {}
    return {}

def save_manifest(manifest_path, manifest_data):
    try:
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, indent=4)
    except IOError as e:
        print(f"    [error] Could not save manifest {manifest_path}: {e}")

def get_document_processing_signature(document_data, text_chunk_size, text_chunk_overlap, table_threshold, table_rows_per_chunk):
    """Creates a hash signature based on relevant document content and chunking parameters."""
    relevant_content = {
        "text": document_data.get("text", ""), # Changed from "text_content"
        "file_type": document_data.get("file_type", "").lower()
    }
    parameters = {
        "text_chunk_size": text_chunk_size,
        "text_chunk_overlap": text_chunk_overlap,
        "table_threshold": table_threshold,
        "table_rows_per_chunk": table_rows_per_chunk
    }
    # Combine content and parameters into a string for hashing
    signature_string = json.dumps(relevant_content, sort_keys=True) + \
                       json.dumps(parameters, sort_keys=True)
    
    return hashlib.md5(signature_string.encode('utf-8')).hexdigest()

def split_text_recursively(text: str, chunk_size: int, chunk_overlap: int, separators: list[str] = None) -> list[str]:
    """
    Splits text into chunks of a target size with overlap, trying to respect separators.
    The "recursive" aspect refers to trying a list of separators hierarchically.
    The core mechanism is an iterative sliding window.

    Args:
        text: The input string to split.
        chunk_size: The target maximum size of each chunk (in characters).
        chunk_overlap: The number of characters to overlap between consecutive chunks.
        separators: A list of strings to use as separators, in order of preference.
                    Defaults to common text separators like paragraphs, newlines, sentences.

    Returns:
        A list of text chunks.
    """
    if separators is None:
        # Default separators, from coarser (paragraphs) to finer (spaces)
        # The empty string "" can be a conceptual fallback for character-level,
        # but hard cuts at chunk_size handle cases where no listed separator is found.
        separators = ["\n\n", "\n", ". ", "! ", "? ", "; ", ": ", " ", ""]

    if not text or not text.strip():
        return []

    # Ensure chunk_overlap is sensible
    effective_chunk_overlap = chunk_overlap
    if effective_chunk_overlap >= chunk_size:
        # Fallback: if overlap is too large, set to a fraction of chunk_size or 0 if chunk_size is tiny.
        effective_chunk_overlap = chunk_size // 2 if chunk_size > 1 else 0
    if effective_chunk_overlap < 0:
        effective_chunk_overlap = 0

    final_chunks: list[str] = []
    current_pos: int = 0
    text_len: int = len(text)

    while current_pos < text_len:
        # Determine the end of the current window
        window_end_pos: int = min(current_pos + chunk_size, text_len)
        
        # This is the text within our current processing window
        window_text: str = text[current_pos:window_end_pos]
        
        # Assume the chunk will be the entire window (hard cut) unless a better split is found
        actual_chunk_end_in_text: int = window_end_pos

        # Only try to find a better split point if we're not at the very end of the text
        # (i.e., if the window doesn't already go to the end of the text)
        # OR if the window is exactly chunk_size (meaning we might be able to make it smaller via a separator)
        if window_end_pos < text_len or len(window_text) == chunk_size :
            # Iterate through separators by their specified priority
            for sep in separators:
                if not sep:  # Skip empty string separators in this logic
                    continue

                # Look for the last occurrence of this separator within the current window_text.
                # rfind searches from [start, end), so search up to len(window_text).
                # The goal is to make the chunk as long as possible up to chunk_size, ending on a separator.
                sep_occurrence_idx_in_window = window_text.rfind(sep)

                if sep_occurrence_idx_in_window != -1:
                    # Found this separator. The split point is *after* this separator.
                    potential_split_offset_in_window = sep_occurrence_idx_in_window + len(sep)
                    
                    # This split point is valid if it's > 0 (creates a non-empty prefix)
                    # and is within the window.
                    if potential_split_offset_in_window > 0:
                        actual_chunk_end_in_text = current_pos + potential_split_offset_in_window
                        # Found a prioritized separator; use this split point and stop searching for other separators for this window.
                        break 
            # If no separator from the list was found in the window,
            # actual_chunk_end_in_text remains window_end_pos (hard cut).
        
        # Create the actual chunk
        current_chunk_text: str = text[current_pos:actual_chunk_end_in_text]

        if current_chunk_text.strip(): # Add non-empty, stripped chunks
            final_chunks.append(current_chunk_text.strip())

        # If this chunk takes us to the end of the text, we're done
        if actual_chunk_end_in_text >= text_len:
            break
        
        # Determine the starting position of the next chunk, including overlap
        next_chunk_start_pos = actual_chunk_end_in_text - effective_chunk_overlap
        
        # Stall prevention: if the next starting position is not past the current one,
        # it means the chunk created was too short relative to the overlap.
        # This can happen if len(current_chunk_text) <= effective_chunk_overlap.
        if next_chunk_start_pos <= current_pos :
            # print(f"    [debug] Stall detected or small chunk. Chunk len: {len(current_chunk_text)}, Overlap: {effective_chunk_overlap}. Advancing without overlap.")
            # Force progress by starting the next chunk immediately after the current one.
            next_chunk_start_pos = actual_chunk_end_in_text
            # If still no progress (e.g. empty chunk was made, though strip() should prevent this)
            if next_chunk_start_pos <= current_pos:
                 next_chunk_start_pos = current_pos + 1


        current_pos = next_chunk_start_pos
        
        # Safety break for pathological cases (e.g., extremely small chunk_size or odd text)
        # Check if an unreasonable number of chunks are being made.
        if len(final_chunks) > text_len + 10 and text_len > 0: # Heuristic
            print(f"    [warn] Text splitting produced an excessive number of chunks ({len(final_chunks)}) "
                  f"for text length {text_len}. Aborting split for this document and returning as single chunk.")
            return [text.strip()] if text.strip() else []


    # Final filter for any empty strings that might have slipped through (e.g. if original text was just whitespace)
    return [chunk for chunk in final_chunks if chunk]

def split_table_text(table_string, single_chunk_threshold, rows_per_chunk):
    """
    Splits a string representation of a table (from df.to_string()) into chunks.
    Each chunk consists of the table header(s) and a specified number of data rows.
    TODO: Enhance header identification for multi-line headers.
    """
    if not table_string or not table_string.strip():
        return []

    if len(table_string) <= single_chunk_threshold:
        return [table_string]

    lines = table_string.splitlines()
    
    # Filter out lines that are completely empty or just whitespace
    processed_lines = [line for line in lines if line.strip()]

    if not processed_lines:
        return []

    # --- Header Identification ---
    # Simplistic assumption for now: the first non-empty line is the main header.
    # TODO: Enhance header identification for multi-line headers 
    # (e.g., multi-index columns, or index names on separate lines).
    # A more robust method would involve analyzing the structure of several initial lines
    # to determine where the actual data rows begin.
    header_string = processed_lines[0]
    data_row_strings = processed_lines[1:]

    if not data_row_strings:
        # This means the table string had only one non-empty line (or was empty after processing)
        # Treat that single line as a chunk (it's effectively just the header).
        return [header_string]

    # --- Chunking Data Rows with Header ---
    chunks = []
    current_chunk_data_rows = []
    
    for i in range(0, len(data_row_strings), rows_per_chunk):
        current_data_rows_group = data_row_strings[i:i + rows_per_chunk]
        # Each chunk must contain the full header string.
        chunk_content = header_string + "\n" + "\n".join(current_data_rows_group)
        chunks.append(chunk_content)
        
    return chunks


def main(input_folder):
    print(f"🚀 Starting Document Chunking Script...")
    print(f"📂 Input JSON folder: {input_folder}")
    print(f"💾 Output Chunks folder: {CHUNK_OUTPUT_FOLDER}")
    print(f"📖 Manifest file: {CHUNK_MANIFEST_FILE}")
    print("-" * 30)

    if not os.path.isdir(input_folder):
        print(f"❌ Error: Input folder not found: {input_folder}")
        # Attempt to use fallback if default was tried and failed
        if input_folder == DEFAULT_CLASSIFIED_JSON_INPUT_FOLDER and os.path.isdir(FALLBACK_CLASSIFIED_JSON_INPUT_FOLDER):
            print(f"ℹ️ Default input folder not found, attempting fallback: {FALLBACK_CLASSIFIED_JSON_INPUT_FOLDER}")
            input_folder = FALLBACK_CLASSIFIED_JSON_INPUT_FOLDER
            print(f"📂 Using fallback input JSON folder: {input_folder}")
        else:
            return

    os.makedirs(CHUNK_OUTPUT_FOLDER, exist_ok=True)
    manifest_data = load_manifest(CHUNK_MANIFEST_FILE)

    processed_files_count = 0
    skipped_files_count = 0
    total_chunks_created_this_run = 0
    error_count = 0

    source_json_files = [f for f in os.listdir(input_folder) if f.endswith(".json")]

    for json_filename in source_json_files:
        file_path = os.path.join(input_folder, json_filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                document_data = json.load(f)

            current_doc_signature = get_document_processing_signature(
                document_data, TEXT_CHUNK_SIZE, TEXT_CHUNK_OVERLAP, 
                TABLE_TEXT_SINGLE_CHUNK_THRESHOLD, TABLE_ROWS_PER_CHUNK
            )

            manifest_entry = manifest_data.get(json_filename)
            
            # Check manifest and existence of chunks
            if manifest_entry and \
               manifest_entry.get("signature") == current_doc_signature and \
               all(os.path.exists(os.path.join(CHUNK_OUTPUT_FOLDER, cf)) for cf in manifest_entry.get("generated_chunk_files", [])):
                print(f"  ⏭️ Skipping (no changes, chunks exist): {json_filename}")
                skipped_files_count += 1
                continue
            
            # If we're here, we need to process/re-process
            print(f"  📄 Processing document: {json_filename}")
            processed_files_count += 1

            # --- Pre-emptive cleanup of old chunks for this source file ---
            if manifest_entry and "generated_chunk_files" in manifest_entry:
                print(f"     Old version or params found. Deleting {len(manifest_entry['generated_chunk_files'])} old chunks for {json_filename}...")
                for old_chunk_file in manifest_entry["generated_chunk_files"]:
                    old_chunk_path = os.path.join(CHUNK_OUTPUT_FOLDER, old_chunk_file)
                    if os.path.exists(old_chunk_path):
                        try:
                            os.remove(old_chunk_path)
                        except OSError as e:
                            print(f"      [error] Could not delete old chunk {old_chunk_path}: {e}")
            # --- End of pre-emptive cleanup ---


            doc_text = document_data.get("text", "") # Changed from "text_content"
            file_type = document_data.get("file_type", "").lower()
            
            # Identifiers and metadata
            parent_document_identifier = document_data.get("normalized_identifier", json_filename)
            original_filename = document_data.get("file_name", "") # Try to get original_filename
            if not original_filename and "normalized_identifier" in document_data: # If normalized_identifier was used as parent
                 original_filename = document_data.get("normalized_identifier").split('_normalized.')[0] + '.' + document_data.get("file_type","") if '.' in document_data.get("normalized_identifier") else document_data.get("normalized_identifier")


            source_path_in_raw = document_data.get("source_path_in_raw", "")
            
            classifications = document_data.get("classifications_p1_lite", {})
            # Ensure classifications is a dict, even if it's missing or null in source
            if classifications is None:
                classifications = {}


            generated_chunks_text = []
            chunking_strategy_note = "unknown_as_single"

            if file_type in TEXT_FILE_TYPES:
                print(f"     Ribeira text-based splitting strategy for file type: {file_type}")
                generated_chunks_text = split_text_recursively(doc_text, TEXT_CHUNK_SIZE, TEXT_CHUNK_OVERLAP)
                chunking_strategy_note = "text_recursive"
            elif file_type in TABLE_FILE_TYPES:
                print(f"    🈸 Applying table-based splitting strategy for file type: {file_type}")
                generated_chunks_text = split_table_text(doc_text, TABLE_TEXT_SINGLE_CHUNK_THRESHOLD, TABLE_ROWS_PER_CHUNK)
                chunking_strategy_note = "table_rows"
            else:
                print(f"    [warn] Unknown or unsupported file type '{file_type}' for {json_filename}. Treating as single text chunk.")
                # Default to treating as a single text chunk if type is unknown but text_content exists
                if doc_text:
                    generated_chunks_text = [doc_text] 
                else:
                    print(f"    [warn] No text_content found for {json_filename}. Skipping chunk generation for this file.")
                    generated_chunks_text = []


            current_file_chunk_names = []
            for i, chunk_text_content in enumerate(generated_chunks_text):
                chunk_sequence_num = i + 1
                # Sanitize parent_document_identifier for use in filename, remove .json if present
                safe_parent_id_for_filename = parent_document_identifier.replace('.json', '')
                chunk_id = f"{safe_parent_id_for_filename}_chunk_{chunk_sequence_num:03d}"
                
                chunk_data = {
                    "chunk_id": chunk_id,
                    "parent_document_identifier": parent_document_identifier,
                    "original_filename": original_filename, # Inherited
                    "source_path_in_raw": source_path_in_raw, # Inherited
                    "chunk_text": chunk_text_content,
                    "classifications_p1_lite": classifications, # Inherited
                    "chunk_metadata": {
                        "chunk_sequence": chunk_sequence_num,
                        "parent_file_type": file_type,
                        "chunking_strategy": chunking_strategy_note,
                        "source_script": os.path.basename(__file__)
                    }
                }
                
                # Add page numbers or other positional info if available (future enhancement)
                # if "page_number" in chunk_text_content_metadata: # Example
                #    chunk_data["source_page_number"] = chunk_text_content_metadata["page_number"]

                chunk_filename = f"{chunk_id}.json"
                chunk_output_path = os.path.join(CHUNK_OUTPUT_FOLDER, chunk_filename)
                current_file_chunk_names.append(chunk_filename)

                with open(chunk_output_path, 'w', encoding='utf-8') as f_chunk:
                    json.dump(chunk_data, f_chunk, indent=4, ensure_ascii=False)
                total_chunks_created_this_run += 1
            
            if generated_chunks_text:
                print(f"    ✅ Generated {len(generated_chunks_text)} chunks for {json_filename}")

            # Update manifest for this successfully processed file
            manifest_data[json_filename] = {
                "signature": current_doc_signature,
                "generated_chunk_files": current_file_chunk_names,
                "last_processed_timestamp": datetime.now().isoformat() # Added timestamp
            }

        except json.JSONDecodeError:
            print(f"    [error] Failed to decode JSON from: {json_filename}. Skipping.")
            error_count += 1
            if json_filename in manifest_data: del manifest_data[json_filename] # Remove from manifest if error
        except Exception as e:
            print(f"    [error] Unexpected error processing file {json_filename}: {type(e).__name__} - {e}")
            error_count += 1
            if json_filename in manifest_data: del manifest_data[json_filename] # Remove from manifest if error
            import traceback
            traceback.print_exc()
    
    # --- General Orphaned Chunk Cleanup ---
    print("-" * 30)
    print("🧹 Performing cleanup of orphaned chunk files...")
    all_manifested_chunks = set()
    for entry in manifest_data.values():
        for chunk_file in entry.get("generated_chunk_files", []):
            all_manifested_chunks.add(chunk_file)

    orphaned_deleted_count = 0
    if os.path.exists(CHUNK_OUTPUT_FOLDER): # Check if output folder exists
        for item_in_output_dir in os.listdir(CHUNK_OUTPUT_FOLDER):
            if item_in_output_dir.endswith(".json") and item_in_output_dir != os.path.basename(CHUNK_MANIFEST_FILE):
                if item_in_output_dir not in all_manifested_chunks:
                    orphan_path = os.path.join(CHUNK_OUTPUT_FOLDER, item_in_output_dir)
                    try:
                        os.remove(orphan_path)
                        print(f"    🗑️ Deleted orphaned chunk: {item_in_output_dir}")
                        orphaned_deleted_count += 1
                    except OSError as e:
                        print(f"    [error] Could not delete orphaned chunk {orphan_path}: {e}")
    print(f"    Cleanup finished. Deleted {orphaned_deleted_count} orphaned files.")

    save_manifest(CHUNK_MANIFEST_FILE, manifest_data)

    print("-" * 30)
    print(f"✅ Document Chunking Completed.")
    print(f"Total source documents encountered: {len(source_json_files)}")
    print(f"Documents processed/re-processed this run: {processed_files_count}")
    print(f"Documents skipped (no changes): {skipped_files_count}")
    print(f"Total chunks created this run: {total_chunks_created_this_run}")
    print(f"Errors encountered: {error_count}")
    print(f"Chunks saved to: {CHUNK_OUTPUT_FOLDER}")
    print(f"Manifest updated: {CHUNK_MANIFEST_FILE}")
    print("🏁 Script finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Chunks classified JSON documents into smaller pieces. Uses a manifest to skip unchanged files and clean orphans.",
        epilog=f"If --input-folder is not specified, it defaults to {DEFAULT_CLASSIFIED_JSON_INPUT_FOLDER}, then falls back to {FALLBACK_CLASSIFIED_JSON_INPUT_FOLDER} if the default is not found."
    )
    parser.add_argument(
        "--input-folder",
        help=f"Path to the folder containing classified JSON files. Defaults to '{DEFAULT_CLASSIFIED_JSON_INPUT_FOLDER}'.",
        default=DEFAULT_CLASSIFIED_JSON_INPUT_FOLDER
    )
    # Future: Add arguments for chunk_size, overlap, etc. if needed

    args = parser.parse_args()
    main(args.input_folder)
