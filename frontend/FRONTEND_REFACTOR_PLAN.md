# Chatchat Frontend Refactor Plan

## 0. 当前真实问题

前端现在已经不是“组件多”这么简单，而是出现了明显的横向耦合：

- `src/app/useChatApp.ts` 负责聊天、辩论、知识库、记忆、模型、侧边栏切换，已经变成总控器。
- `src/lib/api.ts` 同时承接 auth / chats / debates / models / memories / knowledge 的请求与响应归一化。
- `src/types.ts` 变成全局类型桶，业务边界被抹平。
- `src/components/*` 以页面和平铺组件为主，目录能看出 UI 形态，看不出业务归属。
- `WorkspaceMainView`、`Sidebar`、`MainHeader` 承担的是工作区编排，但没有独立的 workspace slice。

这会导致两个直接问题：

- 你想改一个功能，经常要同时进 `app/`、`components/`、`lib/`、`types.ts`。
- 后端已经按领域和 runtime 拆开，前端如果还维持“全局大 Hook + 平铺组件”，前后端会越来越不对齐。

## 1. 重构目标

这次建议采用“轻量版 `feature-first + shared`”，先不强推完整 FSD。

目标是：

- 业务代码按功能归属，而不是按技术类型归属。
- `shared` 只放稳定、无业务语义的基础能力，不再当第二个杂物间。
- 每个 feature 自己拥有 `api / model / ui / lib / types`。
- `App` 和 workspace 层只负责装配，不再持有全部业务细节。
- 迁移过程中允许新旧结构并存，按 feature 逐步切。

## 2. 建议的目标目录

```text
src/
  app/
    bootstrap/
    providers/
    styles/
    index.tsx

  shared/
    api/
      http.ts
      ndjson.ts
      errors.ts
    config/
    hooks/
    lib/
    ui/
    types/

  features/
    auth/
      api/
      model/
      ui/
      index.ts

    workspace/
      model/
      ui/
      lib/
      index.ts

    chats/
      api/
      model/
      ui/
      lib/
      index.ts

    debates/
      api/
      model/
      ui/
      lib/
      index.ts

    knowledge/
      api/
      model/
      ui/
      lib/
      index.ts

    memories/
      api/
      model/
      ui/
      lib/
      index.ts

    models/
      api/
      model/
      ui/
      lib/
      index.ts
```

这个版本故意不先上 `entities / widgets / pages`。

原因：

- 你现在最需要的是把横向大文件按 feature 切开。
- 如果一开始就加完整分层，迁移成本会高，目录会先比业务更复杂。
- 等 `features/*` 稳定后，再判断是否补 `widgets` 或 `entities`。

## 3. shared 的边界

`shared` 只允许放下面几类内容：

- 通用 HTTP client、流解析、错误封装。
- 通用 hooks，例如 `useLatest`, `useEventListener`, `useMediaQuery`。
- 无业务语义的 UI primitives，例如 Button、Dialog、Spinner、Tabs。
- 日期、下载、剪贴板、格式化等纯工具函数。
- 环境变量、常量、主题 token。

不要放进 `shared` 的内容：

- `ConversationDetail`、`DebateSessionDetail` 这类业务模型。
- `tool_mode`、`reasoning_profile` 这类产品语义枚举。
- 面向具体 feature 的请求函数。
- “因为多个文件都用了”但其实带业务含义的类型和工具。

规则很简单：

- 没有业务语义，才能进 `shared`。
- 带业务语义，但被多个页面复用，优先留在所属 feature。

## 4. 现有文件到新结构的映射

### Auth

- `src/app/useAuthSession.ts` -> `src/features/auth/model/useAuthSession.ts`
- `src/components/LoginView.tsx` -> `src/features/auth/ui/LoginView.tsx`

### Workspace

- `src/components/Sidebar.tsx`
- `src/components/MainHeader.tsx`
- `src/components/WorkspaceMainView.tsx`
- `src/app/workspaceSections.ts`

建议迁到：

- `src/features/workspace/ui/*`
- `src/features/workspace/model/*`

### Chats

- `src/app/useConversationStreams.ts`
- `src/app/chatSessionUtils.ts`
- `src/components/ConversationView.tsx`
- `src/components/ChatComposer.tsx`
- `src/components/MessageList.tsx`
- `src/components/message/*`
- `src/components/context/*`
- `src/components/thinking/*`
- `src/components/markdown/*`

建议迁到：

- `src/features/chats/api/*`
- `src/features/chats/model/*`
- `src/features/chats/ui/*`
- `src/features/chats/lib/*`

### Debates

- `src/components/DebateRoomView.tsx`
- `src/components/DebateCreateView.tsx`
- `src/components/DebatesHomeView.tsx`
- `src/components/debate/*`

建议迁到：

- `src/features/debates/api/*`
- `src/features/debates/model/*`
- `src/features/debates/ui/*`
- `src/features/debates/lib/*`

### Knowledge

