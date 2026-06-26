#!/usr/bin/env python
"""
Script to compute and store embeddings for the Coursera courses in Firestore.
Uses Vertex AI text-embedding-004 model.
- name_embedding: 128 dimensions (lightweight config)
- description_embedding: 768 dimensions (default config, RETRIEVAL_DOCUMENT task type)
"""

import argparse
import sys
import time
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector

# Add parent directory of backend/crawl_jobs to path if needed
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Load .env file
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"Loaded environment from {env_path}")
else:
    print("Warning: No .env file found.")

from langchain_google_vertexai import VertexAIEmbeddings

COLLECTION_NAME = "learning_material"

def get_firestore_client():
    db_name = os.getenv("FIRESTORE_DATABASE")
    if db_name and db_name != "(default)":
        return firestore.Client(database=db_name)
    return firestore.Client()

def embed_batch_with_retry(embeddings_obj, texts, max_attempts=5, initial_backoff=2):
    """Embeds a list of texts with exponential backoff retry."""
    backoff = initial_backoff
    for attempt in range(max_attempts):
        try:
            return embeddings_obj.embed_documents(texts)
        except Exception as e:
            print(f"Error during embedding (attempt {attempt + 1}/{max_attempts}): {e}")
            if attempt == max_attempts - 1:
                raise
            time.sleep(backoff)
            backoff *= 2

def stream_collection_paginated(col_ref, fields_to_select, page_size=1000):
    """Yields documents from a collection in pages to avoid gRPC stream timeouts."""
    last_doc = None
    while True:
        query = col_ref.order_by("__name__").select(fields_to_select).limit(page_size)
        if last_doc:
            query = query.start_after(last_doc)
        
        docs = list(query.stream())
        if not docs:
            break
            
        for doc in docs:
            yield doc
            
        last_doc = docs[-1]

