"""
FastAPI 路由
定义 API 端点
"""

import io
import json
import logging
import hashlib
import os
import platform
import shutil
import subprocess
import tempfile
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from threading import Thread, Lock
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Query, Body, UploadFile, File, Form, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from .models import (
    CreateTaskRequest,
    CreateTaskResponse,
    RegenerateAudioRequest,
    TaskResponse,
)
from .task_manager import task_manager, TaskStatus
from .task_executor import task_executor
from src.config import Config
from src.database import mysql_client
from src.draft.voice_catalog import (
    build_voice_key,
    normalize_tts_options,
    parse_voice_key,
)
from src.draft.voice_clone import VoiceCloneStore
from src.draft.voice_preview import VoicePreviewService
from src.draft.voiceover import VoiceOverGenerator
from src.text.provider_catalog import (
    get_provider,
    list_llm_providers,
    list_provider_models,
)
from src.text.provider_models import ProviderModelSyncError, refresh_provider_models
from src.utils.path_fixer import (
    apply_content_info,
    apply_extract_path,
    apply_meta_info,
    generate_fix_bat,
    generate_fix_sh,
    normalize_extract_path,
    validate_extract_path,
)
from src.utils.rendering import canvas_for_ratio, normalize_ratio
from src.utils.subtitle_text import normalize_subtitle_text

router = APIRouter(prefix="/ai/native/video/kepu", tags=["tasks"])
logger = logging.getLogger(__name__)

ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD_IMAGE_COUNT = 20
EXPORT_JOBS = {}
EXPORT_JOBS_LOCK = Lock()
ALLOWED_DOCUMENT_EXTENSIONS = {".txt", ".md", ".markdown", ".docx", ".pdf"}
MAX_DOCUMENT_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_VOICE_REFERENCE_UPLOAD_BYTES = 20 * 1024 * 1024


def _voice_clone_store() -> VoiceCloneStore:
    return VoiceCloneStore(Config.BASE_DIR, mysql_client)


def _model_dict(model, exclude_none: bool = False) -> dict:
    if model is None:
        return {}
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=exclude_none)
    return model.dict(exclude_none=exclude_none)


def _snapshot_tts_options(voice_type: str, options: Optional[dict] = None) -> dict:
    config = Config.tts_config()
    selection = parse_voice_key(voice_type, default_provider=config.get("provider"))
    provider_config = config if selection.provider == "doubao" else config.get("mimo") or {}
    normalized = normalize_tts_options(options, provider_config, selection.provider)
    snapshot = {"speed_level": normalized["speed_level"]}
    if selection.provider == "doubao":
        snapshot["volume_ratio"] = normalized["volume_ratio"]
    else:
        snapshot["style_prompt"] = normalized["style_prompt"]
    return snapshot


def _resolve_new_task_voice(voice_type: Optional[str]) -> str:
    config = Config.tts_config()
    default_provider = (config.get("provider") or "doubao").lower()
    if voice_type:
        selection = parse_voice_key(voice_type, default_provider=default_provider)
    elif default_provider == "mimo":
        default_voice = (config.get("mimo") or {}).get("default_voice") or "冰糖"
        selection = parse_voice_key(
            default_voice if str(default_voice).startswith("mimo-clone:")
            else build_voice_key("mimo", default_voice)
        )
    else:
        selection = parse_voice_key(
            build_voice_key(
                "doubao",
                config.get("default_voice") or "zh_male_jieshuoxiaoming_moon_bigtts",
            )
        )

    enabled_providers = config.get("enabled_providers") or ["doubao", "mimo"]
    if selection.provider not in enabled_providers:
        raise HTTPException(status_code=400, detail=f"{selection.provider} TTS 当前未启用")
    if selection.kind == "clone":
        clone = _voice_clone_store().get(selection.voice_id)
        if not clone:
            raise HTTPException(status_code=400, detail="克隆音色不存在")
        if clone.get("status") != "ready" or not clone.get("is_enabled"):
            raise HTTPException(status_code=400, detail="克隆音色需先试听成功并启用")
        return selection.key

    record = mysql_client.find_tts_voice(selection.provider, selection.voice_id)
    if record and record.get("is_enabled"):
        return selection.key
    if voice_type:
        raise HTTPException(status_code=400, detail="音色不存在或未对新任务开放")

    fallback = mysql_client.list_tts_voices(provider=selection.provider)
    if not fallback:
        fallback = mysql_client.list_tts_voices()
    if not fallback:
        raise HTTPException(status_code=400, detail="当前没有可用音色")
    return fallback[0]["id"]


def _parse_options_json(value) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _safe_draft_name(name: str, task_id: str) -> str:
    """生成可用的本地草稿目录名。"""
    base = (name or "本地上传图片").strip() or "本地上传图片"
    invalid_chars = set('<>:"/\\|?*\n\r\t')
    safe = "".join("_" if ch in invalid_chars else ch for ch in base).strip("._ ")
    safe = safe[:20] or "本地上传图片"
    return f"{safe}_{task_id[:8]}"


def _validate_upload_image(file: UploadFile):
    content_type = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()
    if content_type not in ALLOWED_IMAGE_CONTENT_TYPES and suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="只支持 JPG、PNG、WEBP 格式的图片")


def _decode_plain_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def _normalize_document_text(text: str) -> str:
    lines = [line.rstrip() for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized = "\n".join(lines)
    while "\n\n\n" in normalized:
        normalized = normalized.replace("\n\n\n", "\n\n")
    return normalized.strip()


def _extract_docx_text(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            document_xml = archive.read("word/document.xml")
    except KeyError:
        raise HTTPException(status_code=400, detail="DOCX 文件缺少正文内容")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="DOCX 文件格式无效")

    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError:
        raise HTTPException(status_code=400, detail="DOCX 正文解析失败")

    paragraphs = []
    for paragraph in root.findall(".//w:p", ns):
        parts = []
        for node in paragraph.iter():
            tag = node.tag.rsplit("}", 1)[-1]
            if tag == "t" and node.text:
                parts.append(node.text)
            elif tag == "tab":
                parts.append("\t")
            elif tag in {"br", "cr"}:
                parts.append("\n")
        line = "".join(parts).strip()
        if line:
            paragraphs.append(line)
    return "\n\n".join(paragraphs)


def _extract_pdf_text(content: bytes) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        raise HTTPException(status_code=501, detail="当前环境缺少 pdftotext，暂无法解析 PDF")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        result = subprocess.run(
            [pdftotext, "-layout", "-enc", "UTF-8", temp_path, "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="PDF 解析超时，请尝试更小的文件")
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="ignore").strip()
        raise HTTPException(status_code=400, detail=f"PDF 解析失败：{error or '文件格式无效'}")
    return result.stdout.decode("utf-8", errors="ignore")


def _extract_uploaded_document_text(filename: str, content: bytes) -> tuple[str, str]:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="只支持 TXT、Markdown、DOCX、PDF 文档")
    if suffix in {".txt", ".md", ".markdown"}:
        return _decode_plain_text(content), "text"
    if suffix == ".docx":
        return _extract_docx_text(content), "docx"
    if suffix == ".pdf":
        return _extract_pdf_text(content), "pdf"
    raise HTTPException(status_code=400, detail="不支持的文档格式")


def _task_animation_seed(task_id: str) -> int:
    return int(hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:12], 16)


def _segment_duration_seconds(segment: dict) -> float:
    try:
        duration = segment.get("duration")
        if duration:
            return float(duration)
    except (TypeError, ValueError):
        pass
    return 4.0


def _normalize_local_media_url(url: Optional[str], request: Request) -> Optional[str]:
    if not url or "/media/" not in url:
        return url
    media_path = url.split("/media/", 1)[1]
    return str(request.url_for("media", file_path=media_path))


def _local_media_url_from_path(path: Optional[str], request: Request) -> Optional[str]:
    if not path:
        return None
    try:
        resolved = Path(path).resolve()
    except (OSError, RuntimeError):
        return None

    for root in (Config.BASE_DIR / "output", Config.BASE_DIR / "data" / "media"):
        try:
            root_resolved = root.resolve()
            rel = resolved.relative_to(root_resolved)
        except (OSError, ValueError):
            continue
        return str(request.url_for("media", file_path=str(rel).replace(os.sep, "/")))
    return None


def _task_ratio(task) -> str:
    ratio = getattr(task, "ratio", "16:9")
    db_task = mysql_client.get_task(getattr(task, "task_id", ""))
    if db_task and db_task.get("ratio"):
        ratio = db_task.get("ratio")
    return normalize_ratio(ratio)


def _task_canvas(task) -> dict:
    return canvas_for_ratio(_task_ratio(task))


def _ratio_slug(ratio: str) -> str:
    return normalize_ratio(ratio).replace(":", "x")


