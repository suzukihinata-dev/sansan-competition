from __future__ import annotations

from datetime import datetime
import unittest

from sansan_competition.classroom import GoogleClassroomClient, fetch_submission_analysis
from sansan_competition.models import JST
from sansan_competition.normalization import normalize_course, normalize_coursework
from sansan_competition.outputs import build_classroom_reminder_output


class FakeRequest:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class FakeStudentSubmissionsResource:
    def __init__(self, pages):
        self._pages = pages

    def list(self, **kwargs):
        return FakeRequest(self._pages[kwargs.get("pageToken")])


class FakeCourseWorkResource:
    def __init__(self, course_work, submission_pages):
        self._course_work = course_work
        self._submission_pages = submission_pages

    def get(self, **kwargs):
        return FakeRequest(self._course_work)

    def studentSubmissions(self):
        return FakeStudentSubmissionsResource(self._submission_pages)


class FakeStudentsResource:
    def __init__(self, pages):
        self._pages = pages

    def list(self, **kwargs):
        return FakeRequest(self._pages[kwargs.get("pageToken")])


class FakeAnnouncementsResource:
    def __init__(self, sink):
        self._sink = sink

    def create(self, **kwargs):
        self._sink.append(kwargs)
        return FakeRequest(
            {
                "id": "ann_001",
                "alternateLink": "https://classroom.google.com/ann_001",
                "state": kwargs["body"].get("state"),
                "courseId": kwargs["courseId"],
            }
        )


class FakeCoursesResource:
    def __init__(self, course, students_pages, course_work, submission_pages, announcement_sink):
        self._course = course
        self._students_pages = students_pages
        self._course_work = course_work
        self._submission_pages = submission_pages
        self._announcement_sink = announcement_sink

    def get(self, **kwargs):
        return FakeRequest(self._course)

    def students(self):
        return FakeStudentsResource(self._students_pages)

    def courseWork(self):
        return FakeCourseWorkResource(self._course_work, self._submission_pages)

    def announcements(self):
        return FakeAnnouncementsResource(self._announcement_sink)


class FakeClassroomService:
    def __init__(self, course, students_pages, course_work, submission_pages, announcement_sink):
        self._courses = FakeCoursesResource(
            course,
            students_pages,
            course_work,
            submission_pages,
            announcement_sink,
        )

    def courses(self):
        return self._courses


class ClassroomIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.announcement_calls = []
        self.service = FakeClassroomService(
            course={
                "id": "course_001",
                "name": "数学I",
                "section": "1年A組",
            },
            students_pages={
                None: {
                    "students": [
                        {
                            "userId": "student_001",
                            "profile": {"name": {"fullName": "山田太郎"}},
                        }
                    ],
                    "nextPageToken": "page_2",
                },
                "page_2": {
                    "students": [
                        {
                            "userId": "student_002",
                            "profile": {"name": {"fullName": "佐藤花子"}},
                        },
                        {
                            "userId": "student_003",
                            "profile": {"name": {"fullName": "鈴木一郎"}},
                        },
                    ]
                },
            },
            course_work={
                "id": "cw_001",
                "courseId": "course_001",
                "title": "二次関数プリント",
                "workType": "ASSIGNMENT",
                "dueDate": {"year": 2026, "month": 7, "day": 5},
                "dueTime": {"hours": 12, "minutes": 0},
            },
            submission_pages={
                None: {
                    "studentSubmissions": [
                        {
                            "id": "sub_001",
                            "courseId": "course_001",
                            "courseWorkId": "cw_001",
                            "userId": "student_001",
                            "state": "NEW",
                        },
                        {
                            "id": "sub_002",
                            "courseId": "course_001",
                            "courseWorkId": "cw_001",
                            "userId": "student_002",
                            "state": "TURNED_IN",
                            "late": False,
                            "updateTime": "2026-07-05T02:15:00Z",
                            "submissionHistory": [
                                {
                                    "stateHistory": {
                                        "state": "TURNED_IN",
                                        "stateTimestamp": "2026-07-05T01:30:00Z",
                                        "actorUserId": "student_002",
                                    }
                                }
                            ],
                            "assignmentSubmission": {
                                "attachments": [{"driveFile": {"id": "file_001"}}]
                            },
                        },
                    ],
                    "nextPageToken": "page_2",
                },
                "page_2": {
                    "studentSubmissions": [
                        {
                            "id": "sub_003",
                            "courseId": "course_001",
                            "courseWorkId": "cw_001",
                            "userId": "student_003",
                            "state": "RETURNED",
                            "late": True,
                            "updateTime": "2026-07-05T15:00:00Z",
                            "submissionHistory": [
                                {
                                    "stateHistory": {
                                        "state": "TURNED_IN",
                                        "stateTimestamp": "2026-07-05T14:30:00Z",
                                        "actorUserId": "student_003",
                                    }
                                }
                            ],
                            "assignmentSubmission": {"attachments": []},
                        }
                    ]
                },
            },
            announcement_sink=self.announcement_calls,
        )
        self.client = GoogleClassroomClient(self.service)

    def test_fetch_submission_analysis_supports_live_classroom_shapes(self) -> None:
        analysis = fetch_submission_analysis(
            self.client,
            course_id="course_001",
            course_work_id="cw_001",
            now=datetime(2026, 7, 5, 9, 0, tzinfo=JST),
        )

        counts = analysis.counts()
        self.assertEqual(counts["totalStudents"], 3)
        self.assertEqual(counts["unsubmittedCount"], 1)
        self.assertEqual(counts["lateCount"], 1)
        self.assertEqual(counts["attachmentMissingPossibleCount"], 1)
        self.assertEqual(analysis.evaluations[0].student_name, "山田太郎")
        student_002 = next(
            entry for entry in analysis.evaluations if entry.student_id == "student_002"
        )
        self.assertEqual(
            student_002.submitted_at.isoformat(timespec="minutes"),
            "2026-07-05T10:30+09:00",
        )

    def test_create_announcement_from_output_uses_contract_payload(self) -> None:
        course = normalize_course(
            {
                "id": "course_001",
                "name": "数学I",
                "section": "1年A組",
            }
        )
        course_work = normalize_coursework(
            {
                "id": "cw_001",
                "courseId": "course_001",
                "title": "二次関数プリント",
            }
        )
        reminder_output = build_classroom_reminder_output(
            course=course,
            course_work=course_work,
            reminder_title="課題提出リマインド",
            reminder_body="まだ提出していない人は提出してください。",
            target_student_ids=["student_001"],
            scheduled_time="2026-07-05T12:30:00Z",
        )

        created = self.client.create_announcement_from_output(reminder_output)

        self.assertEqual(created["id"], "ann_001")
        self.assertEqual(len(self.announcement_calls), 1)
        body = self.announcement_calls[0]["body"]
        self.assertEqual(
            body["text"],
            "課題提出リマインド\n\nまだ提出していない人は提出してください。",
        )
        self.assertEqual(body["assigneeMode"], "INDIVIDUAL_STUDENTS")
        self.assertEqual(
            body["individualStudentsOptions"]["studentIds"],
            ["student_001"],
        )
        self.assertEqual(body["scheduledTime"], "2026-07-05T12:30:00Z")


if __name__ == "__main__":
    unittest.main()
