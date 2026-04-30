# 认证与用户隔离

更新时间：2026-04-27

## 1. 功能范围

当前认证系统提供：

- 用户名密码登录。
- Cookie Session。
- 查询当前登录态。
- 退出登录。
- 修改密码。
- 多用户数据隔离。

当前不提供公开注册页。

## 2. 后端 API

```text
POST   /api/auth/login
POST   /api/auth/logout
GET    /api/auth/session
PATCH  /api/auth/password
```

关键文件：

- `backend/app/api/auth.py`
- `backend/app/auth/`
- `backend/app/storage/models.py`

## 3. Session

登录成功后：

1. 验证用户名密码。
2. 创建 `user_sessions`。
3. 写入 Cookie。
4. 前端后续请求带 `credentials: include`。

Cookie 配置：

```env
AUTH_SESSION_COOKIE_NAME=chatchat_session
AUTH_SESSION_TTL_HOURS=168
AUTH_COOKIE_SECURE=false
```

生产 HTTPS 环境建议开启 `AUTH_COOKIE_SECURE=true`。

## 4. 用户隔离

所有主要资源都绑定 `user_id`：

- conversations
- messages
- message attachments
- knowledge documents
- knowledge folders
- memory items
- debate sessions
- provider file refs

后端通过 `require_current_user` 注入当前用户，并在查询中带 `user_id` 过滤。

## 5. 前端入口

关键文件：

- `frontend/src/features/auth/`
- `frontend/src/App.tsx`
- `frontend/src/shared/api/http.ts`

前端会在 401 时触发未登录处理。

## 6. 当前边界

- 不支持公开注册。
- 不支持 OAuth。
- 不支持多租户组织结构。
- 用户创建通常通过脚本或数据库初始化完成。

