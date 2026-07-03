from __future__ import annotations

import argparse
import json
import sys

from sansan_competition import (
    Course,
    CourseWork,
    StudentSubmission,
    build_course_summary_output,
    build_reminder_generation_output,
)


def _build_sample_context() -> tuple[Course, CourseWork, list[StudentSubmission]]:
    course = Course(
        course_id="123456789",
        name="数学I",
        section="1年A組",
        description="",
        state="ACTIVE",
        teacher_ids=["teacher_1"],
        student_count=30,
    )
    coursework = CourseWork(
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
    submissions = [
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
    return course, coursework, submissions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sansan-competition")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("sample-reminder", help="Print a sample reminder-generation JSON payload")
    subparsers.add_parser("sample-course-summary", help="Print a sample course-summary JSON payload")
    args = parser.parse_args(argv)

    course, coursework, submissions = _build_sample_context()

    if args.command == "sample-course-summary":
        payload = build_course_summary_output(
            request_id="req_20260703_001",
            course=course,
            coursework=coursework,
            submissions=submissions,
        ).to_dict()
    else:
        payload = build_reminder_generation_output(
            request_id="req_20260703_001",
            course=course,
            coursework=coursework,
            submissions=submissions,
        ).to_dict()

    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
