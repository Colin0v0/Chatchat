import unittest
from unittest.mock import patch

from app.chat.types import ChatImagePayload
from app.chat.history import IMAGE_ANALYSIS_SYSTEM_PROMPT, IMAGE_CONTEXT_LABEL, MessageHistoryService
from app.storage.models import Message, MessageAttachment


class _StubDb:
    def add(self, obj):
        return None

    def commit(self):
        return None

    def refresh(self, obj):
        return None


class _StubImageTextService:
    async def extract_markdown(self, attachments):
        raise AssertionError('cached image_context should be reused in this test')


class MessageHistoryServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_prepare_adds_cautious_image_system_prompt_and_keeps_native_images(self):
        service = MessageHistoryService(_StubDb(), _StubImageTextService())
        message = Message(
            role='user',
            content='who is this',
            image_context='## Structured image brief\n### Image 1\nDetailed visual observations:\nblue hair\n\nVisible text:\nNo readable text was detected in the uploaded image.',
        )
        message.attachments = [
            MessageAttachment(
                kind='image',
                original_name='demo.png',
                mime_type='image/png',
                relative_path='tests/assets/test-image.jpg',
                size_bytes=1,
                position=0,
            )
        ]

        with patch('app.chat.history.supports_native_image_input', return_value=True), patch(
            'app.chat.history.read_image_data_url',
            return_value='data:image/png;base64,AAA',
        ):
            prepared = await service.prepare(model='openai:any-native-vision', messages=[message])

        self.assertEqual(prepared.messages[0].role, 'system')
        self.assertEqual(prepared.messages[0].content, IMAGE_ANALYSIS_SYSTEM_PROMPT)
        self.assertIn('may be inaccurate or uncertain', prepared.messages[0].content)
        self.assertEqual(prepared.messages[1].role, 'user')
        self.assertIn(f'{IMAGE_CONTEXT_LABEL}:', prepared.messages[1].content)
        self.assertEqual(len(prepared.messages[1].images), 1)
        self.assertIsInstance(prepared.messages[1].images[0], ChatImagePayload)

    async def test_prepare_text_only_model_receives_labeled_brief_without_native_image(self):
        service = MessageHistoryService(_StubDb(), _StubImageTextService())
        message = Message(
            role='user',
            content='',
            image_context='## Structured image brief\n### Image 1\nDetailed visual observations:\nwhite coat\n\nVisible text:\n- Demo',
        )
        message.attachments = [
            MessageAttachment(
                kind='image',
                original_name='demo.png',
                mime_type='image/png',
                relative_path='tests/assets/test-image.jpg',
                size_bytes=1,
                position=0,
            )
        ]

        with patch('app.chat.history.supports_native_image_input', return_value=False):
            prepared = await service.prepare(model='openai:deepseek-chat', messages=[message])

        self.assertEqual(prepared.messages[0].role, 'system')
        self.assertEqual(prepared.messages[1].images, ())
        self.assertIn('Please describe the uploaded image in detail.', prepared.messages[1].content)
        self.assertIn(f'{IMAGE_CONTEXT_LABEL}:', prepared.messages[1].content)


if __name__ == '__main__':
    unittest.main()
