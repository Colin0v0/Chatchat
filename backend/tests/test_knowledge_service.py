import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import UploadFile
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.knowledge.service import KnowledgeService
from app.retrieval.rag.types import RagChunk
from app.storage.database import Base
from app.storage.models import KnowledgeChunk, KnowledgeDocument, User


class _FakeEmbedder:
    def __init__(self, settings, model_name):
        self.model_name = model_name

    async def embed_chunk_specs(self, chunk_specs):
        return (
            [
                RagChunk(
                    id=spec.id,
                    path=spec.path,
                    directory=spec.directory,
                    heading=spec.heading,
                    content=spec.content,
                    order=spec.order,
                    embedding=[0.1, 0.2, 0.3],
                    tags=list(spec.tags),
                )
                for spec in chunk_specs
            ],
            [],
        )

    async def embed_query(self, query):
        return [0.1, 0.2, 0.3]


class _FakeReranker:
    def __init__(self, settings, rerank_window):
        self.rerank_window = rerank_window

    def rerank(self, query, candidates):
        return candidates


def make_settings(storage_root: str):
    return SimpleNamespace(
        knowledge_storage_root=storage_root,
        knowledge_max_file_size_bytes=2 * 1024 * 1024,
        knowledge_max_documents_per_user=100,
        knowledge_max_total_size_bytes=100 * 1024 * 1024,
        knowledge_top_k=4,
        knowledge_section_max_chars=1400,
        knowledge_candidate_limit=12,
        knowledge_rerank_window=12,
        knowledge_neighbor_window=1,
        knowledge_min_score=0.22,
        knowledge_embedding_model="qwen3-embedding:0.6b",
        knowledge_rerank_model="dengcao/Qwen3-Reranker-0.6B:Q8_0",
    )


class KnowledgeServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db: Session = self.session_factory()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    async def test_reindex_document_replaces_existing_chunks_without_deleted_instance_error(self):
        user = User(username="alice", password_hash="hash", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        document = KnowledgeDocument(
            user_id=user.id,
            title="notes.md",
            mime_type="text/markdown",
            extension=".md",
            size_bytes=32,
            relative_path=f"{user.id}/1.md",
            sha1="abc123",
            status="ready",
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        self.db.add(
            KnowledgeChunk(
                document_id=document.id,
                user_id=user.id,
                chunk_key="legacy",
                chunk_index=0,
                path="notes.md",
                directory="",
                heading="Old",
                content="old content",
                token_count=2,
                tags_json="[]",
                embedding_json="[0.9]",
            )
        )
        self.db.commit()

        file_path = Path(self.temp_dir.name) / f"{user.id}" / "1.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("# Title\n\n## Section\n\nnew content", encoding="utf-8")

        settings = make_settings(self.temp_dir.name)
        with patch("app.knowledge.service.OllamaEmbedder", _FakeEmbedder), patch(
            "app.knowledge.service.OllamaModelReranker", _FakeReranker
        ):
            service = KnowledgeService(settings)
            indexed = await service.reindex_document(
                db=self.db,
                user_id=user.id,
                document_id=document.id,
            )

        self.assertIsNotNone(indexed)
        self.assertEqual(indexed.status, "ready")
        chunk_keys = list(
            self.db.scalars(
                select(KnowledgeChunk.chunk_key).where(KnowledgeChunk.document_id == document.id)
            ).all()
        )
        self.assertNotIn("legacy", chunk_keys)
        self.assertGreater(len(chunk_keys), 0)

    async def test_batch_upload_and_delete_documents(self):
        user = User(username="bob", password_hash="hash", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        settings = make_settings(self.temp_dir.name)
        with patch("app.knowledge.service.OllamaEmbedder", _FakeEmbedder), patch(
            "app.knowledge.service.OllamaModelReranker", _FakeReranker
        ):
            service = KnowledgeService(settings)
            documents = await service.create_documents(
                db=self.db,
                user_id=user.id,
                uploads=[
                    UploadFile(filename="a.md", file=BytesIO(b"# A\n\nhello"), headers=None),
                    UploadFile(filename="b.md", file=BytesIO(b"# B\n\nworld"), headers=None),
                ],
            )

            self.assertEqual(len(documents), 2)
            self.assertEqual(
                list(self.db.scalars(select(KnowledgeDocument.title).order_by(KnowledgeDocument.id.asc())).all()),
                ["a.md", "b.md"],
            )

            deleted_ids, deleted_paths = service.delete_documents(
                db=self.db,
                user_id=user.id,
                document_ids=[documents[0].id, documents[1].id],
            )

            self.assertEqual(deleted_ids, [documents[0].id, documents[1].id])
            self.assertEqual(len(deleted_paths), 2)
            self.assertEqual(self.db.scalar(select(func.count(KnowledgeDocument.id))), 0)


if __name__ == "__main__":
    unittest.main()
