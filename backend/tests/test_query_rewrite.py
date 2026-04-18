import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.retrieval.query_rewrite import RagQueryRewriter


class QueryRewriteTests(unittest.IsolatedAsyncioTestCase):
    async def test_rewriter_uses_recent_context_and_applies_normalized_query(self):
        settings = SimpleNamespace(
            rag_query_rewrite_enabled=True,
            rag_query_rewrite_model="codex:gpt-5.2",
            rag_query_rewrite_history_messages=4,
        )
        rewriter = RagQueryRewriter(settings)

        history = [
            {"role": "user", "content": "我在看知识库里的部署文档"},
            {"role": "assistant", "content": "好的，你具体想看哪部分？"},
            {"role": "user", "content": "WSL2 连接模型那段"},
        ]

        with patch(
            "app.retrieval.query_rewrite.complete_model_response",
            return_value="search query: WSL2 连接模型 部署文档",
        ):
            result = await rewriter.rewrite(query="WSL2 那一段怎么配", history_messages=history)

        self.assertTrue(result.applied)
        self.assertEqual(result.effective_query, "WSL2 连接模型 部署文档")
        self.assertEqual(result.context_message_count, 2)

    async def test_invalid_rewrite_keeps_original_query(self):
        settings = SimpleNamespace(
            rag_query_rewrite_enabled=True,
            rag_query_rewrite_model="codex:gpt-5.2",
            rag_query_rewrite_history_messages=4,
        )
        rewriter = RagQueryRewriter(settings)

        with patch(
            "app.retrieval.query_rewrite.complete_model_response",
            return_value="Here is a standalone retrieval query for you",
        ):
            result = await rewriter.rewrite(query="部署文档", history_messages=[])

        self.assertFalse(result.applied)
        self.assertEqual(result.effective_query, "部署文档")


if __name__ == "__main__":
    unittest.main()
