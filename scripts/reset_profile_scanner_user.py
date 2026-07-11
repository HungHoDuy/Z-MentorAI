"""Delete Profile Scanner test data for one user, with dry-run as the default."""

import argparse

from google.cloud import firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter


COLLECTIONS_BY_USER_ID = (
    "profile_scanner_cv_documents",
    "profile_scanner_profile_versions",
    "profile_scanner_holland_assessments",
    "profile_scanner_assessments",
)
DIRECT_DOCUMENT_COLLECTIONS = (
    "profile_scanner_profiles",
    "profile_scanner_alignment_results",
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete data. Without this flag the command only prints a dry-run.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    db = firestore.Client(project=args.project)
    storage_client = storage.Client(project=args.project)
    documents = []

    for collection_name in COLLECTIONS_BY_USER_ID:
        query = db.collection(collection_name).where(
            filter=FieldFilter("user_id", "==", args.user_id)
        )
        for snapshot in query.stream():
            documents.append((collection_name, snapshot.reference))

    for collection_name in DIRECT_DOCUMENT_COLLECTIONS:
        reference = db.collection(collection_name).document(args.user_id)
        if reference.get().exists:
            documents.append((collection_name, reference))

    prefix = f"users/{args.user_id}/cv_documents/"
    blobs = list(storage_client.list_blobs(args.bucket, prefix=prefix))
    mode = "DELETE" if args.confirm else "DRY-RUN"
    print(f"[{mode}] user_id={args.user_id}")
    for collection_name, reference in documents:
        print(f"Firestore: {collection_name}/{reference.id}")
    for blob in blobs:
        print(f"GCS: gs://{args.bucket}/{blob.name}")

    if not args.confirm:
        print("No data deleted. Re-run with --confirm after reviewing the list.")
        return

    batch = db.batch()
    pending = 0
    for _, reference in documents:
        batch.delete(reference)
        pending += 1
        if pending == 400:
            batch.commit()
            batch = db.batch()
            pending = 0
    if pending:
        batch.commit()
    for blob in blobs:
        blob.delete()
    print(f"Deleted {len(documents)} Firestore documents and {len(blobs)} GCS objects.")


if __name__ == "__main__":
    main()
