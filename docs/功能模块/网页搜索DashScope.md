# 网页搜索 DashScope

更新时间：2026-04-27

## 1. 当前实现

网页搜索当前使用 DashScope 原生 Generation API 的联网搜索能力。

不用 OpenAI-compatible `enable_search`，因为 OpenAI-compatible 协议不返回可展示来源和角标引用，无法满足当前链路：

- sources 展示
- dedupe
- filter
- rerank
- context 注入

## 2. 请求形状

后端请求 DashScope 原生 endpoint：

```text
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation
```

核心参数：

```json
{
  "model": "qwen-plus",
  "input": {
    "messages": [
      {
        "role": "user",
        "content": "请联网搜索..."
      }
    ]
  },
  "parameters": {
    "result_format": "message",
    "enable_search": true,
    "search_options": {
      "enable_source": true,
      "enable_citation": true,
      "forced_search": true,
      "search_strategy": "turbo",
      "citation_format": "[ref_<number>]"
    }
  }
}
```

## 3. 响应解析

后端读取：

```text
output.search_info.search_results
```

并映射到内部：

```text
WebSearchResult
  title
  url
  domain
  excerpt
  content
  provider_score
  published_at
```

如果来源本身没有 snippet，后端会从模型回答文本里按 `[ref_1]` 这类角标抽取对应句子作为 excerpt。

## 4. 后端链路

```text
user query
  -> parse_web_query
  -> classify_web_intent
  -> translate_query_for_search
  -> rewrite_web_query
  -> DashScopeWebSearchProvider
  -> dedupe_results
  -> filter_results
  -> WebLexicalReranker
  -> top_k / min_score
  -> SourceItem(type=web)
  -> ContextEntry
```

关键文件：

- `backend/app/retrieval/websearch/providers/dashscope.py`
- `backend/app/retrieval/websearch/service.py`
- `backend/app/retrieval/websearch/planner.py`
- `backend/app/retrieval/websearch/translator.py`
- `backend/app/retrieval/websearch/filter.py`
- `backend/app/retrieval/websearch/reranker.py`

## 5. 配置

```env
WEB_SEARCH_PROVIDER=dashscope
WEB_SEARCH_BASE_URL=https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation
WEB_SEARCH_API_KEY=
WEB_SEARCH_MODEL=qwen-plus
WEB_SEARCH_STRATEGY=turbo
WEB_SEARCH_FORCED=true
WEB_SEARCH_ENABLE_SOURCE=true
WEB_SEARCH_ENABLE_CITATION=true
WEB_SEARCH_CITATION_FORMAT=[ref_<number>]
WEB_SEARCH_MAX_RESULTS=5
WEB_SEARCH_TOP_K=4
WEB_SEARCH_MIN_SCORE=0.2
WEB_SEARCH_CONTENT_MAX_CHARS=1600
WEB_SEARCH_TRANSLATION_MODEL=codex:gpt-5.2
```

`WEB_SEARCH_API_KEY` 留空时复用 `DASHSCOPE_API_KEY`。

## 6. 搜索策略

`WEB_SEARCH_STRATEGY` 当前建议：

- `turbo`
  - 默认，速度和成本更稳。
- `max`
  - 更深搜索，适合以后做深度研究模式。

当前默认不启用网页抓取，因为网页抓取延迟、成本和模型限制都更高。

## 7. 配置错误和 404 排查

如果搜索报 404，优先检查：

- 后端是否已重启。
- `WEB_SEARCH_BASE_URL` 是否是 DashScope 原生 endpoint。
- 是否误用了 `DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1` 当 web search endpoint。

当前代码会把 `compatible-mode/v1` 自动归一化为原生 Generation endpoint。

## 8. 当前边界

- DashScope search_results 主要是结构化来源，不一定提供完整网页正文。
- 目前通过角标句子补 excerpt，够用于来源展示和轻量上下文。
- 后续如需长正文，可单独接网页抓取服务，但不建议作为默认搜索链路。

