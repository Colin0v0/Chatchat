import unittest

from app.memory.normalizer import normalize_candidate, normalize_memory_fields
from app.memory.types import MemoryCandidate


class MemoryNormalizerTests(unittest.TestCase):
    def test_normalize_english_name_memory_into_chinese_profile(self):
        normalized = normalize_candidate(
            MemoryCandidate(
                scope="global",
                kind="fact",
                title="User Name",
                detail="User's name is 杜宇 (Dú Yǔ). Recognized from greeting '怎么又跟我打招呼了？'",
                tags=("personal",),
                confidence=1.0,
            )
        )

        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.kind, "profile")
        self.assertEqual(normalized.title, "姓名")
        self.assertEqual(normalized.detail, "用户叫杜宇 （Dú Yǔ）")
        self.assertIn("个人", normalized.tags)

    def test_drop_meta_assistant_capability_memory(self):
        normalized = normalize_memory_fields(
            kind="fact",
            title="Assistant Capabilities",
            detail="Assistant can: explain concepts, translate, summarize content, optimize text, rewrite styles.",
            tags=("capabilities", "analysis"),
        )
        self.assertIsNone(normalized)


if __name__ == "__main__":
    unittest.main()
