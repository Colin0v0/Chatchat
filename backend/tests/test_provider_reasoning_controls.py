import unittest

from app.provider_codecs.anthropic import apply_anthropic_reasoning_controls
from app.provider_codecs.gemini import apply_gemini_reasoning_controls


class AnthropicReasoningControlTests(unittest.TestCase):
    def test_enables_claude_thinking_with_budget_tokens(self):
        payload: dict[str, object] = {}

        apply_anthropic_reasoning_controls(payload, reasoning_profile="high")

        self.assertEqual(
            payload,
            {
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": 2048,
                }
            },
        )

    def test_skips_claude_thinking_when_off(self):
        payload: dict[str, object] = {}

        apply_anthropic_reasoning_controls(payload, reasoning_profile="off")

        self.assertEqual(payload, {})


class GeminiReasoningControlTests(unittest.TestCase):
    def test_enables_gemini_thinking_and_includes_thoughts(self):
        payload: dict[str, object] = {}

        apply_gemini_reasoning_controls(payload, reasoning_profile="medium")

        self.assertEqual(
            payload,
            {
                "generationConfig": {
                    "thinkingConfig": {
                        "includeThoughts": True,
                        "thinkingBudget": 1024,
                    }
                }
            },
        )

    def test_disables_gemini_thinking_with_zero_budget(self):
        payload: dict[str, object] = {}

        apply_gemini_reasoning_controls(payload, reasoning_profile="off")

        self.assertEqual(
            payload,
            {
                "generationConfig": {
                    "thinkingConfig": {
                        "includeThoughts": False,
                        "thinkingBudget": 0,
                    }
                }
            },
        )


if __name__ == "__main__":
    unittest.main()
