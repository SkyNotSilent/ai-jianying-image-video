"""
自动配音模块
支持豆包 TTS 和小米 MiMo TTS
"""

import base64
import logging
import time
import uuid
from pathlib import Path

import requests

from src.config import Config

logger = logging.getLogger(__name__)


MIMO_TTS_VOICES = [
    {
        "id": "mimo_default",
        "name": "MiMo 默认",
        "gender": "auto",
        "language": "auto",
        "provider": "mimo",
        "description": "小米 MiMo 默认音色，自动匹配语言和表达。",
    },
    {"id": "冰糖", "name": "冰糖", "gender": "female", "language": "zh", "provider": "mimo", "description": "中文女声，清亮自然。"},
    {"id": "茉莉", "name": "茉莉", "gender": "female", "language": "zh", "provider": "mimo", "description": "中文女声，柔和克制。"},
    {"id": "苏打", "name": "苏打", "gender": "male", "language": "zh", "provider": "mimo", "description": "中文男声，干净年轻。"},
    {"id": "白桦", "name": "白桦", "gender": "male", "language": "zh", "provider": "mimo", "description": "中文男声，稳定沉着。"},
    {"id": "Mia", "name": "Mia", "gender": "female", "language": "en", "provider": "mimo", "description": "English female voice."},
    {"id": "Chloe", "name": "Chloe", "gender": "female", "language": "en", "provider": "mimo", "description": "English female voice."},
    {"id": "Milo", "name": "Milo", "gender": "male", "language": "en", "provider": "mimo", "description": "English male voice."},
    {"id": "Dean", "name": "Dean", "gender": "male", "language": "en", "provider": "mimo", "description": "English male voice."},
]


