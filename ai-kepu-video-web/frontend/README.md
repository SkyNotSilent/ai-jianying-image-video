# InsightCut Frontend

基于 Vue 3 + Vite + Vant 4 的前端工作台，用于创建、预览、编辑和导出 AI 解释型视频。

## 功能

- 创建视频任务：主题/文案、创作风格、画面风格、配音和字数
- 管理资产记录：查看历史生成任务
- 模型配置：管理生文、生图、TTS 接口参数
- 预览与编辑：调整分段文本、图片、音频和字幕
- 结果导出：下载剪映/CapCut 草稿 ZIP 和 MP4 成片

## 本地开发

```bash
npm install
cp .env.example .env.development
npm run dev -- --host 127.0.0.1 --port 2001
```

默认后端地址为 `http://localhost:2002`，可在 `.env.development` 中通过 `VITE_API_BASE_URL` 修改。

## 构建

```bash
npm run build
```

构建产物输出到 `dist/`。

## 主要路由

- `/#/`：创建任务 / 资产记录
- `/#/settings`：模型配置
- `/#/process/:taskId`：生成进度
- `/#/preview/:taskId`：预览与编辑
- `/#/result/:taskId`：结果导出
