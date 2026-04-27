# 知识库 RAG

更新时间：2026-04-27

## 1. 功能范围

知识库当前用于用户私有 Markdown 资料检索。

支持：

- 上传单个 Markdown。
- 批量上传 Markdown。
- 上传本地文件夹。
- 保留文件夹相对路径。
- 新建知识库分组。
- 删除知识库分组。
- 按分组查看文档。
- 按分组参与聊天检索。
- 批量移动文档到分组。
- 批量删除文档。
- 单文档重新索引。
- 全量同步索引。

## 2. 前端入口

页面：

- `frontend/src/features/knowledge/ui/KnowledgePage.tsx`

状态：

- `frontend/src/features/knowledge/model/useKnowledgeManager.ts`

API：

- `frontend/src/features/knowledge/api/knowledge.ts`

用户操作：

- 拖拽 Markdown 上传。
- 点击选择文件。
- 点击选择文件夹。
- 选择“归入”分组。
- 输入分组名。
- 左侧分组筛选。
- 批量选择当前分组文档。
- 移动到分组。
- 删除文档或分组。

## 3. 后端 API

```text
GET    /api/knowledge/documents
POST   /api/knowledge/documents
POST   /api/knowledge/documents/batch
POST   /api/knowledge/documents/{document_id}/reindex
POST   /api/knowledge/reindex
DELETE /api/knowledge/documents/{document_id}
POST   /api/knowledge/documents/delete
PATCH  /api/knowledge/documents/folder
GET    /api/knowledge/folders
POST   /api/knowledge/folders
DELETE /api/knowledge/folders
GET    /api/knowledge/status
```

关键文件：

- `backend/app/api/knowledge.py`
- `backend/app/knowledge/service.py`

## 4. 数据模型

表：

- `knowledge_documents`
- `knowledge_chunks`
- `knowledge_folders`

重要字段：

- `knowledge_documents.folder`
- `knowledge_documents.relative_path`
- `knowledge_documents.status`
- `knowledge_chunks.embedding`
- `knowledge_chunks.content`
- `knowledge_chunks.heading`
- `knowledge_chunks.path`

默认分组在数据库里用空字符串保存，前端显示为“默认分组”。

## 5. 上传流程

```text
UploadFile
  -> 校验文件类型和大小
  -> 计算 sha1
  -> 保存到 KNOWLEDGE_STORAGE_ROOT
  -> 写 knowledge_documents
  -> status=pending
```

上传文件夹时，前端会传 `relative_paths`，后端保存相对路径，方便 UI 展示原始目录结构。

## 6. 索引流程

```text
pending document
  -> 读取 Markdown
  -> 解析标题和段落
  -> chunking
  -> DashScope embedding
  -> 写 knowledge_chunks
  -> status=ready
```

失败时：

- `status=failed`
- `error_message` 保存错误原因

关键文件：

- `backend/app/retrieval/rag/chunking.py`
- `backend/app/retrieval/rag/embedder.py`

## 7. 检索流程

```text
user query
  -> 可选 query rewrite
  -> query embedding
  -> pgvector recall
  -> 文本匹配补分
  -> DashScope rerank
  -> 邻近 chunk 扩展
  -> SourceItem(type=note)
  -> ContextEntry
```

关键文件：

- `backend/app/retrieval/query_rewrite.py`
- `backend/app/retrieval/rag/retriever.py`
- `backend/app/retrieval/rag/model_reranker.py`
- `backend/app/retrieval/rag/neighbors.py`

## 8. Query Rewrite

知识库模式会尝试把上下文依赖问题改写为完整检索问题。

例如：

```text
用户：上面那套部署方案怎么改？
改写：Chatchat 纯 CPU API 部署方案如何调整服务器配置？
```

配置：

```env
RAG_QUERY_REWRITE_ENABLED=true
RAG_QUERY_REWRITE_MODEL=codex:gpt-5.2
RAG_QUERY_REWRITE_HISTORY_MESSAGES=6
```

改写只影响检索，不替换用户最终问题。

## 9. 分组规则

分组是逻辑分组，不直接等于服务端物理目录。

删除分组时：

- 分组记录删除。
- 分组内文档移动到默认分组。
- 文档文件不删除。
- 如果默认分组存在同名冲突，后端会拒绝。

## 10. 配置

```env
KNOWLEDGE_STORAGE_ROOT=./storage/knowledge
KNOWLEDGE_EMBEDDING_PROVIDER=dashscope
KNOWLEDGE_EMBEDDING_MODEL=text-embedding-v4
KNOWLEDGE_EMBEDDING_DIMENSIONS=1024
KNOWLEDGE_EMBEDDING_BATCH_SIZE=8
KNOWLEDGE_RERANK_PROVIDER=dashscope
KNOWLEDGE_RERANK_MODEL=gte-rerank-v2
KNOWLEDGE_TOP_K=5
KNOWLEDGE_CANDIDATE_LIMIT=4
KNOWLEDGE_RERANK_WINDOW=2
KNOWLEDGE_MIN_SCORE=0.22
```

## 11. 当前边界

- 当前主要支持 Markdown。
- 不使用本地 embedding。
- 不使用本地 reranker。
- 切换 embedding 维度后必须重建索引。
- 大文件和大量文档需要调高上传限制和服务器资源。

