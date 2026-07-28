# Chatchat

简体中文 | [English](README.md)

Chatchat 是一个面向个人与团队的自托管 AI 工作台，将多模型聊天、私有知识库检索、多模态附件、语音能力、记忆管理和按用户隔离的数据管理整合在一个 Web 应用中。

## 功能特性

- 通过可配置的 Provider 和模型目录接入多种聊天模型。
- 流式输出文本、推理内容、来源与上下文事件。
- 私有知识库支持向量检索、重排和查询改写。
- 可选网页搜索，并将引用来源纳入对话上下文。
- 支持图片、文档附件、语音转写和文本朗读。
- 支持全局、会话、工作、候选和文档记忆。
- 账号、会话、知识库、记忆和设置均按用户隔离。

## 项目结构

```text
Chatchat/
  backend/      FastAPI、SQLAlchemy 与模型编排后端
  dev/          本地开发和构建辅助文件
  frontend/     React、Vite 与 TypeScript 工作台
  docs/         架构、功能、配置和部署文档
  storage/      运行时用户数据（已被 Git 忽略）
```

## 快速开始

环境要求：Python、Node.js 与 pnpm、Docker、Docker Compose、PostgreSQL、Redis。

```bash
# 启动本地开发所需的 PostgreSQL 与 Redis。
docker compose -f dev/docker-compose.dev-infra.yml up -d

# 创建本地后端配置。这个文件绝不能提交。
cp backend/.env.example backend/.env

# 启动后端。
cd backend
python app.py --reload --host 127.0.0.1 --port 8050
```

在另一个终端启动前端：

```bash
cd frontend
pnpm install
pnpm dev
```

请编辑 `backend/.env`，配置至少一个模型提供方，并设置 `DEFAULT_PROVIDER` 和 `DEFAULT_MODEL`。更多说明见[本地开发文档](dev/README.md)。

## 配置与隐私

- `backend/.env` 保存本地配置和 API Key，已被 Git 忽略。
- `storage/` 保存上传文件、生成媒体和知识库源文件等运行数据，已被 Git 忽略。
- `backend/.env.example` 只包含安全的占位配置，可作为配置模板。
- 对外部署时，请设置强密码；在 HTTPS 环境中将 `AUTH_COOKIE_SECURE=true`；并将 `CORS_ALLOWED_ORIGINS` 限制为你的前端域名。

## 文档导航

- [文档索引](docs/README.md)
- [系统架构](docs/architecture.md)
- [配置说明](docs/configuration.md)
- [部署指南](docs/deployment.md)
- [开发说明](docs/development.md)

## 开发

运行后端测试：

```bash
PYTHONPATH=backend python -m pytest backend/tests
```

构建前端：

```bash
cd frontend
pnpm build
```

## 参与贡献

欢迎贡献代码、文档和问题反馈。提交前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，安全问题请按 [SECURITY.md](SECURITY.md) 处理。

## 许可证

Chatchat 使用 [MIT License](LICENSE) 开源。
