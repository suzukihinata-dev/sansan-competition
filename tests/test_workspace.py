from __future__ import annotations

import unittest

from sansan_competition.classroom import GoogleClassroomClient
from sansan_competition.workspace import (
    GoogleCalendarClient,
    GoogleDriveClient,
    GoogleWorkspaceLessonClient,
)


class _Request:
    def __init__(self, value: dict) -> None:
        self.value = value

    def execute(self) -> dict:
        return self.value


class _CalendarEvents:
    def get(self, **kwargs):
        return _Request(
            {
                "id": kwargs["eventId"],
                "summary": "情報I 第3回",
                "start": {"dateTime": "2026-07-13T10:00:00+09:00"},
                "end": {"dateTime": "2026-07-13T11:30:00+09:00"},
            }
        )


class _CalendarService:
    def events(self):
        return _CalendarEvents()


class _DriveFiles:
    def __init__(self) -> None:
        self.created_query = ""

    def list(self, **kwargs):
        self.created_query = kwargs["q"]
        return _Request(
            {
                "files": [
                    {
                        "id": "handout-001",
                        "name": "第3回 補助資料.pdf",
                        "mimeType": "application/pdf",
                        "webViewLink": "https://drive.google.com/handout-001",
                    }
                ]
            }
        )

    def get(self, **kwargs):
        return _Request("transcript text")

    def export(self, **kwargs):
        return _Request(b"transcript text")


class _DriveService:
    def __init__(self) -> None:
        self.file_resource = _DriveFiles()

    def files(self):
        return self.file_resource


class _Topics:
    def __init__(self) -> None:
        self.created = []

    def list(self, **kwargs):
        return _Request({"topic": []})

    def create(self, **kwargs):
        self.created.append(kwargs)
        return _Request({"topicId": "topic-001", "name": kwargs["body"]["name"]})


class _CourseWork:
    def __init__(self) -> None:
        self.created = []

    def list(self, **kwargs):
        return _Request({"courseWork": []})

    def create(self, **kwargs):
        self.created.append(kwargs)
        return _Request({"id": "cw-001", "title": kwargs["body"]["title"]})


class _CourseWorkMaterials:
    def __init__(self) -> None:
        self.created = []

    def list(self, **kwargs):
        return _Request({"courseWorkMaterial": []})

    def create(self, **kwargs):
        self.created.append(kwargs)
        return _Request({"id": "material-001", "title": kwargs["body"]["title"]})


class _Courses:
    def __init__(self) -> None:
        self.topic_resource = _Topics()
        self.coursework_resource = _CourseWork()
        self.material_resource = _CourseWorkMaterials()

    def get(self, **kwargs):
        return _Request({"id": kwargs["id"], "name": "情報I"})

    def topics(self):
        return self.topic_resource

    def courseWork(self):
        return self.coursework_resource

    def courseWorkMaterials(self):
        return self.material_resource


class _ClassroomService:
    def __init__(self) -> None:
        self.course_resource = _Courses()

    def courses(self):
        return self.course_resource


class WorkspaceClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.classroom_service = _ClassroomService()
        self.client = GoogleWorkspaceLessonClient(
            GoogleCalendarClient(_CalendarService()),
            GoogleDriveClient(_DriveService()),
            GoogleClassroomClient(self.classroom_service),
        )

    def test_assembles_bundle_from_three_google_sources(self) -> None:
        bundle, ai_payload = self.client.assemble_bundle(
            course_id="course-001",
            calendar_event_id="event-001",
            drive_query="name contains '第3回'",
        )

        self.assertEqual(bundle.course_id, "course-001")
        self.assertEqual(bundle.calendar_event["summary"], "情報I 第3回")
        self.assertEqual(bundle.drive_sources[0].source_id, "handout-001")
        self.assertEqual(ai_payload["lessonId"], bundle.lesson_id)

    def test_publish_creates_topic_and_material_only_after_approval(self) -> None:
        bundle, _ = self.client.assemble_bundle(
            course_id="course-001",
            calendar_event_id="event-001",
        )

        with self.assertRaises(ValueError):
            self.client.publish(
                bundle=bundle,
                items=[
                    {
                        "kind": "material",
                        "title": "第3回補助資料",
                        "sourceIds": ["handout-001"],
                    }
                ],
                approved=False,
            )
        self.assertEqual(self.classroom_service.course_resource.topic_resource.created, [])

        result = self.client.publish(
            bundle=bundle,
            items=[
                {
                    "kind": "material",
                    "title": "第3回補助資料",
                    "sourceIds": ["handout-001"],
                }
            ],
            approved=True,
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["topicId"], "topic-001")
        created_body = self.classroom_service.course_resource.material_resource.created[0]["body"]
        self.assertEqual(created_body["topicId"], "topic-001")
        self.assertEqual(
            created_body["materials"][0]["driveFile"]["driveFile"]["id"],
            "handout-001",
        )


if __name__ == "__main__":
    unittest.main()
