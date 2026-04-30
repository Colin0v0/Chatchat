# 系统架构与目录

更新时间：2026-04-30

## 1. 架构定位

Chatchat 是一个自托管 AI 聊天工作台。应用本身负责 Web UI、用户数据、上下文构建和模型编排；模型、检索、语音等能力通过 provider 接入。

核心组成：

- `frontend`：React + Vite + TypeScript 单页应用。
- `backend`：FastAPI + SQLAlchemy + Alembic 后端。
- `postgres`：保存用户、会话、消息、知识库、向量和记忆。
- `redis`：缓存和运行时辅助状态。
- `storage`：媒体附件、知识库原文、生成文件等。
- provider：模型、检索、语音和图片生成等外部能力。

## 2. 根目录

```text
Chatchat/
  backend/
  frontend/
  docs/
  storage/
  docker-compose.yml
  dev/docker-compose.dev-infra.yml
  README.md
```

目录职责：

- `backend/`：后端服务、模型调用、检索、记忆、数据库迁移。
- `frontend/`：前端界面、状态管理、API 调用。
- `docs/`：部署、开发、功能模块说明。
- `storage/`：运行时文件目录。
- `docker-compose.yml`：完整部署栈示例。
- `dev/docker-compose.dev-infra.yml`：本地开发数据库和 Redis。

## 3. 后端目录

```text
backend/app/
  api/
  application/
  audio/
  auth/
  chat/
  core/
  debate/
  knowledge/
  memory/
  multimodal/
  provider_codecs/
  provider_transports/
  providers/
  retrieval/
  runtime/
  storage/
  tools/
```

关键职责：

- `api/`：FastAPI 路由层。
- `application/`：聊天请求准备、会话处理、运行时分发。
- `runtime/`：统一流式运行时。
- `providers/`：模型目录、能力矩阵、provider registry。
- `provider_transports/`：真实上游 HTTP 调用。
- `provider_codecs/`：provider 请求和流式响应归一化。
- `retrieval/`：知识库、网页搜索、附件上下文。
- `tools/`：工具策略、上下文规划、上下文注入。
- `storage/`：数据库、ORM、Alembic、媒体文件。

## 4. 前端目录

```text
frontend/src/
  features/
    auth/
    chats/
    debates/
    knowledge/
    memories/
    models/
    settings/
    workspace/
  shared/
    api/
    hooks/
    ui/
  lib/
  App.tsx
  main.tsx
  types.ts
```

关键职责：

- `features/auth`：登录、会话状态。
- `features/chats`：聊天界面、消息、输入框、流式事件。
- `features/debates`：辩论创建、房间、裁判交互。
- `features/knowledge`：知识库分组、上传、移动、删除。
- `features/memories`：记忆管理。
- `features/models`：模型选择、reasoning profile。
- `features/settings`：设置页、语音播放 provider。
- `features/workspace`：整体工作台、侧边栏、页面切换。
- `shared/api`：通用 API 请求工具。
- `shared/ui`：共享 UI 组件。

## 5. 请求流概览

普通聊天请求：

```text
Browser
  -> frontend ChatComposer
  -> POST /api/chat/stream
  -> application/chat_preparation
  -> memory / retrieval / tool context
  -> runtime orchestrator
  -> provider transport
  -> NDJSON stream
  -> frontend MessageList
```

知识库检索请求：

```text
Browser
  -> tool_mode=knowledge
  -> ToolRuntimeService
  -> query rewrite
  -> KnowledgeService.retrieve_context
  -> vector search + optional rerank
  -> context/source injection
```

网页搜索请求：

```text
Browser
  -> tool_mode=search
  -> WebSearchService
  -> WebSearchProvider
  -> dedupe/filter/rerank
  -> context/source injection
```
