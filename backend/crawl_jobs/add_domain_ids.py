#!/usr/bin/env python
"""
Migration script to extract flat domain IDs from the nested domain_types list
and store them in a new field `domainIDs` on all courses in the learning_material collection.
This allows simple Firestore filtering and composite indexing for vector search.
"""

import sys
import time
import os
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import firestore

# Add parent directory of backend/crawl_jobs to path if needed
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Load .env file
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"Loaded environment from {env_path}")
else:
    print("Warning: No .env file found.")

COLLECTION_NAME = "learning_material"

def get_firestore_client():
    db_name = os.getenv("FIRESTORE_DATABASE")
    if db_name and db_name != "(default)":
        return firestore.Client(database=db_name)
    return firestore.Client()

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
    db = get_firestore_client()
    print(f"Connected to Firestore project: {db.project}")
    col_ref = db.collection(COLLECTION_NAME)

    print(f"Starting migration to add domainIDs to collection '{COLLECTION_NAME}'...")
    
    # We select domain_types and the existing domainIDs to see if we can skip already migrated ones
    fields_to_select = ["domain_types", "domainIDs"]
    doc_stream = stream_collection_paginated(col_ref, fields_to_select, page_size=1000)

    batch_docs = []
    processed_count = 0
    updated_count = 0
    skipped_count = 0
    batch_size = 500

    for doc_snap in doc_stream:
        doc_data = doc_snap.to_dict()
        doc_id = doc_snap.id
        processed_count += 1

        domain_types = doc_data.get("domain_types") or []
        existing_domain_ids = doc_data.get("domainIDs")

        # Extract flat list of unique domain IDs
        extracted_domain_ids = []
        for dt in domain_types:
            if isinstance(dt, dict):
                d_id = dt.get("domainId")
                if d_id and d_id not in extracted_domain_ids:
                    extracted_domain_ids.append(d_id)

        # Check if already migrated
        # If existing matches extracted, we can skip
        if existing_domain_ids is not None and sorted(existing_domain_ids) == sorted(extracted_domain_ids):
            skipped_count += 1
            if processed_count % 2000 == 0:
                print(f"Scanned {processed_count} documents. Skipped {skipped_count} already migrated.")
            continue

        batch_docs.append((doc_id, extracted_domain_ids))

        # Commit batch when limit reached
        if len(batch_docs) >= batch_size:
            write_batch = db.batch()
            for doc_id, domain_ids in batch_docs:
                doc_ref = col_ref.document(doc_id)
                write_batch.update(doc_ref, {"domainIDs": domain_ids})
            
            write_batch.commit()
            updated_count += len(batch_docs)
            print(f"Committed batch of {len(batch_docs)} updates. Total updated: {updated_count}")
            batch_docs = []
            time.sleep(0.5)

    # Process remaining
    if batch_docs:
        write_batch = db.batch()
        for doc_id, domain_ids in batch_docs:
            doc_ref = col_ref.document(doc_id)
            write_batch.update(doc_ref, {"domainIDs": domain_ids})
        write_batch.commit()
        updated_count += len(batch_docs)
        print(f"Committed final batch of {len(batch_docs)} updates. Total updated: {updated_count}")

    print("\nFinished Database Migration!")
    print(f"Total scanned: {processed_count}")
    print(f"Total skipped (already migrated): {skipped_count}")
    print(f"Total updated: {updated_count}")

if __name__ == "__main__":
    main()
