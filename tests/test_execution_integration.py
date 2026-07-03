"""結合テスト: mocky取得 → kimu正規化/分析/生成 → mocky実行 (REQUIREMENTS 20.2)。"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sansan_competition.analysis import analyze_submissions
from sansan_competition.contract import (
    build_reminder_generation_response,
    validate_agent_output,
)
from sansan_competition.models import JST
from sansan_competition.normalization import (
    normalize_course,
    normalize_coursework,
    normalize_submission_batch,
)
from sansan_competition.execution.classroom_client import MockClassroomClient
from sansan_competition.execution.google_auth import (
    MockAuthProvider,
    READ_SCOPES,
    WRITE_SCOPES,
)
from sansan_competition.execution.posting import OutputExecutor
from sansan_competition.execution.renderers import MockGoogleDocsClient

# PDF生成は reportlab に依存する。未導入環境では EXPORT_PDF は error に劣化する。
_HAS_REPORTLAB = importlib.util.find_spec("reportlab") is not None


class IntegrationTests(unittest.TestCase):
    def test_full_pipeline(self) -> None:
        auth = MockAuthProvider()
        auth.login(READ_SCOPES + WRITE_SCOPES)
        classroom = MockClassroomClient(auth)

        raw_course = classroom.list_courses()[0]
        raw_work = classroom.list_course_work(raw_course["id"])[0]
        raw_subs = classroom.list_submissions(raw_course["id"], raw_work["id"])

        course = normalize_course(raw_course)
        course_work = normalize_coursework(raw_work)
        submissions, issues = normalize_submission_batch(raw_subs)
        self.assertEqual(issues, [])

        analysis = analyze_submissions(
            course,
            course_work,
            submissions,
            now=datetime(2026, 7, 3, 13, 0, tzinfo=JST),
            normalization_issues=issues,
        )
        self.assertEqual(len(analysis.unsubmitted), 12)

        response = build_reminder_generation_response(
            "req_integration",
            analysis,
            reminder_title="課題提出リマインド",
            reminder_body="まだ提出していない人は提出してください。",
        )
        # kimuの契約バリデータを通ること
        self.assertEqual(validate_agent_output(response), [])

        approved = {a["actionId"] for a in response["approval"]["actions"]}
        with tempfile.TemporaryDirectory() as tmp:
            executor = OutputExecutor(
                classroom=classroom, docs=MockGoogleDocsClient(), out_dir=tmp
            )
            results = executor.execute(response, approved)
            statuses = {r.type: r.status for r in results}
            self.assertEqual(statuses["CREATE_CLASSROOM_ANNOUNCEMENT"], "success")
            self.assertEqual(
                statuses["EXPORT_PDF"], "success" if _HAS_REPORTLAB else "error"
            )
            self.assertEqual(statuses["EXPORT_MARKDOWN"], "success")
            # 生成物が存在する
            self.assertTrue(any(Path(tmp).iterdir()))


if __name__ == "__main__":
    unittest.main()
