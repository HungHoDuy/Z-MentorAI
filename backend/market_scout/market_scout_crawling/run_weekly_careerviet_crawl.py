from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run weekly CareerViet crawl job 1: links + raw details.")
    parser.add_argument("--batch-id", default=None, help="Batch id, for example 2026W31. Defaults to current ISO week.")
    parser.add_argument("--scope", choices=("it", "sales", "it-sales", "all"), default=os.getenv("CAREERVIET_SCOPE", "it-sales"))
    parser.add_argument("--start-page", type=int, default=int(os.getenv("CAREERVIET_START_PAGE", "1")))
    parser.add_argument("--max-pages", type=int, default=int(os.getenv("CAREERVIET_MAX_PAGES", "10")))
    parser.add_argument("--max-jobs", type=int, default=int(os.getenv("CAREERVIET_MAX_JOBS", "200")))
    parser.add_argument("--workers", type=int, default=int(os.getenv("CAREERVIET_WORKERS", "2")))
    parser.add_argument("--todo-collection", default=os.getenv("CAREERVIET_TODO_COLLECTION"))
    parser.add_argument("--dest-collection", default=os.getenv("CAREERVIET_DEST_COLLECTION"))
    parser.add_argument("--skip-link-extraction", action="store_true")
    parser.add_argument("--skip-detail-scrape", action="store_true")
    parser.add_argument("--keyword", action="append", default=[])
    return parser.parse_args()


def default_batch_id(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    iso_year, iso_week, _ = current.isocalendar()
    return f"{iso_year}W{iso_week:02d}"


def run_command(command: list[str], cwd: Path) -> None:
    print("Running:", " ".join(command), flush=True)
    subprocess.run(command, cwd=str(cwd), check=True)


def main() -> None:
    args = parse_args()
    batch_id = args.batch_id or default_batch_id()
    todo_collection = args.todo_collection or f"todo_careerviet_weekly_{batch_id}"
    dest_collection = args.dest_collection or f"careerviet_jobs_weekly_{batch_id}"
    script_dir = Path(__file__).resolve().parent

    print(
        "Starting weekly CareerViet crawl:",
        {
            "batch_id": batch_id,
            "scope": args.scope,
            "start_page": args.start_page,
            "max_pages": args.max_pages,
            "max_jobs": args.max_jobs,
            "workers": args.workers,
            "todo_collection": todo_collection,
            "dest_collection": dest_collection,
        },
        flush=True,
    )

    if not args.skip_link_extraction:
        extract_command = [
            sys.executable,
            "extract_links.py",
            "--todo-collection",
            todo_collection,
            "--batch-id",
            batch_id,
            "--scope",
            args.scope,
            "--start-page",
            str(args.start_page),
            "--max-pages",
            str(args.max_pages),
            "--max-links",
            str(args.max_jobs),
            "--workers",
            str(args.workers),
        ]
        for keyword in args.keyword:
            extract_command.extend(["--keyword", keyword])
        run_command(extract_command, script_dir)

    if not args.skip_detail_scrape:
        scrape_command = [
            sys.executable,
            "scrape_details.py",
            "--todo-collection",
            todo_collection,
            "--dest-collection",
            dest_collection,
            "--batch-id",
            batch_id,
            "--scope",
            args.scope,
            "--limit",
            str(args.max_jobs),
            "--workers",
            str(args.workers),
        ]
        run_command(scrape_command, script_dir)

    print(
        "Weekly CareerViet crawl finished:",
        {
            "batch_id": batch_id,
            "todo_collection": todo_collection,
            "dest_collection": dest_collection,
        },
        flush=True,
    )


if __name__ == "__main__":
    main()
