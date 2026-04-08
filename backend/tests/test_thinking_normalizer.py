import unittest

from app.llm.thinking import ThinkTagStreamNormalizer, split_complete_think_blocks


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


if __name__ == "__main__":
    unittest.main()
