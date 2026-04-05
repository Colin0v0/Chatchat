import unittest

from app.chat.context import select_history_window, trim_history_messages
from app.chat.prompt_builder import summarize_older_history
from app.storage.models import Message


def make_message(message_id: int, role: str, content: str) -> Message:
    message = Message(
        id=message_id,
        role=role,
        content=content,
    )
    message.attachments = []
    message.attachment_context = None
    message.image_context = None
    return message


class ChatContextWindowTests(unittest.TestCase):
    def test_trim_history_messages_keeps_recent_window(self):
        messages = [
            make_message(1, "user", "你好"),
            make_message(2, "assistant", "你好，我在。"),
            make_message(3, "user", "我们来讨论一个很长很长的问题。" * 40),
            make_message(4, "assistant", "先给我一点方向。"),
            make_message(5, "user", "现在请直接给结论。"),
        ]

        trimmed = trim_history_messages(messages, message_limit=3, token_budget=45)

        self.assertEqual([message.id for message in trimmed], [5])
        self.assertEqual(trimmed[-1].content, "现在请直接给结论。")

    def test_trim_history_messages_drops_leading_assistant(self):
        messages = [
            make_message(1, "user", "第一问"),
            make_message(2, "assistant", "第一答"),
            make_message(3, "user", "第二问"),
            make_message(4, "assistant", "第二答"),
            make_message(5, "user", "第三问"),
        ]

        trimmed = trim_history_messages(messages, message_limit=2, token_budget=1000)

        self.assertEqual([message.id for message in trimmed], [5])
        self.assertEqual(trimmed[0].role, "user")

    def test_select_history_window_preserves_older_messages_for_summary(self):
        messages = [
            make_message(1, "user", "第一问"),
            make_message(2, "assistant", "第一答"),
            make_message(3, "user", "第二问" * 80),
            make_message(4, "assistant", "第二答"),
            make_message(5, "user", "第三问"),
        ]

        window = select_history_window(messages, message_limit=3, token_budget=55)

        self.assertEqual([message.id for message in window.recent_messages], [5])
        self.assertEqual([message.id for message in window.older_messages], [1, 2, 3, 4])

    def test_summarize_older_history_builds_turn_based_recap(self):
        messages = [
            make_message(1, "user", "想做一个带上下文面板的聊天界面"),
            make_message(2, "assistant", "可以把历史摘要、记忆和检索来源分层展示。"),
            make_message(3, "user", "同时不要把实现搞得很乱"),
            make_message(4, "assistant", "那就把提示词组装和可视化上下文统一收口。"),
        ]

        summary = summarize_older_history(messages=messages, token_budget=120)

        self.assertIn("Turn 1", summary)
        self.assertIn("User:", summary)
        self.assertIn("Assistant:", summary)
        self.assertIn("上下文面板", summary)


if __name__ == "__main__":
    unittest.main()
