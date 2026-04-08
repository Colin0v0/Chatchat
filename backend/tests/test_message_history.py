import unittest
from unittest.mock import patch

from app.chat.types import ChatFileReferencePayload
from app.chat.history import ATTACHMENT_CONTEXT_LABEL, IMAGE_ANALYSIS_SYSTEM_PROMPT, MessageHistoryService
from app.storage.models import Message, MessageAttachment


class _StubDb:
    def add(self, obj):
        return None

    def commit(self):
        return None

    def refresh(self, obj):
        return None


class _StubAttachmentContextService:
    async def extract_markdown(self, attachments, include_images=True):
        raise AssertionError('cached image_context should be reused in this test')


class MessageHistoryServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_prepare_local_image_flow_adds_cautious_system_prompt_and_attachment_brief(self):
        service = MessageHistoryService(_StubDb(), _StubAttachmentContextService())
        message = Message(
            role='user',
            content='who is this',
            attachment_context='## Structured image brief\n### Image 1\nDetailed visual observations:\nblue hair\n\nVisible text:\nNo readable text was detected in the uploaded image.',
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

        with patch('app.chat.history.uses_native_multimodal', return_value=False):
            prepared = await service.prepare(model='openai:any-native-vision', messages=[message])

        self.assertEqual(prepared.messages[0].role, 'system')
        self.assertEqual(prepared.messages[0].content, IMAGE_ANALYSIS_SYSTEM_PROMPT)
        self.assertIn('may be inaccurate or uncertain', prepared.messages[0].content)
        self.assertEqual(prepared.messages[1].role, 'user')
        self.assertEqual(prepared.messages[1].images, ())
        self.assertIn(f'{ATTACHMENT_CONTEXT_LABEL}:', prepared.messages[1].content)

    async def test_prepare_empty_prompt_uses_default_attachment_prompt_for_local_flow(self):
        service = MessageHistoryService(_StubDb(), _StubAttachmentContextService())
        message = Message(
            role='user',
            content='',
            attachment_context='## Structured image brief\n### Image 1\nDetailed visual observations:\nwhite coat\n\nVisible text:\n- Demo',
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

        with patch('app.chat.history.uses_native_multimodal', return_value=False):
            prepared = await service.prepare(model='openai:deepseek-chat', messages=[message])

        self.assertEqual(prepared.messages[0].role, 'system')
        self.assertEqual(prepared.messages[1].images, ())
        self.assertIn('Please analyze the uploaded attachments in detail.', prepared.messages[1].content)
        self.assertIn(f'{ATTACHMENT_CONTEXT_LABEL}:', prepared.messages[1].content)

    async def test_prepare_upstream_service_model_uses_file_references(self):
        service = MessageHistoryService(_StubDb(), _StubAttachmentContextService())
        message = Message(
            role='user',
            content='总结这个文件',
        )
        message.attachments = [
            MessageAttachment(
                kind='file',
                original_name='demo.pdf',
                mime_type='application/pdf',
                relative_path='tests/assets/demo.pdf',
                size_bytes=1,
                position=0,
            )
        ]

        with patch('app.chat.history.uses_native_multimodal', return_value=True), patch(
            'app.chat.history.ensure_upstream_file_id',
            return_value='file_demo',
        ):
            prepared = await service.prepare(model='openai_local:claude-sonnet-4-6', messages=[message])

        self.assertEqual(len(prepared.messages), 1)
        self.assertEqual(prepared.messages[0].role, 'user')
        self.assertEqual(prepared.messages[0].content, '总结这个文件')
        self.assertEqual(prepared.messages[0].files, (ChatFileReferencePayload(file_id='file_demo'),))
        self.assertEqual(prepared.messages[0].images, ())


if __name__ == '__main__':
    unittest.main()
