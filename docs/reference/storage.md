# 数据存储与迁移

更新时间：2026-04-27

## 1. 数据库要求

当前正式启动只支持 PostgreSQL。

必须启用扩展：

- `vector`
- `pg_trgm`

SQLite 启动支持已移除。

## 2. Alembic 迁移

后端启动时会执行：

```text
alembic upgrade head
```

迁移入口：

- `backend/app/storage/database.py`
- `backend/app/storage/bootstrap.py`
- `backend/alembic/env.py`
- `backend/alembic/versions/`

启动时会检查：

- 数据库 dialect 是否为 PostgreSQL
- `vector` 扩展是否可用
- schema 是否迁移到 head

## 3. 启动日志说明

Alembic 正常运行不代表启动失败。

以前可能看到：

```text
INFO [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO [alembic.runtime.migration] Will assume transactional DDL.
```

这只是迁移日志。当前已降低 Alembic logger 级别，并移除 Alembic `fileConfig()` 对 Uvicorn logger 的重置，避免遮住 `Application startup complete`。

## 4. 主要数据表

用户与登录：

- `users`
- `user_sessions`

聊天：

- `conversations`
- `messages`
- `message_attachments`

知识库：

- `knowledge_documents`
- `knowledge_chunks`
- `knowledge_folders`

记忆：

- `memory_documents`
- `memory_items`

辩论：

- `debate_sessions`
- `debate_participants`
- `debate_turns`
- `debate_judge_decisions`

运行追踪：

- `runs`
- `run_events`

Provider 文件引用：

- `provider_file_refs`

## 5. 文件存储

`MEDIA_ROOT` 保存：

- 用户附件
- 生成图片
- 语音合成结果
- 其他可公开访问媒体

`KNOWLEDGE_STORAGE_ROOT` 保存：

- 知识库 Markdown 原文

数据库只保存文件相对路径和元数据。

## 6. 开发数据库

本地开发推荐使用：

```powershell
docker compose -f dev/docker-compose.dev-infra.yml up -d
```

默认端口：

- PostgreSQL：`127.0.0.1:5433`
- Redis：`127.0.0.1:6380`

默认数据库：

- database：`chatchat_dev`
- user：`chatchat_dev`
- password：`chatchat_dev`

