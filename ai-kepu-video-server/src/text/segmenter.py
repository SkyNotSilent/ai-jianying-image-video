"""
文本分段模块
保证语义连贯性：优先在句末强标点断开，其次逗号类弱标点，
超过 max_length 才强制切割。
切完后合并过短段落（<= min_length）到前一段，避免 TTS 爆破音。

注意：segmenter 返回含标点的原始文本，供 TTS 使用；
字幕显示时的首尾标点清理在 builder.py 中进行。
"""

import re
import logging
from typing import List

logger = logging.getLogger(__name__)

MAX_LEN = 22  # 单段字数上限（含标点）
MIN_LEN = 8   # 单段字数下限；过短的段合并到前一段，避免 TTS 爆破音

# 强标点：句子结束，优先在此断开
STRONG_PUNCT = re.compile(r'[。！？!?…]+')
# 弱标点：次选断点
WEAK_PUNCT   = re.compile(r'[，,；;、]+')
# 句末标点后必须跟随上一段的右侧成对符号
CLOSING_MARKS = '”’」』》〉】）》'
QUOTE_PAIRS = {'“': '”', '‘': '’', '「': '」', '『': '』', '《': '》', '〈': '〉'}
# 段首不允许出现的标点（从切点开始的下一段可能以标点开头）
LEADING_PUNCT = re.compile(rf'^[。！？!?…，,；;、：:{CLOSING_MARKS}]+')
# 段尾不允许出现的标点（字幕显示用，TTS 文本保留）
TRAILING_PUNCT_DISPLAY = re.compile(r'[。！？!?…，,；;、]+$')


def _balanced_quote_spans(text: str):
    """Return complete quote spans; unmatched quotes intentionally stay unprotected."""
    stack = []
    spans = []
    for index, char in enumerate(text):
        if char in QUOTE_PAIRS:
            stack.append((char, index))
        elif stack and char == QUOTE_PAIRS[stack[-1][0]]:
            _, start = stack.pop()
            spans.append((start, index + 1))
    return spans


def _extend_cut_past_balanced_quote(text: str, cut_end: int) -> int:
    """Move a cut after any complete quote that currently contains it."""
    spans = _balanced_quote_spans(text)
    extended = cut_end
    changed = True
    while changed:
        changed = False
        for start, end in spans:
            if start < extended < end:
                extended = end
                changed = True
    return extended


class TextSegmenter:
    """文本分段器 - 语义优先，超限才切，过短则合并"""

    def __init__(self, max_length: int = MAX_LEN, min_length: int = MIN_LEN):
        self.max_length = max_length
        self.min_length = min_length

    def split(self, text: str) -> List[str]:
        logger.info(f"开始分段: 文本长度={len(text)}")
        text = re.sub(r'\s+', '', text)
        segments = self._smart_split(text)
        segments = self._merge_short(segments)
        segments = [s for s in segments if re.sub(r'[^\w]', '', s)]
        logger.info(f"分段完成: 共 {len(segments)} 段")
        return segments

    def _merge_short(self, segments: List[str]) -> List[str]:
        """
        把过短的段落（<= min_length）合并到相邻段：
        优先合并到前一段（合并后 <= max_length），否则合并到后一段。
        """
        result = list(segments)
        changed = True
        while changed:
            changed = False
            i = 0
            while i < len(result):
                if len(result[i]) <= self.min_length:
                    # 尝试合并到前一段
                    if i > 0 and len(result[i-1]) + len(result[i]) <= self.max_length:
                        result[i-1] = result[i-1] + result[i]
                        result.pop(i)
                        changed = True
                        continue
                    # 尝试合并到后一段
                    if i < len(result) - 1 and len(result[i]) + len(result[i+1]) <= self.max_length:
                        result[i+1] = result[i] + result[i+1]
                        result.pop(i)
                        changed = True
                        continue
                i += 1
        return result

    def _smart_split(self, text: str) -> List[str]:
        """
        策略：
        1. 找下一个强标点位置 p。
           - 若 p <= max_length：在 p 处切（保留标点），继续。
           - 若 p > max_length：在 max_length 内找最靠后的弱标点；
             有则在弱标点处切，无则硬切到 max_length。
        2. 如果全文没有更多强标点，则对剩余文本按弱标点/硬切处理。
        返回含标点的原始文本段，供 TTS 使用。
        """
        result = []
        start = 0
        n = len(text)

        while start < n:
            # 段首若有残留标点，拼回上一段末尾再跳过（保证上一段 TTS 有完整句尾停顿）
            punct_start = start
            while start < n and LEADING_PUNCT.match(text[start]):
                start += 1
            if result and start > punct_start:
                result[-1] = result[-1] + text[punct_start:start]
            if start >= n:
                break
            remaining = text[start:]

            if len(remaining) <= self.max_length:
                seg = remaining.strip()
                if seg:
                    result.append(seg)
                break

            # 在整段剩余文本里找第一个强标点
            m = STRONG_PUNCT.search(remaining)
            if m and m.end() <= self.max_length:
                cut_end = _extend_cut_past_balanced_quote(remaining, m.end())
                while cut_end < len(remaining) and remaining[cut_end] in CLOSING_MARKS:
                    cut_end += 1
                seg = remaining[:cut_end].strip()
                if seg:
                    result.append(seg)
                start += cut_end
                continue

            # 强标点不存在或超限 → 在 max_length 内找最靠后的弱标点
            chunk = remaining[:self.max_length]
            weak_pos = -1
            for wm in WEAK_PUNCT.finditer(chunk):
                weak_pos = wm.end()

            if weak_pos > 0:
                cut_end = _extend_cut_past_balanced_quote(remaining, weak_pos)
                seg = remaining[:cut_end].strip()
                if seg:
                    result.append(seg)
                start += cut_end
            else:
                cut_end = _extend_cut_past_balanced_quote(remaining, self.max_length)
                seg = remaining[:cut_end].strip()
                if seg:
                    result.append(seg)
                start += cut_end

        return result


