-- 为 task_assets 表添加 status 和 error_message 字段
-- 用于支持资产生成失败的状态跟踪

USE ai_video_generator;

-- 添加 status 字段
ALTER TABLE task_assets
ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'completed' COMMENT '资产状态：completed/failed'
AFTER metadata_json;

-- 添加 error_message 字段
ALTER TABLE task_assets
ADD COLUMN error_message TEXT COMMENT '错误信息（失败时）'
AFTER status;

-- 添加索引以便快速查询失败的资产
ALTER TABLE task_assets
ADD INDEX idx_status (status);
