import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.retrieval.query_rewrite import RagQueryRewriter


class QueryRewriteTests(unittest.IsolatedAsyncioTestCase):
    async def test_rewriter_uses_recent_context_and_applies_normalized_query(self):
        settings = SimpleNamespace(
            rag_query_rewrite_enabled=True,
            rag_query_rewrite_model="codex:gpt-5.4",
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
            rag_query_rewrite_model="codex:gpt-5.4",
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

    async def test_memory_hints_are_passed_to_rewrite_prompt(self):
        settings = SimpleNamespace(
            rag_query_rewrite_enabled=True,
            rag_query_rewrite_model="codex:gpt-5.4",
            rag_query_rewrite_history_messages=2,
        )
        rewriter = RagQueryRewriter(settings)

        captured: dict[str, object] = {}

        async def fake_complete(**kwargs):
            captured["messages"] = kwargs["messages"]
            return "Chatchat memory 系统 候选记忆面板"

        with patch("app.retrieval.query_rewrite.complete_model_response", fake_complete):
            result = await rewriter.rewrite(
                query="这个面板怎么做",
                history_messages=[],
                memory_query_hints=["用户当前在做 Chatchat memory 系统"],
            )

        self.assertEqual(result.memory_hint_count, 1)
        self.assertTrue(result.applied)
        messages = captured["messages"]
        self.assertIn("用户当前在做 Chatchat memory 系统", messages[1].content)


if __name__ == "__main__":
    unittest.main()
