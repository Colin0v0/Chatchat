# Chatchat

Chatchat 是一个面向个人/小团队的聊天工作台，当前提供：

- 多模型聊天：DeepSeek 官网、OpenAI-compatible API、OpenAI Codex、Claude、Gemini、Trio
- 登录与多用户隔离：基于账号密码和 Cookie Session
- 推理展示：支持 reasoning/thinking 流式展示与持久化
- 检索增强：用户知识库 `RAG`、`Web Search`，知识库 embedding / rerank 走百炼
- 多模态输入：图片、PDF、DOCX、XLSX、CSV、文本类文件
- 语音转写：百炼 `qwen3-asr-flash`
- 语音播放：百炼 `cosyvoice-v3-flash`，浏览器本机语音兜底
- 记忆系统：全局记忆、会话记忆、工作记忆、候选记忆、记忆文档

当前部署口径是纯 CPU + 云端 API：

- 不再依赖 Ollama、本地 OCR、本地视觉模型、本地 ASR、本地 embedding 或本地 reranker
- DeepSeek 聊天走 DeepSeek 官方 API，也就是 `DEEPSEEK_*`
- embedding、rerank、语音输入和云端音色走百炼/DashScope，也就是 `DASHSCOPE_*`
- PostgreSQL、Redis、媒体文件和知识库原文仍可放在本机或 Docker 里，它们是基础设施，不属于本地模型推理

当前代码默认遵循这几个原则：

- 优先做清晰重构，不堆补丁
- 不主动引入隐式 fallback
- 能力按领域收口，避免逻辑散落

详细开发说明见 [docs/开发文档.md](docs/开发文档.md)，纯 CPU/API 部署说明见 [docs/部署与模型接入.md](docs/部署与模型接入.md)。

## 文档地图

- [docs/部署与模型接入.md](docs/部署与模型接入.md)：服务器规格、Docker 部署、DeepSeek/百炼环境变量、API-only 链路
- [docs/开发文档.md](docs/开发文档.md)：当前代码结构、后端/前端目录职责、主要运行链路和开发约定
- [docs/后端重构.md](docs/后端重构.md)：后端 runtime、provider、tool、storage 的迁移状态和后续方向
- [docs/前端重构.md](docs/前端重构.md)：前端 feature-first 拆分计划和当前迁移状态
- [docs/语音对话与实时打断架构.md](docs/语音对话与实时打断架构.md)：ASR/TTS、浏览器本机音色、阿里云音色和播放打断设计

## 开发环境

当前推荐的本地开发形态是：

- `backend`：在 VSCode / 宿主机 Python 里直接运行
- `postgres-dev`：通过 Docker 单独启动开发数据库
- `redis-dev`：通过 Docker 单独启动开发缓存

启动开发基建：

```powershell
docker-compose -f docker-compose.dev-infra.yml up -d
```

如果本机拉不到 `docker.io`，先覆盖镜像地址再启动：

```powershell
$env:DEV_POSTGRES_IMAGE = "你的可用镜像仓库/pgvector/pgvector:pg16"
$env:DEV_REDIS_IMAGE = "你的可用镜像仓库/redis:7-alpine"
docker-compose -f docker-compose.dev-infra.yml up -d
```

如果你已经在 Docker Desktop 配好了镜像代理或镜像加速器，这两项不用设置。

启动后端开发服务：

```powershell
cd backend
.\scripts\run_dev_backend.ps1
```

首次启动空的开发库时，脚本会自动：

- 创建 `vector` / `pg_trgm` 扩展
- 运行 Alembic baseline / head migration
- 对旧的未版本化 PostgreSQL schema 补齐迁移

这套开发环境默认使用：

- PostgreSQL：`127.0.0.1:5433` / `chatchat_dev`
- Redis：`127.0.0.1:6380`

生产环境仍然保持单独的 Docker 栈，不和开发库共用容器、端口或数据卷。

## 当前架构

```text
Chatchat/
  backend/      FastAPI + SQLAlchemy + LLM / Retrieval / Memory
  frontend/     React 19 + Vite + TypeScript
  docs/         架构、部署、重构说明
  storage/      媒体附件、用户知识库原文等持久化文件
  docker-compose.yml
  README.md
```

## 当前核心功能

### 1. 聊天与推理

