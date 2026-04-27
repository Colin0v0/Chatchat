import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.retrieval.rag.embedder import (
    LocalModelEmbedder,
    OpenAICompatibleEmbedder,
    build_knowledge_embedder,
)


def make_settings():
    return SimpleNamespace(
        knowledge_embedding_batch_size=8,
        knowledge_embedding_provider="local",
        knowledge_embedding_base_url="",
        knowledge_embedding_api_key="",
        knowledge_embedding_dimensions=1024,
        knowledge_embedding_timeout_seconds=30.0,
        knowledge_embedding_max_length=1024,
        knowledge_embedding_device="cpu",
        local_model_idle_timeout_seconds=60.0,
        dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        dashscope_api_key="",
    )


class EmbedderFactoryTests(unittest.TestCase):
    def test_factory_uses_local_model_for_relative_paths(self):
        embedder = build_knowledge_embedder(make_settings(), "../models/Qwen3-Embedding-0.6B")
        self.assertIsInstance(embedder, LocalModelEmbedder)

    def test_factory_uses_local_model_for_plain_model_names(self):
        embedder = build_knowledge_embedder(make_settings(), "qwen3-embedding:0.6b")
        self.assertIsInstance(embedder, LocalModelEmbedder)

    def test_factory_uses_openai_compatible_embedder_for_api_provider(self):
        settings = make_settings()
        settings.knowledge_embedding_provider = "dashscope"
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

    def test_openai_compatible_embedder_validates_embedding_dimensions(self):
        settings = make_settings()
        settings.knowledge_embedding_provider = "api"
        settings.knowledge_embedding_api_key = "test-key"
        embedder = OpenAICompatibleEmbedder(settings, "text-embedding-v4")

        vectors = embedder._parse_embeddings(
            {"data": [{"index": 0, "embedding": [0.1] * 1024}]}
        )

        self.assertEqual(len(vectors), 1)
        self.assertEqual(len(vectors[0]), 1024)

    def test_openai_compatible_embedder_delays_missing_key_error_until_request(self):
        settings = make_settings()
        settings.knowledge_embedding_provider = "api"
        embedder = OpenAICompatibleEmbedder(settings, "text-embedding-v4")

        with self.assertRaisesRegex(RuntimeError, "DASHSCOPE_API_KEY"):
            embedder._headers()

    def test_local_embedder_resolves_relative_model_paths_from_backend_dir(self):
        settings = make_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            backend_dir = Path(temp_dir) / "backend"
            model_dir = Path(temp_dir) / "models" / "Qwen3-Embedding-0.6B"
            model_dir.mkdir(parents=True, exist_ok=True)
            with patch("app.retrieval.rag.embedder.BACKEND_DIR", backend_dir):
                embedder = LocalModelEmbedder(settings, "../models/Qwen3-Embedding-0.6B")
                self.assertEqual(
                    embedder._resolve_model_path(),
                    str(model_dir.resolve()),
                )

    def test_local_embedder_resolves_alias_from_models_dir(self):
        settings = make_settings()
        with tempfile.TemporaryDirectory() as temp_dir:
            backend_dir = Path(temp_dir) / "backend"
            models_dir = Path(temp_dir) / "models"
            model_dir = models_dir / "Qwen3-Embedding-0___6B"
            model_dir.mkdir(parents=True, exist_ok=True)
            with patch("app.retrieval.rag.embedder.BACKEND_DIR", backend_dir), patch(
                "app.retrieval.rag.embedder.MODELS_DIR",
                models_dir,
            ):
                embedder = LocalModelEmbedder(settings, "qwen3-embedding:0.6b")
                self.assertEqual(embedder._resolve_model_path(), str(model_dir.resolve()))


if __name__ == "__main__":
    unittest.main()
