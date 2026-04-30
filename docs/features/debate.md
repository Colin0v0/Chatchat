# 辩论模式

更新时间：2026-04-27

## 1. 功能范围

辩论模式支持让两个模型围绕一个主题进行结构化辩论，并可选裁判模型。

支持：

- 创建辩论主题。
- 选择正方模型。
- 选择反方模型。
- 可选裁判模型。
- 选择辩论风格。
- 多阶段推进。
- 用户向裁判提问。
- 裁判给出判定。
- 活跃流重连。
- 辩论重命名。
- 辩论删除。

## 2. 后端 API

```text
GET    /api/debate/sessions
POST   /api/debate/sessions
GET    /api/debate/sessions/{session_id}
PATCH  /api/debate/sessions/{session_id}
DELETE /api/debate/sessions/{session_id}
POST   /api/debate/sessions/{session_id}/next
POST   /api/debate/sessions/{session_id}/judge/ask
POST   /api/debate/sessions/{session_id}/judge/decision
GET    /api/debate/sessions/{session_id}/stream/active
```

关键文件：

- `backend/app/api/debate.py`
- `backend/app/debate/`
- `backend/app/runtime/modes/debate*.py`
- `backend/app/runtime/debate_runs.py`

## 3. 数据模型

表：

- `debate_sessions`
- `debate_participants`
- `debate_turns`
- `debate_judge_decisions`

关系：

- 一个 session 有多个 participants。
- 一个 session 有多个 turns。
- judge decision 绑定 session。

## 4. 运行流程

```text
create session
  -> 保存 topic/config/participants
  -> next
  -> runtime debate mode
  -> 调用当前阶段对应模型
  -> 保存 turn
  -> 推进 stage
```

活跃流通过 `DebateRunRegistry` 追踪。

## 5. 前端入口

关键文件：

- `frontend/src/features/debates/`
- `frontend/src/features/debates/ui/DebateCreateView.tsx`
- `frontend/src/features/debates/ui/DebateRoomView.tsx`
- `frontend/src/features/debates/ui/room/`

## 6. 当前边界

- 辩论不是通用 agent 框架。
- 阶段推进由后端固定策略控制。
- 模型是否可选取决于 `model_catalog.json`。