- 支持普通聊天、重试回答、停止生成
- reasoning 面板支持流式展示
- reasoning 会随 assistant message 一起持久化到数据库
- 前端消费统一 NDJSON 事件流：
  - `meta`
  - `status`
  - `reasoning`
  - `token`
  - `sources`
  - `context`
  - `done`
  - `error`

### 2. 检索

- `none`：不检索
- `rag`：检索当前用户上传的 Markdown 知识库
- `web`：联网搜索

知识库支持逻辑文件夹分组：

- 可以上传单个/多个 Markdown 到指定分组
- 可以直接上传文件夹，保留目录相对路径
- 可以在知识库页面按分组查看、筛选、批量移动、批量删除
- 聊天开启知识库模式后，可以选择检索全部知识库、默认分组或某个文件夹分组

`rag` 模式当前会先做一层“查询重写”：

- 结合最近几轮对话，把“它 / 那个 / 上面那段”改写成更完整的检索问题
- 只影响知识库检索，不影响最终用户原始问题
- 相关配置见 `RAG_QUERY_REWRITE_*`

### 3. 多模态与附件

后端现在按 API 模型能力处理附件：

- `native_multimodal="false"`
  - 不走本地 OCR / 视觉模型
  - 文件仍可走轻量解析器抽取文本
  - 把结果写入 `attachment_context`

- `native_multimodal="codex"`
  - 图片直接作为原生多模态输入发送给 Codex / GPT-5
  - 文档和其他文件继续走本地解析
  - 不复用 `/v1/files` 直传链路

- `native_multimodal="gemini"` / `"claude"`
  - 图片和支持的文档按 provider 原生多模态协议发送
  - 其他文件仍走本地轻量解析器

当前 `native_multimodal` 由 [backend/model_catalog.json](backend/model_catalog.json) 控制。
`capabilities.input.*` 会同时约束前端上传入口和后端校验；当前 DeepSeek v4 Pro / Flash 已关闭图片上传。

### 4. 认证与用户

- 不开放注册页
- 通过数据库注入/脚本创建账号
- 登录后通过 Cookie Session 维持状态
- 会话、记忆、设置按用户隔离

创建用户脚本：

```powershell
cd backend
python scripts/create_user.py --username alice --password secret123
```

如果要接管历史无主数据：

```powershell
cd backend
python scripts/create_user.py --username alice --password secret123 --take-ownership-of-orphans
```

## 模型配置

模型由 [backend/model_catalog.json](backend/model_catalog.json) 管理。

当前常用字段：

- `id`
- `display_name`
- `provider_ref`
- `upstream_model`
- `thinking_mode`
- `context_window`
- `native_multimodal`
- `enabled`

当前 provider 主要有：

- `openai`，当前主要用于 DeepSeek 这类 OpenAI-compatible API
- `codex`
- `claude`
- `gemini`
- `trio`

前端 `/api/models` 当前使用的模型能力字段：

- `supports_thinking`
- `supports_thinking_trace`
- `supports_attachment_upload`
- `chat_model`
- `reasoning_model`

## 环境变量

后端支持分层环境文件：

- 默认：`backend/.env`
- 命名环境：`CHATCHAT_ENV=<name>` 时额外加载 `backend/.env.<name>`
- 显式文件：`CHATCHAT_ENV_FILE=<path>`

示例：

```powershell
$env:CHATCHAT_ENV = "dev.windows"
cd backend
python app.py
```

```bash
CHATCHAT_ENV=deploy.wsl python app.py
```

### 关键环境变量

#### 数据库 / 缓存

本地开发使用 `docker-compose.dev-infra.yml` 里的 Postgres / Redis：

```env
DATABASE_URL=postgresql+psycopg://chatchat_dev:chatchat_dev@127.0.0.1:5433/chatchat_dev
REDIS_URL=redis://127.0.0.1:6380/0
```

完整 Docker 部署使用 `docker-compose.yml` 里的内置服务：

```env
DATABASE_URL=postgresql+psycopg://chatchat:chatchat@postgres:5432/chatchat
REDIS_URL=redis://redis:6379/0
```

#### 模型与路由

```env
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=
CODEX_BASE_URL=
CODEX_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=
MODEL_CATALOG_PATH=./model_catalog.json
MODEL_CATALOG_STRICT=true
DEFAULT_PROVIDER=openai
DEFAULT_MODEL=openai:deepseek-v4-flash
```

