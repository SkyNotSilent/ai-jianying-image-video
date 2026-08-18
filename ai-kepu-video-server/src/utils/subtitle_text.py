"""字幕文本清洗规则。"""

import re


_SUBTITLE_PUNCT = re.compile(r'[。！？!?…，,；;、：:]')
_WHITESPACE = re.compile(r"\s+")


def normalize_subtitle_text(text: str) -> str:
    """字幕保持单行，去掉口播停顿标点并保留引号、书名号等语义符号。"""
    raw = str(text or "")
    compact = _WHITESPACE.sub(" ", raw).strip()
    clean = _SUBTITLE_PUNCT.sub("", compact).strip()
    return clean or compact
