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


if __name__ == "__main__":
    unittest.main()
