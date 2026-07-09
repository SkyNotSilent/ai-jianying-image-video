#!/usr/bin/env python3
"""Fail when README local image/video links point at missing files."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".webm", ".mov"}


def is_local_asset(raw: str) -> bool:
    target = raw.strip().split("#", 1)[0].split("?", 1)[0]
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return False
    return Path(target).suffix.lower() in ASSET_SUFFIXES


def main() -> int:
    text = README.read_text(encoding="utf-8")
    refs = set()
    for pattern in (IMAGE_RE, LINK_RE):
        for match in pattern.findall(text):
            if is_local_asset(match):
                refs.add(match.strip().split("#", 1)[0].split("?", 1)[0])

    missing = sorted(ref for ref in refs if not (ROOT / ref).is_file())
    if missing:
        print("README references missing local assets:", file=sys.stderr)
        for ref in missing:
            print(f"- {ref}", file=sys.stderr)
        return 1

    print(f"README asset check passed: {len(refs)} local asset references.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