def main():
    parser = argparse.ArgumentParser(description="Generate embeddings for Coursera learning material in Firestore.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of documents to process.")
    parser.add_argument("--batch-size", type=int, default=30, help="Number of documents to process per batch (default: 30).")
    parser.add_argument("--dry-run", action="store_true", help="Compute embeddings but do not save them to Firestore.")
    parser.add_argument("--force", action="store_true", help="Recompute embeddings even if they already exist in Firestore.")
    args = parser.parse_args()

    db = get_firestore_client()
    print(f"Connected to Firestore project: {db.project}")

    # Initialize embeddings
    print("Initializing Vertex AI embeddings models...")
    try:
        name_embeddings = VertexAIEmbeddings(
            model_name="text-embedding-004",
            dimensions=128
        )
        desc_embeddings = VertexAIEmbeddings(
            model_name="text-embedding-004"
            # Default task_type for embed_documents is RETRIEVAL_DOCUMENT
        )
    except Exception as e:
        print(f"Failed to initialize VertexAIEmbeddings. Make sure your credentials/environment is correct. Error: {e}")
        sys.exit(1)

    col_ref = db.collection(COLLECTION_NAME)
    print(f"Streaming documents from collection '{COLLECTION_NAME}'...")

    # We will fetch document snapshots to determine what needs to be embedded.
    # Note: Stream helps to avoid loading the entire payload of all documents.
    # We use select() to only fetch required fields (name, description, name_embedding, description_embedding)
    # to minimize network overhead and database read bandwidth.
    fields_to_select = ["name", "description"]
    if not args.force:
        fields_to_select.extend(["name_embedding", "description_embedding"])

    doc_stream = stream_collection_paginated(col_ref, fields_to_select, page_size=1000)

    batch_doc_ids = []
    batch_names = []
    batch_descriptions = []

    processed_count = 0
    updated_count = 0
    skipped_count = 0

    print("Scanning collection for documents to process...")

    for doc_snap in doc_stream:
        if args.limit is not None and updated_count >= args.limit:
            print(f"Reached specified limit of {args.limit} updates. Stopping.")
            break

        doc_data = doc_snap.to_dict()
        doc_id = doc_snap.id
        processed_count += 1

        # Check if embeddings already exist and are stored as Firestore native Vectors
        has_embeddings = (
            "name_embedding" in doc_data and doc_data["name_embedding"] is not None and
            "description_embedding" in doc_data and doc_data["description_embedding"] is not None and
            isinstance(doc_data["name_embedding"], Vector) and
            isinstance(doc_data["description_embedding"], Vector)
        )

        if has_embeddings and not args.force:
            skipped_count += 1
            if processed_count % 1000 == 0:
                print(f"Scanned {processed_count} documents. Skipped {skipped_count} already embedded.")
            continue

        name = doc_data.get("name")
        description = doc_data.get("description")

        # Sanitize name and description for embedding. Empty values can cause API errors.
        # Fallback to a space or a generic text if empty.
        name_clean = str(name).strip() if name else " "
        if not name_clean:
            name_clean = " "

        desc_clean = str(description).strip() if description else " "
        if not desc_clean:
            # Fallback to name if description is empty
            desc_clean = name_clean
        # Truncate description to 4000 characters (~800 tokens) to prevent exceeding Vertex AI total request token limits in a batch
        if len(desc_clean) > 4000:
            desc_clean = desc_clean[:4000]

        batch_doc_ids.append(doc_id)
        batch_names.append(name_clean)
        batch_descriptions.append(desc_clean)

        if len(batch_doc_ids) >= args.batch_size:
            # Process the accumulated batch
            print(f"\nProcessing batch of size {len(batch_doc_ids)} (total processed: {processed_count}, updated: {updated_count})...")
            try:
                # 1. Compute name embeddings (128-dim)
                print(f"Computing name embeddings for batch of {len(batch_names)} documents...")
                name_vecs = embed_batch_with_retry(name_embeddings, batch_names)

                # 2. Compute description embeddings (768-dim, RETRIEVAL_DOCUMENT)
                print(f"Computing description embeddings for batch of {len(batch_descriptions)} documents...")
                desc_vecs = embed_batch_with_retry(desc_embeddings, batch_descriptions)

                # 3. Save to Firestore
                if not args.dry_run:
                    print("Saving embeddings to Firestore...")
                    write_batch = db.batch()
                    for i, doc_id in enumerate(batch_doc_ids):
                        doc_ref = col_ref.document(doc_id)
                        write_batch.update(doc_ref, {
                            "name_embedding": Vector(name_vecs[i]),
                            "description_embedding": Vector(desc_vecs[i]),
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        })
                    write_batch.commit()
                    updated_count += len(batch_doc_ids)
                    print(f"Batch successfully committed. Total updated: {updated_count}")
                else:
                    updated_count += len(batch_doc_ids)
                    print(f"[Dry Run] Embeddings computed successfully for {len(batch_doc_ids)} docs. Firestore update skipped.")

            except Exception as e:
                print(f"Error processing batch: {e}")
                print("Stopping process. You can run the script again to resume.")
                sys.exit(1)

            # Clear batch lists
            batch_doc_ids = []
            batch_names = []
            batch_descriptions = []

            # Polite sleep between batches
            time.sleep(1.0)

    # Process any remaining documents
    if batch_doc_ids and (args.limit is None or updated_count < args.limit):
        print(f"\nProcessing final remaining batch of size {len(batch_doc_ids)}...")
        try:
            name_vecs = embed_batch_with_retry(name_embeddings, batch_names)
            desc_vecs = embed_batch_with_retry(desc_embeddings, batch_descriptions)

            if not args.dry_run:
                write_batch = db.batch()
                for i, doc_id in enumerate(batch_doc_ids):
                    doc_ref = col_ref.document(doc_id)
                    write_batch.update(doc_ref, {
                        "name_embedding": Vector(name_vecs[i]),
                        "description_embedding": Vector(desc_vecs[i]),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    })
                write_batch.commit()
                updated_count += len(batch_doc_ids)
                print(f"Final batch successfully committed. Total updated: {updated_count}")
            else:
                updated_count += len(batch_doc_ids)
                print(f"[Dry Run] Final batch computed successfully. Total updated: {updated_count}")

        except Exception as e:
            print(f"Error processing final batch: {e}")
            sys.exit(1)

    print(f"\nFinished process!")
    print(f"Total scanned: {processed_count}")
    print(f"Total skipped (already embedded): {skipped_count}")
    print(f"Total updated: {updated_count}")

if __name__ == "__main__":
    main()
