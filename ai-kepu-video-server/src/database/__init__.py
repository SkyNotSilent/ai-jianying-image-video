"""
数据库模块初始化
固定使用本地 SQLite + 内存缓存
"""

# db_client 是新的语义化名称；mysql_client 保留给现有业务代码兼容。
from .sqlite_client import sqlite_client as db_client, SQLiteClient
mysql_client = db_client
MySQLClient = SQLiteClient
from .memory_cache import memory_cache as redis_client, MemoryCache as RedisClient

__all__ = [
    "db_client",
    "SQLiteClient",
    "mysql_client",
    "MySQLClient",
    "redis_client",
    "RedisClient",
]
