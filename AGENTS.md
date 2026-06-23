# InsightCut 项目说明

## 项目结构

```
Auto-jianji/
├── ai-kepu-video-server/    # 后端服务（FastAPI）
│   ├── api_server.py         # FastAPI 应用入口
│   ├── main.py               # 命令行工具入口
│   └── src/                  # 源代码
└── ai-kepu-video-web/        # 前端项目
    └── frontend/             # Vue 3 前端应用
```

## 启动服务

### 代理文档同步规则

- 本仓库同时维护 `CLAUDE.md` 和 `AGENTS.md` 两份代理说明。
- 两份文件的内容必须保持一致；如果修改端口、启动命令、环境变量、项目约定或开发注意事项，必须同步修改另一份文件。
- 默认端口固定为：前端 `2001`，后端 `2002`。前后端端口不能冲突。

### 一键启动前后端

当用户说"启动"、"打开"、"重新启动端口"时，需要同时启动前后端服务：

**1. 停止旧进程（如果存在）**
```bash
# 停止前端（端口 2001）
lsof -ti:2001 | xargs kill -9 2>/dev/null || true

# 停止后端（端口 2002）
lsof -ti:2002 | xargs kill -9 2>/dev/null || true
```

**2. 启动后端服务**
```bash
cd /Users/mima1234/Documents/AI产品经理/Auto-jianji/ai-kepu-video-server && \
source venv/bin/activate && \
python -m uvicorn api_server:app --host 0.0.0.0 --port 2002 --reload
```
- 后端地址：http://localhost:2002
- API 文档：http://localhost:2002/docs
- 健康检查：http://localhost:2002/health

**3. 启动前端服务**
```bash
cd /Users/mima1234/Documents/AI产品经理/Auto-jianji/ai-kepu-video-web/frontend && \
npm run dev
```
- 前端地址：http://localhost:2001

### 前后端配置对齐

- 前端配置文件：`ai-kepu-video-web/frontend/.env.development`
  ```
  VITE_API_BASE_URL=http://localhost:2002
  VITE_POLLING_INTERVAL=2000
  ```
- 后端监听端口：`2002`
- 前端开发端口：`2001`

## 重要说明

1. **后端入口文件**：使用 `api_server.py`（不是 `main.py`）
2. **虚拟环境**：后端需要激活 venv 虚拟环境
3. **后台运行**：两个服务都应该在后台运行（`run_in_background: true`）
4. **启动顺序**：先启动后端，再启动前端（避免前端启动时后端未就绪）

## 开发注意事项

- 前端使用 Vue 3 + Vite
- 后端使用 FastAPI + Python 3.9
- 素材库按 `segment_index` 排序展示（播放顺序）
- 本地维护巡检：在 `ai-kepu-video-server/` 下运行 `python scripts/maintenance_report.py --dry-run` 查看日志、数据库、媒体目录体量和未引用素材；只有显式使用 `--apply` 才会删除未被数据库引用的媒体文件。
- **任务失败不能丢已生成内容**：任何任务被标记为 `failed` 时，已经生成的分镜文本、图片 prompt、图片、音频、草稿文件等资产必须继续入库并在素材库/预览页正常展示；失败状态只表示后续流程停止，不代表清空或隐藏已有资产。
- **超时失败也要先保资产**：自动超时、手动失败、异常失败前，必须尽量保存当前已生成的 `task_segments` 和 `task_assets`，让用户能查看、替换、重新生成或基于已有素材继续处理。

## 模型调用架构

### 生文模块（LLM）

使用 **LiteLLM** 统一调用层，支持 100+ 模型提供商：

- **配置方式**：`base_url` + `api_key` + `model` + `protocol`
- **支持的协议**：
  - `openai`：OpenAI 兼容接口（包括 OpenRouter、Ollama、LM Studio 等）
  - `anthropic`：Anthropic 原生接口
- **自动识别**：模型名带前缀（如 `openai/gpt-4`、`anthropic/claude-3-opus`）会自动识别 provider
- **核心文件**：`src/text/generator.py` 的 `_call_api()` 方法

### 生图模块

使用 **Agnes Image 2.1 Flash**，OpenAI 兼容 images/generations 接口：

- **API URL**：`https://apihub.agnes-ai.com/v1/images/generations`
- **模型**：`agnes-image-2.1-flash`
- **价格**：当前免费
- **配置方式**：`api_url` + `api_key` + `model`
- **核心文件**：`src/media/image_generator.py`
- **请求格式注意**：Agnes 的 `response_format` 必须放在 `extra_body.response_format`，不能放在请求体顶层
- **免费限速注意**：附件文档未列出明确 RPM；当前按公开资料的免费 `RPM 20` 处理，项目内生图请求至少间隔 3 秒，`IMAGE_CONCURRENCY` 保持 `1`，遇到 429 按 `retry-after` 或 60 秒等待后重试

### TTS 模块

独立配置，按 `tts.provider` 分发到不同 TTS provider，任务创建和重配音接口仍统一使用 `voice_type` 作为音色 ID：

- **豆包 TTS**：`provider=doubao`，保留现有 `api_url/appid/token/cluster/default_voice` 配置，音色列表来自本地 SQLite。
- **小米 MiMo TTS**：`provider=mimo`，配置保存在 `tts.mimo.base_url/api_key/model/default_voice/format/style_prompt`。
- **小米接口注意**：MiMo TTS 不走 `/v1/audio/speech`，而是请求 OpenAI 兼容的 `/v1/chat/completions`；待合成文本放在 assistant message，风格指令放在 user message，音频从 `choices[0].message.audio.data` 读取 base64 后写出 wav。
- **小米预置音色**：`mimo_default/冰糖/茉莉/苏打/白桦/Mia/Chloe/Milo/Dean`；`/ai/native/video/kepu/voices` 会根据当前 TTS provider 动态返回豆包或小米音色。
- **VoiceClone 注意**：小米文档没有远端保存 `voice_id` 机制；后续接入声音克隆时，每次请求都需要携带本地参考音频 DataURL。

## 存储配置

### 本地存储模式（当前使用）

**只使用本地存储**，所有文件存储在本地：

- **媒体文件目录**：
  - `output/` - 新任务生成的文件（如"开心"项目）
  - `data/media/` - 旧任务的文件（如"3:4测试v3"）

- **媒体服务端点**：`/media/{file_path}`
  - 自动支持两个目录，优先查找 `output/`，回退到 `data/media/`
  - 示例：`http://localhost:2002/media/开心/images/segment_000.png`

- **上传/生成文件**：
  - 统一使用 `LocalUploader` 复制到 `data/media/`
  - 不再支持 OSS/COS 上传、`USE_REMOTE_DB` 切换、MySQL/Redis 远程模式
  - 数据固定使用本地 SQLite：`ai-kepu-video-server/data/local.db`