class LongTextSegmenter:
    """长文本分段器 - 约 150 字/段，优先在段落和句子边界断开"""

    SENTENCE_END = re.compile(rf'[^。！？!?…]+[。！？!?…]*[{CLOSING_MARKS}]*')

    def __init__(self, max_length: int = 150, min_length: int = 50):
        self.max_length = max_length
        self.min_length = min_length

    def split(self, text: str) -> List[str]:
        logger.info(f"开始长文本分段: 文本长度={len(text)}")
        text = (text or "").strip()
        if not text:
            return []

        paragraphs = [
            re.sub(r'[ \t]+', '', p).strip()
            for p in re.split(r'\n+', text)
            if p.strip()
        ]

        segments = []
        for paragraph in paragraphs:
            segments.extend(self._split_paragraph(paragraph))

        segments = self._merge_short(segments)
        segments = [s for s in segments if re.sub(r'[^\w\u4e00-\u9fff]', '', s)]
        logger.info(f"长文本分段完成: 共 {len(segments)} 段")
        return segments

    def _split_paragraph(self, paragraph: str) -> List[str]:
        if len(paragraph) <= self.max_length:
            return [paragraph]

        sentences = [
            m.group(0).strip()
            for m in self.SENTENCE_END.finditer(paragraph)
            if m.group(0).strip()
        ]
        if not sentences:
            sentences = [paragraph]

        result = []
        current = ""
        for sentence in sentences:
            if len(sentence) > self.max_length:
                if current:
                    result.append(current)
                    current = ""
                result.extend(self._hard_split(sentence))
                continue

            if not current:
                current = sentence
            elif len(current) + len(sentence) <= self.max_length:
                current += sentence
            else:
                result.append(current)
                current = sentence

        if current:
            result.append(current)
        return result

    def _hard_split(self, text: str) -> List[str]:
        result = []
        start = 0
        while start < len(text):
            remaining = text[start:]
            cut_end = min(self.max_length, len(remaining))
            cut_end = _extend_cut_past_balanced_quote(remaining, cut_end)
            segment = remaining[:cut_end].strip()
            if segment:
                result.append(segment)
            start += cut_end
        return result

    def _merge_short(self, segments: List[str]) -> List[str]:
        if not segments:
            return []

        result = []
        for segment in segments:
            if (
                result
                and len(segment) < self.min_length
                and len(result[-1]) + len(segment) <= self.max_length
            ):
                result[-1] += segment
            else:
                result.append(segment)

        merged = []
        i = 0
        while i < len(result):
            segment = result[i]
            if (
                len(segment) < self.min_length
                and i + 1 < len(result)
                and len(segment) + len(result[i + 1]) <= self.max_length
            ):
                merged.append(segment + result[i + 1])
                i += 2
            else:
                merged.append(segment)
                i += 1
        return merged

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    segmenter = TextSegmenter()
    test = "不是因为感受太浅，而是因为它太深了，深到语言够不着。有些问题，越想越看不清楚，越模糊。你盯着一个字看太久，它就不像是那个字了。我们以为答案在终点，却不知道每一个答案后面，藏着一个更深的问题。也许「不知道」，才是最接近真实的答案。"
    for i, s in enumerate(segmenter.split(test), 1):
        print(f"[{i}] ({len(s)}字) {s}")
