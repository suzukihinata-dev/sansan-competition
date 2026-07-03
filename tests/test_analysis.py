from __future__ import annotations

from datetime import datetime
import unittest

from sansan_competition.analysis import analyze_submissions, build_ai_task_input
from sansan_competition.models import AgentTaskType, JST
from sansan_competition.normalization import (
    normalize_course,
    normalize_coursework,
    normalize_submission_batch,
)


class AnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.course = normalize_course(
            {
                "id": "course_001",
                "name": "数学I",
                "section": "1年A組",
                "studentCount": 4,
            }
        )
        self.course_work = normalize_coursework(
            {
                "id": "cw_001",
                "courseId": "course_001",
                "title": "二次関数プリント",
                "workType": "ASSIGNMENT",
                "dueDate": "2026-07-05",
                "dueTime": "12:00",
            }
        )
        self.submissions, self.issues = normalize_submission_batch(
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
                    "submissionTime": "2026-07-05T10:00:00+09:00",
                    "attachments": [{"driveFile": {"id": "file_001"}}],
                },
                {
                    "id": "sub_003",
                    "courseId": "course_001",
                    "courseWorkId": "cw_001",
                    "studentId": "student_003",
                    "studentName": "鈴木一郎",
                    "state": "TURNED_IN",
                    "submissionTime": "2026-07-05T13:15:00+09:00",
                    "late": True,
                },
                {
                    "id": "sub_004",
                    "courseId": "course_001",
                    "courseWorkId": "cw_001",
                    "studentId": "student_004",
                    "studentName": "高橋未来",
                    "state": "NEW",
                }
            ]
        )

    def test_analyze_submissions_counts_due_soon_late_and_attachment_flags(self) -> None:
        analysis = analyze_submissions(
            self.course,
            self.course_work,
            self.submissions,
            now=datetime(2026, 7, 5, 9, 0, tzinfo=JST),
            normalization_issues=self.issues,
        )

        counts = analysis.counts()
        self.assertEqual(counts["unsubmittedCount"], 2)
        self.assertEqual(counts["dueSoonCount"], 2)
        self.assertEqual(counts["lateCount"], 1)
        self.assertEqual(counts["attachmentMissingPossibleCount"], 1)

    def test_build_ai_task_input_omits_personal_identifiers_by_default(self) -> None:
        analysis = analyze_submissions(
            self.course,
            self.course_work,
            self.submissions,
            now=datetime(2026, 7, 5, 9, 0, tzinfo=JST),
        )

        payload = build_ai_task_input(AgentTaskType.REMINDER_GENERATION, analysis)
        detailed_payload = build_ai_task_input(
            AgentTaskType.REMINDER_GENERATION,
            analysis,
            include_student_names=True,
        )

        first_entry = payload["facts"]["submissions"][0]
        detailed_first_entry = detailed_payload["facts"]["submissions"][0]

        self.assertNotIn("studentId", first_entry)
        self.assertNotIn("studentName", first_entry)
        self.assertIn("studentId", detailed_first_entry)
        self.assertIn("studentName", detailed_first_entry)


if __name__ == "__main__":
    unittest.main()
