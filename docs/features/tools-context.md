# 工具模式与上下文注入

更新时间：2026-04-27

## 1. Tool Mode

当前聊天请求支持三种工具模式：

- `none`
  - 不检索。
- `knowledge`
  - 使用用户知识库 RAG。
- `search`
  - 使用网页搜索。

类型定义：

- `backend/app/schemas.py`
- `backend/app/tools/policy.py`

## 2. 前端入口

聊天输入区可以切换工具模式。

相关文件：

- `frontend/src/features/chats/ui/ChatComposer.tsx`
- `frontend/src/features/chats/ui/composer/ComposerMobileToolbar.tsx`
- `frontend/src/features/workspace/model/useChatApp.ts`

知识库模式下还能选择知识库分组。

## 3. 上下文构建流程

核心类：

- `ToolRuntimeService`

关键文件：

- `backend/app/tools/service.py`
- `backend/app/tools/plan.py`
- `backend/app/tools/policy.py`
- `backend/app/retrieval/strategy.py`

流程：

1. 根据 tool mode 构建 `ToolPolicy`。
2. 根据 query 和 policy 构建 `ToolContextPlan`。
3. 对知识库模式执行 RAG query rewrite。
4. 并行执行需要的上下文来源。
5. 合并 sources。
6. 合并 context entries。
7. 按策略加权排序。
8. 生成 system context message。
9. 注入最终聊天模型。

## 4. Source 类型

统一 source 类型：

- `note`
  - 知识库来源。
- `web`
  - 网页来源。
- `file`
  - 当前会话附件来源。

定义位置：

- `backend/app/retrieval/types.py`

## 5. 合并策略

当前策略：

- direct answer
- note-first
- web-first

策略会影响不同 source 的排序权重和回答指令。

例如：

- 知识库模式更偏向 note。
- 搜索模式更偏向 web。
- 文件上下文可以作为补充。

## 6. 最终上下文格式

后端构建 system message，包含：

- source type
- path/title/url/domain
- trust/freshness/match reason
- content
- 回答指令

最终提示要求：

- 使用 note 时引用 path。
- 使用 file 时引用文件名或附件名。
- 使用 web 时引用 URL 或站点名。
- 不引用内部 `[Source N]` 标签。

## 7. 配置失败处理

如果用户开启 `search` 但未配置搜索 provider，会返回明确拒绝：

```text
当前 Search 模式还没配置好，暂时不能联网搜索。
```

如果开启 `knowledge` 但没有 ready 文档，也会返回可理解的提示。
