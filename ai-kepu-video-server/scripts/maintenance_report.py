#!/usr/bin/env python3
"""Report local storage/log/database health and optionally delete unreferenced media.

Default mode is read-only. Use --apply to delete only files that are not referenced
by the SQLite database.
"""

import argparse
import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse


SERVER_ROOT = Path(os.environ.get("INSIGHTCUT_SERVER_ROOT", Path(__file__).resolve().parents[1])).resolve()
DB_PATH = SERVER_ROOT / "data" / "local.db"
OUTPUT_DIR = SERVER_ROOT / "output"
MEDIA_DIR = SERVER_ROOT / "data" / "media"
LOG_DIR = SERVER_ROOT / "logs"


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def tree_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(file_size(item) for item in path.rglob("*") if item.is_file())


def iter_files(path: Path):
    if not path.exists():
        return
    for item in path.rglob("*"):
        if item.is_file():
            yield item.resolve()


def local_path_from_db_value(value: str):
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        marker = "/media/"
        if marker not in parsed.path:
            return None
        return (MEDIA_DIR / parsed.path.split(marker, 1)[1].lstrip("/")).resolve()

    path = Path(raw)
    if not path.is_absolute():
        path = SERVER_ROOT / path
    return path.resolve()


def collect_referenced_paths():
    referenced = set()
    if not DB_PATH.exists():
        return referenced

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        queries = [
            ("task_segments", ["image_path", "image_url", "audio_path", "audio_url"]),
            ("task_assets", ["path", "url"]),
            ("task_results", ["draft_path", "draft_url", "video_url"]),
        ]
        for table, columns in queries:
            selected = ", ".join(columns)
            for row in conn.execute(f"SELECT {selected} FROM {table}"):
                for column in columns:
                    local_path = local_path_from_db_value(row[column])
                    if local_path:
                        referenced.add(local_path)
    finally:
        conn.close()
    return referenced


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve())
        return True
    except ValueError:
        return False


def unreferenced_media_files(referenced):
    roots = [OUTPUT_DIR.resolve(), MEDIA_DIR.resolve()]
    candidates = []
    for root in roots:
        for path in iter_files(root):
            if path not in referenced:
                candidates.append(path)
    return sorted(candidates)


def cleanup_empty_dirs(root: Path):
    removed = []
    if not root.exists():
        return removed
    for path in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
        try:
            path.rmdir()
            removed.append(str(path.relative_to(SERVER_ROOT)))
        except OSError:
            pass
    return removed


def db_counts():
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(DB_PATH)
    try:
        tables = ["tasks", "task_steps", "task_segments", "task_assets", "task_results", "tts_voices"]
        counts = {}
        for table in tables:
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return counts
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Report only; this is the default.")
    parser.add_argument("--apply", action="store_true", help="Delete unreferenced media files.")
    parser.add_argument("--max-items", type=int, default=50, help="Maximum unreferenced files to list.")
    args = parser.parse_args()

    if args.dry_run and args.apply:
        parser.error("--dry-run and --apply cannot be used together")

    referenced = collect_referenced_paths()
    unreferenced = unreferenced_media_files(referenced)
    unreferenced_bytes = sum(file_size(path) for path in unreferenced)
    deleted = []
    removed_dirs = []

    if args.apply:
        for path in unreferenced:
            if not (is_within(path, OUTPUT_DIR) or is_within(path, MEDIA_DIR)):
                continue
            try:
                path.unlink()
                deleted.append(str(path.relative_to(SERVER_ROOT)))
            except OSError:
                pass
        removed_dirs = cleanup_empty_dirs(OUTPUT_DIR) + cleanup_empty_dirs(MEDIA_DIR)

    report = {
        "mode": "apply" if args.apply else "dry-run",
        "sizes_bytes": {
            "logs": tree_size(LOG_DIR),
            "output": tree_size(OUTPUT_DIR),
            "data_media": tree_size(MEDIA_DIR),
            "database": file_size(DB_PATH),
        },
        "database_counts": db_counts(),
        "referenced_paths": len(referenced),
        "unreferenced_media": {
            "count": len(unreferenced),
            "bytes": unreferenced_bytes,
            "sample": [str(path.relative_to(SERVER_ROOT)) for path in unreferenced[: args.max_items]],
        },
        "deleted": deleted,
        "removed_empty_dirs": removed_dirs,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
