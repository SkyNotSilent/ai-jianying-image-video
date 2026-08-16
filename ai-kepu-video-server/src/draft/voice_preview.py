"""本地 TTS 试听缓存。"""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, Optional

from src.config import Config
from src.draft.voice_catalog import normalize_tts_options, parse_voice_key
from src.draft.voiceover import VoiceOverGenerator

PRESET_VOICE_PREVIEW_TEXT = "欢迎来到 InsightCut，让我们一起把灵感变成精彩视频。"
PRESET_VOICE_PREVIEW_VERSION = "preset-v1"


class VoicePreviewService:
    def __init__(self, base_dir: Path = None, tts_config: Dict = None, clone_store=None):
        self.base_dir = Path(base_dir or Config.BASE_DIR).resolve()
        self.tts_config = deepcopy(tts_config or Config.tts_config())
        self.clone_store = clone_store
        self.root = self.base_dir / "data" / "media" / "_voice_previews"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _merged_config(base: Dict, override: Optional[Dict]) -> Dict:
        merged = deepcopy(base)
        incoming = override or {}
        for key, value in incoming.items():
            if key == "mimo" and isinstance(value, dict):
                merged.setdefault("mimo", {}).update(value)
            elif value is not None:
                merged[key] = value
        return merged

    def _clone_revision(self, clone_id: str) -> Dict:
        if not self.clone_store or not hasattr(self.clone_store, "get"):
            return {}
        record = self.clone_store.get(clone_id) or {}
        return {
            "updated_at": record.get("updated_at"),
            "file_size": record.get("file_size"),
            "reference_path": record.get("reference_path"),
        }

    def generate(
        self,
        voice_type: str,
        text: str,
        tts_options: Optional[Dict],
        config_override: Optional[Dict] = None,
    ) -> Dict:
        config = self._merged_config(self.tts_config, config_override)
        selection = parse_voice_key(voice_type, default_provider=config.get("provider"))
        clean_text = (
            PRESET_VOICE_PREVIEW_TEXT
            if selection.kind == "preset"
            else str(text or "").strip()[:120]
        )
        if not clean_text:
            raise ValueError("试听文本不能为空")
        provider_config = config if selection.provider == "doubao" else config.get("mimo") or {}
        requested_options = tts_options
        if selection.kind == "preset":
            requested_options = {
                "speed_level": "normal",
                "volume_ratio": 1.0,
                "style_prompt": "",
            }
        options = normalize_tts_options(requested_options, provider_config, selection.provider)
        if selection.kind == "preset" and selection.provider == "mimo":
            options["style_prompt"] = ""
        mimo = config.get("mimo") or {}
        if selection.kind == "preset":
            identity = {
                "version": PRESET_VOICE_PREVIEW_VERSION,
                "voice_type": selection.key,
            }
        else:
            identity = {
                "voice_type": selection.key,
                "text": clean_text,
                "options": options,
                "provider": selection.provider,
                "request_config": {
                    "auth_method": config.get("auth_method"),
                    "api_url": config.get("api_url"),
                    "cluster": config.get("cluster"),
                    "mimo_base_url": mimo.get("base_url"),
                    "mimo_model": mimo.get("model"),
                    "mimo_clone_model": mimo.get("clone_model"),
                    "mimo_format": mimo.get("format"),
                },
                "clone_revision": self._clone_revision(selection.voice_id),
            }
        digest = hashlib.sha256(
            json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:32]
        target = self.root / f"{digest}.wav"
        url = f"/media/_voice_previews/{target.name}"
        if target.exists() and target.stat().st_size > 44:
            return {"url": url, "path": str(target), "cached": True}

        generator = VoiceOverGenerator(
            output_dir=str(self.root),
            tts_config=config,
            clone_store=self.clone_store,
        )
        generated = Path(
            generator.generate(
                clean_text,
                filename=digest,
                voice_type=selection.key,
                speed_level=options.get("speed_level"),
                volume_ratio=options.get("volume_ratio"),
                style_prompt=options.get("style_prompt"),
            )
        )
        if generated.resolve() != target.resolve():
            generated.replace(target)
        if not target.exists() or target.stat().st_size <= 44:
            raise RuntimeError("试听音频生成失败")
        return {"url": url, "path": str(target), "cached": False}
