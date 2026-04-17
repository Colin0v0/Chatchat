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
        self.assertEqual(payload["max_output_tokens"], 64)
        self.assertEqual(payload["text"], {"format": {"type": "json_object"}})

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

    def test_trio_reranker_payload_uses_openai_compatible_flow(self):
        reranker = ModelReranker(_build_settings(knowledge_rerank_model="trio:your-model-path"), rerank_window=2)

        payload = reranker._build_openai_payload("query")

        self.assertEqual(reranker._provider, "trio")
        self.assertNotIn("thinking", payload)
        self.assertNotIn("reasoning_effort", payload)
        self.assertEqual(reranker._request_gate(), ("trio", 1))

    def test_extract_codex_content_falls_back_to_output_text(self):
        reranker = ModelReranker(_build_settings(knowledge_rerank_model="codex:gpt-5.2"), rerank_window=2)
        payload = {
            "output": [],
            "output_text": '{"score": 0.73}',
        }
        self.assertEqual(reranker._extract_codex_content(payload), '{"score": 0.73}')

    def test_parse_score_accepts_serialized_payload_fallback(self):
        reranker = ModelReranker(_build_settings(knowledge_rerank_model="codex:gpt-5.2"), rerank_window=2)
        self.assertAlmostEqual(
            reranker._parse_score('{"output":[{"content":[{"text":"{\\"score\\":0.41}"}]}]}'),
            0.41,
        )


if __name__ == "__main__":
    unittest.main()
