# 模型目录与 Provider

更新时间：2026-04-30

## 1. 模型目录

模型主要由 `backend/model_catalog.json` 管理，业务代码不直接硬编码模型能力。

模型目录描述：

- 模型 ID。
- provider 引用。
- 上游模型名。
- display name。
- 输入能力。
- reasoning 能力。
- 原生多模态能力。
- 默认 reasoning profile。
- 是否启用。

关键文件：

- `backend/model_catalog.json`
- `backend/app/providers/catalog.py`
- `backend/app/providers/registry.py`

## 2. Provider Family

后端按 provider family 归一化模型调用：

- OpenAI-compatible family。
- Anthropic-compatible family。
- Gemini-compatible family。
- 其他兼容 family。

新增 provider 时，应同时补充：

- transport。
- codec。
- registry。
- model catalog 条目。

## 3. Provider Transport

真实上游 HTTP 调用在：

- `backend/app/provider_transports/`

Transport 负责：

- 构造请求。
- 注入 API key。
- 处理超时。
- 流式读取。
- 转换上游错误。

## 4. Provider Codec

Codec 负责把内部消息和参数转换成 provider 请求 payload，也负责解析流式 chunk。

关键目录：

- `backend/app/provider_codecs/`

runtime 只处理统一的内部消息、事件和参数，不直接依赖具体 provider payload。

## 5. Reasoning Profile

统一 reasoning profile：

- `off`
- `auto`
- `low`
- `medium`
- `high`
- `max`
- `provider_default`

模型目录声明支持哪些 profile。前端据此展示 reasoning 强度选择器。

不同 provider 的映射由 codec 或 transport 处理。

## 6. 多模态能力声明

模型目录中的能力字段控制附件入口：

- `capabilities.input.image`
- `capabilities.input.pdf`
- `capabilities.input.document`

`native_multimodal` 控制后端是否把附件作为 provider 原生多模态输入发送。未声明支持的输入类型应在前端和后端同时拦截。

## 7. 边界

- 模型是否可用以模型目录和 provider 配置为准。
- 前端展示能力不应超过后端校验能力。
- provider 失败应转换为统一错误结构。
- 可选 provider 未配置时，对应模型不应作为默认模型。
