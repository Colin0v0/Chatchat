# Chatchat

Chatchat 是一个自托管的 AI 聊天工作台，提供多模型聊天、知识库检索、多模态附件、语音能力、记忆管理和多用户隔离。

项目目标是把常见的个人/团队 AI 工作流收敛到一个清晰的 Web 应用里：前端负责工作台体验，后端负责模型编排、上下文构建、检索、记忆和数据持久化。

## 功能特性

- 多模型会话：通过模型目录接入不同的聊天模型提供方。
- 流式响应：统一输出状态、文本、推理内容、来源、上下文和完成事件。
- 知识库检索：支持用户私有知识库、向量检索、重排和查询改写。
- 网页搜索：可选外部搜索提供方，并把来源纳入回答上下文。
- 多模态附件：支持图片和常见文档类型，按模型能力选择原生输入或文本解析。
- 记忆系统：支持全局、会话、工作、候选记忆和记忆文档。
- 语音能力：支持语音转写和文本朗读，可接入浏览器或外部语音提供方。
- 多用户隔离：账号、会话、知识库、记忆和设置都按用户隔离。
- 可观测运行链路：保存消息、推理内容、来源和上下文组成信息。

## 架构概览

```text
Chatchat/
  backend/      FastAPI + SQLAlchemy 后端与运行时编排
  dev/          本地开发与部署示例
  frontend/     React + Vite + TypeScript 前端
  docs/         架构、功能模块与部署文档
  storage/      上传文件、生成媒体与知识库源文件
```

核心后端链路：

```text
请求
  -> 鉴权 / 会话
  -> 会话与消息持久化
  -> 历史 / 记忆 / 检索上下文
  -> 模型运行时
  -> 流式事件
  -> assistant 消息持久化
  -> 异步记忆刷新
```

## 快速开始

本地开发细节见 [dev/README.md](dev/README.md)。

启动开发数据库和缓存：

```bash
docker compose -f dev/docker-compose.dev-infra.yml up -d
```

启动后端：

```bash
cd backend
python app.py
```

启动前端：

```bash
cd frontend
pnpm install
pnpm dev
```

默认前端开发服务由 Vite 提供，后端服务由 FastAPI 提供。首次接入模型前，需要在后端环境变量和 `backend/model_catalog.json` 中配置可用模型提供方。

## 配置说明

常用配置入口：

- `backend/.env`：后端运行配置。
- `backend/model_catalog.json`：模型目录、提供方映射和能力声明。
- `dev/docker-compose.dev-infra.yml`：本地开发数据库和缓存。
- `docker-compose.yml`：部署编排示例。

后端至少需要配置：

- 数据库连接。
- 缓存连接。
- 默认模型。
- 至少一个可用模型提供方。

知识库、网页搜索、语音、图片生成等能力可以按需配置。未配置的能力应在 UI 或后端返回明确不可用状态。

## 文档导航

- [文档索引](docs/README.md)
- [系统架构](docs/architecture.md)
- [配置说明](docs/configuration.md)
- [部署指南](docs/deployment.md)
- [开发说明](docs/development.md)

## 开发

本地开发流程：

- [dev/README.md](dev/README.md)

后端测试：

```bash
PYTHONPATH=backend python -m pytest backend/tests
```

前端构建：

```bash
cd frontend
pnpm build
```

## 设计原则

- 模型接入通过提供方和模型目录隔离。
- 上下文构建由 history、memory、retrieval、tool context 分层组成。
- 用户数据默认按账号隔离。
- 外部能力通过显式配置启用。
- 错误应清晰暴露，不用隐式替代路径掩盖配置问题。
