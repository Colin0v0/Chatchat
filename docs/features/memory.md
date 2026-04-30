# 记忆系统

更新时间：2026-04-30

## 1. 功能范围

记忆系统用于保存和管理用户长期或会话相关信息。

当前支持：

- 全局记忆。
- 会话记忆。
- 工作记忆。
- 候选记忆。
- 记忆文档。
- 手动创建记忆。
- 自动候选记忆。
- 高置信长期记忆自动确认。
- promote candidate。
- dismiss candidate。
- 更新和删除记忆。

## 2. 记忆层级

层级：

- global
  - 用户长期偏好或长期事实。
- conversation
  - 当前会话相关记忆。
- working
  - 临时工作记忆。
- candidate
  - 系统提取但尚未确认的候选。

## 3. 后端 API

```text
GET    /api/memories
POST   /api/memories/items
PATCH  /api/memories/items/{memory_id}
POST   /api/memories/{memory_id}/promote
POST   /api/memories/{memory_id}/dismiss
DELETE /api/memories/items/{memory_id}
```

关键文件：

- `backend/app/api/memories.py`
- `backend/app/memory/service.py`
- `backend/app/memory/store.py`
- `backend/app/memory/types.py`

## 4. 数据模型

表：

- `memory_documents`
- `memory_items`

记忆字段包括：

- scope
- kind
- title
- detail
- tags
- confidence
- pinned
- active
- auto_managed
- conversation_id

## 5. 自动记忆策略

记忆刷新在 assistant 回复结束后异步调度，由 `MemoryService.schedule_refresh` 触发。

当前写入分层：

- 显式记忆请求可直接写入 active memory。
- 高置信长期记忆：
  - `profile` / `preference` 中的稳定条目可自动提升为 `global active`。
  - 该路径用于低频、高价值、跨会话信息。
- 普通自动记忆：
  - 普通事实默认进入 `conversation candidate`。
  - 当前任务、临时约束等短期信息进入 `working active`，并带过期时间。
  - 候选记忆需要用户在记忆页 promote 后才会成为 active memory。

归一化职责：

- `MemoryExtractor` 从最近一轮对话抽取候选。
- `memory.normalizer` 清洗标题、正文和标签，合并同义字段。
- `MemoryService` 根据 scope、kind、confidence 和短期标记决定写入层级。

## 6. prompt 注入

回答前，运行时会调用 `MemoryService.build_prompt_payload`：

- 先清理过期 working memory。
- 加载当前用户的 `memory_documents`。
- 按用户问题召回 active memory hits。
- 构造成一条 system message 注入模型上下文。

冲突处理原则：

- 当前会话优先于历史记忆。
- `memory_documents` 是压缩后的稳定背景。
- `Relevant memory hits` 是本轮检索到的精确条目。

## 7. 前端入口

关键文件：

- `frontend/src/features/memories/`

前端能力：

- 查看 active memory。
- 查看 candidate memory。
- 新建手动记忆。
- 编辑记忆。
- 删除记忆。
- promote/dismiss candidate。

## 8. 当前边界

- 当前记忆不是完整向量记忆系统。
- 自动记忆仍然偏保守，只有高置信长期记忆会自动进入 `global active`。
- 普通项目上下文和临时事实默认不会自动进入全局长期记忆。
- 带附件的消息默认更谨慎处理自动候选。
