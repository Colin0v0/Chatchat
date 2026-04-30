import unittest

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.memory.store import MemoryStore
from app.memory.types import MemoryCandidate
from app.storage.database import Base
from app.storage.models import MemoryItem, User


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE VIRTUAL TABLE memory_search
                    USING fts5(memory_id UNINDEXED, content, tokenize='unicode61')
                    """
                )
            )
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db: Session = self.session_factory()
        self.store = MemoryStore(self.db)
        self.user = User(username="tester", password_hash="hash", is_active=True)
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_merge_candidates_collapses_similar_global_memory(self):
        existing = self.store.create_manual_memory(
            user_id=self.user.id,
            scope="global",
            kind="profile",
            title="姓名",
            detail="用户叫杜宇",
            tags=["个人"],
            confidence=0.9,
            pinned=False,
            active=True,
            conversation_id=None,
        )
        self.db.commit()

        merged = self.store.merge_candidates(
            candidates=[
                MemoryCandidate(
                    scope="global",
                    kind="profile",
                    title="User Name",
                    detail="User's name is 杜宇",
                    tags=("personal",),
                    confidence=1.0,
                )
            ],
            user_id=self.user.id,
            conversation_id=12,
            user_message_id=101,
            assistant_message_id=102,
        )
        self.db.commit()

        items = self.db.scalars(select(MemoryItem)).all()
        self.assertEqual(len(items), 1)
        self.assertEqual(merged[0].id, existing.id)
        self.assertEqual(items[0].title, "姓名")
        self.assertEqual(items[0].detail, "用户叫杜宇")
        self.assertIn("personal", items[0].tags)

    def test_merge_candidates_demotes_transient_global_memory_to_working(self):
        merged = self.store.merge_candidates(
            candidates=[
                MemoryCandidate(
                    scope="global",
                    kind="project",
                    title="当前项目是记忆系统重构",
                    detail="这次先解决全局重复问题",
                    tags=("记忆",),
                    confidence=0.85,
                )
            ],
            user_id=self.user.id,
            conversation_id=7,
            user_message_id=201,
            assistant_message_id=202,
        )
        self.db.commit()

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].scope, "working")
        self.assertEqual(merged[0].conversation_id, 7)
        self.assertEqual(merged[0].write_policy, "session")
        self.assertIsNotNone(merged[0].expires_at)

    def test_recall_uses_database_ranked_search_when_not_using_sqlite_fts(self):
        item = self.store.create_manual_memory(
            user_id=self.user.id,
            scope="conversation",
            kind="project",
            title="KPI 重构方案",
            detail="当前正在推进 PostgreSQL memory 检索改造",
            tags=["kpi", "postgres"],
            confidence=0.9,
            pinned=False,
            active=True,
            conversation_id=42,
        )
        self.store.create_manual_memory(
            user_id=self.user.id,
            scope="conversation",
            kind="fact",
            title="天气",
            detail="今天下雨",
            tags=["daily"],
            confidence=0.6,
            pinned=False,
            active=True,
            conversation_id=42,
        )
        self.db.commit()

        self.store._uses_sqlite_memory_search = lambda: False  # type: ignore[method-assign]

        matches = self.store.recall(
            query="PostgreSQL KPI 改造",
            user_id=self.user.id,
            conversation_id=42,
            limit=4,
        )

        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0].memory_id, item.id)
        self.assertGreater(matches[0].score, 0.0)


if __name__ == "__main__":
    unittest.main()
