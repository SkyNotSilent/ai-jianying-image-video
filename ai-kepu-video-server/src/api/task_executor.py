"""
异步任务执行器
将 pipeline 包装为异步任务，支持进度回调
"""

import logging
import json
import time
import zipfile
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from typing import List, Optional
from .task_manager import task_manager, TaskStatus
from .task_runtime import TaskCancellation, TaskCancelled, task_runtime
from src.core.pipeline import VideoEditorPipeline
from src.database import db_client
from src.utils.local_uploader import LocalUploader
from src.utils.rendering import canvas_for_ratio, normalize_ratio
from src.config import Config

logger = logging.getLogger(__name__)


class RecoverableTaskError(RuntimeError):
    """Raised when saved checkpoints can be used to resume the task."""


def _require_checkpoint(saved: bool, description: str) -> None:
    if not saved:
        raise RecoverableTaskError(f"{description}保存失败")


def _upload_warning(error: Exception) -> str:
    return f"Upload failed: {error}"


def _preserved_upload_warning(error: Optional[str]) -> Optional[str]:
    if error and error.startswith("Upload failed: "):
        return error
    return None


@dataclass
class ResumeWork:
    prompt_indexes: List[int]
    image_indexes: List[int]
    audio_indexes: List[int]
    media_paths: List[Optional[str]]
    voiceover_files: List[Optional[str]]


def _completed_local_path(segment: dict, asset_type: str) -> Optional[str]:
    path = segment.get(f"{asset_type}_path")
    if (
        segment.get(f"{asset_type}_status") == "completed"
        and path
        and Path(path).is_file()
    ):
        return path
    return None


def build_resume_work(segments: List[dict]) -> ResumeWork:
    prompt_indexes = []
    image_indexes = []
    audio_indexes = []
    media_paths = []
    voiceover_files = []

    for index, segment in enumerate(segments):
        if not segment.get("image_prompt"):
            prompt_indexes.append(index)
        image_path = _completed_local_path(segment, "image")
        audio_path = _completed_local_path(segment, "audio")
        media_paths.append(image_path)
        voiceover_files.append(audio_path)
        if image_path is None:
            image_indexes.append(index)
        if audio_path is None:
            audio_indexes.append(index)

    return ResumeWork(
        prompt_indexes=prompt_indexes,
        image_indexes=image_indexes,
        audio_indexes=audio_indexes,
        media_paths=media_paths,
        voiceover_files=voiceover_files,
    )


