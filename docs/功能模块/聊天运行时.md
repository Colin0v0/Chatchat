# 聊天运行时

更新时间：2026-04-27

## 1. 功能范围

聊天运行时支持：

- 新建会话
- 连续对话
- 流式回答
- 停止生成
- 重试回答
- 活跃流重连
- reasoning/thinking 展示
- sources/context 展示
- assistant 消息反馈
- 会话标题生成
- 会话重命名和删除

## 2. 关键 API

- `POST /api/chat/stream`
- `GET /api/chat/stream/active`
- `POST /api/chat/regenerate`
- `PATCH /api/chat/messages/{message_id}/feedback`

关键文件：

- `backend/app/api/chat.py`
- `backend/app/application/chat.py`
- `backend/app/application/chat_preparation.py`
- `backend/app/application/chat_requests.py`
- `backend/app/runtime/orchestrator.py`
- `backend/app/runtime/modes/chat.py`

## 3. 请求流程

```text
POST /api/chat/stream
  -> 鉴权
  -> 解析 FormData
  -> 保存附件
  -> 创建或加载 conversation
  -> 保存 user message
  -> 构建 tool policy
  -> 构建上下文
  -> runtime orchestrator
  -> provider transport
  -> NDJSON stream
```

## 4. 流式事件

后端输出 NDJSON。

主要事件：

- `meta`
  - run id、conversation id、message id 等元信息。
- `status`
  - 当前阶段，例如准备、检索、请求模型。
- `reasoning`
  - reasoning/thinking 增量。
- `token`
  - assistant 正文增量。
- `sources`
  - 检索来源。
- `context`
  - 上下文调试信息。
- `done`
  - 完成。
- `error`
  - 错误。

前端消费文件：

- `frontend/src/features/chats/api/streamChat.ts`
- `frontend/src/features/chats/model/useConversationStreams.ts`
- `frontend/src/features/chats/ui/MessageList.tsx`

## 5. 消息持久化

消息表：

- `messages`

保存内容：

- role
- content
- reasoning
- response mode
- feedback
- image context
- attachment context

附件表：

- `message_attachments`

## 6. 活跃流重连

当移动端切换页面、刷新或网络短断时，前端可以请求：

```text
GET /api/chat/stream/active
```

后端通过 `ChatRunRegistry` 追踪 active run。

关键文件：

- `backend/app/runtime/chat_runs.py`
- `frontend/src/features/chats/model/useConversationStreams.ts`

## 7. 当前边界

- 当前是服务端主动流式响应，不是完整 agent tool loop。
- 检索工具在模型调用前完成上下文注入。
- 模型是否支持 reasoning 由模型目录控制。

