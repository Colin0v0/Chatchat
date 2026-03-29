import unittest
from pathlib import Path

from app.multimodal.image import ImageTextService
from app.storage.models import MessageAttachment


class _StubVision:
    def __init__(self, summary: str):
        self._summary = summary

    def describe(self, image_path: Path):
        class _Description:
            def __init__(self, summary: str):
                self.summary = summary

        return _Description(self._summary)


class _StubLine:
    def __init__(self, text: str):
        self.text = text


class _StubOcr:
    def __init__(self, lines):
        self._lines = lines

    def extract_lines(self, image_path: Path):
        return list(self._lines)


class ImageTextServiceTests(unittest.TestCase):
    def test_structured_brief_uses_fixed_visual_window(self):
        service = ImageTextService(
            min_confidence=0.55,
            text_max_chars=4000,
            vision_model_name='unused',
            vision_prompt='<MORE_DETAILED_CAPTION>',
            vision_max_new_tokens=320,
            vision_num_beams=4,
            vision_summary_max_chars=40,
            vision_device='cpu',
        )
        service._vision = _StubVision('alpha ' * 20)
        service._ocr = _StubOcr([])

        result = service._extract_markdown_sync([
            MessageAttachment(
                kind='image',
                original_name='demo.png',
                mime_type='image/png',
                relative_path='tests/assets/test-image.jpg',
                size_bytes=1,
                position=0,
            )
        ])

        self.assertIn('## Structured image brief', result.markdown)
        self.assertIn('Detailed visual observations:', result.markdown)
        self.assertIn('Visible text:', result.markdown)
        self.assertIn('...', result.markdown)

    def test_full_markdown_is_capped_by_total_limit(self):
        service = ImageTextService(
            min_confidence=0.55,
            text_max_chars=120,
            vision_model_name='unused',
            vision_prompt='<MORE_DETAILED_CAPTION>',
            vision_max_new_tokens=320,
            vision_num_beams=4,
            vision_summary_max_chars=400,
            vision_device='cpu',
        )
        service._vision = _StubVision('detail ' * 30)
        service._ocr = _StubOcr([_StubLine('visible text ' * 10)])

        result = service._extract_markdown_sync([
            MessageAttachment(
                kind='image',
                original_name='demo.png',
                mime_type='image/png',
                relative_path='tests/assets/test-image.jpg',
                size_bytes=1,
                position=0,
            )
        ])

        self.assertLessEqual(len(result.markdown), 120)
        self.assertTrue(result.markdown.endswith('...'))


if __name__ == '__main__':
    unittest.main()
