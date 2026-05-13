import unittest

from app.core.config import Settings
from app.retrieval.rag.model_reranker import ModelReranker
from app.retrieval.rag.types import RagChunk, RetrievalCandidate


def _build_settings(**overrides) -> Settings:
    values = {
        "knowledge_rerank_provider": "dashscope",
        "knowledge_rerank_model": "gte-rerank-v2",
        "dashscope_api_key": "test-key",
    }
    values.update(overrides)
    return Settings(_env_file=(), **values)


def _candidate(*, content: str, path: str = "notes.md", heading: str = "Intro") -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk=RagChunk(
            id="chunk-1",
            path=path,
            directory="",
            heading=heading,
            content=content,
            order=1,
            embedding=[],
        ),
        vector_score=0.4,
        keyword_score=0.3,
        hybrid_score=0.5,
    )


class ModelRerankerPayloadTests(unittest.TestCase):
    def test_dashscope_reranker_payload_uses_text_rerank_shape(self):
        reranker = ModelReranker(_build_settings(), rerank_window=2)

        payload = reranker._build_dashscope_rerank_payload(
            query="怎么部署",
            candidates=[
                _candidate(content="部署到 CPU 服务器。"),
                _candidate(content="无关内容", path="other.md", heading="Misc"),
            ],
        )

        self.assertEqual(payload["model"], "gte-rerank-v2")
        self.assertEqual(payload["input"]["query"], "怎么部署")
        self.assertEqual(
            payload["input"]["documents"],
            ["notes.md | Intro\n部署到 CPU 服务器。", "other.md | Misc\n无关内容"],
        )
        self.assertEqual(payload["parameters"], {"return_documents": False, "top_n": 2})

    def test_dashscope_model_prefix_is_supported(self):
        reranker = ModelReranker(_build_settings(knowledge_rerank_model="dashscope:gte-rerank-v2"), rerank_window=2)

        self.assertEqual(reranker._provider, "dashscope")
        self.assertEqual(reranker._upstream_model, "gte-rerank-v2")
        self.assertTrue(reranker.enabled)

    def test_non_dashscope_provider_is_disabled(self):
        reranker = ModelReranker(
            _build_settings(
                knowledge_rerank_provider="openai",
                knowledge_rerank_model="openai:gpt-4.1",
            ),
            rerank_window=2,
        )

        self.assertFalse(reranker.enabled)
        self.assertEqual(reranker.disabled_reason, "unsupported_provider")

    def test_legacy_chat_model_id_is_disabled(self):
        reranker = ModelReranker(
            _build_settings(knowledge_rerank_model="openai:deepseek-v4-flash"),
            rerank_window=2,
        )

        self.assertFalse(reranker.enabled)
        self.assertEqual(reranker.disabled_reason, "unsupported_model_provider")

    def test_missing_dashscope_key_disables_reranker(self):
        reranker = ModelReranker(
            _build_settings(dashscope_api_key="", knowledge_rerank_api_key=""),
            rerank_window=2,
        )

        self.assertFalse(reranker.enabled)
        self.assertEqual(reranker.disabled_reason, "dashscope_api_key_missing")

    def test_dashscope_reranker_parse_maps_scores_by_index(self):
        reranker = ModelReranker(_build_settings(), rerank_window=2)

        scores = reranker._parse_dashscope_rerank_scores(
            {
                "output": {
                    "results": [
                        {"index": 1, "relevance_score": 1.2},
                        {"index": 0, "score": "0.41"},
                    ]
                }
            },
            expected_count=3,
        )

        self.assertEqual(scores, [0.41, 1.0, 0.0])


if __name__ == "__main__":
    unittest.main()