class VoiceOverGenerator:
    """配音生成器 - 按配置分发到豆包或小米 MiMo TTS"""

    def __init__(self, output_dir: str = "output/voiceovers"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tts_config = Config.tts_config()
        self.provider = (self.tts_config.get("provider") or "doubao").lower()
        self.api_url = self.tts_config.get("api_url") or Config.DOUBAO_TTS_API_URL
        self.appid = self.tts_config.get("appid") or Config.DOUBAO_TTS_APPID
        self.token = self.tts_config.get("token") or Config.DOUBAO_TTS_TOKEN
        self.cluster = self.tts_config.get("cluster") or Config.DOUBAO_TTS_CLUSTER
        self.default_voice = self.tts_config.get("default_voice") or Config.DOUBAO_TTS_DEFAULT_VOICE
        self.mimo_config = self.tts_config.get("mimo") or {}

    def generate(
        self,
        text: str,
        filename: str = None,
        voice_type: str = None,
        speed_ratio: float = 1.25,
        volume_ratio: float = 1.0,
    ) -> str:
        """
        生成配音，返回 wav 文件路径。

        Args:
            text: 文本内容
            filename: 输出文件名（不含扩展名）
            voice_type: 声音类型
            speed_ratio: 语速倍率，1.25 为默认（1.25倍速）
            volume_ratio: 音量倍率，1.0 为正常
        """
        if self.provider == "mimo":
            return self._generate_mimo(text, filename, voice_type)
        return self._generate_doubao(text, filename, voice_type, speed_ratio, volume_ratio)

    def _output_path(self, text: str, filename: str = None) -> Path:
        if not filename:
            safe = "".join(c for c in text[:10] if c.isalnum() or c in "_ ")
            filename = safe.strip() or "voice"
        return self.output_dir / f"{filename}.wav"

    def _generate_doubao(
        self,
        text: str,
        filename: str = None,
        voice_type: str = None,
        speed_ratio: float = 1.25,
        volume_ratio: float = 1.0,
    ) -> str:
        output_path = self._output_path(text, filename)
        logger.debug(f"生成配音: {text[:30]}... -> {output_path}")
        logger.debug(f"使用 TTS 配置 - APPID: {'已设置' if self.appid else '未设置'}, TOKEN: {'已设置' if self.token else '未设置'}")

        if not self.appid or not self.token:
            raise ValueError("TTS 配置未完成，请在模型配置页或 .env 中填写 DOUBAO_TTS_APPID / DOUBAO_TTS_TOKEN")

        voice = voice_type or self.default_voice
        reqid = uuid.uuid4().hex

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer;{self.token}",
        }
        payload = {
            "app": {"appid": self.appid, "token": self.token, "cluster": self.cluster},
            "user": {"uid": "auto_video"},
            "audio": {
                "voice_type": voice,
                "encoding": "wav",
                "rate": 24000,
                "speed_ratio": speed_ratio,
                "volume_ratio": volume_ratio,
            },
            "request": {
                "reqid": reqid,
                "text": text,
                "operation": "query",
            },
        }

        for attempt in range(5):
            try:
                resp = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 30 * (attempt + 1)))
                    logger.warning(f"TTS 限流 429（第{attempt+1}次），等待 {wait}s 后重试")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            except requests.exceptions.HTTPError:
                raise
            except Exception as e:
                if attempt == 4:
                    raise
                wait = 10 * (attempt + 1)
                logger.warning(f"TTS 请求失败（第{attempt+1}次），{wait}s 后重试: {e}")
                time.sleep(wait)

        data = resp.json()
        if data.get("code") != 3000 or not data.get("data"):
            raise RuntimeError(f"豆包 TTS 失败: code={data.get('code')} msg={data.get('message')}")

        audio_bytes = base64.b64decode(data["data"])
        output_path.write_bytes(audio_bytes)

        logger.debug(f"配音生成成功: {output_path} ({len(audio_bytes)} 字节)")
        return str(output_path)

    def _generate_mimo(
        self,
        text: str,
        filename: str = None,
        voice_type: str = None,
    ) -> str:
        output_path = self._output_path(text, filename)
        base_url = (self.mimo_config.get("base_url") or Config.MIMO_TTS_BASE_URL).rstrip("/")
        llm_config = Config.llm_config()
        api_key = (
            self.mimo_config.get("api_key")
            or self.tts_config.get("api_key")
            or Config.MIMO_TTS_API_KEY
            or (llm_config.get("api_key") if isinstance(llm_config, dict) else "")
        )
        model = self.mimo_config.get("model") or Config.MIMO_TTS_MODEL
        audio_format = (self.mimo_config.get("format") or Config.MIMO_TTS_FORMAT or "wav").lower()
        voice = voice_type or self.mimo_config.get("default_voice") or Config.MIMO_TTS_DEFAULT_VOICE
        style_prompt = self.mimo_config.get("style_prompt") or Config.MIMO_TTS_STYLE_PROMPT

        if not api_key:
            raise ValueError("小米 MiMo TTS 配置未完成，请在模型配置页填写 API Key")

        endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": style_prompt},
                {"role": "assistant", "content": text},
            ],
            "audio": {
                "format": audio_format,
                "voice": voice,
            },
        }

        logger.debug(
            "生成 MiMo 配音: provider=mimo model=%s voice=%s format=%s -> %s",
            model,
            voice,
            audio_format,
            output_path,
        )

        resp = None
        for attempt in range(5):
            try:
                resp = requests.post(endpoint, headers=headers, json=payload, timeout=90)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 60))
                    if attempt == 4:
                        resp.raise_for_status()
                    logger.warning(f"小米 MiMo TTS 限流 429（第{attempt+1}次），等待 {wait}s 后重试")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            except requests.exceptions.HTTPError:
                raise
            except Exception as e:
                if attempt == 4:
                    raise
                wait = 10 * (attempt + 1)
                logger.warning(f"小米 MiMo TTS 请求失败（第{attempt+1}次），{wait}s 后重试: {e}")
                time.sleep(wait)

        data = resp.json()
        try:
            audio_data = data["choices"][0]["message"]["audio"]["data"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("小米 MiMo TTS 响应缺少 choices[0].message.audio.data") from exc
        if not audio_data:
            raise RuntimeError("小米 MiMo TTS 返回空音频")

        audio_bytes = base64.b64decode(audio_data)
        output_path.write_bytes(audio_bytes)

        logger.debug(f"小米 MiMo 配音生成成功: {output_path} ({len(audio_bytes)} 字节)")
        return str(output_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gen = VoiceOverGenerator()
    path = gen.generate("人工智能正在改变我们的世界，带来无限可能。", filename="test")
    print(f"音频保存到: {path}")
