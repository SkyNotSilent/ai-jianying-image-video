"""
本地文件上传工具
文件保存在本地目录，通过 FastAPI 静态文件路由提供访问
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 本地存储目录
LOCAL_MEDIA_DIR = Path(__file__).parent.parent.parent / "data" / "media"

# 本地开发服务器地址（会在 api_server.py 中通过挂载 /media 路由来访问）
LOCAL_BASE_URL = os.environ.get("LOCAL_MEDIA_URL", "http://localhost:2002/media")


class LocalUploader:
    """本地文件上传器"""

    def __init__(self, **kwargs):
        LOCAL_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        logger.debug(f"本地文件存储目录: {LOCAL_MEDIA_DIR}")

    def upload(
        self,
        file_path: str,
        storage_path: Optional[str] = None,
        enable_md5: bool = False,
    ) -> str:
        """
        复制文件到本地媒体目录

        Args:
            file_path: 本地源文件路径
            storage_path: 存储路径（相对路径）
            enable_md5: 忽略

        Returns:
            文件的本地访问 URL
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if storage_path is None:
            draft_name = file_path.stem
            storage_path = f"{draft_name}/{file_path.name}"

        # 目标路径
        dest = LOCAL_MEDIA_DIR / storage_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        # 复制文件
        shutil.copy2(str(file_path), str(dest))
        logger.debug(f"文件保存到本地: {file_path.name} -> {dest}")

        # 返回访问 URL
        url = f"{LOCAL_BASE_URL}/{storage_path}"
        logger.debug(f"本地访问 URL: {url}")
        return url

    def upload_with_progress(
        self,
        file_path: str,
        storage_path: Optional[str] = None,
    ) -> str:
        """带进度的上传（本地直接复制）"""
        return self.upload(file_path, storage_path)
