# 部署与模型接入

更新时间：2026-04-30

本文档说明 Chatchat 的通用部署结构和模型接入方式。具体 provider 的 API 地址、模型名和鉴权方式通过环境变量与模型目录配置，不在本文档中绑定到某个云厂商。

## 1. 部署组成

一个完整部署通常包含：

- 前端静态服务。
- 后端 API 服务。
- PostgreSQL 数据库。
- Redis 缓存。
- 持久化文件目录。
- 一个或多个外部模型 provider。

```text
browser
  -> frontend
  -> backend
      -> model providers
      -> retrieval providers
      -> speech providers
      -> PostgreSQL
      -> Redis
      -> storage/
```

## 2. 本地开发

启动数据库和缓存：

```bash
docker compose -f dev/docker-compose.dev-infra.yml up -d
```

启动后端：

```bash
cd backend
python app.py
```

启动前端：

```bash
cd frontend
pnpm install
pnpm dev
```

## 3. 生产部署

生产环境可以使用根目录的 `docker-compose.yml` 作为参考。推荐把镜像构建和运行拆开：

- 在 CI 或构建机上构建前后端镜像。
- 在服务器上拉取镜像并启动服务。
- 数据库、缓存和文件目录使用持久化卷。
- provider key 通过环境变量注入。

最小服务依赖：

```text
frontend
backend
postgres
redis
storage volume
```

## 4. 核心环境变量

基础设施：

```env
DATABASE_URL=
REDIS_URL=
MEDIA_ROOT=./storage/media
MODEL_CATALOG_PATH=./model_catalog.json
DEFAULT_PROVIDER=
DEFAULT_MODEL=
```

模型 provider：

```env
OPENAI_BASE_URL=
OPENAI_API_KEY=

CLAUDE_BASE_URL=
CLAUDE_API_KEY=

GEMINI_BASE_URL=
GEMINI_API_KEY=
```

项目可以继续扩展其他 provider，只要在后端 provider registry 和 `model_catalog.json` 中声明即可。

## 5. 模型目录

`backend/model_catalog.json` 负责声明：

- 模型 id。
- 展示名称。
- provider 引用。
- 上游模型名。
- 上下文窗口。
- reasoning 能力。
- 多模态输入能力。
- 是否启用。

前端和后端都以模型目录中的能力声明为准，避免 UI 允许上传但后端或模型不支持的情况。

## 6. 可选能力

这些能力可以按需启用：

- 知识库 embedding。
- rerank。
- Web Search。
- 语音转写。
- 文本朗读。
- 图片生成。

对应环境变量按能力分组，例如：

```env
KNOWLEDGE_EMBEDDING_PROVIDER=
KNOWLEDGE_EMBEDDING_BASE_URL=
KNOWLEDGE_EMBEDDING_API_KEY=
KNOWLEDGE_EMBEDDING_MODEL=

KNOWLEDGE_RERANK_PROVIDER=
KNOWLEDGE_RERANK_BASE_URL=
KNOWLEDGE_RERANK_API_KEY=
KNOWLEDGE_RERANK_MODEL=

WEB_SEARCH_PROVIDER=
WEB_SEARCH_BASE_URL=
WEB_SEARCH_API_KEY=
WEB_SEARCH_MODEL=

AUDIO_TRANSCRIPTION_ENABLED=false
AUDIO_TRANSCRIPTION_BASE_URL=
AUDIO_TRANSCRIPTION_API_KEY=
AUDIO_TRANSCRIPTION_MODEL=

AUDIO_TTS_ENABLED=false
AUDIO_TTS_BASE_URL=
AUDIO_TTS_API_KEY=
AUDIO_TTS_MODEL=

OPENAI_IMAGE_BASE_URL=
OPENAI_IMAGE_API_KEY=
OPENAI_IMAGE_MODEL=
```

未配置的可选能力应在调用时返回明确错误或在前端保持不可用状态。

## 7. 数据持久化

建议持久化：

- PostgreSQL 数据卷。
- Redis 数据卷。
- `storage/` 文件目录。

`storage/` 通常保存：

- 用户上传附件。
- 生成的媒体文件。
- 知识库原文件。

数据库保存：

- 用户和 session。
- 会话和消息。
- 附件 metadata。
- 知识库 chunk 和向量。
- 记忆条目和记忆文档。
- 模型运行记录。

## 8. 部署检查清单

- 数据库连接可用。
- Redis 连接可用。
- 至少一个聊天模型可用。
- `model_catalog.json` 中的默认模型已启用。
- `storage/` 可写。
- 前端能访问后端 API。
- CORS 和 Cookie 设置符合部署域名。
- 可选能力的 provider key 已按需配置。
