"""字幕文本清洗规则。"""

import re


_LEADING_PUNCT = re.compile(r'^[。！？!?…，,；;、：:]+')
_TRAILING_PUNCT = re.compile(r'[。！？!?…，,；;、：:\s]+$')
_WHITESPACE = re.compile(r"\s+")


def normalize_subtitle_text(text: str) -> str:
    """字幕保持单行，并去掉首尾容易显脏的标点。"""
    raw = str(text or "")
    compact = _WHITESPACE.sub(" ", raw).strip()
    clean = _TRAILING_PUNCT.sub("", _LEADING_PUNCT.sub("", compact))
    return clean or compact
