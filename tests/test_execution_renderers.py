from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sansan_competition.analysis import analyze_submissions
from sansan_competition.contract import build_submission_analysis_response
from sansan_competition.models import JST
from sansan_competition.execution.errors import AgentError, ErrorCode
from sansan_competition.execution.renderers import (
    MockGoogleDocsClient,
    render_google_document,
    render_markdown,
    render_pdf,
)
from sansan_competition.normalization import (
    normalize_course,
    normalize_coursework,
    normalize_submission_batch,
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


def _report_google_document_output() -> dict:
    course = normalize_course(
        {
            "id": "course_001",
            "name": "数学I",
            "section": "1年A組",
            "description": "二次関数の基礎",
            "teacherIds": ["teacher_001"],
            "studentCount": 2,
        }
    )
    course_work = normalize_coursework(
        {
            "id": "cw_001",
            "courseId": "course_001",
            "title": "二次関数プリント",
            "description": "配布プリントを解いて提出",
            "workType": "ASSIGNMENT",
            "dueDate": "2026-07-05",
            "dueTime": "23:59",
        }
    )
    submissions, issues = normalize_submission_batch(
        [
            {
                "id": "sub_001",
                "courseId": "course_001",
                "courseWorkId": "cw_001",
                "studentId": "student_001",
                "studentName": "山田太郎",
                "state": "NEW",
            },
            {
                "id": "sub_002",
                "courseId": "course_001",
                "courseWorkId": "cw_001",
                "studentId": "student_002",
                "studentName": "佐藤花子",
                "state": "TURNED_IN",
                "submissionTime": "2026-07-05T20:15:00+09:00",
                "attachments": [{"driveFile": {"id": "file_001"}}],
            },
        ]
    )
    analysis = analyze_submissions(
        course,
        course_work,
        submissions,
        now=datetime(2026, 7, 3, 13, 0, tzinfo=JST),
        normalization_issues=issues,
    )
    return build_submission_analysis_response(
        "req_renderer_report",
        analysis,
    )["outputs"]["googleDocument"]


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

    def test_google_document_report_tables_keep_data_rows(self) -> None:
        payload = _report_google_document_output()
        client = MockGoogleDocsClient()
        created = client.create_document(payload["title"], payload["blocks"])
        table_requests = [
            request["insertTable"]
            for request in created["requests"]
            if "insertTable" in request
        ]
        self.assertTrue(table_requests)
        self.assertTrue(all(request["rows"] >= 2 for request in table_requests))

    def test_google_document_requires_title(self) -> None:
        with self.assertRaises(AgentError) as ctx:
            render_google_document({"blocks": []}, MockGoogleDocsClient())
        self.assertEqual(ctx.exception.code, ErrorCode.DOCUMENT_EXPORT_FAILED)


if __name__ == "__main__":
    unittest.main()
