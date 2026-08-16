from src.text.segmenter import LongTextSegmenter, TextSegmenter


def test_short_segments_keep_a_closing_quote_with_sentence_punctuation():
    text = (
        "试着换个问题：不要总问“这件事多久能赚钱”，"
        "而是问“如果我连续做三年，它会把我带到哪里？”"
        "很多人的人生，不是输在能力上。"
    )

    segments = TextSegmenter(max_length=22, min_length=0).split(text)

    quoted_question = next(segment for segment in segments if "把我带到哪里" in segment)
    assert quoted_question.endswith("？”")
    assert not any(segment.startswith("”") for segment in segments)


def test_long_segments_keep_a_closing_quote_with_sentence_punctuation():
    text = "他说：“先确认问题出在哪里？”然后再决定怎么修。" * 8

    segments = LongTextSegmenter(max_length=40, min_length=0).split(text)

    assert not any(segment.startswith("”") for segment in segments)
    assert all("？”" in segment for segment in segments if "问题出在哪里" in segment)


def test_short_segmenter_does_not_split_a_long_balanced_quote():
    text = (
        "他说：“真正重要的不是今天立刻得到结果，而是连续三年坚持做正确的事情，"
        "最后你会走到完全不同的地方。”然后继续解释。"
    )

    segments = TextSegmenter(max_length=22, min_length=0).split(text)

    quoted_segment = next(segment for segment in segments if "真正重要" in segment)
    assert "真正重要的不是今天立刻得到结果，而是连续三年坚持做正确的事情，最后你会走到完全不同的地方。”" in quoted_segment
    assert sum("真正重要" in segment or "完全不同的地方" in segment for segment in segments) == 1


def test_long_segmenter_does_not_hard_split_a_long_balanced_quote():
    text = (
        "他说：“真正重要的不是今天立刻得到结果，而是连续三年坚持做正确的事情，"
        "最后你会走到完全不同的地方。”然后继续解释。"
    )

    segments = LongTextSegmenter(max_length=40, min_length=0).split(text)

    quoted_segment = next(segment for segment in segments if "真正重要" in segment)
    assert quoted_segment.endswith("。”")
    assert "完全不同的地方" in quoted_segment


def test_nested_balanced_quotes_remain_in_one_segment():
    text = "他说：“书里写着‘延迟满足不是压抑欲望，而是选择更大的回报’，这句话值得反复思考。”然后停顿。"

    segments = TextSegmenter(max_length=22, min_length=0).split(text)

    quoted_segment = next(segment for segment in segments if "书里写着" in segment)
    assert "‘延迟满足不是压抑欲望，而是选择更大的回报’" in quoted_segment
    assert quoted_segment.endswith("。”")


def test_unclosed_quote_falls_back_to_normal_length_splitting():
    text = "他说“这句话没有结束，但后面仍然需要按照普通长度继续切分，不能把剩余全文全部吞掉。"

    segments = TextSegmenter(max_length=22, min_length=0).split(text)

    assert "".join(segments) == text
    assert max(map(len, segments)) <= 22


def test_plain_text_keeps_existing_weak_punctuation_boundaries():
    text = "很多人总想立刻看到回报，今天学了东西，明天就想变现，最后不断更换方向。"

    assert TextSegmenter(max_length=22, min_length=0).split(text) == [
        "很多人总想立刻看到回报，今天学了东西，",
        "明天就想变现，最后不断更换方向。",
    ]
