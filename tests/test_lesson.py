from __future__ import annotations

import unittest

from sansan_competition.lesson import (
    LessonBundleValidationError,
    build_ai_lesson_payload,
    build_lesson_bundle,
    build_publication_plan,
    classify_drive_source,
)


class LessonBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event = {
            "id": "event-001",
            "summary": "情報I 第3回",
            "start": {"dateTime": "2026-07-13T10:00:00+09:00"},
            "end": {"dateTime": "2026-07-13T11:30:00+09:00"},
            "htmlLink": "https://calendar.google.com/event-001",
        }
        self.files = [
            {
                "id": "recording-001",
                "name": "情報I 第3回 授業録画.mp4",
                "mimeType": "video/mp4",
                "webViewLink": "https://drive.google.com/recording-001",
            },
            {
                "id": "transcript-001",
                "name": "情報I 第3回 文字起こし",
                "mimeType": "application/vnd.google-apps.document",
                "webViewLink": "https://docs.google.com/document/d/transcript-001",
            },
            {
                "id": "handout-001",
                "name": "第3回 補助資料.pdf",
                "mimeType": "application/pdf",
                "webViewLink": "https://drive.google.com/handout-001",
            },
        ]

    def test_classifies_drive_sources_without_reading_content(self) -> None:
        self.assertEqual(classify_drive_source("授業録画.mp4", "video/mp4"), "recording")
        self.assertEqual(
            classify_drive_source("第3回 文字起こし", "application/vnd.google-apps.document"),
            "transcript",
        )
        self.assertEqual(classify_drive_source("配布資料.pdf", "application/pdf"), "supplement")

    def test_builds_stable_bundle_with_classroom_items_and_topic(self) -> None:
        bundle = build_lesson_bundle(
            course_id="course-001",
            course_name="情報I",
            calendar_event=self.event,
            drive_files=self.files,
            coursework=[
                {
                    "id": "cw-001",
                    "title": "第3回確認課題",
                    "topicId": "topic-old",
                    "state": "PUBLISHED",
                }
            ],
            coursework_materials=[
                {
                    "id": "material-001",
                    "title": "第3回資料",
                    "topicId": "topic-old",
                    "state": "PUBLISHED",
                }
            ],
            transcript_segments=[
                {
                    "segmentId": "segment-001",
                    "sourceId": "transcript-001",
                    "startSeconds": 12,
                    "endSeconds": 24,
                    "text": "データの構造を確認します。",
                }
            ],
        )

        same_bundle = build_lesson_bundle(
            course_id="course-001",
            course_name="情報I",
            calendar_event=self.event,
            drive_files=self.files,
        )
        self.assertEqual(bundle.lesson_id, same_bundle.lesson_id)
        self.assertEqual(bundle.topic_name, "2026-07-13 情報I 第3回")
        self.assertEqual([source.kind for source in bundle.drive_sources], [
            "recording",
            "transcript",
            "supplement",
        ])
        self.assertEqual(bundle.classroom_items[0]["itemType"], "assignment")
        self.assertEqual(bundle.publication_status, "ready")

    def test_ai_payload_preserves_citations_and_excludes_student_identifiers(self) -> None:
        bundle = build_lesson_bundle(
            course_id="course-001",
            course_name="情報I",
            calendar_event=self.event,
            drive_files=self.files,
            transcript_segments=[
                {
                    "segmentId": "segment-001",
                    "sourceId": "transcript-001",
                    "startSeconds": 12,
                    "endSeconds": 24,
                    "text": "授業で扱った重要な考え方です。",
                }
            ],
        )
        payload = build_ai_lesson_payload(
            bundle,
            transcript_texts={"transcript-001": "補足説明をここに保存します。"},
        )

        self.assertEqual(payload["privacy"]["studentIdentifiersIncluded"], False)
        self.assertTrue(payload["privacy"]["answerMustCiteSource"])
        self.assertEqual(payload["chunks"][0]["sourceId"], "transcript-001")
        self.assertEqual(payload["chunks"][0]["sourceUrl"], self.files[1]["webViewLink"])
        self.assertEqual(payload["chunks"][1]["startSeconds"], 12.0)

    def test_publication_plan_requires_known_sources_and_explicit_items(self) -> None:
        bundle = build_lesson_bundle(
            course_id="course-001",
            course_name="情報I",
            calendar_event=self.event,
            drive_files=self.files,
        )

        plan = build_publication_plan(
            bundle,
            [
                {
                    "kind": "material",
                    "title": "第3回授業資料",
                    "sourceIds": ["handout-001"],
                }
            ],
        )
        self.assertTrue(plan["requiresTeacherApproval"])
        self.assertEqual(plan["items"][0]["sourceIds"], ["handout-001"])

        with self.assertRaises(LessonBundleValidationError):
            build_publication_plan(
                bundle,
                [{"kind": "material", "title": "不正な資料", "sourceIds": ["missing"]}],
            )


if __name__ == "__main__":
    unittest.main()
