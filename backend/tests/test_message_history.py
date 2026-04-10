import unittest
from unittest.mock import patch

from app.chat.types import ChatDocumentPayload, ChatFileReferencePayload
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

        with patch('app.chat.history.resolve_native_multimodal_mode', return_value='false'):
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

        with patch('app.chat.history.resolve_native_multimodal_mode', return_value='false'):
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

        with patch('app.chat.history.resolve_native_multimodal_mode', return_value='local'), patch(
            'app.chat.history.ensure_upstream_file_id',
            return_value='file_demo',
        ):
            prepared = await service.prepare(model='openai_local:claude-sonnet-4-6', messages=[message])

        self.assertEqual(len(prepared.messages), 1)
        self.assertEqual(prepared.messages[0].role, 'user')
        self.assertEqual(prepared.messages[0].content, '总结这个文件')
        self.assertEqual(prepared.messages[0].files, (ChatFileReferencePayload(file_id='file_demo'),))
        self.assertEqual(prepared.messages[0].images, ())

    async def test_prepare_codex_flow_sends_images_natively_and_keeps_file_context_local(self):
        class _CodexAttachmentContextService:
            async def extract_markdown(self, attachments, include_images=True):
                return type(
                    'Result',
                    (),
                    {'markdown': '## File attachments\nnotes from doc', 'has_images': False, 'has_files': True},
                )()

        service = MessageHistoryService(_StubDb(), _CodexAttachmentContextService())
        message = Message(role='user', content='看一下图片和文档')
        message.attachments = [
            MessageAttachment(
                kind='image',
                original_name='demo.png',
                mime_type='image/png',
                relative_path='tests/assets/test-image.jpg',
                size_bytes=1,
                position=0,
            ),
            MessageAttachment(
                kind='file',
                original_name='demo.pdf',
                mime_type='application/pdf',
                relative_path='tests/assets/demo.pdf',
                size_bytes=1,
                position=1,
            ),
        ]

        with patch('app.chat.history.resolve_native_multimodal_mode', return_value='codex'), patch(
            'app.chat.history.read_image_data_url',
            return_value='data:image/png;base64,ZmFrZQ==',
        ), patch(
            'app.chat.history.ensure_upstream_file_id',
            return_value='file_demo',
        ):
            prepared = await service.prepare(model='codex:gpt-5.4', messages=[message])

        self.assertEqual(len(prepared.messages), 1)
        self.assertEqual(prepared.messages[0].role, 'user')
        self.assertEqual(len(prepared.messages[0].images), 1)
        self.assertEqual(prepared.messages[0].files, (ChatFileReferencePayload(file_id='file_demo'),))
        self.assertEqual(prepared.messages[0].content, '看一下图片和文档')

    async def test_prepare_gemini_flow_sends_images_and_pdf_natively_and_keeps_other_files_local(self):
        class _GeminiAttachmentContextService:
            async def extract_markdown(self, attachments, include_images=True):
                return type(
                    'Result',
                    (),
                    {'markdown': '## File attachments\nnotes from txt', 'has_images': False, 'has_files': True},
                )()

        service = MessageHistoryService(_StubDb(), _GeminiAttachmentContextService())
        message = Message(role='user', content='看图并读文件')
        message.attachments = [
            MessageAttachment(
                kind='image',
                original_name='demo.png',
                mime_type='image/png',
                relative_path='tests/assets/test-image.jpg',
                size_bytes=1,
                position=0,
            ),
            MessageAttachment(
                kind='file',
                original_name='demo.pdf',
                mime_type='application/pdf',
                relative_path='tests/assets/demo.pdf',
                size_bytes=1,
                position=1,
            ),
            MessageAttachment(
                kind='file',
                original_name='notes.txt',
                mime_type='text/plain',
                relative_path='tests/assets/demo.txt',
                size_bytes=1,
                position=2,
            ),
        ]

        with patch('app.chat.history.resolve_native_multimodal_mode', return_value='gemini'), patch(
            'app.chat.history.read_image_data_url',
            return_value='data:image/png;base64,ZmFrZQ==',
        ), patch(
            'app.chat.history.read_attachment_base64',
            return_value='JVBERi0xLjc=',
        ):
            prepared = await service.prepare(model='gemini:gemini-3-flash', messages=[message])

        self.assertEqual(len(prepared.messages), 1)
        self.assertEqual(prepared.messages[0].role, 'user')
        self.assertEqual(len(prepared.messages[0].images), 1)
        self.assertEqual(
            prepared.messages[0].documents,
            (ChatDocumentPayload(mime_type='application/pdf', filename='demo.pdf', base64_data='JVBERi0xLjc='),),
        )
        self.assertEqual(prepared.messages[0].files, ())
        self.assertIn(ATTACHMENT_CONTEXT_LABEL, prepared.messages[0].content)


if __name__ == '__main__':
    unittest.main()
