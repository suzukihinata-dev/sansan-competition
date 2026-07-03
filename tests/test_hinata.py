from __future__ import annotations

import unittest

from sansan_competition import (
    Course,
    CourseWork,
    StudentSubmission,
    build_error_output,
    build_reminder_generation_output,
    validate_agent_output_dict,
)


class HinataOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.course = Course(
            course_id="123456789",
            name="数学I",
            section="1年A組",
            description="",
            state="ACTIVE",
            teacher_ids=["teacher_1"],
            student_count=30,
        )
        self.coursework = CourseWork(
            course_work_id="987654321",
            course_id="123456789",
            title="二次関数プリント",
            description="",
            work_type="ASSIGNMENT",
            max_points=100,
            due_date="2026-07-05",
            due_time="23:59",
            state="PUBLISHED",
            materials=[],
            topic_id="topic_1",
        )
        self.submissions = [
            StudentSubmission(
                student_submission_id="sub_1",
                course_id="123456789",
                course_work_id="987654321",
                student_id="student_1",
                student_name="山田太郎",
                state="NEW",
                late=False,
            ),
            StudentSubmission(
                student_submission_id="sub_2",
                course_id="123456789",
                course_work_id="987654321",
                student_id="student_2",
                student_name="佐藤花子",
                state="TURNED_IN",
                late=False,
            ),
        ]

    def test_reminder_output_matches_schema(self) -> None:
        output = build_reminder_generation_output(
            request_id="req_20260703_001",
            course=self.course,
            coursework=self.coursework,
            submissions=self.submissions,
        )
        payload = output.to_dict()
        self.assertEqual(validate_agent_output_dict(payload), [])
        self.assertEqual(payload["agentTaskType"], "REMINDER_GENERATION")
        self.assertIn("gui", payload)
        self.assertIn("outputs", payload)
        self.assertIn("approval", payload)
        self.assertTrue(payload["approval"]["required"])
        self.assertIn("outputs.classroomReminder", {action["payloadRef"] for action in payload["approval"]["actions"]})

    def test_reminder_text_avoids_other_students_in_posting_payload(self) -> None:
        output = build_reminder_generation_output(
            request_id="req_20260703_002",
            course=self.course,
            coursework=self.coursework,
            submissions=self.submissions,
        )
        classroom_reminder = output.to_dict()["outputs"]["classroomReminder"]
        self.assertNotIn("山田太郎", classroom_reminder["text"])
        self.assertNotIn("佐藤花子", classroom_reminder["text"])

    def test_error_output_contains_minimum_required_fields(self) -> None:
        output = build_error_output(
            request_id="req_20260703_003",
            task_type="SUBMISSION_ANALYSIS",
            title="提出状況の取得に失敗しました",
            short_summary="Google Classroom APIから提出状況を取得できませんでした。",
            recommended_action="権限を確認して再実行してください。",
            error_code="CLASSROOM_API_PERMISSION_DENIED",
            error_message="提出状況を取得する権限がありません。",
            recoverable=True,
        )
        payload = output.to_dict()
        self.assertEqual(validate_agent_output_dict(payload), [])
        self.assertEqual(payload["status"], "error")
        self.assertIn("errors", payload)


if __name__ == "__main__":
    unittest.main()
