from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.repositories.salary_repository import (
    DEFAULT_CLEANED_COLLECTION,
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.services import SalaryIndexService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build salary benchmark index fields in Firestore.")
    parser.add_argument("--collection", default=None, help="Firestore collection to backfill.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for testing on a small sample.")
    parser.add_argument("--batch-size", type=int, default=25, help="Firestore batch size.")
    parser.add_argument("--max-title-keys", type=int, default=50, help="Maximum title index keys per document.")
    parser.add_argument("--dry-run", action="store_true", help="Compute index fields without writing to Firestore.")
    return parser.parse_args()


def commit_operations(firestore_client: Any, collection: Any, operations: list[tuple[str, dict[str, Any]]]) -> int:
    if not operations:
        return 0

    batch = firestore_client.batch()
    for document_id, fields in operations:
        batch.set(collection.document(document_id), fields, merge=True)

    try:
        batch.commit()
        return len(operations)
    except Exception as exc:
        if not _is_transaction_too_big_error(exc) or len(operations) == 1:
            raise

        midpoint = len(operations) // 2
        return commit_operations(firestore_client, collection, operations[:midpoint]) + commit_operations(
            firestore_client,
            collection,
            operations[midpoint:],
        )


def _is_transaction_too_big_error(exc: Exception) -> bool:
    return "Transaction too big" in str(exc)


def main() -> None:
    load_env_file()
    args = parse_args()

    collection_name = args.collection or env_or_default("MARKET_SCOUT_CLEANED_COLLECTION", DEFAULT_CLEANED_COLLECTION)
    firestore_client = build_firestore_client()
    index_service = SalaryIndexService(max_title_search_keys=args.max_title_keys)

    collection = firestore_client.collection(collection_name)
    snapshots = collection.limit(args.limit).stream() if args.limit is not None else collection.stream()

    pending_operations: list[tuple[str, dict[str, Any]]] = []
    scanned = 0
    indexed = 0
    written = 0
    skipped = 0

    for snapshot in snapshots:
        scanned += 1
        fields = index_service.build_index_fields(snapshot.id, snapshot.to_dict() or {})
        if fields is None:
            skipped += 1
            continue

        indexed += 1
        if not args.dry_run:
            pending_operations.append((snapshot.id, fields))

        if len(pending_operations) >= args.batch_size:
            written += commit_operations(firestore_client, collection, pending_operations)
            pending_operations = []

    if pending_operations:
        written += commit_operations(firestore_client, collection, pending_operations)

    print(
        json.dumps(
            {
                "status": "success",
                "collection": collection_name,
                "scanned_documents": scanned,
                "indexed_documents": indexed,
                "written_documents": written,
                "skipped_documents": skipped,
                "batch_size": args.batch_size,
                "max_title_keys": args.max_title_keys,
                "dry_run": args.dry_run,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
