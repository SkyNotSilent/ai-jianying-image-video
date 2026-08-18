"""
图片生成模块
基于 OpenAI/兼容图像生成接口生成 AI 图像
"""

import base64
import logging
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.config import Config

logger = logging.getLogger(__name__)
_RATE_LIMIT_LOCK = threading.Lock()
_LAST_IMAGE_REQUEST_AT = 0.0
_DEFAULT_REQUEST_INTERVAL_SECONDS = 3.0

# 风格预设（附加到 prompt 末尾）
STYLE_PRESETS = {
    "写实风格":   "photorealistic, cinematic lighting, 4k, high detail",
    "电影质感":   "cinematic lighting, film still, dramatic composition, high detail",
    "电影胶片":   "film grain, cinematic, anamorphic lens, vintage color grading, 35mm film",
    "吉卜力":     "soft pastel colors, warm sunlight, peaceful, dreamy, Studio Ghibli inspired",
    "治愈系":     "soft pastel colors, warm sunlight, peaceful, dreamy, Studio Ghibli inspired",
    "3D动画":     "3D animated film style, stylized characters, soft lighting, detailed environment",
    "赛博朋克":   "cyberpunk, neon lights, rainy night, futuristic city, blade runner aesthetic",
    "国风":       "Chinese ink painting, traditional brush strokes, misty mountains, elegant, minimalist",
    "水墨国风":   "Chinese ink painting, traditional brush strokes, misty mountains, elegant, minimalist",
    "油彩画":     "oil painting, visible brush strokes, rich colors, painterly texture, gallery quality",
    "毛毡风":     "felt craft art style, handmade felt texture, wool fabric, cute flat illustration, soft tactile surface, warm pastel tones, cozy miniature diorama look",
}


class ImageGenerator:
    """图片生成器 - OpenAI/兼容 images generations 接口"""

    def __init__(self, output_dir: str = "output/images"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.image_config = Config.image_config()
        self.api_url = self.image_config.get("api_url") or Config.SEEDREAM_API_URL
        self.api_key = self.image_config.get("api_key") or Config.SEEDREAM_API_KEY
        self.model = self.image_config.get("model") or Config.SEEDREAM_MODEL
        self.size = self.image_config.get("size") or "auto"
        retry_count = Config.generation_config().get("retry_count", 2)
        self.max_attempts = max(1, min(6, int(retry_count) + 1))

    def generate(
        self,
        prompt: str,
        index: int = 0,
        width: int = 1920,
        height: int = 1080,
        style: str = "写实风格",
        style_suffix: str = None,
        filename: str = None,
    ) -> str:
        """
        生成 AI 图像，返回本地路径。

        Args:
            prompt: 英文图像描述
            index: 片段序号（用于文件命名）
            width: 图片宽度
            height: 图片高度
            style: 风格预设
            style_suffix: 自定义风格 prompt 后缀，优先级高于 style 预设
            filename: 自定义文件名（不含扩展名），如果为 None 则使用 segment_{index:03d}
        """
        output_stem = filename or f"segment_{index:03d}"

        # 组合 prompt + 风格
        suffix = (style_suffix or "").strip() or STYLE_PRESETS.get(style, STYLE_PRESETS["写实风格"])
        full_prompt = f"{prompt}, {suffix}"

        if not self.api_key:
            raise ValueError("图像生成 API Key 未配置")

        # 尺寸映射（可配置，auto 时按宽高比选择常见兼容规格）
        size = self._pick_size(width, height)

        logger.debug(f"生成图像 [{index+1}]: {full_prompt[:60]}...")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "size": size,
        }
        if not self._is_openai_official_endpoint():
            # Agnes 等中转/兼容接口要求 response_format 放在 extra_body 中。
            payload["extra_body"] = {"response_format": "url"}
            payload["stream"] = False

        resp = None
        for attempt in range(self.max_attempts):
            try:
                self._wait_for_rate_limit()
                resp = requests.post(self.api_url, headers=headers, json=payload, timeout=90)
                resp.raise_for_status()
                break
            except requests.HTTPError as e:
                if attempt == self.max_attempts - 1:
                    raise
                wait_seconds = self._retry_delay(resp)
                logger.warning(f"图像生成失败（第{attempt+1}次），{wait_seconds:.0f}秒后重试: {e}")
                time.sleep(wait_seconds)
            except Exception as e:
                if attempt == self.max_attempts - 1:
                    raise
                logger.warning(f"图像生成失败（第{attempt+1}次），3秒后重试: {e}")
                time.sleep(3)
        data = resp.json()

        if not data.get("data"):
            raise RuntimeError(f"图像生成接口返回异常: {data}")

        image_bytes = self._extract_image_bytes(data)
        output_path = self.output_dir / f"{output_stem}{self._detect_image_extension(image_bytes)}"
        output_path.write_bytes(image_bytes)
        logger.debug(f"图像保存: {output_path} ({len(image_bytes)} 字节)")
        return str(output_path)

    def _is_openai_official_endpoint(self) -> bool:
        parsed = urlparse(self.api_url)
        return parsed.netloc in {"api.openai.com", "api.openai.com:443"}

    def _wait_for_rate_limit(self) -> None:
        global _LAST_IMAGE_REQUEST_AT
        with _RATE_LIMIT_LOCK:
            now = time.monotonic()
            elapsed = now - _LAST_IMAGE_REQUEST_AT
            if elapsed < _DEFAULT_REQUEST_INTERVAL_SECONDS:
                time.sleep(_DEFAULT_REQUEST_INTERVAL_SECONDS - elapsed)
            _LAST_IMAGE_REQUEST_AT = time.monotonic()

    def _retry_delay(self, resp) -> float:
        if resp is not None and resp.status_code == 429:
            retry_after = resp.headers.get("retry-after")
            try:
                return max(float(retry_after), _DEFAULT_REQUEST_INTERVAL_SECONDS)
            except (TypeError, ValueError):
                return 60.0
        return _DEFAULT_REQUEST_INTERVAL_SECONDS

    def _extract_image_bytes(self, data: dict) -> bytes:
        item = data["data"][0]
        if item.get("url"):
            # 下载阶段沿用统一失败重试次数。
            for attempt in range(self.max_attempts):
                try:
                    img_resp = requests.get(item["url"], timeout=90)
                    img_resp.raise_for_status()
                    return img_resp.content
                except Exception as e:
                    if attempt == self.max_attempts - 1:
                        raise
                    logger.warning(f"图片下载失败（第{attempt+1}次），3秒后重试: {e}")
                    time.sleep(3)
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("base64"):
            return base64.b64decode(item["base64"])
        raise RuntimeError(f"图像生成接口返回缺少 url/b64_json: {data}")

    def _detect_image_extension(self, image_bytes: bytes) -> str:
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
            return ".webp"
        return ".jpg"

    def _pick_size(self, width: int, height: int) -> str:
        """根据宽高比选择常见 OpenAI/兼容接口支持的 size 参数。"""
        if self.size and self.size != "auto":
            return self.size

        ratio = width / height
        model = (self.model or "").lower()
        if "dall-e-3" in model or "dalle-3" in model:
            if ratio >= 1.6:
                return "1792x1024"
            elif ratio <= 0.65:
                return "1024x1792"
            return "1024x1024"

        if ratio >= 1.6:
            return "1536x1024"
        elif ratio <= 0.65:
            return "1024x1536"
        else:
            return "1024x1024"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gen = ImageGenerator()
    path = gen.generate(
        prompt="A futuristic city with flying cars, golden hour, wide angle",
        index=0,
        style="电影胶片",
    )
    print(f"图片保存到: {path}")
