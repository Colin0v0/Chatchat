import unittest

from app.memory.extractor import MemoryExtractor


class MemoryExtractorPayloadParsingTests(unittest.TestCase):
    def setUp(self):
        self.extractor = MemoryExtractor(extract_limit=3)

    def test_parse_payload_accepts_think_blocks_and_fenced_json(self):
        raw = """<think>internal reasoning</think>
```json
{"items":[{"scope":"conversation","kind":"fact","title":"偏好","detail":"喜欢简洁回答","tags":["偏好"],"confidence":0.9}]}
```
"""

        payload = self.extractor._parse_payload(raw)

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertIn("items", payload)

    def test_parse_payload_repairs_invalid_backslash_escape(self):
        raw = (
            '{"items":[{"scope":"conversation","kind":"fact","title":"formula",'
            '"detail":"determinant derivative \\cdot result","tags":["math"],"confidence":0.8}]}'
        )

        payload = self.extractor._parse_payload(raw)

        self.assertIsNotNone(payload)
        assert payload is not None
        items = payload.get("items")
        self.assertIsInstance(items, list)


if __name__ == "__main__":
    unittest.main()
