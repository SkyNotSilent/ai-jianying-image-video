from src.utils.subtitle_text import normalize_subtitle_text


def test_subtitle_normalization_keeps_balanced_quotes():
    text = '而是问“如果我连续做三年，它会把我带到哪里？”'

    assert normalize_subtitle_text(text) == text


def test_subtitle_normalization_still_removes_plain_edge_punctuation():
    assert normalize_subtitle_text('，，这是字幕。') == '这是字幕'