- `src/app/useKnowledgeManager.ts`
- `src/components/KnowledgePage.tsx`

建议迁到：

- `src/features/knowledge/*`

### Memories

- `src/app/useMemoryManager.ts`
- `src/components/MemoriesPage.tsx`

建议迁到：

- `src/features/memories/*`

### Models

- `src/app/modelOptions.ts`
- `src/app/modelCapabilities.ts`
- `src/app/reasoningProfiles.ts`
- `src/components/ModelSelect.tsx`
- `src/components/ReasoningProfileSelect.tsx`
- `src/components/ModelsPage.tsx`

建议迁到：

- `src/features/models/model/*`
- `src/features/models/ui/*`
- `src/features/models/lib/*`

### API 与类型

- `src/lib/api.ts`
- `src/types.ts`

建议拆成：

- `src/shared/api/http.ts`
- `src/shared/api/ndjson.ts`
- `src/shared/api/errors.ts`
- `src/features/auth/api/*`
- `src/features/chats/api/*`
- `src/features/debates/api/*`
- `src/features/knowledge/api/*`
- `src/features/memories/api/*`
- `src/features/models/api/*`

类型原则：

- 请求/响应 DTO 尽量跟 feature API 放一起。
- 只有纯基础类型才进 `shared/types`。

## 5. `useChatApp` 的拆法

`useChatApp` 不要再继续加逻辑，建议按“状态域”拆成多个 feature hooks：

```text
features/chats/model/
  useConversationList.ts
  useConversationDetail.ts
  useChatComposer.ts
  useChatStreaming.ts
  useConversationActions.ts

features/debates/model/
  useDebateList.ts
  useDebateRoom.ts
  useDebateCreate.ts

features/workspace/model/
  useWorkspaceSection.ts
  useSidebarState.ts
```

然后保留一个薄的装配层：

- `features/workspace/model/useWorkspaceApp.ts`

这个 Hook 只负责拼装 feature 输出，不直接处理底层请求、流式消息和业务规则。

## 6. `lib/api.ts` 的拆法

当前 `lib/api.ts` 的问题不是文件大，而是“所有 feature 共用一个入口”。

建议分两层：

### shared 基础层

- `shared/api/http.ts`
  - `apiFetch`
  - `ApiError`
  - base url
  - unauthorized handler

- `shared/api/ndjson.ts`
  - 流式事件解析

### feature API 层

- `features/auth/api/session.ts`
- `features/chats/api/conversations.ts`
- `features/chats/api/streamChat.ts`
- `features/debates/api/debates.ts`
- `features/knowledge/api/knowledge.ts`
- `features/memories/api/memories.ts`
- `features/models/api/models.ts`

这样以后改一个 feature 的请求，不会再碰整个 `api.ts`。

## 7. 迁移顺序

建议按下面顺序做，不要一次性搬家：

1. 先建立新目录和 import alias。
2. 先拆 `shared/api`，把 `lib/api.ts` 压成基础层 + feature API。
3. 先迁移 `auth`、`models`、`workspace` 这三个相对独立的 slice。
4. 再拆 `chats`，优先拆 `useConversationStreams`、`ChatComposer`、`MessageList`。
5. 再拆 `debates`，把 `DebateRoomView` 和 `components/debate/*` 合并进同一 feature。
6. 最后迁 `knowledge` 和 `memories`。
7. 当 `useChatApp` 只剩装配职责时，再把它改名成 `useWorkspaceApp` 或直接删掉。

## 8. 第一刀建议

如果只开一个前端重构 PR，我建议第一刀做这些：

1. 新建 `shared/api/http.ts`、`shared/api/errors.ts`、`shared/api/ndjson.ts`。
2. 新建 `features/auth`、`features/models`、`features/workspace`。
3. 把 `useAuthSession`、`LoginView`、`ModelSelect`、`ReasoningProfileSelect`、`workspaceSections` 先迁走。
4. `App.tsx` 改成只组合 `auth + workspace`。
5. 暂时保留旧 `useChatApp`，但不再往里面继续加新逻辑。

这样做的好处：

- 风险低。
- PR 可控。
- 后面拆 chats / debates 时，基础边界已经先立住了。

## 9. 不建议现在做的事

- 不建议一开始就全量引入 `react-router`，当前只有 `/` 和 `/login`，先把业务切片做好更重要。
- 不建议先造 `shared/types` 大全集，这会把现在的 `types.ts` 问题原样复制过去。
- 不建议一上来就把所有 UI primitive 重写一遍，先迁移归属，再收敛设计系统。

## 10. 这套方案的判断标准

重构完成后，应该达到下面的效果：

- 新增一个知识库交互，不需要修改 chats / debates / models 的目录。
- 改一个 debate API，不需要再打开全局 `lib/api.ts`。
- 改一个聊天流式状态，不需要再穿过 `App -> useChatApp -> components/*` 一整条链。
- 新人看到目录，能先找到 feature，再找到该 feature 的 `api / model / ui`。
