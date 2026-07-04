from __future__ import annotations

import unittest

from sansan_competition.normalization import (
    normalize_coursework,
    normalize_submission,
    normalize_submission_batch,
)


class NormalizationTests(unittest.TestCase):
    def test_normalize_coursework_parses_classroom_due_fields(self) -> None:
        course_work = normalize_coursework(
            {
                "id": "cw_001",
                "courseId": "course_001",
                "title": "ワークシート",
                "dueDate": {"year": 2026, "month": 7, "day": 5},
                "dueTime": {"hours": 23, "minutes": 30},
            }
        )

        self.assertEqual(course_work.due_date, "2026-07-05")
        self.assertEqual(course_work.due_time, "23:30")
        self.assertEqual(course_work.due_at.isoformat(timespec="minutes"), "2026-07-05T23:30+09:00")

    def test_normalize_coursework_supports_courseworktype_without_due_fields(self) -> None:
        course_work = normalize_coursework(
            {
                "id": "cw_002",
                "courseId": "course_001",
                "title": "短答課題",
                "courseWorkType": "SHORT_ANSWER_QUESTION",
            }
        )

        self.assertEqual(course_work.work_type, "SHORT_ANSWER_QUESTION")
        self.assertIsNone(course_work.due_at)
        self.assertIsNone(course_work.due_date)
        self.assertIsNone(course_work.due_time)

    def test_normalize_coursework_defaults_malformed_due_time(self) -> None:
        course_work = normalize_coursework(
            {
                "id": "cw_003",
                "courseId": "course_001",
                "title": "締切確認",
                "dueDate": "2026-07-06",
                "dueTime": "not-a-time",
            }
        )

        self.assertEqual(course_work.due_date, "2026-07-06")
        self.assertEqual(course_work.due_time, "23:59")
        self.assertEqual(course_work.due_at.isoformat(timespec="minutes"), "2026-07-06T23:59+09:00")

    def test_normalize_coursework_drops_malformed_due_date(self) -> None:
        course_work = normalize_coursework(
            {
                "id": "cw_004",
                "courseId": "course_001",
                "title": "壊れた締切",
                "dueDate": {"month": 7, "day": 7},
                "dueTime": {"hours": 12, "minutes": 0},
            }
        )

        self.assertIsNone(course_work.due_at)
        self.assertIsNone(course_work.due_date)
        self.assertIsNone(course_work.due_time)

    def test_normalize_submission_batch_collects_partial_failures(self) -> None:
        submissions, issues = normalize_submission_batch(
            [
                {
                    "id": "sub_001",
                    "courseId": "course_001",
                    "courseWorkId": "cw_001",
                    "studentId": "student_001",
                    "state": "NEW",
                },
                {
                    "id": "sub_002",
                    "courseWorkId": "cw_001",
                    "studentId": "student_002",
                    "state": "TURNED_IN",
                },
            ]
        )

        self.assertEqual(len(submissions), 1)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "PARTIAL_CLASSROOM_DATA")

    def test_normalize_submission_uses_student_id_when_user_id_is_missing(self) -> None:
        submission = normalize_submission(
            {
                "id": "sub_003",
                "courseId": "course_001",
                "courseWorkId": "cw_001",
                "studentId": "student_003",
                "state": "NEW",
            }
        )

        self.assertEqual(submission.student_id, "student_003")

    def test_normalize_submission_supports_classroom_nested_shapes(self) -> None:
        submission = normalize_submission(
            {
                "id": "sub_001",
                "courseId": "course_001",
                "courseWorkId": "cw_001",
                "userId": "student_001",
                "state": "TURNED_IN",
                "updateTime": "2026-07-05T11:45:00Z",
                "submissionHistory": [
                    {
                        "stateHistory": {
                            "state": "TURNED_IN",
                            "stateTimestamp": "2026-07-05T10:30:00Z",
                            "actorUserId": "student_001",
                        }
                    }
                ],
                "assignmentSubmission": {
                    "attachments": [{"driveFile": {"id": "file_001"}}]
                },
            }
        )

        self.assertEqual(submission.student_id, "student_001")
        self.assertEqual(
            submission.submitted_at.isoformat(timespec="minutes"),
            "2026-07-05T19:30+09:00",
        )
        self.assertEqual(len(submission.attachments), 1)

    def test_normalize_submission_batch_preserves_unknown_status(self) -> None:
        submissions, issues = normalize_submission_batch(
            [
                {
                    "id": "sub_004",
                    "courseId": "course_001",
                    "courseWorkId": "cw_001",
                    "studentId": "student_004",
                    "state": "MYSTERY_STATE",
                }
            ]
        )

        self.assertEqual(len(submissions), 1)
        self.assertEqual(submissions[0].state, "MYSTERY_STATE")
        self.assertEqual(issues, [])

    def test_normalize_submission_batch_collects_non_mapping_and_bad_name_records(self) -> None:
        submissions, issues = normalize_submission_batch(
            [
                {
                    "id": "sub_005",
                    "courseId": "course_001",
                    "courseWorkId": "cw_001",
                    "studentId": "student_005",
                    "state": "NEW",
                },
                None,
                {
                    "id": "sub_006",
                    "courseId": "course_001",
                    "courseWorkId": "cw_001",
                    "studentId": "student_006",
                    "studentName": {"displayName": "Alice"},
                    "state": "TURNED_IN",
                },
                {
                    "id": "sub_007",
                    "courseId": "course_001",
                    "courseWorkId": "cw_001",
                    "state": "NEW",
                },
            ]
        )

        self.assertEqual(len(submissions), 1)
        self.assertEqual(submissions[0].student_id, "student_005")
        self.assertEqual(len(issues), 3)
        self.assertTrue(any("mapping" in issue.message for issue in issues))
        self.assertTrue(any("studentName" in issue.message for issue in issues))
        self.assertTrue(any("studentId, userId" in issue.message for issue in issues))


if __name__ == "__main__":
    unittest.main()
