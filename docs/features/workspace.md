# 前端工作台

更新时间：2026-04-27

## 1. 功能范围

前端工作台负责把所有功能整合到一个应用界面里。

主要能力：

- 登录态管理。
- 桌面/移动端布局。
- 左侧导航。
- 会话列表。
- 辩论列表。
- 模型选择。
- reasoning 强度选择。
- 工具模式选择。
- 知识库分组选择。
- 设置页。
- 语音播放设置。

## 2. Workspace

关键文件：

- `frontend/src/features/workspace/`
- `frontend/src/features/workspace/model/useChatApp.ts`
- `frontend/src/features/workspace/ui/`

职责：

- 组织应用状态。
- 装配当前 active view。
- 处理会话、辩论、知识库、记忆等 feature 的交互。
- 处理移动端侧边栏。

## 3. Chat UI

关键文件：

- `frontend/src/features/chats/ui/ChatComposer.tsx`
- `frontend/src/features/chats/ui/ConversationView.tsx`
- `frontend/src/features/chats/ui/MessageList.tsx`
- `frontend/src/features/chats/api/streamChat.ts`

能力：

- 输入消息。
- 上传附件。
- 语音输入。
- 选择模型。
- 选择 reasoning profile。
- 选择工具模式。
- 选择知识库分组。
- 渲染流式消息。
- 渲染 reasoning 面板。
- 渲染来源。
- 播放 assistant 语音。

## 4. Knowledge UI

关键文件：

- `frontend/src/features/knowledge/ui/KnowledgePage.tsx`
- `frontend/src/features/knowledge/model/useKnowledgeManager.ts`

能力：

- 上传文件。
- 上传文件夹。
- 新建分组。
- 删除分组。
- 分组筛选。
- 文档搜索。
- 批量选择。
- 批量移动。
- 批量删除。
- 同步索引。

## 5. Settings UI

关键文件：

- `frontend/src/features/settings/`

能力：

- 用户信息。
- 修改密码。
- 语音播放 provider。
- 浏览器本机音色。
- 云端音色。

## 6. 共享 UI

当前共享 UI：

- `WorkspacePage`
- `AppLogo`
- `ConfirmDialog`
- `IconButton`

目录：

- `frontend/src/shared/ui/`

## 7. 当前边界

- `useChatApp.ts` 仍偏大，是后续拆分重点。
- `frontend/src/lib/api.ts` 仍是兼容聚合入口，后续应继续迁移到各 feature。
- UI 目前以功能可用和移动端适配为主，还不是完整设计系统。