DeepSeek 聊天模型走 `DEEPSEEK_*`，百炼 `DASHSCOPE_*` 用于 embedding、rerank、语音输入和语音播放。
如果不接 OpenAI / Codex，可以把 `OPENAI_API_KEY`、`CODEX_API_KEY` 留空；DeepSeek 不依赖 OpenAI key。

如果要接入 OpenAI Codex，推荐单独配置：

```env
CODEX_BASE_URL=https://api.openai.com/v1
CODEX_API_KEY=sk-...
DEFAULT_PROVIDER=codex
DEFAULT_MODEL=codex:gpt-5.3-codex
```

#### 并发与连接池

```env
REQUEST_TIMEOUT_SECONDS=180
OPENAI_CONNECT_TIMEOUT_SECONDS=30
HTTP_POOL_MAX_CONNECTIONS=100
HTTP_POOL_MAX_KEEPALIVE_CONNECTIONS=20
OPENAI_HTTP_MAX_CONCURRENCY=8
WEB_SEARCH_HTTP_MAX_CONCURRENCY=4
MODEL_MAX_CONCURRENCY_PER_MODEL=3
ATTACHMENT_PROCESSING_MAX_CONCURRENCY=2
MEMORY_REFRESH_MAX_CONCURRENCY=1
```

#### 检索 / 知识库

```env
KNOWLEDGE_STORAGE_ROOT=./storage/knowledge
KNOWLEDGE_EMBEDDING_PROVIDER=dashscope
KNOWLEDGE_EMBEDDING_MODEL=text-embedding-v4
KNOWLEDGE_EMBEDDING_DIMENSIONS=1024
KNOWLEDGE_EMBEDDING_BATCH_SIZE=8
KNOWLEDGE_RERANK_PROVIDER=dashscope
KNOWLEDGE_RERANK_MODEL=gte-rerank-v2
KNOWLEDGE_RERANK_BASE_URL=https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank
KNOWLEDGE_RERANK_TIMEOUT_SECONDS=30
KNOWLEDGE_MAX_FILE_SIZE_BYTES=2097152
KNOWLEDGE_MAX_DOCUMENTS_PER_USER=100
KNOWLEDGE_MAX_TOTAL_SIZE_BYTES=104857600
RAG_QUERY_REWRITE_ENABLED=true
RAG_QUERY_REWRITE_MODEL=codex:gpt-5.2
RAG_QUERY_REWRITE_HISTORY_MESSAGES=6
WEB_SEARCH_BASE_URL=https://api.tavily.com
WEB_SEARCH_API_KEY=
WEB_SEARCH_TRANSLATION_MODEL=codex:gpt-5.2
```

切换 embedding 模型后，旧知识库向量需要重新索引。

#### 语音

```env
AUDIO_TRANSCRIPTION_ENABLED=true
AUDIO_TRANSCRIPTION_MODEL=qwen3-asr-flash
AUDIO_TRANSCRIPTION_TIMEOUT_SECONDS=60
AUDIO_TTS_ENABLED=true
AUDIO_TTS_MODEL=cosyvoice-v3-flash
AUDIO_TTS_VOICE=longanyang
AUDIO_TTS_FORMAT=mp3
AUDIO_TTS_SAMPLE_RATE=24000
AUDIO_TTS_TIMEOUT_SECONDS=60
```

Embedding、rerank、语音输入和语音播放默认复用 `DASHSCOPE_API_KEY`。TTS 默认使用百炼原生语音合成接口，只有需要改代理地址时才配置 `AUDIO_TTS_BASE_URL`。

## 本地开发

### 1. 启动后端

```powershell
cd backend
python app.py --reload
```

默认后端接口：

- `http://127.0.0.1:8050/api/health`

### 2. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

默认前端地址：

- `http://127.0.0.1:5200`
- 开发态默认代理后端：`http://127.0.0.1:8050`

开发与部署端口约定：

- 开发：前端 `5200`，后端 `8050`
- Docker 部署：前端 `3300`，后端 `8000`

## Docker

当前 `docker compose` 主要启动：

- `frontend`
- `backend`

后端不包含本地模型栈，适合纯 CPU + API 模型部署。
默认 compose 会启动：

- `postgres`：PostgreSQL + pgvector
- `redis`：缓存与运行状态辅助
- `backend`：FastAPI 服务
- `frontend`：Nginx 托管的前端静态资源

启动：

```bash
docker compose up -d --build
```

停止：

