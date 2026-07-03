from __future__ import annotations

import json
from datetime import datetime

from sansan_competition import (
    analyze_submissions,
    build_reminder_generation_response,
    build_submission_analysis_response,
    normalize_course,
    normalize_coursework,
    normalize_submission_batch,
)
from sansan_competition.models import JST


def main() -> None:
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

    analysis = analyze_submissions(
        course,
        course_work,
        submissions,
        now=datetime(2026, 7, 3, 13, 0, tzinfo=JST),
        normalization_issues=issues,
    )

    payload = {
        "submissionAnalysis": build_submission_analysis_response(
            "req_20260703_demo_analysis",
            analysis,
        ),
        "reminderGeneration": build_reminder_generation_response(
            "req_20260703_demo_reminder",
            analysis,
            reminder_title="課題提出リマインド",
            reminder_body=(
                "課題「二次関数プリント」の提出期限が近づいています。"
                "まだ提出していない人は、7月5日までに提出してください。"
            ),
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
