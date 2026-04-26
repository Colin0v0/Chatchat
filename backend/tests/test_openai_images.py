import io
import unittest

from PIL import Image

from app.core.config import settings
from app.provider_transports.openai_images import (
    normalize_image_output_format,
    normalize_image_quality,
    normalize_image_size,
    openai_image_base_url,
    openai_image_headers,
)
from app.image_processing import prepare_generated_image_bytes


class OpenAIImageTransportTests(unittest.TestCase):
    def test_image_base_url_falls_back_to_openai_base_url(self):
        original_image_base_url = settings.openai_image_base_url
        original_openai_base_url = settings.openai_base_url
        settings.openai_image_base_url = ""
        settings.openai_base_url = "https://example.test/v1"
        try:
            self.assertEqual(openai_image_base_url(), "https://example.test/v1")
        finally:
            settings.openai_image_base_url = original_image_base_url
            settings.openai_base_url = original_openai_base_url

    def test_image_headers_prefer_image_api_key(self):
        original_image_api_key = settings.openai_image_api_key
        original_openai_api_key = settings.openai_api_key
        settings.openai_image_api_key = "sk-image"
        settings.openai_api_key = "sk-chat"
        try:
            self.assertEqual(openai_image_headers(), {"Authorization": "Bearer sk-image"})
        finally:
            settings.openai_image_api_key = original_image_api_key
            settings.openai_api_key = original_openai_api_key

    def test_image_option_normalizers_accept_supported_values(self):
        self.assertEqual(normalize_image_quality("high"), "high")
        self.assertEqual(normalize_image_output_format("jpg"), "jpeg")
        self.assertEqual(normalize_image_size("1024x1024"), "1024x1024")
        self.assertEqual(normalize_image_size("1536x1024"), "1536x1024")
        self.assertEqual(normalize_image_size("1024X1536"), "1024x1536")
        self.assertEqual(normalize_image_size("auto"), "auto")

    def test_image_option_normalizers_reject_unsupported_values(self):
        with self.assertRaises(ValueError):
            normalize_image_quality("cinematic")
        with self.assertRaises(ValueError):
            normalize_image_output_format("gif")
        with self.assertRaises(ValueError):
            normalize_image_size("square")
        with self.assertRaises(ValueError):
            normalize_image_size("0x1024")
        with self.assertRaises(ValueError):
            normalize_image_size("1280x720")
        with self.assertRaises(ValueError):
            normalize_image_size("3840x2160")
        with self.assertRaises(ValueError):
            normalize_image_size("4096x4096")

    def test_prepare_generated_image_bytes_resizes_to_requested_size(self):
        source = Image.new("RGB", (64, 64), color=(255, 0, 0))
        buffer = io.BytesIO()
        source.save(buffer, format="PNG")

        resized = prepare_generated_image_bytes(
            content=buffer.getvalue(),
            output_format="png",
            target_size="128x72",
        )

        with Image.open(io.BytesIO(resized)) as result:
            self.assertEqual(result.size, (128, 72))


if __name__ == "__main__":
    unittest.main()
