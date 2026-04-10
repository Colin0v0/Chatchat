import unittest

from app.core.config import Settings
from app.retrieval.rag.model_reranker import ModelReranker


def _build_settings(**overrides) -> Settings:
    values = {"knowledge_rerank_model": "codex:gpt-5.2"}
    values.update(overrides)
    return Settings(_env_file=(), **values)


class ModelRerankerPayloadTests(unittest.TestCase):
    def test_codex_reranker_payload_uses_responses_reasoning_controls(self):
        reranker = ModelReranker(_build_settings(knowledge_rerank_model="codex:gpt-5.2"), rerank_window=2)

        payload = reranker._build_codex_payload("query")

        self.assertEqual(payload["reasoning"], {"effort": "none"})
        self.assertIn("input", payload)

    def test_openai_local_reranker_payload_disables_thinking_with_local_flag(self):
        reranker = ModelReranker(
            _build_settings(knowledge_rerank_model="openai_local:claude-haiku-4-5"),
            rerank_window=2,
        )

        payload = reranker._build_openai_payload("query")

        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertNotIn("reasoning_effort", payload)

    def test_openai_reranker_payload_does_not_add_reasoning_controls(self):
        reranker = ModelReranker(_build_settings(knowledge_rerank_model="openai:gpt-4.1"), rerank_window=2)

        payload = reranker._build_openai_payload("query")

        self.assertNotIn("thinking", payload)
        self.assertNotIn("reasoning_effort", payload)


if __name__ == "__main__":
    unittest.main()
