import unittest

from app.chat.title import generate_conversation_title, should_refresh_title


class ConversationTitleTests(unittest.TestCase):
    def test_generate_conversation_title_removes_filters_and_truncates(self):
        title = generate_conversation_title(
            content="folder:work tag:agent 帮我把这个多步骤编排方案整理成开发计划，并且给出里程碑。",
            uploaded_count=0,
            max_length=18,
        )

        self.assertTrue(title.startswith("帮我把这个多步骤编排方案整理成开发"))
        self.assertTrue(title.endswith("…"))

    def test_should_refresh_title_accepts_generic_initial_title(self):
        self.assertTrue(
            should_refresh_title(
                current_title="New chat",
                source_content="请帮我整理本周项目复盘",
                uploaded_count=0,
                max_length=20,
            )
        )


if __name__ == "__main__":
    unittest.main()
