"""Safe filesystem collection and cleanup for task deletion."""

import errno
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import unquote, urlparse

from src.config import Config


@dataclass
class DeletionReport:
    deleted_files: int
    deleted_directories: int
    skipped_paths: list[str]
    failed_paths: list[str]


def _storage_roots() -> tuple[Path, Path]:
    return (
        (Config.BASE_DIR / "output").resolve(),
        (Config.BASE_DIR / "data" / "media").resolve(),
    )


def _path_from_value(value) -> Optional[Path]:
    if value is None:
        return None
    raw_value = str(value).strip()
    if not raw_value:
        return None

    parsed = urlparse(raw_value)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
        }:
            return None
        media_path = unquote(parsed.path)
        if media_path == "/media":
            relative_path = ""
        elif media_path.startswith("/media/"):
            relative_path = media_path[len("/media/"):]
        else:
            return None
        return (Config.BASE_DIR / "data" / "media" / relative_path).resolve()

    if raw_value == "/media":
        return (Config.BASE_DIR / "data" / "media").resolve()
    if raw_value.startswith("/media/"):
        return (
            Config.BASE_DIR / "data" / "media" / raw_value[len("/media/"):]
        ).resolve()

    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = Config.BASE_DIR / path
    return path.resolve()


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _add_parent_directories(paths: set[Path], path: Path) -> None:
    for root in _storage_roots():
        if not _is_within(path, root):
            continue
        parent = path if path.is_dir() else path.parent
        while parent != root and _is_within(parent, root):
            paths.add(parent)
            parent = parent.parent
        return


def collect_task_paths(
    task_row: dict,
    segments: list[dict],
    assets: list[dict],
) -> set[Path]:
    """Snapshot DB-attributed paths plus complete task-ID-owned directories."""
    paths: set[Path] = set()
    values = []
    result = (task_row or {}).get("result") or {}
    values.extend(result.get(field) for field in ("draft_path", "draft_url", "video_url"))
    for segment in segments or []:
        values.extend(
            segment.get(field)
            for field in ("image_path", "image_url", "audio_path", "audio_url")
        )
    for asset in assets or []:
        values.extend(asset.get(field) for field in ("path", "url"))

    for value in values:
        path = _path_from_value(value)
        if path is None:
            continue
        paths.add(path)
        _add_parent_directories(paths, path)

    task_id = str((task_row or {}).get("task_id") or "")
    if task_id and Path(task_id).name == task_id:
        for root in _storage_roots():
            owned_root = (root / task_id).resolve()
            if owned_root.parent != root or not owned_root.exists():
                continue
            paths.add(owned_root)
            for child in owned_root.rglob("*"):
                paths.add(child.resolve())

    return paths


def delete_task_files(
    paths: Iterable[Path],
    allowed_roots: Iterable[Path],
) -> DeletionReport:
    """Delete only resolved paths contained by the configured storage roots."""
    roots = {Path(root).expanduser().resolve() for root in allowed_roots}
    skipped_paths: list[str] = []
    failed_paths: list[str] = []
    deletable = []

    for raw_path in paths:
        path = Path(raw_path).expanduser()
        resolved = path.resolve()
        if resolved in roots or not any(_is_within(resolved, root) for root in roots):
            skipped_paths.append(str(resolved))
            continue
        deletable.append((path, resolved))

    deleted_files = 0
    deleted_directories = 0
    unique_paths = {(str(path), str(resolved)): (path, resolved) for path, resolved in deletable}
    ordered = sorted(
        unique_paths.values(),
        key=lambda item: (item[0].is_dir() and not item[0].is_symlink(), len(item[0].parts)),
        reverse=False,
    )

    files = [item for item in ordered if not item[0].is_dir() or item[0].is_symlink()]
    directories = sorted(
        (item for item in ordered if item[0].is_dir() and not item[0].is_symlink()),
        key=lambda item: len(item[0].parts),
        reverse=True,
    )

    for path, resolved in files:
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
                deleted_files += 1
        except OSError:
            failed_paths.append(str(resolved))

    for path, resolved in directories:
        try:
            if path.exists():
                path.rmdir()
                deleted_directories += 1
        except OSError as exc:
            if exc.errno not in {errno.ENOTEMPTY, errno.EEXIST}:
                failed_paths.append(str(resolved))

    return DeletionReport(
        deleted_files=deleted_files,
        deleted_directories=deleted_directories,
        skipped_paths=sorted(set(skipped_paths)),
        failed_paths=sorted(set(failed_paths)),
    )
