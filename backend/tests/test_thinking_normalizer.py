import unittest

from app.chat.types import ChatMessagePayload
from app.llm.thinking import ThinkTagStreamNormalizer, inject_thinking_system_prompt, split_complete_think_blocks


class ThinkingNormalizerTests(unittest.TestCase):
    def test_split_complete_think_blocks_separates_reasoning_and_answer(self):
        reasoning, answer = split_complete_think_blocks("A<think>step 1</think>B")

        self.assertEqual(reasoning, "step 1")
        self.assertEqual(answer, "AB")

    def test_stream_normalizer_emits_reasoning_when_enabled(self):
        normalizer = ThinkTagStreamNormalizer(emit_reasoning=True)

        reasoning_a, answer_a = normalizer.feed("hello<think>plan")
        reasoning_b, answer_b = normalizer.feed("</think>world")
        tail_reasoning, tail_answer = normalizer.flush()

        self.assertEqual(reasoning_a, "plan")
        self.assertEqual(answer_a, "hello")
        self.assertEqual(reasoning_b, "")
        self.assertEqual(answer_b, "world")
        self.assertEqual(tail_reasoning, "")
        self.assertEqual(tail_answer, "")

    def test_stream_normalizer_strips_reasoning_when_disabled(self):
        normalizer = ThinkTagStreamNormalizer(emit_reasoning=False)

        reasoning_a, answer_a = normalizer.feed("hello<think>plan")
        reasoning_b, answer_b = normalizer.feed("</think>world")

        self.assertEqual(reasoning_a, "")
        self.assertEqual(answer_a, "hello")
        self.assertEqual(reasoning_b, "")
        self.assertEqual(answer_b, "world")

    def test_inject_thinking_system_prompt_prepends_for_claude_sonnet(self):
        messages = [ChatMessagePayload(role="user", content="hello")]

        injected = inject_thinking_system_prompt(
            model="openai_local:claude-sonnet-4-6",
            messages=messages,
            reasoning_profile="medium",
        )

        self.assertEqual(injected[0].role, "system")
        self.assertTrue(injected[0].content.startswith("<|think|>"))
        self.assertEqual(injected[1:], messages)

    def test_inject_thinking_system_prompt_prefixes_existing_system_message(self):
        messages = [
            ChatMessagePayload(role="system", content="existing instructions"),
            ChatMessagePayload(role="user", content="hello"),
        ]

        injected = inject_thinking_system_prompt(
            model="openai_local:claude-sonnet-4-6",
            messages=messages,
            reasoning_profile="medium",
        )

        self.assertEqual(len(injected), 2)
        self.assertEqual(injected[0].role, "system")
        self.assertTrue(injected[0].content.startswith("<|think|>"))
        self.assertIn("existing instructions", injected[0].content)

    def test_inject_thinking_system_prompt_respects_catalog_default_on_when_request_is_none(self):
        messages = [ChatMessagePayload(role="user", content="hello")]

        injected = inject_thinking_system_prompt(
            model="openai_local:claude-sonnet-4-6",
            messages=messages,
            reasoning_profile="auto",
        )

        self.assertEqual(injected[0].role, "system")
        self.assertTrue(injected[0].content.startswith("<|think|>"))
        self.assertEqual(injected[1:], messages)

    def test_inject_thinking_system_prompt_skips_non_target_models_or_disabled_mode(self):
        messages = [ChatMessagePayload(role="user", content="hello")]

        disabled = inject_thinking_system_prompt(
            model="openai_local:claude-sonnet-4-6",
            messages=messages,
            reasoning_profile="off",
        )
        other_model = inject_thinking_system_prompt(
            model="openai_local:claude-haiku-4-5",
            messages=messages,
            reasoning_profile="medium",
        )

        self.assertEqual(disabled, messages)
        self.assertEqual(other_model, messages)


if __name__ == "__main__":
    unittest.main()
