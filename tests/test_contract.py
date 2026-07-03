from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import unittest

from sansan_competition.contract import (
    build_error_response,
    build_reminder_generation_response,
    build_submission_analysis_response,
    load_contract_schema,
    validate_agent_output,
)
from sansan_competition.models import AgentTaskType, JST
from sansan_competition.normalization import (
    normalize_course,
    normalize_coursework,
    normalize_submission_batch,
)
from sansan_competition.analysis import analyze_submissions


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        course = normalize_course(
            {
                "id": "123456789",
                "name": "数学I",
                "section": "1年A組",
                "description": "二次関数の基礎",
                "teacherIds": ["teacher_001"],
                "studentCount": 3,
            }
        )
        course_work = normalize_coursework(
            {
                "id": "987654321",
                "courseId": "123456789",
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
                    "courseId": "123456789",
                    "courseWorkId": "987654321",
                    "studentId": "student_001",
                    "studentName": "山田太郎",
                    "state": "NEW",
                },
                {
                    "id": "sub_002",
                    "courseId": "123456789",
                    "courseWorkId": "987654321",
                    "studentId": "student_002",
                    "studentName": "佐藤花子",
                    "state": "TURNED_IN",
                    "submissionTime": "2026-07-05T20:15:00+09:00",
                    "attachments": [{"driveFile": {"id": "file_001"}}],
                },
                {
                    "id": "sub_003",
                    "courseId": "123456789",
                    "courseWorkId": "987654321",
                    "studentId": "student_003",
                    "studentName": "鈴木一郎",
                    "state": "TURNED_IN",
                    "submissionTime": "2026-07-06T00:30:00+09:00",
                    "late": True,
                },
            ]
        )
        self.course = course
        self.analysis = analyze_submissions(
            course,
            course_work,
            submissions,
            now=datetime(2026, 7, 3, 13, 0, tzinfo=JST),
            normalization_issues=issues,
        )

    def test_schema_file_loads(self) -> None:
        schema = load_contract_schema()
        self.assertEqual(schema["properties"]["schemaVersion"]["const"], "1.0.0")

    def test_submission_analysis_response_passes_validator(self) -> None:
        response = build_submission_analysis_response(
            "req_test_submission_analysis",
            self.analysis,
        )
        self.assertEqual(validate_agent_output(response), [])

    def test_reminder_generation_response_requires_approval(self) -> None:
        response = build_reminder_generation_response(
            "req_test_reminder_generation",
            self.analysis,
            reminder_title="課題提出リマインド",
            reminder_body="まだ提出していない人は提出してください。",
        )
        self.assertTrue(response["approval"]["required"])
        self.assertEqual(validate_agent_output(response), [])

    def test_error_response_passes_validator(self) -> None:
        response = build_error_response(
            "req_test_error",
            AgentTaskType.SUBMISSION_ANALYSIS,
            title="提出状況の取得に失敗しました",
            short_summary="Google Classroom APIから提出状況を取得できませんでした。",
            recommended_action="Googleアカウントの権限を確認し、再度実行してください。",
            error_code="CLASSROOM_API_PERMISSION_DENIED",
            error_message="提出状況を取得する権限がありません。",
            course=self.course,
            generated_at=datetime(2026, 7, 3, 13, 10, tzinfo=JST),
        )
        self.assertEqual(validate_agent_output(response), [])

    def test_sample_json_files_pass_validator(self) -> None:
        samples_dir = Path(__file__).resolve().parent.parent / "samples"
        for sample_file in samples_dir.glob("*.json"):
            payload = json.loads(sample_file.read_text())
            with self.subTest(sample=sample_file.name):
                self.assertEqual(validate_agent_output(payload), [])


if __name__ == "__main__":
    unittest.main()
