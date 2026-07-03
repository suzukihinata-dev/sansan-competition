from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from sansan_competition.execution.errors import AgentError, ErrorCode
from sansan_competition.execution.renderers import (
    MockGoogleDocsClient,
    render_google_document,
    render_markdown,
    render_pdf,
)

# PDF生成は reportlab に依存し、未導入環境では AgentError で優雅に劣化する設計。
# その環境では PDF レンダリングの成功を前提とするテストをスキップする。
_HAS_REPORTLAB = importlib.util.find_spec("reportlab") is not None

SAMPLE = (
    Path(__file__).resolve().parent.parent
    / "samples"
    / "reminder_generation_success.json"
)


def _outputs() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))["outputs"]


class RendererTests(unittest.TestCase):
    def test_markdown_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = render_markdown(_outputs()["markdown"], tmp)
            out = Path(result["path"])
            self.assertTrue(out.exists())
            self.assertIn("課題提出リマインド", out.read_text(encoding="utf-8"))
            self.assertGreater(result["bytes"], 0)

    def test_markdown_empty_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AgentError) as ctx:
                render_markdown({"fileName": "a.md"}, tmp)
            self.assertEqual(ctx.exception.code, ErrorCode.INVALID_AGENT_OUTPUT)

    @unittest.skipUnless(_HAS_REPORTLAB, "reportlab not installed")
    def test_pdf_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = render_pdf(_outputs()["pdf"], tmp)
            out = Path(result["path"])
            self.assertTrue(out.exists())
            self.assertEqual(out.read_bytes()[:4], b"%PDF")

    def test_google_document_handles_bullet_list(self) -> None:
        # kimuの googleDocument は bulletList ブロックを含む
        client = MockGoogleDocsClient()
        result = render_google_document(_outputs()["googleDocument"], client)
        self.assertTrue(result["documentId"].startswith("mockdoc_"))
        self.assertTrue(result["url"].startswith("https://docs.google.com/"))

    def test_google_document_requires_title(self) -> None:
        with self.assertRaises(AgentError) as ctx:
            render_google_document({"blocks": []}, MockGoogleDocsClient())
        self.assertEqual(ctx.exception.code, ErrorCode.DOCUMENT_EXPORT_FAILED)


if __name__ == "__main__":
    unittest.main()
