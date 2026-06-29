"""视频渲染比例、画布与字幕参数工具。"""

from typing import Dict


RATIO_CANVASES: Dict[str, Dict[str, int]] = {
    "16:9": {"width": 1920, "height": 1080, "fps": 30},
    "9:16": {"width": 1080, "height": 1920, "fps": 30},
    "3:4": {"width": 1080, "height": 1440, "fps": 30},
}

SUBTITLE_PRESETS: Dict[str, Dict[str, float]] = {
    "16:9": {
        "font_size_ratio": 0.055,
        "y_ratio": 0.88,
        "draft_transform_y": -0.8,
        "draft_base_size": 7.0,
        "draft_border_width": 0.0,
    },
    "9:16": {
        "font_size_ratio": 0.038,
        "y_ratio": 0.925,
        "draft_transform_y": -0.85,
        "draft_base_size": 8.0,
        "draft_border_width": 0.0,
    },
    "3:4": {
        "font_size_ratio": 0.042,
        "y_ratio": 0.91,
        "draft_transform_y": -0.83,
        "draft_base_size": 7.6,
        "draft_border_width": 0.0,
    },
}


def normalize_ratio(ratio: str = None) -> str:
    value = (ratio or "16:9").strip()
    if value not in RATIO_CANVASES:
        return "16:9"
    return value


def canvas_for_ratio(ratio: str = None) -> Dict[str, int]:
    return dict(RATIO_CANVASES[normalize_ratio(ratio)])


def ratio_for_canvas(width: int, height: int) -> str:
    # 计算宽高比
    ratio = width / height if height > 0 else 1.0

    # 判断最接近的比例
    if abs(ratio - 0.75) < 0.1:  # 3:4 (0.75)
        return "3:4"
    elif abs(ratio - 1.0) < 0.1:  # 接近方形，归为3:4
        return "3:4"
    elif ratio > 1.5:  # 16:9 (1.778)
        return "16:9"
    else:  # 9:16 (0.5625)
        return "9:16"


def subtitle_preset_for_ratio(ratio: str = None) -> Dict[str, float]:
    return dict(SUBTITLE_PRESETS[normalize_ratio(ratio)])


def subtitle_preset_for_canvas(width: int, height: int) -> Dict[str, float]:
    return subtitle_preset_for_ratio(ratio_for_canvas(width, height))
