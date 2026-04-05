import unittest

from app.retrieval.file_context import ConversationFileContextService
from app.storage.models import Message, MessageAttachment


class _StubDb:
    def add(self, obj):
        return None

    def commit(self):
        return None

    def refresh(self, obj):
        return None


class _StubAttachmentContextService:
    async def extract_markdown(self, attachments):
        raise AssertionError("attachment context should already be cached in this test")


class _Settings:
    file_retrieval_top_k = 3
    file_retrieval_chunk_token_limit = 120
    file_retrieval_min_score = 0.1


class FileContextRetrievalTests(unittest.IsolatedAsyncioTestCase):
    async def test_retrieve_context_returns_attachment_hits(self):
        service = ConversationFileContextService(_Settings(), _StubAttachmentContextService())
        message = Message(
            role="user",
            content="这是我整理的发布方案文档",
            attachment_context="上线步骤\n\n先灰度发布，再观察监控，最后全量放开。",
        )
        message.attachments = [
            MessageAttachment(
                kind="file",
                original_name="发布方案.md",
                mime_type="text/markdown",
                relative_path="conversation/发布方案.md",
                size_bytes=1,
                position=0,
            )
        ]

        payload = await service.retrieve_context(
            db=_StubDb(),
            query="灰度发布要怎么安排",
            messages=[message],
        )

        self.assertEqual(len(payload.entries), 1)
        self.assertEqual(payload.entries[0].source.type, "file")
        self.assertIn("灰度发布", payload.entries[0].content)


if __name__ == "__main__":
    unittest.main()
