"""
日志配置模块
统一配置日志格式、输出目标、日志级别
"""

import logging
import os
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir: str = "logs", log_level: str = "INFO"):
    """
    配置日志系统

    Args:
        log_dir: 日志文件目录
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    os.environ.setdefault("LITELLM_LOG", "ERROR")

    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 日志格式
    log_format = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # 清除已有的处理器
    root_logger.handlers.clear()

    # 1. 控制台处理器（彩色输出）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)

    # 2. 文件处理器 - 所有日志
    all_log_file = log_path / "app.log"
    file_handler = RotatingFileHandler(
        all_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)

    # 3. 错误日志文件
    error_log_file = log_path / "error.log"
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(log_format)
    root_logger.addHandler(error_handler)

    # 4. 任务日志文件
    task_log_file = log_path / "task.log"
    task_handler = RotatingFileHandler(
        task_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    task_handler.setLevel(logging.INFO)
    task_handler.setFormatter(log_format)

    # 只记录任务相关的日志
    task_logger = logging.getLogger('src.api.task_executor')
    task_logger.addHandler(task_handler)

    for noisy_logger in ("LiteLLM", "litellm", "openai", "httpx", "httpcore"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    logging.info(f"日志系统初始化完成，日志目录: {log_path.absolute()}")
    logging.info(f"日志级别: {log_level}")


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器

    Args:
        name: 日志记录器名称（通常使用 __name__）

    Returns:
        logging.Logger: 日志记录器实例
    """
    return logging.getLogger(name)
