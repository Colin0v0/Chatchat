import unittest
from types import SimpleNamespace

from app.retrieval.rag.embedder import OpenAICompatibleEmbedder, build_knowledge_embedder


def make_settings():
    return SimpleNamespace(
        knowledge_embedding_batch_size=8,
        knowledge_embedding_provider="dashscope",
        knowledge_embedding_base_url="",
        knowledge_embedding_api_key="",
        knowledge_embedding_dimensions=1024,
        knowledge_embedding_timeout_seconds=30.0,
        dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        dashscope_api_key="",
    )


class EmbedderFactoryTests(unittest.TestCase):
    def test_factory_uses_openai_compatible_embedder_for_dashscope_provider(self):
        settings = make_settings()
        settings.knowledge_embedding_api_key = "test-key"

        embedder = build_knowledge_embedder(settings, "text-embedding-v4")

        self.assertIsInstance(embedder, OpenAICompatibleEmbedder)
        self.assertEqual(
            embedder._request_payload(["hello"]),
            {
                "model": "text-embedding-v4",
                "input": ["hello"],
                "dimensions": 1024,
            },
        )

    def test_factory_rejects_local_embedding_provider(self):
        settings = make_settings()
        settings.knowledge_embedding_provider = "local"

        with self.assertRaisesRegex(RuntimeError, "only supports API providers"):
            build_knowledge_embedder(settings, "../models/Qwen3-Embedding-0.6B")

    def test_openai_compatible_embedder_validates_embedding_dimensions(self):
        settings = make_settings()
        settings.knowledge_embedding_api_key = "test-key"
        embedder = OpenAICompatibleEmbedder(settings, "text-embedding-v4")

        vectors = embedder._parse_embeddings(
            {"data": [{"index": 0, "embedding": [0.1] * 1024}]}
        )

        self.assertEqual(len(vectors), 1)
        self.assertEqual(len(vectors[0]), 1024)

    def test_openai_compatible_embedder_delays_missing_key_error_until_request(self):
        settings = make_settings()
        embedder = OpenAICompatibleEmbedder(settings, "text-embedding-v4")

        with self.assertRaisesRegex(RuntimeError, "DASHSCOPE_API_KEY"):
            embedder._headers()


if __name__ == "__main__":
    unittest.main()
