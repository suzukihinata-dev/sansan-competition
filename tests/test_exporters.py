from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sansan_competition.exporters import (
    create_google_document_from_output,
    extract_output_payload,
    render_google_document_html,
    save_markdown_output,
)


class FakeRequest:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class FakeFilesResource:
    def __init__(self, sink):
        self._sink = sink

    def create(self, **kwargs):
        self._sink.append(kwargs)
        return FakeRequest(
            {
                "id": "doc_001",
                "name": kwargs["body"]["name"],
                "webViewLink": "https://docs.google.com/document/d/doc_001/edit",
            }
        )


class FakePermissionsResource:
    def __init__(self, sink):
        self._sink = sink

    def create(self, **kwargs):
        self._sink.append(kwargs)
        return FakeRequest({"id": "perm_001"})


class FakeDriveService:
    def __init__(self):
        self.file_create_calls = []
        self.permission_create_calls = []
        self._files = FakeFilesResource(self.file_create_calls)
        self._permissions = FakePermissionsResource(self.permission_create_calls)

    def files(self):
        return self._files

    def permissions(self):
        return self._permissions


class ExporterTests(unittest.TestCase):
    def test_extract_output_payload_reads_from_agent_output(self) -> None:
        payload = {
            "outputs": {
                "markdown": {
                    "fileName": "test.md",
                    "title": "title",
                    "content": "# body",
                }
            }
        }

        extracted = extract_output_payload(payload, "markdown")

        self.assertEqual(extracted["fileName"], "test.md")

    def test_save_markdown_output_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = save_markdown_output(
                {
                    "fileName": "report.md",
                    "title": "Report",
                    "content": "# Example",
                },
                output_dir=temp_dir,
            )

            path = Path(temp_dir) / "report.md"
            self.assertEqual(result.path, path.resolve())
            self.assertEqual(path.read_text(encoding="utf-8"), "# Example")

    def test_render_google_document_html_preserves_structure(self) -> None:
        html = render_google_document_html(
            {
                "title": "数学I 提出状況レポート",
                "documentType": "report",
                "blocks": [
                    {"type": "heading1", "text": "数学I 提出状況レポート"},
                    {"type": "paragraph", "text": "1行目\n2行目"},
                    {"type": "heading2", "text": "注意事項"},
                    {
                        "type": "bulletList",
                        "items": ["教師が確認すること。", "他の生徒名を出さないこと。"],
                    },
                    {
                        "type": "table",
                        "columns": ["生徒名", "状態"],
                        "rows": [["山田太郎", "未提出"]],
                    },
                ],
            }
        )

        self.assertIn("<h1>数学I 提出状況レポート</h1>", html)
        self.assertIn("<br />", html)
        self.assertIn("<ul>", html)
        self.assertIn("<table>", html)
        self.assertIn("<th>生徒名</th>", html)
        self.assertIn("<td>未提出</td>", html)

    def test_create_google_document_from_output_uploads_html_and_shares(self) -> None:
        drive_service = FakeDriveService()

        result = create_google_document_from_output(
            {
                "title": "数学I 提出状況レポート 2026-07-03",
                "documentType": "report",
                "blocks": [
                    {"type": "heading1", "text": "数学I 提出状況レポート"},
                    {"type": "paragraph", "text": "本文です。"},
                ],
            },
            drive_service=drive_service,
            share_emails=["teacher@example.com", "assistant@example.com"],
        )

        self.assertEqual(result.document_id, "doc_001")
        self.assertEqual(
            result.url,
            "https://docs.google.com/document/d/doc_001/edit",
        )
        self.assertEqual(
            result.shared_with,
            ["teacher@example.com", "assistant@example.com"],
        )
        self.assertEqual(len(drive_service.file_create_calls), 1)
        create_call = drive_service.file_create_calls[0]
        self.assertEqual(
            create_call["body"]["mimeType"],
            "application/vnd.google-apps.document",
        )
        self.assertEqual(create_call["body"]["name"], "数学I 提出状況レポート 2026-07-03")
        media_body = create_call["media_body"]
        media_bytes = (
            media_body.data
            if hasattr(media_body, "data")
            else media_body.getbytes(0, media_body.size())
        )
        self.assertIn(b"<html", media_bytes)
        self.assertEqual(len(drive_service.permission_create_calls), 2)
        self.assertEqual(
            drive_service.permission_create_calls[0]["body"]["emailAddress"],
            "teacher@example.com",
        )


if __name__ == "__main__":
    unittest.main()
