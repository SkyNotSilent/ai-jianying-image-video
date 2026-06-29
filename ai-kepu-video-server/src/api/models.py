"""
API 数据模型
定义请求和响应的数据结构
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, Enum):
    """步骤状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CreateTaskRequest(BaseModel):
    """创建任务请求"""
    theme: str = Field(..., min_length=1, max_length=5000, description="视频主题或剧本文案")
    name: Optional[str] = Field(None, max_length=100, description="项目名称")
    input_mode: str = Field(default="script", description="输入模式：script=写作模式，theme=主题模式")
    style: str = Field(default="温暖感人", description="文章风格")
    ratio: str = Field(default="16:9", description="视频比例：16:9/9:16/3:4")
    length: int = Field(default=300, ge=0, le=2000, description="主题模式下的目标脚本字数；0 表示自动")
    voice_type: Optional[str] = Field(None, description="TTS 音色 ID")


class CreateTaskFromImagesRequest(BaseModel):
    """从本地图片创建任务请求"""
    style: Optional[str] = Field(default="温暖感人", description="文章风格|画面风格")
    ratio: Optional[str] = Field(default="16:9", description="视频比例：16:9/9:16/1:1")
    voice_type: Optional[str] = Field(None, description="TTS 音色 ID")
    name: Optional[str] = Field(None, max_length=100, description="项目名称")


class StepProgress(BaseModel):
    """步骤进度"""
    name: str = Field(..., description="步骤名称")
    status: StepStatus = Field(..., description="步骤状态")
    progress: Optional[int] = Field(None, description="当前进度")
    total: Optional[int] = Field(None, description="总数")
    duration: Optional[float] = Field(None, description="耗时（秒）")


class TaskProgress(BaseModel):
    """任务进度"""
    current_step: str = Field(..., description="当前步骤")
    steps: List[StepProgress] = Field(..., description="所有步骤")


class TaskResult(BaseModel):
    """任务结果"""
    draft_path: str = Field(..., description="草稿路径")
    draft_url: Optional[str] = Field(None, description="草稿下载链接")
    video_url: Optional[str] = Field(None, description="视频下载链接")
    theme: str = Field(..., description="视频主题")
    segments_count: int = Field(..., description="段落数")
    total_duration: Optional[float] = Field(None, description="总时长（秒）")
    created_at: str = Field(..., description="创建时间")


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    voice_type: Optional[str] = Field(None, description="任务创建时使用的 TTS 音色 ID")
    progress: Optional[TaskProgress] = Field(None, description="任务进度")
    result: Optional[TaskResult] = Field(None, description="任务结果")
    extract_path: Optional[str] = Field(None, description="用户上次使用的解压路径")
    error: Optional[str] = Field(None, description="错误信息")


class CreateTaskResponse(BaseModel):
    """创建任务响应"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
