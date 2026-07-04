from __future__ import annotations

import unittest
from datetime import datetime

from sansan_competition.analysis import analyze_submissions
from sansan_competition.classroom import build_classroom_announcement_request
from sansan_competition.contract import build_reminder_generation_response
from sansan_competition.execution.errors import AgentError, ErrorCode
from sansan_competition.execution.google_auth import (
    MockAuthProvider,
    READ_SCOPES,
    WRITE_SCOPES,
    Scopes,
)
from sansan_competition.execution.classroom_client import MockClassroomClient
from sansan_competition.models import JST
from sansan_competition.normalization import (
    normalize_course,
    normalize_coursework,
    normalize_submission_batch,
)


def _logged_in() -> MockAuthProvider:
    auth = MockAuthProvider()
    auth.login(READ_SCOPES + WRITE_SCOPES)
    return auth


def _sample_analysis():
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
    return analyze_submissions(
        course,
        course_work,
        submissions,
        now=datetime(2026, 7, 3, 13, 0, tzinfo=JST),
        normalization_issues=issues,
    )


class AuthTests(unittest.TestCase):
    def test_login_scoped_credentials(self) -> None:
        auth = MockAuthProvider(email="t@example.com")
        creds = auth.login(READ_SCOPES)
        self.assertEqual(creds.email, "t@example.com")
        self.assertTrue(creds.has_scope(Scopes.COURSES_READONLY))
        self.assertIn("***", creds.masked_token())

    def test_expired_token_raises(self) -> None:
        auth = MockAuthProvider(simulate_expired=True)
        auth.login(READ_SCOPES)
        with self.assertRaises(AgentError) as ctx:
            auth.credentials()
        self.assertEqual(ctx.exception.code, ErrorCode.GOOGLE_AUTH_EXPIRED)


class ClassroomClientTests(unittest.TestCase):
    def test_missing_scope_denied(self) -> None:
        auth = MockAuthProvider()
        auth.login((Scopes.COURSES_READONLY,))  # coursework/submissionスコープ無し
        client = MockClassroomClient(auth)
        self.assertTrue(client.list_courses())
        with self.assertRaises(AgentError) as ctx:
            client.list_course_work("123456789")
        self.assertEqual(ctx.exception.code, ErrorCode.CLASSROOM_API_PERMISSION_DENIED)

    def test_read_scope_cannot_post(self) -> None:
        auth = MockAuthProvider()
        auth.login(READ_SCOPES)  # 書き込みスコープ無し
        client = MockClassroomClient(auth)
        with self.assertRaises(AgentError) as ctx:
            client.create_announcement("123456789", "本文")
        self.assertEqual(ctx.exception.code, ErrorCode.CLASSROOM_API_PERMISSION_DENIED)

    def test_raw_data_feeds_normalization(self) -> None:
        # mocky取得の生データ → kimu正規化 が通ること (ROLE 4.2)
        client = MockClassroomClient(_logged_in())
        raw_subs = client.list_submissions("123456789", "987654321")
        self.assertEqual(len(raw_subs), 30)
        submissions, issues = normalize_submission_batch(raw_subs)
        self.assertEqual(issues, [])
        unsubmitted = [s for s in submissions if s.state == "NEW"]
        self.assertEqual(len(unsubmitted), 12)

    def test_not_found(self) -> None:
        client = MockClassroomClient(_logged_in())
        with self.assertRaises(AgentError) as ctx:
            client.list_course_work("000")
        self.assertEqual(ctx.exception.code, ErrorCode.CLASSROOM_API_NOT_FOUND)

    def test_simulated_failure(self) -> None:
        client = MockClassroomClient(
            _logged_in(), fail_with=ErrorCode.CLASSROOM_API_RATE_LIMITED
        )
        with self.assertRaises(AgentError) as ctx:
            client.list_courses()
        self.assertEqual(ctx.exception.code, ErrorCode.CLASSROOM_API_RATE_LIMITED)


class StructuredHandoffTests(unittest.TestCase):
    def test_reminder_handoff_defaults_to_unsubmitted_students(self) -> None:
        response = build_reminder_generation_response(
            "req_google_handoff",
            _sample_analysis(),
            reminder_title="課題提出リマインド",
            reminder_body="まだ提出していない人は提出してください。",
        )

        reminder = response["outputs"]["classroomReminder"]
        self.assertEqual(reminder["assigneeMode"], "INDIVIDUAL_STUDENTS")
        self.assertEqual(reminder["targetStudentIds"], ["student_001"])
        self.assertIn("投稿対象: 指定生徒 1名", response["outputs"]["markdown"]["content"])
        self.assertEqual(
            response["outputs"]["googleDocument"]["blocks"][2]["text"],
            "未提出者数: 1名 / 投稿対象: 指定生徒 1名 / 口調: polite",
        )

    def test_reminder_handoff_can_explicitly_target_all_students(self) -> None:
        response = build_reminder_generation_response(
            "req_google_all_students",
            _sample_analysis(),
            reminder_title="課題提出リマインド",
            reminder_body="まだ提出していない人は提出してください。",
            target_student_ids=[],
        )

        reminder = response["outputs"]["classroomReminder"]
        self.assertEqual(reminder["assigneeMode"], "ALL_STUDENTS")
        self.assertEqual(reminder["targetStudentIds"], [])
        self.assertIn("投稿対象: コース全員", response["outputs"]["markdown"]["content"])

    def test_classroom_request_preserves_individual_targets(self) -> None:
        response = build_reminder_generation_response(
            "req_google_request",
            _sample_analysis(),
            reminder_title="課題提出リマインド",
            reminder_body="まだ提出していない人は提出してください。",
        )

        request = build_classroom_announcement_request(
            response["outputs"]["classroomReminder"]
        )
        self.assertEqual(request.course_id, "123456789")
        self.assertEqual(request.body["assigneeMode"], "INDIVIDUAL_STUDENTS")
        self.assertEqual(
            request.body["individualStudentsOptions"]["studentIds"],
            ["student_001"],
        )


if __name__ == "__main__":
    unittest.main()