def _media_fingerprint(task, segments: List[dict]) -> str:
    payload = {
        "ratio": _task_ratio(task),
        "animation_seed": _task_animation_seed(task.task_id),
        "segments": [
            {
                "text": seg.get("text") or "",
                "image_path": seg.get("image_path") or "",
                "audio_path": seg.get("audio_path") or "",
                "duration": seg.get("duration"),
            }
            for seg in segments
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _preview_manifest_path(task) -> Path:
    return Path(task.result.draft_path) / "previews" / "manifest_full.json"


def _read_preview_manifest(task) -> Optional[dict]:
    if not task.result or not task.result.draft_path:
        return None
    path = _preview_manifest_path(task)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[{task.task_id}] 读取最终预览 manifest 失败: {e}")
        return None


def _preview_state(task, segments: List[dict]) -> dict:
    ratio = _task_ratio(task)
    fingerprint = _media_fingerprint(task, segments)
    manifest = _read_preview_manifest(task)
    valid = False
    reason = "missing"
    if manifest:
        video_path = Path(manifest.get("video_path") or "")
        if manifest.get("fingerprint") != fingerprint:
            reason = "stale"
        elif normalize_ratio(manifest.get("ratio")) != ratio:
            reason = "ratio_mismatch"
        elif not video_path.exists():
            reason = "file_missing"
        else:
            valid = True
            reason = "valid"
    return {
        "exists": bool(manifest),
        "valid": valid,
        "reason": reason,
        "fingerprint": fingerprint,
        "manifest": manifest,
    }


def _write_preview_manifest(task, video_path: Path, preview_url: str, segments: List[dict]) -> dict:
    manifest = {
        "video_path": str(video_path),
        "preview_url": preview_url,
        "ratio": _task_ratio(task),
        "canvas": _task_canvas(task),
        "fingerprint": _media_fingerprint(task, segments),
        "created_at": datetime.now().isoformat(),
    }
    path = _preview_manifest_path(task)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _official_video_path(task) -> Path:
    draft_path = Path(task.result.draft_path)
    return draft_path / f"{draft_path.name}.mp4"


def _draft_zip_path(task) -> Path:
    draft_path = Path(task.result.draft_path)
    return draft_path / f"{draft_path.name}.zip"


def _pack_draft_zip(task) -> Path:
    draft_path = Path(task.result.draft_path)
    zip_path = _draft_zip_path(task)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in draft_path.rglob("*"):
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(draft_path)
            if rel_path.parts and rel_path.parts[0] in {"previews"}:
                continue
            if file_path.suffix.lower() in {".zip", ".mp4"}:
                continue
            zf.write(file_path, rel_path)
    return zip_path


def _server_target_os() -> str:
    if sys_platform := platform.system().lower():
        if "darwin" in sys_platform:
            return "mac"
        if "windows" in sys_platform:
            return "windows"
    return "mac" if os.name != "nt" else "windows"


def _pick_local_folder() -> Optional[str]:
    """在运行后端的本机弹出系统目录选择器。用户取消时返回 None。"""
    if _server_target_os() == "mac":
        script = 'POSIX path of (choose folder with prompt "选择剪映草稿根目录 com.lveditor.draft")'
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip().rstrip("/")

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(title="选择剪映草稿根目录")
        root.destroy()
        return folder or None
    except Exception as e:
        logger.warning(f"系统目录选择器不可用: {e}")
        return None


def _check_writable_dir(path: Path) -> tuple[bool, Optional[str]]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".kepu_write_test_{uuid.uuid4().hex}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, None
    except Exception as e:
        return False, str(e)


def _validate_local_draft_root(draft_root: str, target_os: Optional[str] = None) -> dict:
    target_os = "mac" if target_os == "mac" else "windows" if target_os == "windows" else _server_target_os()
    valid_path, normalized, issues = validate_extract_path(draft_root, target_os)
    warnings = []

    if target_os != _server_target_os():
        issues.append("直接写入只能选择运行后端这台电脑上的剪映草稿目录")

    root_path = Path(normalized) if normalized else None
    if root_path:
        if root_path.exists() and not root_path.is_dir():
            issues.append("选择的路径不是文件夹")
        else:
            if any((root_path / name).exists() for name in ("draft_info.json", "draft_content.json", "draft_meta_info.json")):
                issues.append("你选择的是单个草稿目录，请选择它的上一级剪映草稿根目录")
            writable, error = _check_writable_dir(root_path)
            if not writable:
                issues.append(f"目录不可写：{error}")

        if root_path.name not in {"com.lveditor.draft", "JianyingPro Drafts", "Drafts"}:
            warnings.append("这个目录名不像剪映草稿根目录，请确认选的是剪映的草稿列表目录")

    blocking = any(
        "必须" in item
        or "请填写" in item
        or "不可写" in item
        or "不是文件夹" in item
        or "只能选择" in item
        or "单个草稿目录" in item
        for item in issues
    )
    return {
        "valid": valid_path and not blocking,
        "path": normalized,
        "target_os": target_os,
        "issues": issues,
        "warnings": warnings,
    }


def _normalize_draft_files_for_location(draft_dir: Path, draft_root: str, draft_name: str, target_os: str) -> None:
    if target_os == "mac":
        _normalize_mac_draft_files(draft_dir, draft_root, draft_name)
        return

    now_us = int(time.time() * 1_000_000)
    content_path = draft_dir / "draft_content.json"
    meta_path = draft_dir / "draft_meta_info.json"

    if content_path.exists():
        content = json.loads(content_path.read_text(encoding="utf-8"))
        content = apply_extract_path(content, draft_root, draft_name, target_os=target_os, force=True)
        content = apply_content_info(content, draft_name, target_os=target_os, now_us=now_us)
        content_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")

    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta = apply_meta_info(meta, draft_root, draft_name, target_os=target_os, now_us=now_us)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _infer_ratio_from_content(content: dict) -> str:
    canvas = content.get("canvas_config") or {}
    ratio = canvas.get("ratio")
    if ratio in {"16:9", "9:16", "3:4"}:
        return ratio
    width = canvas.get("width") or 1920
    height = canvas.get("height") or 1080

    # 计算宽高比
    ratio_value = width / height if height > 0 else 1.0

    # 判断最接近的比例
    if abs(ratio_value - 0.75) < 0.1:  # 3:4 (0.75)
        return "3:4"
    elif abs(ratio_value - 1.0) < 0.1:  # 接近方形，归为3:4
        return "3:4"
    elif ratio_value > 1.5:  # 16:9 (1.778)
        return "16:9"
    else:  # 9:16 (0.5625)
        return "9:16"


def _resolve_material_source(draft_dir: Path, raw_path: str) -> Path:
    clean = str(raw_path or "").strip().strip("'\"").replace("\\", "/")
    if "##/" in clean:
        clean = clean.split("##/", 1)[1]
    if clean.startswith("##_draftpath_placeholder_") and "_##/" in clean:
        clean = clean.split("_##/", 1)[1]
    path = Path(clean)
    if path.is_absolute():
        return path
    return draft_dir / clean


def _mac_material_folder(path: Path, default_folder: str) -> str:
    if default_folder == "audio":
        return "audio"
    if path.suffix.lower() in {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}:
        return "video"
    return "image"


def _media_suffix_from_magic(path: Path) -> Optional[str]:
    """Return the real image/video suffix when the file header is unambiguous."""
    try:
        header = path.read_bytes()[:32]
    except Exception:
        return None
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return ".webp"
    return None


def _mac_target_filename(source: Path, raw_path: str, folder: str) -> str:
    filename = source.name or Path(str(raw_path or "")).name
    if folder == "image" and source.exists():
        real_suffix = _media_suffix_from_magic(source)
        if real_suffix:
            filename = f"{source.stem}{real_suffix}"
    return filename


def _copy_mac_material(draft_dir: Path, raw_path: str, default_folder: str) -> str:
    source = _resolve_material_source(draft_dir, raw_path)
    folder = _mac_material_folder(source, default_folder)
    filename = _mac_target_filename(source, raw_path, folder)
    target_dir = draft_dir / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    if source.exists() and source.resolve() != target.resolve():
        shutil.copy2(source, target)
    # Mac 剪映会在首次打开后迁移/加密 draft_info。这里写入本机绝对路径，
    # 避免占位符路径在迁移时无法映射到我们新建的草稿目录。
    return str(target)


def _material_ids(content: dict) -> set:
    ids = set()
    for values in content.get("materials", {}).values():
        if isinstance(values, list):
            for item in values:
                if isinstance(item, dict) and item.get("id"):
                    ids.add(item["id"])
    return ids


def _remove_dangling_extra_refs(content: dict) -> int:
    ids = _material_ids(content)
    removed = 0
    for track in content.get("tracks", []):
        for segment in track.get("segments", []):
            refs = segment.get("extra_material_refs")
            if not isinstance(refs, list):
                continue
            clean_refs = [ref for ref in refs if ref in ids]
            removed += len(refs) - len(clean_refs)
            segment["extra_material_refs"] = clean_refs
    return removed


def _normalize_mac_draft_files(draft_dir: Path, draft_root: str, draft_name: str) -> None:
    """把 pyJianYingDraft 的 Windows 风格草稿转成 Mac 剪映目录形态。"""
    now_us = int(time.time() * 1_000_000)
    content_path = draft_dir / "draft_content.json"
    info_path = draft_dir / "draft_info.json"
    meta_path = draft_dir / "draft_meta_info.json"
    if not content_path.exists() and info_path.exists():
        content_path = info_path
    if not content_path.exists():
        raise RuntimeError("缺少 draft_content.json，无法生成 Mac 剪映草稿")

    content = json.loads(content_path.read_text(encoding="utf-8"))
    first_image_path = None
    for video in content.get("materials", {}).get("videos", []):
        raw_path = video.get("path") or video.get("media_path") or ""
        mac_path = _copy_mac_material(draft_dir, raw_path, "image")
        video["path"] = mac_path
        video["media_path"] = ""
        video["material_name"] = Path(mac_path).name
        if Path(mac_path).parent.name == "image" and first_image_path is None:
            first_image_path = Path(mac_path)

    for audio in content.get("materials", {}).get("audios", []):
        raw_path = audio.get("path") or ""
        mac_path = _copy_mac_material(draft_dir, raw_path, "audio")
        audio["path"] = mac_path
        audio["name"] = audio.get("name") or Path(mac_path).name

    removed_refs = _remove_dangling_extra_refs(content)
    if removed_refs:
        logger.warning("Mac 剪映草稿清理了 %s 个悬空素材引用：%s", removed_refs, draft_dir)

    ratio = _infer_ratio_from_content(content)
    content = apply_content_info(content, draft_name, target_os="mac", now_us=now_us)
    content["platform"] = {
        "os": "web",
        "os_version": "",
        "app_version": "15.4.0",
        "app_source": "",
        "device_id": "",
        "hard_disk_id": "",
        "mac_address": "",
        "app_id": 348188,
    }
    content["last_modified_platform"] = dict(content["platform"])
    content["version"] = max(int(content.get("version") or 0), 400000)
    content["new_version"] = "127.0.0"
    canvas = content.setdefault("canvas_config", {})
    canvas["ratio"] = ratio
    canvas.setdefault("width", _task_canvas_from_ratio(ratio)["width"])
    canvas.setdefault("height", _task_canvas_from_ratio(ratio)["height"])
    content["path"] = ""

    info_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    if content_path.name == "draft_content.json":
        content_path.unlink(missing_ok=True)

    for folder in ("common_attachment", "cover", "effect"):
        (draft_dir / folder).mkdir(exist_ok=True)
    if first_image_path and first_image_path.exists():
        shutil.copy2(first_image_path, draft_dir / "draft_cover.jpg")

    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        meta = {}
    meta = apply_meta_info(meta, draft_root, draft_name, target_os="mac", now_us=now_us)
    meta["draft_cover"] = "draft_cover.jpg" if (draft_dir / "draft_cover.jpg").exists() else meta.get("draft_cover", "")
    meta["draft_materials"] = []
    meta["draft_timeline_materials_size_"] = sum(
        file_path.stat().st_size for folder in ("image", "audio", "video")
        for file_path in (draft_dir / folder).glob("*") if file_path.is_file()
    )
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    for legacy in ("images", "voiceovers", "audios"):
        legacy_path = draft_dir / legacy
        if legacy_path.exists():
            shutil.rmtree(legacy_path)


def _task_canvas_from_ratio(ratio: str) -> dict:
    return canvas_for_ratio(normalize_ratio(ratio))


def _draft_preflight(draft_dir: Path, target_os: Optional[str] = None) -> dict:
    issues = []
    warnings = []
    is_mac = target_os == "mac"
    content_path = draft_dir / "draft_info.json" if is_mac else draft_dir / "draft_content.json"
    meta_path = draft_dir / "draft_meta_info.json"

    if not content_path.exists():
        issues.append("缺少 draft_info.json" if is_mac else "缺少 draft_content.json")
    if not meta_path.exists():
        issues.append("缺少 draft_meta_info.json")

    if content_path.exists():
        try:
            content = json.loads(content_path.read_text(encoding="utf-8"))
            if not content.get("name"):
                warnings.append("draft_content.json 缺少草稿名称")
            if not content.get("tracks"):
                issues.append("draft_content.json 没有轨道数据")
            material_ids = _material_ids(content)
            materials = content.get("materials", {})
            for group in ("videos", "audios"):
                for item in materials.get(group, []):
                    path = str(item.get("path") or "").strip().strip("'\"")
                    if not path:
                        issues.append(f"{group} 存在空素材路径")
                        continue
                    clean_path = path.replace("\\", "/")
                    if is_mac and clean_path.startswith("##_draftpath_placeholder_") and "_##/" in clean_path:
                        clean_path = clean_path.split("_##/", 1)[1]
                    local_path = Path(clean_path) if Path(clean_path).is_absolute() else draft_dir / clean_path
                    if not local_path.exists():
                        issues.append(f"素材不存在：{path}")
                    if is_mac and group == "videos":
                        real_suffix = _media_suffix_from_magic(local_path)
                        if real_suffix and local_path.suffix.lower() != real_suffix:
                            issues.append(f"图片扩展名和真实格式不一致：{path} 应为 {real_suffix}")
            dangling_refs = []
            for track in content.get("tracks", []):
                for segment in track.get("segments", []):
                    refs = segment.get("extra_material_refs")
                    if isinstance(refs, list):
                        dangling_refs.extend(ref for ref in refs if ref not in material_ids)
            if dangling_refs:
                issues.append(f"存在 {len(dangling_refs)} 个悬空素材引用")
        except Exception as e:
            issues.append(f"{content_path.name} 解析失败：{e}")

    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if not meta.get("draft_name"):
                warnings.append("draft_meta_info.json 缺少草稿名称")
            if not meta.get("draft_fold_path"):
                warnings.append("draft_meta_info.json 缺少草稿目录路径")
        except Exception as e:
            issues.append(f"draft_meta_info.json 解析失败：{e}")

    return {
        "valid": not issues,
        "issues": issues,
        "warnings": warnings,
        "draft_path": str(draft_dir),
        "target_os": target_os or _server_target_os(),
    }


def _set_task_result_preserving(task, segments_count: int, draft_url: Optional[str] = None, video_url: Optional[str] = None):
    existing_draft_url = task.result.draft_url if task.result else None
    existing_video_url = task.result.video_url if task.result else None
    task_manager.set_task_result(
        task.task_id,
        task.result.draft_path,
        segments_count,
        draft_url=draft_url if draft_url is not None else existing_draft_url,
        video_url=video_url if video_url is not None else existing_video_url,
    )


def _asset_label(asset_type: str, source: str, segment_index: Optional[int], path: Optional[str] = None) -> str:
    source_map = {
        "generated": "AI 生成",
        "regenerated": "重新生成",
        "upload": "本地上传",
        "selected": "历史选择",
        "legacy": "历史素材",
        "subtitle": "字幕素材",
    }
    prefix = source_map.get(source, source or "素材")
    if segment_index is not None:
        return f"{prefix} · 分镜 {segment_index + 1}"
    if path:
        return Path(path).name
    return prefix


def _record_asset(
    task_id: str,
    asset_type: str,
    source: str,
    path: Optional[str] = None,
    url: Optional[str] = None,
    segment_index: Optional[int] = None,
    label: Optional[str] = None,
    prompt: Optional[str] = None,
    text: Optional[str] = None,
    voice_type: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    return mysql_client.save_task_asset(
        task_id=task_id,
        asset_type=asset_type,
        source=source,
        path=path,
        url=url,
        segment_index=segment_index,
        label=label or _asset_label(asset_type, source, segment_index, path),
        prompt=prompt,
        text=text,
        voice_type=voice_type,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
    )


def _format_srt_timestamp(seconds: float) -> str:
    millis = int(max(0, seconds) * 1000)
    hours = millis // 3_600_000
    millis %= 3_600_000
    minutes = millis // 60_000
    millis %= 60_000
    secs = millis // 1000
    millis %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _subtitle_srt_path(task) -> Path:
    return Path(task.result.draft_path) / "subtitles" / f"{Path(task.result.draft_path).name}.srt"


def _write_task_srt(task, segments: List[dict]) -> Path:
    srt_path = _subtitle_srt_path(task)
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    cursor = 0.0
    blocks = []
    for index, seg in enumerate(segments, start=1):
        duration = _segment_duration_seconds(seg)
        start = cursor
        end = cursor + duration
        text = normalize_subtitle_text(seg.get("text") or "")
        blocks.append(f"{index}\n{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}\n{text}\n")
        cursor = end
    srt_path.write_text("\n".join(blocks), encoding="utf-8")
    return srt_path


def _ensure_task_assets(task, segments: List[dict]):
    """兼容旧任务：从段落表和草稿目录尽量补齐资产记录。"""
    if not task.result or not task.result.draft_path:
        return
    draft_path = Path(task.result.draft_path)
    current_paths = set()

    for seg in segments:
        index = seg.get("segment_index")
        image_path = seg.get("image_path")
        if image_path:
            current_paths.add(str(image_path))
            _record_asset(
                task.task_id,
                "image",
                "legacy",
                path=str(image_path),
                url=seg.get("image_url"),
                segment_index=index,
                prompt=seg.get("image_prompt"),
                text=seg.get("text"),
            )
        audio_path = seg.get("audio_path")
        if audio_path:
            current_paths.add(str(audio_path))
            _record_asset(
                task.task_id,
                "audio",
                "legacy",
                path=str(audio_path),
                url=seg.get("audio_url"),
                segment_index=index,
                text=seg.get("text"),
                voice_type=getattr(task, "voice_type", None),
            )

    for dirname, asset_type in (("images", "image"), ("voiceovers", "audio")):
        folder = draft_path / dirname
        if not folder.exists():
            continue
        for file_path in folder.iterdir():
            if not file_path.is_file():
                continue
            suffix = file_path.suffix.lower()
            if asset_type == "image" and suffix not in ALLOWED_IMAGE_EXTENSIONS:
                continue
            if asset_type == "audio" and suffix not in {".wav", ".mp3", ".m4a", ".aac"}:
                continue
            source = "upload" if "_upload" in file_path.name else ("regenerated" if "_regen" in file_path.name else "legacy")
            segment_index = None
            if file_path.name.startswith("seg_"):
                try:
                    segment_index = int(file_path.name.split("_", 2)[1])
                except (ValueError, IndexError):
                    segment_index = None
            _record_asset(
                task.task_id,
                asset_type,
                source,
                path=str(file_path),
                segment_index=segment_index,
                voice_type=getattr(task, "voice_type", None) if asset_type == "audio" else None,
            )

    if segments:
        srt_path = _write_task_srt(task, segments)
        _record_asset(
            task.task_id,
            "subtitle",
            "subtitle",
            path=str(srt_path),
            label="项目字幕 SRT",
            text="\n".join(normalize_subtitle_text(seg.get("text") or "") for seg in segments),
        )


def _asset_to_response(asset: dict, request: Request) -> dict:
    asset_id = asset.get("asset_id")
    path = asset.get("path")
    has_file = bool(path and Path(path).is_file())
    file_url = str(request.url_for("download_task_asset_file", task_id=asset["task_id"], asset_id=asset_id)) if has_file else None
    return {
        "asset_id": asset_id,
        "task_id": asset.get("task_id"),
        "segment_index": asset.get("segment_index"),
        "asset_type": asset.get("asset_type"),
        "source": asset.get("source"),
        "path": path,
        "url": _normalize_local_media_url(asset.get("url"), request),
        "file_url": file_url,
        "download_url": file_url,
        "has_file": has_file,
        "label": asset.get("label") or _asset_label(asset.get("asset_type"), asset.get("source"), asset.get("segment_index"), path),
        "prompt": asset.get("prompt"),
        "text": asset.get("text"),
        "voice_type": asset.get("voice_type"),
        "created_at": asset.get("created_at"),
    }


def _export_job_snapshot(job_id: str) -> dict:
    with EXPORT_JOBS_LOCK:
        return dict(EXPORT_JOBS.get(job_id, {}))


def _update_export_job(job_id: str, **updates):
    with EXPORT_JOBS_LOCK:
        job = EXPORT_JOBS.get(job_id)
        if not job:
            return
        job.update(updates)
        job["updated_at"] = datetime.now().isoformat()


def _create_export_job(task_id: str, target: str, payload: Optional[dict] = None) -> dict:
    job_id = uuid.uuid4().hex
    now = datetime.now().isoformat()
    job = {
        "job_id": job_id,
        "task_id": task_id,
        "target": target,
        "status": "pending",
        "message": "等待开始",
        "result": None,
        "error": None,
        "params": payload or {},
        "created_at": now,
        "updated_at": now,
    }
    with EXPORT_JOBS_LOCK:
        EXPORT_JOBS[job_id] = job
    return job


def _active_export_jobs(task_id: str) -> List[dict]:
    with EXPORT_JOBS_LOCK:
        return [
            dict(job) for job in EXPORT_JOBS.values()
            if job.get("task_id") == task_id and job.get("status") in {"pending", "processing"}
        ]


def _run_export_job(job_id: str, target: str, use_preview: bool, payload: Optional[dict] = None):
    _update_export_job(job_id, status="processing", message="正在准备导出")
    job = _export_job_snapshot(job_id)
    task_id = job.get("task_id")
    try:
        task = task_manager.get_task(task_id)
        if not task:
            raise RuntimeError("任务不存在")
        if not task.result or not task.result.draft_path:
            raise RuntimeError("草稿路径不存在")

        segments = mysql_client.get_segments(task_id)
        if not segments:
            raise RuntimeError("段落数据不存在")

        if target == "mp4":
            result = _export_mp4(task, segments, use_preview)
        elif target == "draft":
            result = _export_draft(task, segments)
        elif target == "draft_local":
            result = _export_draft_local(task, segments, payload or {})
        else:
            raise RuntimeError("不支持的导出类型")

        _update_export_job(job_id, status="completed", message="导出完成", result=result)
    except Exception as e:
        logger.exception(f"[{task_id}] 导出任务失败: {e}")
        _update_export_job(job_id, status="failed", message="导出失败", error=str(e))


def _export_mp4(task, segments: List[dict], use_preview: bool) -> dict:
    from src.export.ffmpeg_exporter import FFmpegExporter
    from src.utils.local_uploader import LocalUploader

    output_path = _official_video_path(task)
    preview = _preview_state(task, segments)
    source = "rendered"

    if use_preview and preview["valid"]:
        manifest = preview["manifest"]
        shutil.copy2(manifest["video_path"], output_path)
        source = "preview"
    else:
        segment_texts = [seg.get("text") or "" for seg in segments]
        media_paths = [seg.get("image_path") for seg in segments]
        voiceover_files = [seg.get("audio_path") for seg in segments]
        missing = [path for path in media_paths if not path or not Path(path).exists()]
        if missing:
            raise RuntimeError("分镜图片文件不存在，无法导出 MP4")
        FFmpegExporter(canvas=_task_canvas(task)).export(
            segments=segment_texts,
            media_paths=media_paths,
            voiceover_files=voiceover_files,
            output_path=str(output_path),
            animation_seed=_task_animation_seed(task.task_id),
        )

    video_url = LocalUploader().upload(
        str(output_path),
        f"{task.task_id}/exports/{output_path.stem}_{_ratio_slug(_task_ratio(task))}_{int(time.time())}.mp4",
    )
    _set_task_result_preserving(task, len(segments), video_url=video_url)
    return {
        "target": "mp4",
        "source": source,
        "video_path": str(output_path),
        "video_url": video_url,
        "ratio": _task_ratio(task),
        "canvas": _task_canvas(task),
    }


def _build_editable_draft(task, segments: List[dict]) -> Path:
    from src.core.pipeline import VideoEditorPipeline

    segment_texts = [seg.get("text") or "" for seg in segments]
    media_paths = [seg.get("image_path") for seg in segments]
    voiceover_files = [seg.get("audio_path") for seg in segments]
    missing = [path for path in media_paths if not path or not Path(path).exists()]
    if missing:
        raise RuntimeError("分镜图片文件不存在，无法导出剪映草稿")

    draft_name = Path(task.result.draft_path).name
    pipeline = VideoEditorPipeline(theme=task.theme, output_dir=task.result.draft_path, canvas=_task_canvas(task))
    draft_path = pipeline.draft_builder.build(
        segments=segment_texts,
        media_paths=media_paths,
        draft_name=draft_name,
        voiceover_files=voiceover_files,
        animation_seed=_task_animation_seed(task.task_id),
        output_dir=task.result.draft_path,
    )
    return Path(draft_path)


def _export_draft(task, segments: List[dict]) -> dict:
    from src.utils.local_uploader import LocalUploader

    draft_path = _build_editable_draft(task, segments)
    zip_path = _pack_draft_zip(task)
    draft_url = LocalUploader().upload(
        str(zip_path),
        f"{task.task_id}/exports/{zip_path.stem}_{_ratio_slug(_task_ratio(task))}_{int(time.time())}.zip",
    )
    _set_task_result_preserving(task, len(segments), draft_url=draft_url)
    return {
        "target": "draft",
        "draft_path": draft_path,
        "zip_path": str(zip_path),
        "draft_url": draft_url,
        "ratio": _task_ratio(task),
        "canvas": _task_canvas(task),
    }


def _export_draft_local(task, segments: List[dict], payload: dict) -> dict:
    draft_root = (payload or {}).get("draft_root") or (payload or {}).get("extract_path")
    target_os = (payload or {}).get("target_os") or _server_target_os()
    overwrite = bool((payload or {}).get("overwrite", True))
    root_check = _validate_local_draft_root(draft_root, target_os)
    if not root_check["valid"]:
        raise RuntimeError("；".join(root_check["issues"] or ["剪映草稿目录不可用"]))

    source_draft = _build_editable_draft(task, segments)
    draft_name = source_draft.name
    draft_root_path = Path(root_check["path"])
    target_draft = draft_root_path / draft_name

    if target_draft.exists():
        if not overwrite:
            raise RuntimeError(f"剪映草稿已存在：{target_draft}")
        shutil.rmtree(target_draft)

    def _ignore_export_artifacts(_dir, names):
        return {
            name for name in names
            if name == "previews" or name.endswith(".zip") or name.endswith(".mp4")
        }

    shutil.copytree(source_draft, target_draft, ignore=_ignore_export_artifacts)
    _normalize_draft_files_for_location(target_draft, root_check["path"], draft_name, root_check["target_os"])
    preflight = _draft_preflight(target_draft, root_check["target_os"])
    if not preflight["valid"]:
        raise RuntimeError("；".join(preflight["issues"]))

    task_manager.update_extract_path(task.task_id, root_check["path"])

    return {
        "target": "draft_local",
        "draft_root": root_check["path"],
        "draft_path": str(target_draft),
        "draft_name": draft_name,
        "ratio": _task_ratio(task),
        "canvas": _task_canvas(task),
        "preflight": preflight,
        "warnings": root_check["warnings"] + preflight["warnings"],
    }


@router.get("/config")
async def get_config():
    """获取模型配置"""
    return Config.load_model_config()


@router.put("/config")
async def update_config(config: dict = Body(...)):
    """更新模型配置"""
    return Config.save_model_config(config)


@router.post("/config/test-tts")
async def test_tts_config(request: Request, payload: dict = Body(...)):
    """用当前表单配置合成一句短音频，确认 TTS 配置能真实跑通。"""
    model_config = Config.load_model_config()
    incoming_tts = payload.get("tts")
    if isinstance(incoming_tts, dict):
        model_config["tts"].update({
            key: value
            for key, value in incoming_tts.items()
            if value is not None
        })
    Config._normalize_model_config(model_config)

    test_text = str(payload.get("text") or "InsightCut 配音配置测试成功。")[:80]
    if (model_config["tts"].get("provider") or "doubao").lower() == "mimo":
        voice_type = payload.get("voice_type") or (model_config["tts"].get("mimo") or {}).get("default_voice")
    else:
        voice_type = payload.get("voice_type") or model_config["tts"].get("default_voice")
    output_dir = Config.BASE_DIR / "data" / "media" / "_config_tests"
    filename = f"tts_{uuid.uuid4().hex[:10]}"

    try:
        generator = VoiceOverGenerator(output_dir=str(output_dir), tts_config=model_config["tts"])
        audio_path = Path(generator.generate(test_text, filename=filename, voice_type=voice_type))
    except Exception as exc:
        logger.exception("TTS 配置测试失败")
        raise HTTPException(status_code=502, detail=f"TTS 配置测试失败: {exc}") from exc

    media_path = f"_config_tests/{audio_path.name}"
    return {
        "ok": True,
        "provider": model_config["tts"].get("provider"),
        "auth_method": model_config["tts"].get("auth_method"),
        "voice_type": voice_type,
        "url": str(request.url_for("media", file_path=media_path)) if request else f"/media/{media_path}",
    }


@router.post("/config/models")
async def fetch_config_models(config: dict = Body(...)):
    """根据当前填写的 Base URL 和 API Key 拉取可选模型列表。"""
    protocol = (config.get("protocol") or "openai").lower()
    result = None
    error_status = None
    error_detail = None
    try:
        result = refresh_provider_models("custom", config)
    except ProviderModelSyncError as exc:
        error_status = exc.status_code
        error_detail = exc.public_message
    config = None
    if error_status is not None:
        result = None
        raise HTTPException(
            status_code=error_status, detail=error_detail
        ) from None

    prefix = f"{protocol}/"
    models = []
    for model in result["models"]:
        model_id = str(model.get("id") or "")
        if model_id.startswith(prefix):
            model_id = model_id[len(prefix):]
        models.append({"id": model_id, "label": model.get("label") or model_id})
    return {"models_url": result["models_url"], "models": models}


@router.get("/config/llm-providers")
async def get_llm_providers():
    return {"providers": list_llm_providers()}


@router.get("/config/llm-providers/{provider_id}/models")
async def get_llm_provider_models(provider_id: str):
    if not get_provider(provider_id):
        raise HTTPException(status_code=404, detail="生文服务商不存在")
    return {
        "provider": provider_id,
        "models": list_provider_models(provider_id),
    }


@router.post("/config/llm-providers/{provider_id}/models/refresh")
async def refresh_llm_provider_models(
    provider_id: str, payload: dict = Body(...)
):
    result = None
    error_status = None
    error_detail = None
    try:
        result = refresh_provider_models(provider_id, payload)
    except ProviderModelSyncError as exc:
        error_status = exc.status_code
        error_detail = exc.public_message
    payload = None
    if error_status is not None:
        result = None
        raise HTTPException(
            status_code=error_status, detail=error_detail
        ) from None
    return result


@router.get("/render-config")
async def get_render_config():
    """获取前端实时预览和 FFmpeg 导出共用的渲染参数。"""
    from src.export.ffmpeg_exporter import FFmpegExporter

    return FFmpegExporter.get_render_config()


@router.get("/voices")
async def get_voices(
    provider: Optional[str] = Query(None),
    include_disabled: bool = Query(False),
):
    """返回双 provider 预置音色与 MiMo 本地克隆音色。"""
    normalized_provider = (provider or "").strip().lower() or None
    if normalized_provider not in {None, "doubao", "mimo"}:
        raise HTTPException(status_code=400, detail="provider 只支持 doubao 或 mimo")
    presets = mysql_client.list_tts_voices(
        provider=normalized_provider,
        include_disabled=include_disabled,
    )
    result = [
        {
            "id": voice["id"],
            "voice_id": voice["voice_id"],
            "name": voice["name"],
            "gender": voice.get("gender") or "unknown",
            "language": voice.get("language") or "zh",
            "description": voice.get("description") or "",
            "provider": voice["provider"],
            "kind": "preset",
            "source": voice.get("source") or "builtin",
            "is_enabled": bool(voice.get("is_enabled")),
            "status": "ready",
            "preview_url": voice.get("preview_url"),
            "capabilities": voice.get("capabilities") or {},
        }
        for voice in presets
    ]
    if normalized_provider in {None, "mimo"}:
        for clone in _voice_clone_store().list(include_hidden=include_disabled):
            if not include_disabled and not (
                clone.get("status") == "ready" and clone.get("is_enabled")
            ):
                continue
            result.append({
                "id": clone["voice_type"],
                "voice_id": clone["clone_id"],
                "name": clone["name"],
                "gender": "custom",
                "language": "auto",
                "description": "MiMo 本地参考音频克隆音色",
                "provider": "mimo",
                "kind": "clone",
                "source": "local-clone",
                "is_enabled": bool(clone.get("is_enabled")),
                "status": clone.get("status"),
                "preview_url": clone.get("preview_url"),
                "capabilities": {"style_prompt": True, "speed_level": True},
            })
    return result


@router.put("/voices/availability")
async def update_voice_availability(payload: dict = Body(...)):
    voice_keys = payload.get("voice_keys")
    if not isinstance(voice_keys, list) or not all(isinstance(key, str) for key in voice_keys):
        raise HTTPException(status_code=400, detail="voice_keys 必须是音色 ID 数组")
    try:
        mysql_client.set_voice_availability(voice_keys)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    enabled = mysql_client.list_tts_voices()
    return {"enabled_voice_keys": [voice["id"] for voice in enabled]}


@router.post("/voices/preview")
async def preview_voice(payload: dict = Body(...)):
    voice_type = str(payload.get("voice_type") or "").strip()
    if not voice_type:
        raise HTTPException(status_code=400, detail="请选择试听音色")
    text = str(payload.get("text") or Config.tts_config().get("preview_text") or "这是音色试听。")[:120]
    store = _voice_clone_store()
    try:
        service = VoicePreviewService(
            base_dir=Config.BASE_DIR,
            tts_config=Config.tts_config(),
            clone_store=store,
        )
        return service.generate(
            voice_type,
            text,
            payload.get("tts_options") or {},
            config_override=payload.get("config_override"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("TTS 音色试听失败")
        raise HTTPException(status_code=502, detail=f"音色试听失败: {exc}") from exc


@router.get("/voice-clones")
async def list_voice_clones(include_hidden: bool = Query(False)):
    return _voice_clone_store().list(include_hidden=include_hidden)


@router.post("/voice-clones")
async def create_voice_clone(
    name: str = Form(...),
    consent_confirmed: bool = Form(...),
    file: UploadFile = File(...),
):
    suffix = Path(file.filename or "reference.wav").suffix.lower() or ".wav"
    if suffix not in {".mp3", ".wav", ".webm", ".ogg"}:
        raise HTTPException(status_code=400, detail="只支持 MP3、WAV 或浏览器录音")
    content = await file.read(MAX_VOICE_REFERENCE_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="参考音频为空")
    if len(content) > MAX_VOICE_REFERENCE_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="参考音频不能超过 20 MB")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as staged:
            staged.write(content)
            temporary = Path(staged.name)
        return _voice_clone_store().create(name, temporary, consent_confirmed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


@router.patch("/voice-clones/{clone_id}")
async def update_voice_clone(clone_id: str, payload: dict = Body(...)):
    try:
        return _voice_clone_store().update(clone_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/voice-clones/{clone_id}/reference")
async def replace_voice_clone_reference(
    clone_id: str,
    file: UploadFile = File(...),
):
    suffix = Path(file.filename or "reference.wav").suffix.lower() or ".wav"
    content = await file.read(MAX_VOICE_REFERENCE_UPLOAD_BYTES + 1)
    if not content or len(content) > MAX_VOICE_REFERENCE_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="参考音频为空或过大")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as staged:
            staged.write(content)
            temporary = Path(staged.name)
        return _voice_clone_store().replace_reference(clone_id, temporary)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


@router.post("/voice-clones/{clone_id}/preview")
async def preview_voice_clone(clone_id: str, payload: dict = Body(default={})):
    store = _voice_clone_store()
    clone = store.get(clone_id)
    if not clone:
        raise HTTPException(status_code=404, detail="克隆音色不存在")
    text = str(payload.get("text") or Config.tts_config().get("preview_text") or "这是我的声音试听。")[:120]
    try:
        preview = VoicePreviewService(
            base_dir=Config.BASE_DIR,
            tts_config=Config.tts_config(),
            clone_store=store,
        ).generate(
            clone["voice_type"],
            text,
            payload.get("tts_options") or {},
            config_override=payload.get("config_override"),
        )
        ready = store.mark_ready(clone_id, Path(preview["path"]))
        return {"clone": ready, "preview": preview}
    except Exception as exc:
        store.mark_failed(clone_id, str(exc))
        logger.exception("MiMo 克隆音色试听失败")
        raise HTTPException(status_code=502, detail=f"克隆音色试听失败: {exc}") from exc


@router.delete("/voice-clones/{clone_id}")
async def delete_voice_clone(clone_id: str):
    try:
        return _voice_clone_store().delete_or_hide(clone_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/documents/extract-text")
async def extract_document_text(file: UploadFile = File(...)):
    """提取上传文档中的纯文本，用于文稿页导入。"""
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="只支持 TXT、Markdown、DOCX、PDF 文档")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文档内容为空")
    if len(content) > MAX_DOCUMENT_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文档不能超过 20MB")

    text, document_type = _extract_uploaded_document_text(filename, content)
    normalized = _normalize_document_text(text)
    if not normalized:
        raise HTTPException(status_code=400, detail="未能从文档中提取到可用文字")

    return {
        "filename": filename,
        "type": document_type,
        "text": normalized,
        "char_count": len(normalized.replace("\n", "")),
    }


@router.post("/tasks", response_model=CreateTaskResponse)
async def create_task(request: CreateTaskRequest):
    """
    创建视频生成任务

    - **theme**: 视频主题或剧本文案（主题模式 1-100 字；文稿模式 1-5000 字）
    - **style**: 文章风格或“文章风格|画面风格”（默认：温暖感人）
    - **length**: 主题模式下的目标脚本字数（50-2000，默认：300）
    - **voice_type**: TTS 音色 ID（可选）
    """
    input_mode = "theme" if request.input_mode == "theme" else "script"
    theme_text = request.theme.strip()
    if input_mode == "theme" and len(theme_text) > 100:
        raise HTTPException(status_code=400, detail="主题模式最多输入 100 字")

    voice_type = _resolve_new_task_voice(request.voice_type)
    tts_options = _snapshot_tts_options(
        voice_type,
        _model_dict(request.tts_options, exclude_none=True),
    )

    # 创建任务
    task_id = task_manager.create_task(
        theme=theme_text,
        name=request.name,
        style=request.style,
        length=request.length,
        voice_type=voice_type,
        ratio=normalize_ratio(request.ratio),
        tts_options=tts_options,
    )

    # 启动异步执行
    task_executor.execute_task(
        task_id=task_id,
        theme=theme_text,
        style=request.style,
        length=request.length,
        voice_type=voice_type,
        ratio=normalize_ratio(request.ratio),
        input_mode=input_mode,
    )

    return CreateTaskResponse(
        task_id=task_id,
        status="pending"
    )


@router.post("/tasks/create-from-images", response_model=CreateTaskResponse)
async def create_task_from_images(
    images: List[UploadFile] = File(...),
    style: str = Form("温暖感人"),
    ratio: str = Form("16:9"),
    voice_type: Optional[str] = Form(None),
    tts_options: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
):
    """
    使用本地上传图片创建可编辑任务

    - **images**: 本地图片列表（1-20 张，JPG/PNG/WEBP）
    - **style**: 文章风格或“文章风格|画面风格”
    - **voice_type**: TTS 音色 ID（可选）
    - **name**: 项目名称（可选）
    """
    if not images:
        raise HTTPException(status_code=400, detail="请至少上传 1 张图片")
    if len(images) > MAX_UPLOAD_IMAGE_COUNT:
        raise HTTPException(status_code=400, detail=f"最多上传 {MAX_UPLOAD_IMAGE_COUNT} 张图片")
    if name and len(name) > 100:
        raise HTTPException(status_code=400, detail="项目名称最多 100 字")

    for file in images:
        _validate_upload_image(file)

    canonical_voice = _resolve_new_task_voice(voice_type)
    raw_options = _parse_options_json(tts_options)
    option_snapshot = _snapshot_tts_options(canonical_voice, raw_options)

    theme = (name or "").strip() or "本地上传图片"
    task_id = task_manager.create_task(
        theme=theme,
        name=name or theme,
        style=style or "温暖感人",
        length=300,
        voice_type=canonical_voice,
        ratio=normalize_ratio(ratio),
        tts_options=option_snapshot,
    )

    try:
        from src.utils.local_uploader import LocalUploader

        draft_name = _safe_draft_name(name or theme, task_id)
        draft_path = Path("output") / draft_name
        images_dir = draft_path / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        local_uploader = LocalUploader()
        segments_data = []

        for index, file in enumerate(images):
            suffix = Path(file.filename or "").suffix.lower()
            if suffix not in ALLOWED_IMAGE_EXTENSIONS:
                suffix = ".jpg"

            local_filename = f"seg_{index:03d}_upload{suffix}"
            local_path = images_dir / local_filename

            with open(local_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

            storage_path = f"{task_id}/images/{local_filename}"
            image_url = local_uploader.upload(str(local_path), storage_path)

            segments_data.append({
                "segment_index": index,
                "text": "",
                "image_prompt": "",
                "image_path": str(local_path),
                "image_url": image_url,
                "audio_path": None,
                "audio_url": None,
                "duration": None,
            })
            _record_asset(
                task_id,
                "image",
                "upload",
                path=str(local_path),
                url=image_url,
                segment_index=index,
                label=f"本地上传 · 分镜 {index + 1}",
            )

        if not mysql_client.save_segments(task_id, segments_data):
            raise RuntimeError("保存段落数据失败")

        task_manager.set_task_result(task_id, str(draft_path), len(segments_data))
        task_manager.update_task_status(task_id, TaskStatus.COMPLETED)

        return CreateTaskResponse(
            task_id=task_id,
            status=TaskStatus.COMPLETED
        )
    except HTTPException:
        task_manager.set_task_error(task_id, "上传图片创建任务失败")
        raise
    except Exception as e:
        logger.exception(f"[{task_id}] 从本地图片创建任务失败: {e}")
        task_manager.set_task_error(task_id, str(e))
        raise HTTPException(status_code=500, detail=f"创建图片任务失败: {e}")


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """
    查询任务状态

    - **task_id**: 任务ID
    """
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return task.to_response()


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str, response: Response):
    """恢复存在可用检查点的中断任务。"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    outcome = task_executor.resume_task(task_id)
    if outcome == "started":
        response.status_code = 202
        status = TaskStatus.PROCESSING.value
    elif outcome == "already_running":
        response.status_code = 200
        status = TaskStatus.PROCESSING.value
    elif outcome == "already_completed":
        response.status_code = 200
        status = TaskStatus.COMPLETED.value
    else:
        response.status_code = 409
        status = task.status.value if isinstance(task.status, TaskStatus) else str(task.status)
    return {"task_id": task_id, "status": status, "outcome": outcome}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    response: Response,
    delete_files: bool = Query(False, description="同时删除本地任务文件"),
):
    """删除任务记录，并可安全删除本地任务文件。"""
    outcome = task_manager.request_delete(task_id, delete_files=delete_files)
    if outcome == "missing":
        raise HTTPException(status_code=404, detail="任务不存在")
    response.status_code = 202 if outcome == "deleting" else 200
    result = {
        "task_id": task_id,
        "status": outcome,
        "outcome": outcome,
        "message": "任务已删除" if outcome == "deleted" else "任务正在停止并删除",
    }
    report = task_manager.get_deletion_report(task_id)
    if report is not None:
        result["deletion_report"] = asdict(report)
    return result


@router.get("/tasks/{task_id}/download")
async def download_task(
    task_id: str,
    extract_path: Optional[str] = Query(None, description="用户解压路径，如 D:\\JianyingPro Drafts；留空则按浏览器下载原草稿包"),
    target_os: str = Query("windows", description="目标系统：windows/mac"),
):
    """
    通过浏览器下载任务生成的草稿包

    - **task_id**: 任务ID
    - **extract_path**: 用户解压目标路径（可选），填写时用于将草稿内素材路径转为绝对路径

    返回浏览器可下载的草稿包，包内包含以草稿名命名的根文件夹。
    """
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"任务未完成，当前状态: {task.status}")

    if not task.result or not task.result.draft_path:
        raise HTTPException(status_code=404, detail="草稿路径不存在")

    draft_path = Path(task.result.draft_path)
    zip_path = draft_path / f"{draft_path.name}.zip"

    if not zip_path.exists():
        try:
            zip_path = _pack_draft_zip(task)
        except Exception as e:
            logger.exception(f"准备浏览器下载草稿失败: {e}")
            raise HTTPException(status_code=500, detail=f"准备浏览器下载失败: {e}")

    draft_name = draft_path.name
    target_os = "mac" if target_os == "mac" else "windows"
    normalized_extract_path = ""
    if extract_path:
        valid_path, normalized_extract_path, path_issues = validate_extract_path(extract_path, target_os)
        if not valid_path:
            raise HTTPException(status_code=400, detail="；".join(path_issues))

    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(zip_path, "r") as src_zip, \
             zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst_zip:

            for item in src_zip.infolist():
                data = src_zip.read(item.filename)

                if normalized_extract_path and item.filename == "draft_content.json":
                    draft_json = json.loads(data.decode("utf-8"))
                    draft_json = apply_extract_path(draft_json, normalized_extract_path, draft_name, target_os=target_os)
                    draft_json = apply_content_info(draft_json, draft_name, target_os=target_os)
                    data = json.dumps(draft_json, ensure_ascii=False, indent=2).encode("utf-8")
                elif normalized_extract_path and item.filename == "draft_meta_info.json":
                    meta_json = json.loads(data.decode("utf-8"))
                    meta_json = apply_meta_info(meta_json, normalized_extract_path, draft_name, target_os=target_os)
                    data = json.dumps(meta_json, ensure_ascii=False, indent=2).encode("utf-8")

                dst_zip.writestr(f"{draft_name}/{item.filename}", data)

            if normalized_extract_path:
                if target_os == "mac":
                    dst_zip.writestr(f"{draft_name}/fix_paths.command", generate_fix_sh())
                else:
                    dst_zip.writestr(f"{draft_name}/fix_paths.bat", generate_fix_bat())

        buf.seek(0)
    except Exception as e:
        logger.exception(f"生成下载 ZIP 失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成下载文件失败: {e}")

    if normalized_extract_path:
        task_manager.update_extract_path(task_id, normalized_extract_path)

    filename = f"{task.theme[:20]}.zip"
    encoded_filename = quote(filename)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


@router.get("/tasks/{task_id}/download-mp4")
async def download_video(task_id: str):
    """
    下载任务生成的视频文件

    - **task_id**: 任务ID

    返回 MP4 视频文件供下载
    """
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"任务未完成，当前状态: {task.status}")

    if not task.result or not task.result.draft_path:
        raise HTTPException(status_code=404, detail="草稿路径不存在")

    # 查找 MP4 文件（在草稿目录内）
    draft_path = Path(task.result.draft_path)
    video_path = draft_path / f"{draft_path.name}.mp4"

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="视频文件不存在")

    # 返回文件下载
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"{task.theme[:20]}.mp4"
    )


@router.get("/tasks", response_model=List[dict])
async def list_tasks(
    request: Request,
    status: Optional[str] = Query(None, description="任务状态筛选：pending/processing/completed/failed"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """
    获取任务列表

    - **status**: 任务状态筛选（可选）
    - **limit**: 每页数量（默认 20，最大 100）
    - **offset**: 偏移量（默认 0）
    """
    tasks = task_manager.list_tasks(status=status, limit=limit, offset=offset)
    for task in tasks:
        task["cover_image_url"] = (
            _normalize_local_media_url(task.get("cover_image_url"), request)
            or _local_media_url_from_path(task.get("cover_image_path"), request)
        )
        task.pop("cover_image_path", None)
    return tasks


@router.get("/tasks/{task_id}/segments")
async def get_segments(task_id: str, request: Request):
    """
    获取任务的段落列表

    - **task_id**: 任务ID
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    segments = mysql_client.get_segments(task_id)

    # 只返回 URL 字段，不返回本地路径
    result = []
    for seg in segments:
        result.append({
            'id': seg.get('id'),
            'task_id': seg.get('task_id'),
            'segment_index': seg.get('segment_index'),
            'text': seg.get('text'),
            'image_prompt': seg.get('image_prompt') or '',
            'image_url': _normalize_local_media_url(seg.get('image_url'), request),
            'audio_url': _normalize_local_media_url(seg.get('audio_url'), request),
            'image_status': seg.get('image_status') or 'completed',
            'image_error': seg.get('image_error'),
            'audio_status': seg.get('audio_status') or 'completed',
            'audio_error': seg.get('audio_error'),
            'audio_voice_type': seg.get('audio_voice_type'),
            'audio_tts_options_json': seg.get('audio_tts_options_json'),
            'duration': seg.get('duration'),
            'created_at': seg.get('created_at'),
            'updated_at': seg.get('updated_at'),
        })

    return result


@router.get("/tasks/{task_id}/render-config")
async def get_task_render_config(task_id: str):
    """获取指定任务的渲染参数、分镜动画参数和预览时长。"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    segments = mysql_client.get_segments(task_id)
    from src.export.ffmpeg_exporter import FFmpegExporter, build_animation_params

    config = FFmpegExporter.get_render_config(canvas=_task_canvas(task))
    config["ratio"] = _task_ratio(task)
    config["animation_seed"] = _task_animation_seed(task_id)
    config["animations"] = build_animation_params(len(segments), config["animation_seed"])
    config["segment_durations"] = [_segment_duration_seconds(seg) for seg in segments]
    return config


@router.post("/tasks/{task_id}/preview-render")
async def render_task_preview(
    task_id: str,
    segment_index: Optional[int] = Query(None, ge=0, description="只渲染指定分镜；不传则渲染全片")
):
    """使用最终 FFmpeg 链路生成精准预览 MP4。"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.result or not task.result.draft_path:
        raise HTTPException(status_code=404, detail="草稿路径不存在")

    segments = mysql_client.get_segments(task_id)
    if not segments:
        raise HTTPException(status_code=404, detail="段落数据不存在")
    if segment_index is not None and segment_index >= len(segments):
        raise HTTPException(status_code=404, detail="段落不存在")

    from src.export.ffmpeg_exporter import FFmpegExporter, build_animation_params
    from src.utils.local_uploader import LocalUploader

    seed = _task_animation_seed(task_id)
    all_animation_params = build_animation_params(len(segments), seed)
    if segment_index is None:
        selected = segments
        animation_params = all_animation_params
        ratio_slug = _task_ratio(task).replace(":", "x")
        filename = f"preview_full_{ratio_slug}_{int(time.time())}.mp4"
        mode = "full"
    else:
        selected = [segments[segment_index]]
        animation_params = [all_animation_params[segment_index]]
        ratio_slug = _task_ratio(task).replace(":", "x")
        filename = f"preview_seg_{segment_index:03d}_{ratio_slug}_{int(time.time())}.mp4"
        mode = "segment"

    segment_texts = [seg.get("text") or "" for seg in selected]
    media_paths = [seg.get("image_path") for seg in selected]
    voiceover_files = [seg.get("audio_path") for seg in selected]

    missing = [path for path in media_paths if not path or not Path(path).exists()]
    if missing:
        raise HTTPException(status_code=404, detail="分镜图片文件不存在，无法生成精准预览")

    preview_dir = Path(task.result.draft_path) / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    video_path = preview_dir / filename

    exporter = FFmpegExporter(canvas=_task_canvas(task))
    exporter.export(
        segments=segment_texts,
        media_paths=media_paths,
        voiceover_files=voiceover_files,
        output_path=str(video_path),
        animation_seed=seed,
        animation_params=animation_params,
    )

    preview_url = LocalUploader().upload(str(video_path), f"{task_id}/previews/{filename}")
    manifest = None
    if segment_index is None:
        manifest = _write_preview_manifest(task, video_path, preview_url, segments)
    return {
        "message": "精准预览生成成功",
        "mode": mode,
        "preview_url": preview_url,
        "video_path": str(video_path),
        "manifest": manifest,
    }


@router.get("/tasks/{task_id}/export-state")
async def get_export_state(task_id: str, request: Request):
    """获取导出页状态：比例、最终预览可复用性、MP4/草稿产物状态。"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.result or not task.result.draft_path:
        raise HTTPException(status_code=404, detail="草稿路径不存在")

    segments = mysql_client.get_segments(task_id)
    ratio = _task_ratio(task)
    canvas = _task_canvas(task)
    preview = _preview_state(task, segments)
    draft_zip = _draft_zip_path(task)
    video_path = _official_video_path(task)

    return {
        "task_id": task_id,
        "status": task.status,
        "ratio": ratio,
        "canvas": canvas,
        "preview": {
            "exists": preview["exists"],
            "valid": preview["valid"],
            "reason": preview["reason"],
            "manifest": preview["manifest"],
        },
        "outputs": {
            "mp4": {
                "available": video_path.exists() or bool(task.result.video_url),
                "path": str(video_path),
                "url": _normalize_local_media_url(task.result.video_url, request),
            },
            "draft": {
                "available": draft_zip.exists() or bool(task.result.draft_url),
                "path": str(draft_zip),
                "url": _normalize_local_media_url(task.result.draft_url, request),
            },
        },
        "jobs": _active_export_jobs(task_id),
    }


@router.post("/tasks/{task_id}/draft-folder/select")
async def select_local_draft_folder(task_id: str):
    """在本机弹出目录选择器，返回真实剪映草稿根目录。"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    folder = _pick_local_folder()
    if not folder:
        raise HTTPException(status_code=400, detail="未选择文件夹")
    return _validate_local_draft_root(folder, _server_target_os())


@router.post("/tasks/{task_id}/draft-folder/validate")
async def validate_local_draft_folder(task_id: str, payload: dict = Body(...)):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _validate_local_draft_root(
        (payload or {}).get("draft_root") or (payload or {}).get("path") or "",
        (payload or {}).get("target_os") or _server_target_os(),
    )


@router.post("/tasks/{task_id}/exports")
async def create_export(task_id: str, payload: dict = Body(...)):
    """创建异步导出任务。target=mp4/draft/draft_local；MP4 可复用有效最终预览。"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.result or not task.result.draft_path:
        raise HTTPException(status_code=404, detail="草稿路径不存在")

    target = (payload or {}).get("target")
    use_preview = bool((payload or {}).get("use_preview", True))
    if target not in {"mp4", "draft", "draft_local"}:
        raise HTTPException(status_code=400, detail="target 必须是 mp4、draft 或 draft_local")

    if target == "draft_local":
        root_check = _validate_local_draft_root(
            (payload or {}).get("draft_root") or (payload or {}).get("extract_path") or "",
            (payload or {}).get("target_os") or _server_target_os(),
        )
        if not root_check["valid"]:
            raise HTTPException(status_code=400, detail="；".join(root_check["issues"] or ["剪映草稿目录不可用"]))
        payload = {**(payload or {}), "draft_root": root_check["path"], "target_os": root_check["target_os"]}

    job = _create_export_job(task_id, target, payload)
    thread = Thread(target=_run_export_job, args=(job["job_id"], target, use_preview, payload), daemon=True)
    thread.start()
    return job


@router.get("/tasks/{task_id}/exports/{job_id}")
async def get_export_job(task_id: str, job_id: str):
    job = _export_job_snapshot(job_id)
    if not job or job.get("task_id") != task_id:
        raise HTTPException(status_code=404, detail="导出任务不存在")
    return job


@router.get("/tasks/{task_id}/assets")
async def list_task_assets(
    task_id: str,
    request: Request,
    type: Optional[str] = Query(None, description="image/audio/subtitle/upload"),
    segment_index: Optional[int] = Query(None),
):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    segments = mysql_client.get_segments(task_id)
    _ensure_task_assets(task, segments)
    if type and type not in {"image", "audio", "subtitle", "upload"}:
        raise HTTPException(status_code=400, detail="type 必须是 image/audio/subtitle/upload")
    assets = mysql_client.list_task_assets(task_id, asset_type=type, segment_index=segment_index)
    return [_asset_to_response(asset, request) for asset in assets]


@router.get("/tasks/{task_id}/subtitle.srt")
async def download_task_subtitle(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.result or not task.result.draft_path:
        raise HTTPException(status_code=404, detail="草稿路径不存在")
    segments = mysql_client.get_segments(task_id)
    srt_path = _write_task_srt(task, segments)
    _record_asset(
        task_id,
        "subtitle",
        "subtitle",
        path=str(srt_path),
        label="项目字幕 SRT",
        text="\n".join(normalize_subtitle_text(seg.get("text") or "") for seg in segments),
    )
    return FileResponse(
        path=str(srt_path),
        media_type="application/x-subrip",
        filename=f"{Path(task.result.draft_path).name}.srt",
    )


@router.get("/tasks/{task_id}/assets/download")
async def download_task_assets(
    task_id: str,
    type: str = Query("all", description="all/image/audio/subtitle/upload"),
):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    segments = mysql_client.get_segments(task_id)
    _ensure_task_assets(task, segments)
    if type not in {"all", "image", "audio", "subtitle", "upload"}:
        raise HTTPException(status_code=400, detail="type 必须是 all/image/audio/subtitle/upload")

    assets = mysql_client.list_task_assets(task_id, None if type == "all" else type)
    if not assets:
        raise HTTPException(status_code=404, detail="没有可下载的素材")

    folder_map = {"image": "images", "audio": "audio", "subtitle": "subtitles"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        added = 0
        used_names = set()
        used_paths = set()
        for asset in assets:
            path = Path(asset.get("path") or "")
            if not path.is_file():
                continue
            path_key = str(path.resolve())
            if path_key in used_paths:
                continue
            used_paths.add(path_key)
            folder = folder_map.get(asset.get("asset_type"), "assets")
            prefix = "uploads" if asset.get("source") == "upload" else folder
            name = f"{asset.get('segment_index') + 1:02d}_" if asset.get("segment_index") is not None else ""
            arcname = f"{prefix}/{name}{path.name}"
            if arcname in used_names:
                arcname = f"{prefix}/{added + 1:03d}_{name}{path.name}"
            used_names.add(arcname)
            zf.write(path, arcname)
            added += 1
        if added == 0:
            raise HTTPException(status_code=404, detail="素材文件不存在")

    buf.seek(0)
    filename = f"{Path(task.result.draft_path).name}_assets.zip" if task.result else f"{task_id}_assets.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/tasks/{task_id}/assets/{asset_id}/file")
async def download_task_asset_file(task_id: str, asset_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    asset = mysql_client.get_task_asset(task_id, asset_id)
    if not asset:
        segments = mysql_client.get_segments(task_id)
        _ensure_task_assets(task, segments)
        asset = mysql_client.get_task_asset(task_id, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="素材不存在")
    path = Path(asset.get("path") or "")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="素材文件不存在")
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".srt": "application/x-subrip",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path=str(path), media_type=media_type, filename=path.name)


@router.post("/tasks/{task_id}/segments/{segment_index}/select-image")
async def select_segment_image(task_id: str, segment_index: int, request: Request, payload: dict = Body(...)):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    segments = mysql_client.get_segments(task_id)
    if segment_index >= len(segments):
        raise HTTPException(status_code=404, detail="段落不存在")
    _ensure_task_assets(task, segments)
    asset_id = (payload or {}).get("asset_id")
    asset = mysql_client.get_task_asset(task_id, asset_id)
    if not asset or asset.get("asset_type") != "image":
        raise HTTPException(status_code=404, detail="图片素材不存在")
    image_path = asset.get("path")
    image_url = asset.get("url") or str(request.url_for("download_task_asset_file", task_id=task_id, asset_id=asset_id))
    if image_path and not Path(image_path).exists():
        raise HTTPException(status_code=404, detail="图片文件不存在")
    previous = segments[segment_index]
    success = mysql_client.update_segment(task_id, segment_index, {
        "image_path": image_path,
        "image_url": image_url,
        "image_prompt": asset.get("prompt") or previous.get("image_prompt") or "",
    })
    if not success:
        raise HTTPException(status_code=500, detail="切换图片失败")
    _record_asset(
        task_id,
        "image",
        "selected",
        path=image_path,
        url=image_url,
        segment_index=segment_index,
        prompt=asset.get("prompt"),
        text=previous.get("text"),
    )
    return {
        "message": "图片已切换",
        "image_path": image_path,
        "image_url": image_url,
        "image_prompt": asset.get("prompt") or previous.get("image_prompt") or "",
        "previous_image_path": previous.get("image_path"),
        "previous_image_url": previous.get("image_url"),
    }


@router.put("/tasks/{task_id}/segments/{segment_index}")
async def update_segment(
    task_id: str,
    segment_index: int,
    text: Optional[str] = Body(None),
    image_prompt: Optional[str] = Body(None),
    image_path: Optional[str] = Body(None),
    image_url: Optional[str] = Body(None),
    audio_url: Optional[str] = Body(None)
):
    """
    更新段落内容

    - **task_id**: 任务ID
    - **segment_index**: 段落索引
    - **text**: 新文案（可选）
    - **image_url**: 新图片URL（可选）
    - **audio_url**: 新音频URL（可选）
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    updates = {}
    if text is not None:
        updates['text'] = text
    if image_prompt is not None:
        updates['image_prompt'] = image_prompt
    if image_path is not None:
        updates['image_path'] = image_path
    if image_url is not None:
        updates['image_url'] = image_url
    if audio_url is not None:
        updates['audio_url'] = audio_url

    if not updates:
        raise HTTPException(status_code=400, detail="至少需要提供一个更新字段")

    success = mysql_client.update_segment(task_id, segment_index, updates)
    if not success:
        raise HTTPException(status_code=500, detail="更新段落失败")

    return {"message": "更新成功"}


@router.post("/tasks/{task_id}/segments/{segment_index}/regenerate-image")
async def regenerate_image(task_id: str, segment_index: int):
    """
    重新生成段落图片

    - **task_id**: 任务ID
    - **segment_index**: 段落索引
    """
    logger.info(f"[{task_id}] ========== 开始重新生成图片 ==========")
    logger.info(f"[{task_id}] 段落索引: {segment_index}")

    task = task_manager.get_task(task_id)
    if not task:
        logger.error(f"[{task_id}] 任务不存在")
        raise HTTPException(status_code=404, detail="任务不存在")

    logger.info(f"[{task_id}] 任务主题: {task.theme}")
    logger.info(f"[{task_id}] 草稿路径: {task.result.draft_path}")

    segments = mysql_client.get_segments(task_id)
    if segment_index >= len(segments):
        logger.error(f"[{task_id}] 段落索引超出范围: {segment_index} >= {len(segments)}")
        raise HTTPException(status_code=404, detail="段落不存在")

    segment = segments[segment_index]
    logger.info(f"[{task_id}] 段落文本: {segment['text']}")

    # 重新生成图片
    from src.core.pipeline import VideoEditorPipeline
    logger.info(f"[{task_id}] 创建 VideoEditorPipeline...")
    canvas = _task_canvas(task)
    pipeline = VideoEditorPipeline(theme=task.theme, output_dir=task.result.draft_path, canvas=canvas)

    # 生成图像 prompt
    logger.info(f"[{task_id}] 生成图像描述...")
    parts = (task.style or "").split("|", 2)
    visual_style = parts[1] if len(parts) > 1 and parts[1] else "写实风格"
    visual_style_suffix = parts[2] if len(parts) > 2 and parts[2] else None
    summary = task.theme[:100]
    image_prompt = (segment.get("image_prompt") or "").strip()
    if not image_prompt:
        image_prompt = pipeline.image_prompt_agent.generate_prompt(
            segment['text'],
            summary,
            visual_style_suffix or visual_style,
        )
    logger.info(f"[{task_id}] 图像描述: {image_prompt}")

    # 生成图片
    logger.info(f"[{task_id}] 开始生成图片...")
    import time
    timestamp = int(time.time())
    image_path = pipeline.image_generator.generate(
        image_prompt,
        index=segment_index,
        style=visual_style,
        style_suffix=visual_style_suffix,
        filename=f"seg_{segment_index:03d}_regen_{timestamp}",
        width=canvas["width"],
        height=canvas["height"],
    )
    logger.info(f"[{task_id}] 图片生成完成: {image_path}")

    # 保存到本地媒体目录
    from src.utils.local_uploader import LocalUploader
    from pathlib import Path

    image_url = None
    if image_path and Path(image_path).exists():
        logger.info(f"[{task_id}] 图片文件存在，开始保存到本地媒体目录...")
        try:
            local_uploader = LocalUploader()
            image_filename = Path(image_path).name
            storage_path = f"{task_id}/images/{image_filename}"
            logger.info(f"[{task_id}] 本地媒体路径: {storage_path}")
            image_url = local_uploader.upload(image_path, storage_path)
            logger.info(f"[{task_id}] 图片保存成功: {image_url}")
        except Exception as e:
            logger.error(f"[{task_id}] 图片保存失败: {e}")
            logger.exception(f"[{task_id}] 保存错误详情:")
    else:
        logger.error(f"[{task_id}] 图片文件不存在: {image_path}")

    # 更新数据库
    logger.info(f"[{task_id}] 更新数据库...")
    mysql_client.update_segment(task_id, segment_index, {
        'image_prompt': image_prompt,
        'image_path': image_path,
        'image_url': image_url
    })
    _record_asset(
        task_id,
        "image",
        "regenerated",
        path=image_path,
        url=image_url,
        segment_index=segment_index,
        prompt=image_prompt,
        text=segment.get("text"),
    )
    logger.info(f"[{task_id}] 数据库更新完成")

    logger.info(f"[{task_id}] ========== 图片重新生成完成 ==========")
    return {
        "message": "图片重新生成成功",
        "image_path": image_path,
        "image_url": image_url,
        "image_prompt": image_prompt,
        "previous_image_path": segment.get("image_path"),
        "previous_image_url": segment.get("image_url"),
    }


@router.post("/tasks/{task_id}/segments/{segment_index}/regenerate-audio")
async def regenerate_audio(
    task_id: str,
    segment_index: int,
    payload: Optional[RegenerateAudioRequest] = Body(None),
    voice_type: Optional[str] = Query(None),
):
    """
    重新生成段落音频

    - **task_id**: 任务ID
    - **segment_index**: 段落索引
    - **voice_type**: TTS 音色 ID（可选，如果不提供则使用任务创建时的音色）
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    segments = mysql_client.get_segments(task_id)
    if segment_index >= len(segments):
        raise HTTPException(status_code=404, detail="段落不存在")

    segment = segments[segment_index]

    body_voice = payload.voice_type if payload else None
    requested_voice = body_voice or voice_type
    if requested_voice:
        effective_voice = _resolve_new_task_voice(requested_voice)
    else:
        effective_voice = segment.get("audio_voice_type") or task.voice_type
    if not effective_voice:
        effective_voice = _resolve_new_task_voice(None)

    inherited_options = (
        _parse_options_json(segment.get("audio_tts_options_json"))
        or dict(getattr(task, "tts_options", {}) or {})
    )
    body_options = _model_dict(payload.tts_options, exclude_none=True) if payload else {}
    effective_options = _snapshot_tts_options(
        effective_voice,
        body_options or inherited_options,
    )

    logger.info(f"[{task_id}] 使用音色: {effective_voice}")

    # 重新生成音频
    from src.core.pipeline import VideoEditorPipeline
    logger.info(f"[{task_id}] 创建 VideoEditorPipeline...")
    pipeline = VideoEditorPipeline(theme=task.theme, output_dir=task.result.draft_path, canvas=_task_canvas(task))

    import time
    timestamp = int(time.time())
    logger.info(f"[{task_id}] 开始生成音频...")
    audio_path = pipeline.voiceover_generator.generate(
        segment['text'],
        filename=f"seg_{segment_index:03d}_regen_{timestamp}",
        voice_type=effective_voice,
        speed_level=effective_options.get("speed_level"),
        volume_ratio=effective_options.get("volume_ratio"),
        style_prompt=effective_options.get("style_prompt"),
    )
    logger.info(f"[{task_id}] 音频生成完成: {audio_path}")

    # 保存到本地媒体目录
    from src.utils.local_uploader import LocalUploader
    from pathlib import Path

    audio_url = None
    if audio_path and Path(audio_path).exists():
        try:
            local_uploader = LocalUploader()
            audio_filename = Path(audio_path).name
            storage_path = f"{task_id}/audio/{audio_filename}"
            audio_url = local_uploader.upload(audio_path, storage_path)
            logger.info(f"[{task_id}] 段落 {segment_index} 音频重新生成并保存成功: {audio_url}")
        except Exception as e:
            logger.warning(f"[{task_id}] 段落 {segment_index} 音频保存失败: {e}")

    # 更新数据库
    mysql_client.update_segment(task_id, segment_index, {
        'audio_path': audio_path,
        'audio_url': audio_url,
        'audio_voice_type': effective_voice,
        'audio_tts_options_json': json.dumps(effective_options, ensure_ascii=False),
    })
    _record_asset(
        task_id,
        "audio",
        "regenerated",
        path=audio_path,
        url=audio_url,
        segment_index=segment_index,
        text=segment.get("text"),
        voice_type=effective_voice,
        metadata={"tts_options": effective_options},
    )

    return {
        "message": "音频重新生成成功",
        "audio_path": audio_path,
        "audio_url": audio_url,
        "voice_type": effective_voice,
        "tts_options": effective_options,
    }


@router.post("/tasks/{task_id}/segments/{segment_index}/upload-image")
async def upload_image(task_id: str, segment_index: int, file: UploadFile = File(...)):
    """
    上传自定义图片

    - **task_id**: 任务ID
    - **segment_index**: 段落索引
    - **file**: 图片文件
    """
    from src.utils.local_uploader import LocalUploader
    from pathlib import Path
    import shutil

    logger.info(f"[{task_id}] ========== 开始上传自定义图片 ==========")
    logger.info(f"[{task_id}] 段落索引: {segment_index}")
    logger.info(f"[{task_id}] 文件名: {file.filename}")

    task = task_manager.get_task(task_id)
    if not task:
        logger.error(f"[{task_id}] 任务不存在")
        raise HTTPException(status_code=404, detail="任务不存在")

    segments = mysql_client.get_segments(task_id)
    if segment_index >= len(segments):
        logger.error(f"[{task_id}] 段落索引超出范围: {segment_index} >= {len(segments)}")
        raise HTTPException(status_code=404, detail="段落不存在")
    segment = segments[segment_index]

    # 验证文件类型
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="只支持 JPG、PNG、WEBP 格式的图片")

    # 保存到本地临时文件
    draft_path = Path(task.result.draft_path)
    images_dir = draft_path / "images"
    images_dir.mkdir(exist_ok=True)

    import time
    timestamp = int(time.time())
    file_ext = Path(file.filename).suffix or ".jpg"
    local_filename = f"seg_{segment_index:03d}_upload_{timestamp}{file_ext}"
    local_path = images_dir / local_filename

    logger.info(f"[{task_id}] 保存到本地: {local_path}")
    with open(local_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 保存到本地媒体目录
    image_url = None
    try:
        local_uploader = LocalUploader()
        storage_path = f"{task_id}/images/{local_filename}"
        logger.info(f"[{task_id}] 本地媒体路径: {storage_path}")
        image_url = local_uploader.upload(str(local_path), storage_path)
        logger.info(f"[{task_id}] 图片保存成功: {image_url}")
    except Exception as e:
        logger.error(f"[{task_id}] 图片保存失败: {e}")
        logger.exception(f"[{task_id}] 保存错误详情:")
        raise HTTPException(status_code=500, detail=f"图片保存失败: {e}")

    # 更新数据库
    logger.info(f"[{task_id}] 更新数据库...")
    mysql_client.update_segment(task_id, segment_index, {
        'image_path': str(local_path),
        'image_url': image_url
    })
    _record_asset(
        task_id,
        "image",
        "upload",
        path=str(local_path),
        url=image_url,
        segment_index=segment_index,
        text=segment.get("text"),
    )
    logger.info(f"[{task_id}] 数据库更新完成")

    logger.info(f"[{task_id}] ========== 图片上传完成 ==========")
    return {
        "message": "图片上传成功",
        "image_path": str(local_path),
        "image_url": image_url,
        "previous_image_path": segment.get("image_path"),
        "previous_image_url": segment.get("image_url"),
    }


@router.post("/tasks/{task_id}/rebuild")
async def rebuild_draft(task_id: str):
    """
    根据当前段落数据重新构建草稿和视频

    - **task_id**: 任务ID
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    segments = mysql_client.get_segments(task_id)
    if not segments:
        raise HTTPException(status_code=404, detail="段落数据不存在")

    # 重新构建草稿和视频
    from src.core.pipeline import VideoEditorPipeline
    from src.export.ffmpeg_exporter import FFmpegExporter

    pipeline = VideoEditorPipeline(theme=task.theme, output_dir=task.result.draft_path, canvas=_task_canvas(task))

    # 准备数据
    segment_texts = [seg.get('text') or "" for seg in segments]
    media_paths = [seg.get('image_path') for seg in segments]
    voiceover_files = [seg.get('audio_path') for seg in segments]
    animation_seed = _task_animation_seed(task_id)

    draft_name = Path(task.result.draft_path).name

    # 重新构建草稿
    draft_path = pipeline.draft_builder.build(
        segments=segment_texts,
        media_paths=media_paths,
        draft_name=draft_name,
        voiceover_files=voiceover_files,
        animation_seed=animation_seed,
        output_dir=task.result.draft_path,
    )

    # 重新生成视频
    ffmpeg_exporter = FFmpegExporter(canvas=_task_canvas(task))
    video_path = Path(task.result.draft_path) / f"{draft_name}.mp4"

    ffmpeg_exporter.export(
        segments=segment_texts,
        media_paths=media_paths,
        voiceover_files=voiceover_files,
        output_path=str(video_path),
        animation_seed=animation_seed,
    )

    return {"message": "草稿和视频重新构建成功", "draft_path": draft_path, "video_path": str(video_path)}
