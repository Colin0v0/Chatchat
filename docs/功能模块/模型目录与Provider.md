# 模型目录与 Provider

更新时间：2026-04-27

## 1. 模型目录

当前模型主要由 `backend/model_catalog.json` 管理，不建议在业务代码里散落硬编码。

模型目录描述：

- 模型 ID
- provider family
- chat endpoint
- file endpoint
- display name
- 输入能力
- reasoning 能力
- 原生多模态能力
- 默认 reasoning profile

关键文件：

- `backend/model_catalog.json`
- `backend/app/providers/catalog.py`
- `backend/app/providers/registry.py`

## 2. Provider Family

后端按 provider family 归一化模型调用：

- OpenAI-compatible family
- Anthropic/Claude family
- Gemini family
- 其他兼容 family

当前 DeepSeek 使用 OpenAI-compatible transport，但配置来源是：

```env
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=
```

## 3. Provider Transport

真实上游 HTTP 调用在：

- `backend/app/provider_transports/openai.py`
- `backend/app/provider_transports/anthropic.py`
- `backend/app/provider_transports/gemini.py`
- `backend/app/provider_transports/openai_images.py`

Transport 负责：

- 构造请求
- 注入 API Key
- 处理超时
- 流式读取
- 转换上游错误

## 4. Provider Codec

Codec 负责把内部消息和参数变成 provider 请求 payload，也负责解析流式 chunk。

关键目录：

- `backend/app/provider_codecs/`

这样 runtime 不需要知道每个供应商的细节。

## 5. Reasoning Profile

统一 reasoning profile：

- `off`
- `auto`
- `low`
- `medium`
- `high`
- `max`
- `provider_default`

模型目录会声明支持哪些 profile。前端据此展示 reasoning 强度选择器。

不同 provider 的映射不同：

- OpenAI-compatible 可能映射为 effort。
- Claude/Gemini 可能映射为各自原生参数。
- 不支持 reasoning 的模型不展示相关控制。

## 6. 多模态能力声明

模型目录里的 `native_multimodal` 控制附件链路：

- `false`
  - 不发送原生多模态输入。
- `codex`
  - 图片走 Codex/GPT 原生多模态。
- `gemini`
  - 图片和支持文档走 Gemini 原生协议。
- `claude`
  - 图片和支持文档走 Claude 原生协议。

输入开关：

- `capabilities.input.image`
- `capabilities.input.pdf`
- `capabilities.input.document`

当前 DeepSeek 默认禁用图片上传。

## 7. 当前部署口径

当前建议：

- DeepSeek 负责聊天。
- DashScope 不作为聊天 provider 出现在模型列表里。
- DashScope 负责 embedding、rerank、web search、ASR、TTS。
- 不需要 OpenAI API Key。
- OpenAI-compatible fallback 作为通用能力保留，但当前部署不依赖它。