def _safe_project_name(name: str) -> str:
    safe_name = (
        (name or "")
        .strip()
        .replace(" ", "_")
        .replace("\n", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )[:20]
    return "task" if safe_name in {"", ".", ".."} else safe_name


def _task_output_dir(task_id: str, draft_name: str, segments: List[dict]) -> Path:
    for segment in segments:
        for field in ("image_path", "audio_path"):
            raw_path = segment.get(field)
            if not raw_path:
                continue
            path = Path(raw_path)
            if path.parent.name in {"images", "voiceovers", "audio"}:
                return path.parent.parent
    task_root = Path("output") / task_id
    candidate = task_root / _safe_project_name(draft_name)
    try:
        candidate.resolve().relative_to(task_root.resolve())
    except ValueError:
        return task_root / "task"
    return candidate


def _bounded_concurrency(value, total: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 1
    parsed = max(1, min(8, parsed))
    return min(parsed, max(1, total))


def _asset_counts(paths: list) -> tuple[int, int]:
    completed = sum(1 for path in paths if path)
    return completed, max(0, len(paths) - completed)


class TaskExecutor:
    """任务执行器"""

    def __init__(self, pipeline_factory=VideoEditorPipeline):
        self.pipeline_factory = pipeline_factory

    def execute_task(self, task_id: str, theme: str, style: str, length: int, voice_type: Optional[str] = None, ratio: str = "16:9", input_mode: str = "script") -> bool:
        """在后台线程中执行任务"""
        cancellation = task_runtime.begin(task_id)
        if cancellation is None:
            logger.info(f"[{task_id}] 任务已在执行，跳过重复启动")
            return False

        thread = Thread(
            target=self._run_registered_task,
            args=(
                cancellation,
                task_id,
                theme,
                style,
                length,
                voice_type,
                ratio,
                input_mode,
            ),
        )
        thread.daemon = True
        try:
            thread.start()
        except Exception:
            task_runtime.finish(task_id, cancellation)
            raise
        logger.info(f"[{task_id}] 启动后台任务线程")
        return True

    def _run_registered_task(
        self,
        cancellation: TaskCancellation,
        task_id: str,
        theme: str,
        style: str,
        length: int,
        voice_type: Optional[str],
        ratio: str,
        input_mode: str,
    ) -> None:
        try:
            self._run_task(
                task_id,
                theme,
                style,
                length,
                voice_type,
                ratio,
                input_mode,
                cancellation=cancellation,
            )
        finally:
            task_runtime.finish(task_id, cancellation)

    def cancel_task(self, task_id: str, timeout: float = 30) -> bool:
        if not task_runtime.request_cancel(task_id):
            return True
        return task_runtime.wait_until_stopped(task_id, timeout)

    def resume_task(self, task_id: str) -> str:
        task_row = db_client.get_task(task_id)
        if not task_row:
            return "not_recoverable"
        if task_row.get("status") == TaskStatus.COMPLETED.value:
            return "already_completed"
        if task_runtime.is_running(task_id):
            return "already_running"

        segments = db_client.get_segments(task_id)
        if task_row.get("status") not in {
            TaskStatus.INTERRUPTED.value,
            TaskStatus.FAILED.value,
        } or not (task_row.get("script_text") or segments):
            return "not_recoverable"

        cancellation = task_runtime.begin(task_id)
        if cancellation is None:
            if task_runtime.is_running(task_id):
                return "already_running"
            return "not_recoverable"
        thread = Thread(
            target=self._run_registered_task,
            args=(
                cancellation,
                task_id,
                task_row["theme"],
                task_row["style"],
                task_row["length"],
                task_row.get("voice_type"),
                task_row.get("ratio", "16:9"),
                task_row.get("input_mode", "script"),
            ),
        )
        thread.daemon = True
        try:
            thread.start()
        except Exception:
            task_runtime.finish(task_id, cancellation)
            raise
        return "started"

    def continue_task(self, task_id: str) -> str:
        """Continue a review-first task from its persisted plan checkpoint."""
        task_row = db_client.get_task(task_id)
        if not task_row or not db_client.get_segments(task_id):
            return "not_recoverable"
        if task_runtime.is_running(task_id):
            return "already_running"
        if task_row.get("execution_mode") != "review_first":
            return "not_review_first"

        if not db_client.update_task_workflow(
            task_id,
            "assets_requested",
            status=TaskStatus.INTERRUPTED.value,
            current_step="image_prompt_generation",
        ):
            return "not_recoverable"
        task_manager.invalidate_task_cache(task_id)

        cancellation = task_runtime.begin(task_id)
        if cancellation is None:
            return "already_running" if task_runtime.is_running(task_id) else "not_recoverable"
        thread = Thread(
            target=self._run_registered_task,
            args=(
                cancellation,
                task_id,
                task_row["theme"],
                task_row["style"],
                task_row["length"],
                task_row.get("voice_type"),
                task_row.get("ratio", "16:9"),
                task_row.get("input_mode", "script"),
            ),
        )
        thread.daemon = True
        try:
            thread.start()
        except Exception:
            task_runtime.finish(task_id, cancellation)
            raise
        return "started"

    def run_inline(
        self, task_id: str, cancellation: Optional[TaskCancellation] = None
    ) -> None:
        task_row = db_client.get_task(task_id)
        if not task_row:
            return
        self._run_task(
            task_id,
            task_row["theme"],
            task_row["style"],
            task_row["length"],
            task_row.get("voice_type"),
            task_row.get("ratio", "16:9"),
            task_row.get("input_mode", "script"),
            cancellation=cancellation,
        )

    def _run_task(self, task_id: str, theme: str, style: str, length: int, voice_type: Optional[str] = None, ratio: str = "16:9", input_mode: str = "script", cancellation: Optional[TaskCancellation] = None):
        """执行任务的实际逻辑"""
        task = task_manager.get_task(task_id)
        if not task:
            logger.error(f"[{task_id}] 任务不存在")
            return
        tts_options = dict(getattr(task, "tts_options", {}) or {})

        started_at = time.time()
        pipeline = None
        segments_count = 0
        draft_path = None
        video_path = None
        image_failures = []
        voice_failures = []
        segment_db_indexes = []

        try:
            if cancellation:
                cancellation.raise_if_cancelled()

            task_row = db_client.get_task(task_id) or {}
            execution_mode = task_row.get("execution_mode", "full")
            workflow_phase = task_row.get("workflow_phase", "pending")
            if execution_mode == "review_first":
                workflow_phase = (
                    "generating_assets"
                    if workflow_phase in {"assets_requested", "generating_assets", "ready"}
                    else "planning"
                )
                task.workflow_phase = workflow_phase
                db_client.update_task_workflow(task_id, workflow_phase)

            # 更新任务状态为处理中
            task_manager.update_task_status(task_id, TaskStatus.PROCESSING)
            logger.info(f"[{task_id}] ========== 开始执行任务 ==========")
            input_mode = "theme" if input_mode == "theme" else "script"
            logger.info(f"[{task_id}] 输入长度: {len(theme)}, 输入模式: {input_mode}, 风格: {style}, 目标字数: {length}")
            ratio = normalize_ratio(ratio or getattr(task, "ratio", "16:9"))
            canvas = canvas_for_ratio(ratio)
            logger.info(f"[{task_id}] 视频比例: {ratio}, 画布: {canvas['width']}x{canvas['height']}")

            # 解析 style 字段：格式为 "文章风格|画面风格|自定义画面prompt后缀"
            parts = (style or "").split("|", 2)
            text_style = parts[0] if len(parts) > 0 and parts[0] else "温暖感人"
            visual_style = parts[1] if len(parts) > 1 and parts[1] else "写实风格"
            visual_style_suffix = parts[2] if len(parts) > 2 and parts[2] else None
            visual_prompt_style = visual_style_suffix or visual_style
            logger.info(f"[{task_id}] 文章风格: {text_style}, 画面风格: {visual_style}")

            # 创建草稿名称和目录
            task_row = db_client.get_task(task_id) or task_row
            persisted_segments = db_client.get_segments(task_id)
            draft_base = task_row.get("name") or task.name or theme[:20]
            draft_name = _safe_project_name(draft_base)
            draft_dir = _task_output_dir(task_id, draft_name, persisted_segments)
            draft_dir.mkdir(parents=True, exist_ok=True)

            # 创建 pipeline，指定草稿目录
            pipeline = self.pipeline_factory(
                theme=theme,
                output_dir=str(draft_dir),
                canvas=canvas,
            )

            # 步骤 1: 文案改写 / 主题生成
            logger.info(f"[{task_id}] [1/6] 开始生成/改写脚本...")
            task.start_step("text_generation")
            if task_row.get("script_text"):
                pipeline.article = task_row["script_text"]
                pipeline.summary = task_row.get("summary") or ""
            elif persisted_segments:
                pipeline.article = "\n".join(
                    row["text"] for row in persisted_segments
                )
                pipeline.summary = task_row.get("summary") or theme
                _require_checkpoint(
                    db_client.save_task_checkpoint(
                        task_id,
                        script_text=pipeline.article,
                        summary=pipeline.summary,
                        input_mode=input_mode,
                    ),
                    "旧任务脚本检查点",
                )
            elif input_mode == "script" and task_row.get("script_policy") == "verbatim":
                pipeline.article = theme
                pipeline.summary = theme[:500]
                _require_checkpoint(
                    db_client.save_task_checkpoint(
                        task_id,
                        script_text=pipeline.article,
                        summary=pipeline.summary,
                        input_mode=input_mode,
                    ),
                    "原文脚本检查点",
                )
            else:
                rewrite_result = pipeline.script_rewriter.rewrite(
                    theme,
                    style=text_style,
                    target_length=length,
                    input_mode=input_mode,
                )
                pipeline.article = rewrite_result["script"]
                pipeline.summary = rewrite_result["summary"]
                _require_checkpoint(
                    db_client.save_task_checkpoint(
                        task_id,
                        script_text=pipeline.article,
                        summary=pipeline.summary,
                        input_mode=input_mode,
                    ),
                    "脚本检查点",
                )
            logger.info(f"[{task_id}] [1/6] 脚本生成完成，共 {len(pipeline.article)} 字")
            logger.info(f"[{task_id}] 内容总结: {pipeline.summary}")
            task.complete_step("text_generation")
            if cancellation:
                cancellation.raise_if_cancelled()

            # 步骤 2: 短节奏分段，约 20 字一段，对应更密的画面切换
            logger.info(f"[{task_id}] [2/6] 开始短节奏分段...")
            task.current_step = "segmentation"
            db_client.update_task_status(task_id, "processing", "segmentation")
            if persisted_segments:
                pipeline.segments = [row["text"] for row in persisted_segments]
            else:
                pipeline.segments = pipeline.text_segmenter.split(pipeline.article)
                initial_segments = [
                    {
                        "segment_index": i,
                        "text": segment,
                        "image_prompt": "",
                        "image_status": "pending",
                        "audio_status": "pending",
                        "prompt_status": "pending",
                        "prompt_manual": 0,
                        "prompt_needs_review": 0,
                    }
                    for i, segment in enumerate(pipeline.segments)
                ]
                _require_checkpoint(
                    db_client.save_segments(task_id, initial_segments),
                    "初始分镜检查点",
                )
                persisted_segments = db_client.get_segments(task_id)
            segment_db_indexes = [
                row["segment_index"] for row in persisted_segments
            ]
            segments_count = len(pipeline.segments)
            logger.info(f"[{task_id}] [2/6] 分段完成，共 {segments_count} 段")
            generation_config = Config.generation_config()
            prompt_concurrency = _bounded_concurrency(
                generation_config.get("prompt_concurrency", 4), segments_count
            )
            tts_concurrency = _bounded_concurrency(
                generation_config.get("tts_concurrency", 1), segments_count
            )
            image_concurrency = _bounded_concurrency(
                generation_config.get("image_concurrency", 1), segments_count
            )
            logger.info(
                f"[{task_id}] 生成并发配置: 提示词={prompt_concurrency}, "
                f"配音={tts_concurrency}, 生图={image_concurrency}"
            )
            if cancellation:
                cancellation.raise_if_cancelled()

            # 步骤 3: 逐段生成图像 prompts
            logger.info(f"[{task_id}] [3/6] 开始逐段生成图像描述...")
            task.start_step("image_prompt_generation")
            resume_work = build_resume_work(persisted_segments)
            image_prompts = [row.get("image_prompt") or "" for row in persisted_segments]

            def generate_prompt_item(i: int):
                if cancellation:
                    cancellation.raise_if_cancelled()
                seg = pipeline.segments[i]
                try:
                    prompt = pipeline.image_prompt_agent.generate_prompt(
                        segment_text=seg,
                        summary=pipeline.summary,
                        style=visual_prompt_style,
                        aspect_ratio=ratio,
                    )
                    return {"status": "success", "prompt": prompt, "error": None}
                except TaskCancelled:
                    raise
                except Exception as error:
                    return {"status": "failed", "prompt": "", "error": str(error)}

            pending_prompt_indexes = iter(resume_work.prompt_indexes)
            prompt_failures = []
            prompt_cancelled = False
            completed_prompts = segments_count - len(resume_work.prompt_indexes)

            def submit_next_prompt(executor, futures) -> bool:
                nonlocal prompt_cancelled
                if cancellation and cancellation.is_cancelled():
                    prompt_cancelled = True
                    return False
                try:
                    index = next(pending_prompt_indexes)
                except StopIteration:
                    return False
                _require_checkpoint(
                    db_client.update_segment(
                        task_id,
                        segment_db_indexes[index],
                        {"prompt_status": "processing", "prompt_error": None},
                    ),
                    f"分镜 {segment_db_indexes[index]} 提示词开始检查点",
                )
                futures[executor.submit(generate_prompt_item, index)] = index
                return True

            with ThreadPoolExecutor(max_workers=prompt_concurrency) as prompt_executor:
                prompt_futures = {}
                for _ in range(prompt_concurrency):
                    if not submit_next_prompt(prompt_executor, prompt_futures):
                        break

                while prompt_futures:
                    done, _ = wait(prompt_futures, return_when=FIRST_COMPLETED)
                    for future in done:
                        i = prompt_futures.pop(future)
                        try:
                            result = future.result()
                        except TaskCancelled:
                            prompt_cancelled = True
                            result = {"status": "cancelled", "prompt": "", "error": "任务已取消"}

                        if result["status"] == "success":
                            prompt = result["prompt"]
                            image_prompts[i] = prompt
                            prompt_updates = {
                                "image_prompt": prompt,
                                "image_error": None,
                                "prompt_status": "completed",
                                "prompt_error": None,
                                "prompt_manual": 0,
                                "prompt_needs_review": 0,
                            }
                            if _completed_local_path(persisted_segments[i], "image") is None:
                                prompt_updates["image_status"] = "pending"
                            _require_checkpoint(
                                db_client.update_segment(
                                    task_id, segment_db_indexes[i], prompt_updates
                                ),
                                f"分镜 {segment_db_indexes[i]} 提示词检查点",
                            )
                        elif result["status"] == "failed":
                            prompt_failures.append({"index": i, "error": result["error"]})
                            prompt_error_updates = {
                                "image_error": result["error"],
                                "prompt_status": "failed",
                                "prompt_error": result["error"],
                            }
                            if _completed_local_path(persisted_segments[i], "image") is None:
                                prompt_error_updates["image_status"] = "failed"
                            _require_checkpoint(
                                db_client.update_segment(
                                    task_id,
                                    segment_db_indexes[i],
                                    prompt_error_updates,
                                ),
                                f"分镜 {segment_db_indexes[i]} 提示词错误检查点",
                            )

                        completed_prompts += 1
                        task.update_step_progress(
                            "image_prompt_generation", completed_prompts, segments_count
                        )
                        logger.debug(
                            f"[{task_id}] 图像描述进度: {completed_prompts}/{segments_count}"
                        )

                    if not prompt_cancelled:
                        for _ in range(len(done)):
                            if not submit_next_prompt(prompt_executor, prompt_futures):
                                break

            pipeline.image_prompts = image_prompts
            if prompt_cancelled or (cancellation and cancellation.is_cancelled()):
                raise TaskCancelled("Task execution was cancelled during prompt generation")
            if prompt_failures:
                failed_numbers = "、".join(str(item["index"] + 1) for item in prompt_failures)
                logger.warning(f"[{task_id}] 部分图片提示词生成失败: {prompt_failures}")
                raise RecoverableTaskError(
                    f"图片提示词生成失败 [片段 {failed_numbers}]"
                )
            persisted_segments = db_client.get_segments(task_id)
            resume_work = build_resume_work(persisted_segments)
            for i, segment in enumerate(persisted_segments):
                segment_index = segment_db_indexes[i]
                for asset_type, missing_indexes in (
                    ("image", resume_work.image_indexes),
                    ("audio", resume_work.audio_indexes),
                ):
                    if i in missing_indexes:
                        continue
                    preserved_error = _preserved_upload_warning(
                        segment.get(f"{asset_type}_error")
                    )
                    _require_checkpoint(
                        db_client.update_segment(
                            task_id,
                            segment_index,
                            {
                                f"{asset_type}_status": "completed",
                                f"{asset_type}_error": preserved_error,
                            },
                        ),
                        f"分镜 {segment_index} 已有{asset_type}检查点",
                    )
                    try:
                        asset_record = db_client.save_task_asset(
                            task_id=task_id,
                            asset_type=asset_type,
                            source="generated",
                            path=segment.get(f"{asset_type}_path"),
                            url=segment.get(f"{asset_type}_url"),
                            segment_index=segment_index,
                            label=(
                                f"AI 生成 · 分镜 {i + 1}"
                                if asset_type == "image"
                                else f"配音 · 分镜 {i + 1}"
                            ),
                            prompt=(
                                segment.get("image_prompt")
                                if asset_type == "image"
                                else None
                            ),
                            text=segment.get("text"),
                            voice_type=(
                                segment.get("audio_voice_type") or voice_type
                                if asset_type == "audio"
                                else None
                            ),
                            metadata_json=(
                                segment.get("audio_tts_options_json")
                                or json.dumps({"tts_options": tts_options}, ensure_ascii=False)
                                if asset_type == "audio"
                                else None
                            ),
                            status="completed",
                            error_message=preserved_error,
                        )
                    except Exception as error:
                        raise RecoverableTaskError(
                            f"分镜 {segment_index} 已有{asset_type}资产检查点保存失败: {error}"
                        ) from error
                    if not asset_record:
                        raise RecoverableTaskError(
                            f"分镜 {segment_index} 已有{asset_type}资产检查点保存失败"
                        )
            logger.info(f"[{task_id}] 已保存分镜和图片提示词，共 {len(persisted_segments)} 段")
            logger.info(f"[{task_id}] [3/6] 图像描述生成完成")
            task.complete_step("image_prompt_generation")
            if cancellation:
                cancellation.raise_if_cancelled()

            if execution_mode == "review_first" and workflow_phase == "planning":
                task.current_step = "awaiting_confirmation"
                task.workflow_phase = "awaiting_confirmation"
                task_manager.update_task_status(task_id, TaskStatus.AWAITING_CONFIRMATION)
                _require_checkpoint(
                    db_client.update_task_workflow(
                        task_id,
                        "awaiting_confirmation",
                        status=TaskStatus.AWAITING_CONFIRMATION.value,
                        current_step="awaiting_confirmation",
                    ),
                    "预案确认状态检查点",
                )
                logger.info(f"[{task_id}] 预案已完成，等待用户确认后生成素材")
                return

            # 步骤 4-5: 配音和生图互不依赖，并行执行；内部并发由模型配置页控制。
            logger.info(f"[{task_id}] [4-5/6] 开始并行生成配音和图像（共 {segments_count} 段）...")
            pipeline.voiceover_files = resume_work.voiceover_files
            pipeline.media_paths = resume_work.media_paths

            segment_audio_settings = []
            for segment in persisted_segments:
                segment_voice = segment.get("audio_voice_type") or voice_type
                segment_options = dict(tts_options)
                if segment.get("audio_voice_type") and segment.get("audio_tts_options_json"):
                    try:
                        parsed_segment_options = json.loads(segment["audio_tts_options_json"])
                        if isinstance(parsed_segment_options, dict):
                            segment_options.update(parsed_segment_options)
                    except (TypeError, ValueError):
                        logger.warning(
                            "[%s] 分镜 %s 的配音参数快照无效，改用全片参数",
                            task_id,
                            segment.get("segment_index"),
                        )
                segment_audio_settings.append((segment_voice, segment_options))

            def generate_voiceover_item(i: int, seg: str):
                logger.debug(f"[{task_id}] 配音进度: {i+1}/{segments_count}")
                try:
                    if tts_concurrency == 1 and i > 0:
                        time.sleep(0.5)
                    if cancellation:
                        cancellation.raise_if_cancelled()
                    segment_voice, segment_options = segment_audio_settings[i]
                    path = pipeline.voiceover_generator.generate(
                        seg,
                        filename=f"seg_{i:03d}",
                        voice_type=segment_voice,
                        speed_level=segment_options.get("speed_level"),
                        volume_ratio=segment_options.get("volume_ratio"),
                        style_prompt=segment_options.get("style_prompt"),
                    )
                    return i, {"status": "success", "path": path, "error": None}
                except TaskCancelled:
                    raise
                except Exception as e:
                    logger.error(f"[{task_id}] 音频生成失败 [片段 {i+1}]: {e}")
                    return i, {"status": "failed", "path": None, "error": str(e)}

            def generate_image_item(i: int, prompt: str):
                logger.debug(f"[{task_id}] 图像进度: {i+1}/{segments_count}")
                try:
                    if cancellation:
                        cancellation.raise_if_cancelled()
                    path = pipeline.image_generator.generate(
                        prompt,
                        index=i,
                        style=visual_style,
                        style_suffix=visual_style_suffix,
                        width=canvas["width"],
                        height=canvas["height"],
                    )
                    return i, {"status": "success", "path": path, "error": None}
                except TaskCancelled:
                    raise
                except Exception as e:
                    logger.error(f"[{task_id}] 图片生成失败 [片段 {i+1}]: {e}")
                    return i, {"status": "failed", "path": None, "error": str(e)}

            local_uploader = LocalUploader()
            upload_ts = int(time.time())

            def persist_segment_asset(i: int, asset_type: str, path: str = None, url: str = None, error: str = None):
                segment_index = segment_db_indexes[i]
                upload_error = None
                if asset_type == "image" and path and Path(path).exists():
                    try:
                        image_ext = Path(path).suffix
                        storage_path = f"{task_id}/images/seg_{i:03d}_{upload_ts}{image_ext}"
                        url = local_uploader.upload(path, storage_path)
                    except Exception as e:
                        upload_error = _upload_warning(e)
                        logger.warning(f"[{task_id}] 段落 {i} 图片保存失败: {e}")
                elif asset_type == "audio" and path and Path(path).exists():
                    try:
                        audio_ext = Path(path).suffix
                        storage_path = f"{task_id}/audio/seg_{i:03d}_{upload_ts}{audio_ext}"
                        url = local_uploader.upload(path, storage_path)
                    except Exception as e:
                        upload_error = _upload_warning(e)
                        logger.warning(f"[{task_id}] 段落 {i} 音频保存失败: {e}")

                final_error = error or upload_error
                status = "failed" if error else ("completed" if path else "pending")
                updates = {}
                if asset_type == "image":
                    updates = {"image_path": path, "image_url": url, "image_status": status, "image_error": final_error}
                    label = f"AI 生成 · 分镜 {i + 1}"
                    prompt = image_prompts[i] if i < len(image_prompts) else ""
                    voice = None
                else:
                    segment_voice, segment_options = segment_audio_settings[i]
                    updates = {
                        "audio_path": path,
                        "audio_url": url,
                        "audio_status": status,
                        "audio_error": final_error,
                        "audio_voice_type": (
                            segment_voice
                            if persisted_segments[i].get("audio_voice_type")
                            else ""
                        ),
                        "audio_tts_options_json": json.dumps(segment_options, ensure_ascii=False),
                    }
                    label = f"配音 · 分镜 {i + 1}"
                    prompt = None
                    voice = segment_voice

                _require_checkpoint(
                    db_client.update_segment(task_id, segment_index, updates),
                    f"分镜 {segment_index} {asset_type}检查点",
                )
                asset_record = db_client.save_task_asset(
                    task_id=task_id,
                    asset_type=asset_type,
                    source="generated",
                    path=path,
                    url=url,
                    segment_index=segment_index,
                    label=label,
                    prompt=prompt,
                    text=pipeline.segments[i] if i < len(pipeline.segments) else None,
                    voice_type=voice,
                    metadata_json=(
                        json.dumps({"tts_options": segment_options}, ensure_ascii=False)
                        if asset_type == "audio"
                        else None
                    ),
                    status=status,
                    error_message=final_error,
                )
                if not asset_record:
                    raise RecoverableTaskError(
                        f"分镜 {segment_index} {asset_type}资产检查点保存失败"
                    )

            def generate_voiceovers():
                task.start_step("voiceover_generation")
                completed = segments_count - len(resume_work.audio_indexes)
                failed_items = []
                cancellation_pending = False
                with ThreadPoolExecutor(max_workers=tts_concurrency) as voice_executor:
                    futures = {
                        voice_executor.submit(generate_voiceover_item, i, seg): i
                        for i, seg in enumerate(pipeline.segments)
                        if i in resume_work.audio_indexes
                    }
                    for future in as_completed(futures):
                        i = futures[future]
                        try:
                            _, result = future.result()
                        except TaskCancelled:
                            cancellation_pending = True
                            completed += 1
                            task.update_step_progress(
                                "voiceover_generation", completed, segments_count
                            )
                            continue
                        if result["status"] == "success":
                            pipeline.voiceover_files[i] = result["path"]
                            persist_segment_asset(i, "audio", path=result["path"])
                        else:
                            failed_items.append({"index": i, "type": "audio", "error": result["error"]})
                            pipeline.voiceover_files[i] = None
                            persist_segment_asset(i, "audio", error=result["error"])
                        completed += 1
                        task.update_step_progress("voiceover_generation", completed, segments_count)
                if failed_items:
                    logger.warning(f"[{task_id}] 部分音频生成失败: {failed_items}")
                if not cancellation_pending:
                    task.complete_step("voiceover_generation")
                return failed_items, cancellation_pending

            def generate_images():
                task.start_step("image_generation")
                completed = segments_count - len(resume_work.image_indexes)
                failed_items = []
                cancellation_pending = False
                with ThreadPoolExecutor(max_workers=image_concurrency) as image_executor:
                    futures = {
                        image_executor.submit(generate_image_item, i, prompt): i
                        for i, prompt in enumerate(image_prompts)
                        if i in resume_work.image_indexes
                    }
                    for future in as_completed(futures):
                        i = futures[future]
                        try:
                            _, result = future.result()
                        except TaskCancelled:
                            cancellation_pending = True
                            completed += 1
                            task.update_step_progress(
                                "image_generation", completed, segments_count
                            )
                            continue
                        if result["status"] == "success":
                            pipeline.media_paths[i] = result["path"]
                            persist_segment_asset(i, "image", path=result["path"])
                        else:
                            failed_items.append({"index": i, "type": "image", "error": result["error"]})
                            pipeline.media_paths[i] = None
                            persist_segment_asset(i, "image", error=result["error"])
                        completed += 1
                        task.update_step_progress("image_generation", completed, segments_count)
                if failed_items:
                    logger.warning(f"[{task_id}] 部分图片生成失败: {failed_items}")
                if not cancellation_pending:
                    task.complete_step("image_generation")
                return failed_items, cancellation_pending

            with ThreadPoolExecutor(max_workers=2) as executor:
                voice_future = executor.submit(generate_voiceovers)
                image_future = executor.submit(generate_images)
                voice_failures, voice_cancelled = voice_future.result()
                image_failures, image_cancelled = image_future.result()

            if cancellation:
                cancellation.raise_if_cancelled()
            if voice_cancelled or image_cancelled:
                raise TaskCancelled("Task execution was cancelled during asset generation")

            all_failures = voice_failures + image_failures
            if all_failures:
                logger.warning(f"[{task_id}] 资源生成部分失败，共 {len(all_failures)} 项: {all_failures}")
                raise RecoverableTaskError(
                    f"资源生成中断，共 {len(all_failures)} 项失败"
                )

            logger.info(f"[{task_id}] [4-5/6] 配音和图像生成完成")
            if cancellation:
                cancellation.raise_if_cancelled()

            # 步骤 6: 草稿构建
            logger.info(f"[{task_id}] [6/6] 开始构建剪映草稿...")
            task.start_step("draft_building")
            draft_path = pipeline.draft_builder.build(
                segments=pipeline.segments,
                media_paths=pipeline.media_paths,
                draft_name=draft_name,
                voiceover_files=pipeline.voiceover_files,
                output_dir=str(draft_dir),
            )
            logger.info(f"[{task_id}] [6/6] 草稿构建完成")
            task.complete_step("draft_building")
            if cancellation:
                cancellation.raise_if_cancelled()

            # 检查草稿目录内容
            logger.debug(f"[{task_id}] 检查草稿目录内容: {draft_dir}")
            logger.debug(f"[{task_id}] draft_path 返回值: {draft_path}")
            for item in draft_dir.rglob("*"):
                if item.is_file():
                    logger.debug(f"[{task_id}]   文件: {item.relative_to(draft_dir)} ({item.stat().st_size} bytes)")
                elif item.is_dir():
                    logger.debug(f"[{task_id}]   目录: {item.relative_to(draft_dir)}/")

            # 步骤 6: 打包并保存到本地媒体目录
            logger.info(f"[{task_id}] [6/6] 开始打包并保存到本地媒体目录...")
            zip_path = None
            draft_url = None

            try:
                # 创建临时目录用于打包
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_draft = Path(temp_dir) / draft_name
                    temp_draft.mkdir(parents=True, exist_ok=True)

                    logger.debug(f"[{task_id}] 创建临时打包目录: {temp_draft}")

                    # 复制所有文件到临时目录
                    logger.debug(f"[{task_id}] 复制草稿文件到临时目录...")
                    for item in draft_dir.rglob("*"):
                        if item.is_file():
                            rel_path = item.relative_to(draft_dir)
                            dest = temp_draft / rel_path
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, dest)
                            logger.debug(f"[{task_id}]   复制: {rel_path}")

                    # 打包临时目录
                    zip_path = draft_dir / f"{draft_name}.zip"
                    logger.info(f"[{task_id}] 开始打包: {temp_draft} -> {zip_path}")

                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for file_path in temp_draft.rglob("*"):
                            if file_path.is_file():
                                # 使用相对于临时草稿目录的路径
                                arcname = file_path.relative_to(temp_draft)
                                zf.write(file_path, arcname)
                                logger.debug(f"[{task_id}]   添加: {arcname}")

                    zip_size = zip_path.stat().st_size / 1024 / 1024
                    logger.info(f"[{task_id}] 打包完成，大小: {zip_size:.2f} MB")

                # 保存草稿包到本地媒体目录
                try:
                    draft_url = LocalUploader().upload(str(zip_path))
                    logger.info(f"[{task_id}] 草稿包保存成功: {draft_url}")
                except Exception as e:
                    logger.warning(f"[{task_id}] 草稿包保存失败（不影响本地草稿）: {e}")

            except Exception as e:
                logger.warning(f"[{task_id}] 打包失败（不影响草稿）: {e}")
                logger.exception(f"[{task_id}] 打包错误详情:")

            if cancellation:
                cancellation.raise_if_cancelled()

            # 完整 MP4 改为用户按需异步渲染，不再阻塞默认任务完成。
            video_path = None
            video_url = None

            # 保存段落数据到数据库
            logger.info(f"[{task_id}] 保存段落数据到数据库...")

            # 构建失败信息映射
            failure_map = {}
            for failure in all_failures:
                idx = failure["index"]
                ftype = failure["type"]
                if idx not in failure_map:
                    failure_map[idx] = {}
                failure_map[idx][ftype] = failure["error"]

            segments_data = []

            for i, seg_text in enumerate(pipeline.segments):
                segment_index = segment_db_indexes[i]
                image_path = pipeline.media_paths[i] if i < len(pipeline.media_paths) else None
                audio_path = pipeline.voiceover_files[i] if i < len(pipeline.voiceover_files) else None

                # 获取失败信息
                image_error = failure_map.get(i, {}).get("image")
                audio_error = failure_map.get(i, {}).get("audio")
                image_status = "failed" if image_error else ("completed" if image_path else "pending")
                audio_status = "failed" if audio_error else ("completed" if audio_path else "pending")

                image_url = None
                audio_url = None

                segment_voice, segment_options = segment_audio_settings[i]
                seg_data = {
                    'segment_index': segment_index,
                    'text': seg_text,
                    'image_prompt': image_prompts[i] if i < len(image_prompts) else "",
                    'image_path': image_path,
                    'image_url': image_url,
                    'image_status': image_status,
                    'image_error': image_error,
                    'audio_path': audio_path,
                    'audio_url': audio_url,
                    'audio_status': audio_status,
                    'audio_error': audio_error,
                    'audio_voice_type': (
                        segment_voice
                        if persisted_segments[i].get('audio_voice_type')
                        else ''
                    ),
                    'audio_tts_options_json': json.dumps(segment_options, ensure_ascii=False),
                }
                segments_data.append(seg_data)

                # 保存图片资源（包括失败状态）- 容错处理
                try:
                    db_client.save_task_asset(
                        task_id=task_id,
                        asset_type="image",
                        source="generated",
                        path=image_path,
                        url=image_url,
                        segment_index=segment_index,
                        label=f"AI 生成 · 分镜 {i + 1}",
                        prompt=seg_data["image_prompt"],
                        text=seg_text,
                        status=image_status,
                        error_message=image_error,
                    )
                except Exception as e:
                    logger.warning(f"[{task_id}] 保存图片资源失败 (段落 {i}): {e}")

                # 保存音频资源（包括失败状态）- 容错处理
                try:
                    db_client.save_task_asset(
                        task_id=task_id,
                        asset_type="audio",
                        source="generated",
                        path=audio_path,
                        url=audio_url,
                        segment_index=segment_index,
                        label=f"配音 · 分镜 {i + 1}",
                        text=seg_text,
                        voice_type=segment_voice,
                        metadata_json=json.dumps({"tts_options": segment_options}, ensure_ascii=False),
                        status=audio_status,
                        error_message=audio_error,
                    )
                except Exception as e:
                    logger.warning(f"[{task_id}] 保存音频资源失败 (段落 {i}): {e}")

            _require_checkpoint(
                db_client.save_segments(task_id, segments_data),
                "最终分镜检查点",
            )
            logger.info(f"[{task_id}] 段落数据保存成功，共 {len(segments_data)} 段")

            # 设置任务结果
            task_manager.set_task_result(task_id, draft_path, segments_count, draft_url, video_url)
            task.workflow_phase = "ready"
            db_client.update_task_workflow(task_id, "ready")
            task_manager.update_task_status(task_id, TaskStatus.COMPLETED)

            image_ok, image_failed = _asset_counts(pipeline.media_paths)
            audio_ok, audio_failed = _asset_counts(pipeline.voiceover_files)
            elapsed = time.time() - started_at
            logger.info(f"[{task_id}] ========== 任务完成 ==========")
            logger.info(
                f"[{task_id}] 摘要: 段落={segments_count}, 图片={image_ok}成功/{image_failed}失败, "
                f"音频={audio_ok}成功/{audio_failed}失败, 草稿={draft_path}, 视频=按需渲染, 耗时={elapsed:.1f}s"
            )

        except TaskCancelled as error:
            logger.info(f"[{task_id}] 任务已在阶段检查点取消")
            task_manager.mark_task_interrupted(task_id, str(error))
        except RecoverableTaskError as error:
            logger.warning(f"[{task_id}] 任务在可恢复检查点中断: {error}")
            task_manager.mark_task_interrupted(task_id, str(error))
        except Exception as e:
            elapsed = time.time() - started_at
            image_ok = audio_ok = image_failed = audio_failed = 0
            if pipeline:
                image_ok, image_failed = _asset_counts(getattr(pipeline, "media_paths", []) or [])
                audio_ok, audio_failed = _asset_counts(getattr(pipeline, "voiceover_files", []) or [])
                try:
                    if getattr(pipeline, "segments", None):
                        partial_segments = []
                        image_prompts = getattr(pipeline, "image_prompts", []) or []
                        media_paths = getattr(pipeline, "media_paths", []) or []
                        voiceover_files = getattr(pipeline, "voiceover_files", []) or []
                        for i, seg_text in enumerate(pipeline.segments):
                            segment_index = (
                                segment_db_indexes[i]
                                if i < len(segment_db_indexes)
                                else i
                            )
                            image_path = media_paths[i] if i < len(media_paths) else None
                            audio_path = voiceover_files[i] if i < len(voiceover_files) else None
                            partial_segments.append({
                                "segment_index": segment_index,
                                "text": seg_text,
                                "image_prompt": image_prompts[i] if i < len(image_prompts) else "",
                                "image_path": image_path,
                                "image_status": "completed" if image_path else "pending",
                                "audio_path": audio_path,
                                "audio_status": "completed" if audio_path else "pending",
                            })
                        if partial_segments:
                            db_client.save_segments(task_id, partial_segments)
                            logger.info(f"[{task_id}] 失败前已保存阶段性分镜，共 {len(partial_segments)} 段")
                except Exception as save_error:
                    logger.warning(f"[{task_id}] 失败后保存阶段性分镜失败: {save_error}")
            logger.error(f"[{task_id}] ========== 任务失败 ==========")
            logger.error(f"[{task_id}] 错误类型: {type(e).__name__}")
            logger.error(f"[{task_id}] 错误信息: {str(e)}")
            logger.error(
                f"[{task_id}] 失败摘要: 段落={segments_count}, 图片={image_ok}成功/{image_failed}失败, "
                f"音频={audio_ok}成功/{audio_failed}失败, 草稿={draft_path}, 视频={video_path}, 耗时={elapsed:.1f}s"
            )
            logger.exception(f"[{task_id}] 详细堆栈:")

            task_manager.set_task_error(task_id, str(e))
            # 标记当前步骤失败
            if task.current_step in task.steps:
                task.fail_step(task.current_step, str(e))


# 全局任务执行器实例
task_executor = TaskExecutor()
