# Chatchat

Chatchat 是一个面向个人/小团队的聊天工作台，当前提供：

- 多模型聊天：`Ollama`、`OpenAI`、`OpenAI Codex`、`OpenAI-compatible local router`
- 登录与多用户隔离：基于账号密码和 Cookie Session
- 推理展示：支持 reasoning/thinking 流式展示与持久化
- 检索增强：用户知识库 `RAG`、`Web Search`
- 多模态输入：图片、PDF、DOCX、XLSX、CSV、文本类文件
- 语音转写：可选本地 `SenseVoice / FunASR`
- 记忆系统：全局记忆、会话记忆、工作记忆、候选记忆、记忆文档

当前代码默认遵循这几个原则：

- 优先做清晰重构，不堆补丁
- 不主动引入隐式 fallback
- 能力按领域收口，避免逻辑散落

详细开发说明见 [开发文档.md](开发文档.md)。

## 当前架构

```text
Chatchat/
  backend/      FastAPI + SQLAlchemy + LLM / Retrieval / Memory
  frontend/     React 19 + Vite + TypeScript
  storage/      数据库、媒体、用户知识库文件
  docker-compose.yml
  README.md
  开发文档.md
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

`rag` 模式当前会先做一层“查询重写”：

- 结合最近几轮对话，把“它 / 那个 / 上面那段”改写成更完整的检索问题
- 只影响知识库检索，不影响最终用户原始问题
- 相关配置见 `RAG_QUERY_REWRITE_*`

### 3. 多模态与附件

所有模型前端都允许上传附件，但后端现在按三态处理：

- `native_multimodal="false"`
  - 走本地附件解析链路
  - 图片走本地视觉/OCR
  - 文件走本地解析器
  - 把结果写入 `attachment_context`

- `native_multimodal="local"`
  - 保留当前 OpenAI-compatible 本地路由的原生附件链路
  - 附件上传到上游 `/v1/files`
  - 聊天请求里传 `input_file`

- `native_multimodal="codex"`
  - 图片直接作为原生多模态输入发送给 Codex / GPT-5
  - 文档和其他文件继续走本地解析
  - 不复用 `/v1/files` 直传链路

当前 `native_multimodal` 由 [backend/model_catalog.json](backend/model_catalog.json) 控制。

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

当前 provider 主要有三类：

- `ollama`
- `openai`
- `codex`
- `openai_local`

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

常用模板：

- `backend/.env.dev.windows.example`
- `backend/.env.deploy.wsl.example`

### 关键环境变量

#### 模型与路由

```env
OPENAI_BASE_URL=
OPENAI_API_KEY=
CODEX_BASE_URL=
CODEX_API_KEY=
OPENAI_LOCAL_BASE_URL=
OPENAI_LOCAL_UPSTREAM_SERVICE_BASE_URL=
OPENAI_LOCAL_API_KEY=
OLLAMA_BASE_URL=
MODEL_CATALOG_PATH=./model_catalog.json
MODEL_CATALOG_STRICT=true
DEFAULT_PROVIDER=openai
DEFAULT_MODEL=openai:deepseek-chat
```

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
OPENAI_LOCAL_HTTP_MAX_CONCURRENCY=4
OLLAMA_HTTP_MAX_CONCURRENCY=4
WEB_SEARCH_HTTP_MAX_CONCURRENCY=4
MODEL_MAX_CONCURRENCY_PER_MODEL=3
ATTACHMENT_PROCESSING_MAX_CONCURRENCY=2
MEMORY_REFRESH_MAX_CONCURRENCY=1
```

#### 检索 / 知识库

```env
KNOWLEDGE_STORAGE_ROOT=./storage/knowledge
KNOWLEDGE_EMBEDDING_MODEL=qwen3-embedding:0.6b
KNOWLEDGE_RERANK_MODEL=codex:gpt-5.2
KNOWLEDGE_MAX_FILE_SIZE_BYTES=2097152
KNOWLEDGE_MAX_DOCUMENTS_PER_USER=100
KNOWLEDGE_MAX_TOTAL_SIZE_BYTES=104857600
RAG_QUERY_REWRITE_ENABLED=true
RAG_QUERY_REWRITE_MODEL=openai_local:claude-haiku-4-5
RAG_QUERY_REWRITE_HISTORY_MESSAGES=6
WEB_SEARCH_BASE_URL=https://api.tavily.com
WEB_SEARCH_API_KEY=
WEB_SEARCH_TRANSLATION_MODEL=openai_local:claude-haiku-4-5
```

#### 语音

```env
AUDIO_TRANSCRIPTION_ENABLED=true
AUDIO_TRANSCRIPTION_EAGER_LOAD=false
AUDIO_TRANSCRIPTION_MODEL=iic/SenseVoiceSmall
AUDIO_TRANSCRIPTION_DEVICE=cpu
```

如果当前环境没有装 `funasr`，请直接关闭语音：

```env
AUDIO_TRANSCRIPTION_ENABLED=false
AUDIO_TRANSCRIPTION_EAGER_LOAD=false
```

## 本地开发

### 1. 启动后端

```powershell
cd backend
python app.py
```

默认后端接口：

- `http://127.0.0.1:8000/api/health`

### 2. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

默认前端地址：

- `http://127.0.0.1:5200`

## Docker

当前 `docker compose` 主要启动：

- `frontend`
- `backend`

`Ollama` 默认仍然跑在宿主机，不放进容器。

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

## WSL2 / SSH Tunnel / 远程模型

如果部署环境在 WSL2，模型路由在 Windows 或远端机器，需要先把地址打通。

### 场景 1：Windows 上跑本地模型路由，WSL2 后端访问

把 `OPENAI_LOCAL_BASE_URL` / `OPENAI_LOCAL_UPSTREAM_SERVICE_BASE_URL` 指向 WSL2 可访问的地址，例如：

```env
OPENAI_LOCAL_BASE_URL=http://host.docker.internal:61527/v1
OPENAI_LOCAL_UPSTREAM_SERVICE_BASE_URL=http://host.docker.internal:61527/v1
```

### 场景 2：远端机器通过 SSH 暴露模型路由

```bash
ssh -N -L 61527:127.0.0.1:61527 user@remote-host
```

然后本地后端指向：

```env
OPENAI_LOCAL_BASE_URL=http://127.0.0.1:61527/v1
OPENAI_LOCAL_UPSTREAM_SERVICE_BASE_URL=http://127.0.0.1:61527/v1
```

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
- `GET /api/memories`
- `POST /api/memories/items`
- `PATCH /api/memories/items/{id}`
- `POST /api/memories/{id}/promote`
- `POST /api/memories/{id}/dismiss`
- `DELETE /api/memories/items/{id}`
- `POST /api/audio/transcribe`

说明：

- `rag` 模式现在只检索当前登录用户自己的 Markdown 知识库
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
- [开发文档.md](开发文档.md)
- [backend/model_catalog.json](backend/model_catalog.json)
