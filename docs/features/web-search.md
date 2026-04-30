# 网页搜索

更新时间：2026-04-30

网页搜索是可选检索能力，用于在回答前补充外部来源。该模块不绑定具体搜索供应商，后端通过 provider 适配层把外部搜索结果转换成统一结构。

## 1. 目标

网页搜索链路需要提供：

- 可展示来源。
- 可去重结果。
- 可过滤低质量结果。
- 可参与 rerank。
- 可注入模型上下文。

因此 provider 应尽量返回结构化来源，而不是只返回一段无来源的模型文本。

## 2. 内部结果结构

搜索 provider 输出会归一化为：

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

后续链路会把结果转换为：

- `SourceItem(type=web)`
- `ContextEntry`

## 3. 后端链路

```text
user query
  -> parse_web_query
  -> classify_web_intent
  -> translate_query_for_search
  -> rewrite_web_query
  -> WebSearchProvider
  -> dedupe_results
  -> filter_results
  -> lexical rerank
  -> top_k / min_score
  -> source + context payload
```

关键文件：

- `backend/app/retrieval/websearch/service.py`
- `backend/app/retrieval/websearch/planner.py`
- `backend/app/retrieval/websearch/translator.py`
- `backend/app/retrieval/websearch/filter.py`
- `backend/app/retrieval/websearch/reranker.py`
- `backend/app/retrieval/websearch/providers/`

## 4. 配置

```env
WEB_SEARCH_PROVIDER=
WEB_SEARCH_BASE_URL=
WEB_SEARCH_API_KEY=
WEB_SEARCH_MODEL=
WEB_SEARCH_MAX_RESULTS=5
WEB_SEARCH_TOP_K=4
WEB_SEARCH_MIN_SCORE=0.2
WEB_SEARCH_CONTENT_MAX_CHARS=1600
WEB_SEARCH_TRANSLATION_MODEL=
```

provider 相关的额外参数应由具体 provider 读取和解释。公共链路只依赖归一化后的结果结构。

## 5. 边界

- 网页搜索只在用户开启搜索工具或对应策略命中时运行。
- 搜索结果不替代模型回答，只作为上下文和来源。
- 长正文抓取不是默认能力，可以通过独立 provider 扩展。
- 未配置 provider 时，应返回明确不可用状态。
