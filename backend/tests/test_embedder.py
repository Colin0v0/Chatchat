import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.retrieval.rag.embedder import LocalModelEmbedder, build_knowledge_embedder


def make_settings():
    return SimpleNamespace(
        knowledge_embedding_batch_size=8,
        knowledge_embedding_max_length=1024,
        knowledge_embedding_device="cpu",
        local_model_idle_timeout_seconds=60.0,
    )


class EmbedderFactoryTests(unittest.TestCase):
    def test_factory_uses_local_model_for_relative_paths(self):
        embedder = build_knowledge_embedder(make_settings(), "../models/Qwen3-Embedding-0.6B")
        self.assertIsInstance(embedder, LocalModelEmbedder)

    def test_factory_uses_local_model_for_plain_model_names(self):
        embedder = build_knowledge_embedder(make_settings(), "qwen3-embedding:0.6b")
        self.assertIsInstance(embedder, LocalModelEmbedder)

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