```bash
docker compose down
```

看日志：

```bash
docker compose logs -f
```

## WSL2 / 远程 API

部署环境只需要能访问 DeepSeek、百炼和你配置的其他云 API。

开发模式已经预设：

- Vite dev server 固定占用 `5200`
- Vite 代理默认转发到 `127.0.0.1:8050`
- 如需改前端开发代理目标，可设置环境变量 `CHATCHAT_DEV_API_ORIGIN`
- 如需通过你自己的内网穿透 host 访问 Vite，可设置环境变量 `CHATCHAT_DEV_ALLOWED_HOSTS`

不再需要为本地模型路由配置 WSL2 端口转发。

## 服务器建议

这套服务已经没有 GPU 常驻模型，资源主要花在 FastAPI、PostgreSQL、Redis、文件解析、向量检索和前端静态服务上。最多三五个人一起用、RAG 不高频时，可以按下面选：

| 场景 | CPU / 内存 | 磁盘 | 说明 |
| --- | --- | --- | --- |
| 最小可跑 | 2 vCPU / 4GB | 40GB SSD | 聊天为主，少量文件解析，建议限制并发 |
| 推荐 | 2 vCPU / 8GB | 60GB SSD | 三五个人日常使用更稳，PostgreSQL 和文件解析有余量 |
| 更舒服 | 4 vCPU / 8GB+ | 80GB SSD | 同时上传/解析文件、开知识库索引、多人并发时更从容 |

带宽通常不是瓶颈，1-5 Mbps 就能跑日常聊天；如果经常上传 PDF/DOCX 或多人同时语音，优先选更高上行和更稳定的线路。生产环境建议把 `MODEL_MAX_CONCURRENCY_PER_MODEL` 控在 `2-3`，避免上游 API 和本机文件解析同时被打满。

## 常用接口

### 系统

- `GET /api/health`
- `GET /api/models`

### 认证

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/session`

### 对话

- `GET /api/conversations`
- `GET /api/conversations/{id}`
- `PATCH /api/conversations/{id}`
- `DELETE /api/conversations/{id}`

### 聊天

- `POST /api/chat/stream`
- `POST /api/chat/regenerate`
- `PATCH /api/chat/messages/{message_id}/feedback`

### 检索 / 知识库 / 记忆 / 语音

- `GET /api/knowledge/status`
- `GET /api/knowledge/documents`
- `POST /api/knowledge/documents`
- `POST /api/knowledge/documents/batch`
- `POST /api/knowledge/documents/{id}/reindex`
- `POST /api/knowledge/reindex`
- `DELETE /api/knowledge/documents/{id}`
- `POST /api/knowledge/documents/delete`
- `PATCH /api/knowledge/documents/folder`
- `GET /api/memories`
- `POST /api/memories/items`
- `PATCH /api/memories/items/{id}`
- `POST /api/memories/{id}/promote`
- `POST /api/memories/{id}/dismiss`
- `DELETE /api/memories/items/{id}`
- `POST /api/audio/transcribe`
- `POST /api/audio/speech`

说明：

- `rag` 模式现在只检索当前登录用户自己的 Markdown 知识库
- 知识库文档支持 `folder/path` 逻辑分组，上传文件夹时会保留相对目录
- 查询重写会在 `rag` 检索前结合最近会话，把模糊问题改成更完整的知识库查询
- 知识库 `v1` 只支持 `.md` 上传，不再维护全局 Obsidian 扫描链路
- 支持批量上传和批量删除 Markdown 文档
- 上传文档后只会进入待更新状态，点击“更新知识库”后才会统一切分和建索引

## 测试

后端：

```powershell
$env:PYTHONPATH='E:\VScodeproject\Chatchat\backend'
python -m pytest backend\tests
```

前端：

```powershell
cd frontend
npm run build
```

## 当前文档对应代码状态

本 README 已按当前代码整理，重点同步了：

- 登录/多用户链路
- `native_multimodal` 三态策略
- reasoning 持久化
- memory 系统
- 共享 HTTP 连接池与上游限流
- 本地开发 / Docker / WSL2 / SSH tunnel 场景

如果你要继续开发，请优先同时更新：

- [README.md](README.md)
- [docs/开发文档.md](docs/开发文档.md)
- [docs/部署与模型接入.md](docs/部署与模型接入.md)
- [backend/model_catalog.json](backend/model_catalog.json)
