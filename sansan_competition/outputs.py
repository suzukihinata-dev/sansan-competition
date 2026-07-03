from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from .models import Course, CourseWork, SubmissionAnalysis, SubmissionEvaluation


def build_submission_report_outputs(
    analysis: SubmissionAnalysis,
) -> dict[str, Any]:
    return {
        "markdown": _build_submission_markdown_output(analysis),
        "pdf": _build_submission_pdf_output(analysis),
        "googleDocument": _build_submission_google_document_output(analysis),
        "classroomReminder": None,
    }


def build_reminder_outputs(
    analysis: SubmissionAnalysis,
    *,
    reminder_title: str,
    reminder_body: str,
    tone: str,
    target_student_ids: list[str] | None = None,
    scheduled_time: str | None = None,
) -> dict[str, Any]:
    return {
        "markdown": _build_reminder_markdown_output(
            analysis,
            reminder_title=reminder_title,
            reminder_body=reminder_body,
            tone=tone,
        ),
        "pdf": _build_reminder_pdf_output(
            analysis,
            reminder_title=reminder_title,
            reminder_body=reminder_body,
            tone=tone,
        ),
        "googleDocument": _build_reminder_google_document_output(
            analysis,
            reminder_title=reminder_title,
            reminder_body=reminder_body,
            tone=tone,
        ),
        "classroomReminder": build_classroom_reminder_output(
            course=analysis.course,
            course_work=analysis.course_work,
            reminder_title=reminder_title,
            reminder_body=reminder_body,
            target_student_ids=target_student_ids or [],
            scheduled_time=scheduled_time,
        ),
    }


def build_classroom_reminder_output(
    *,
    course: Course,
    course_work: CourseWork,
    reminder_title: str,
    reminder_body: str,
    target_student_ids: list[str],
    scheduled_time: str | None,
) -> dict[str, Any]:
    assignee_mode = "ALL_STUDENTS"
    if target_student_ids:
        assignee_mode = "INDIVIDUAL_STUDENTS"

    return {
        "target": {
            "courseId": course.course_id,
            "courseWorkId": course_work.course_work_id,
        },
        "postType": "announcement",
        "title": reminder_title,
        "text": reminder_body,
        "materials": [],
        "scheduledTime": scheduled_time,
        "assigneeMode": assignee_mode,
        "targetStudentIds": target_student_ids,
        "requiresTeacherApproval": True,
    }


def _build_submission_markdown_output(
    analysis: SubmissionAnalysis,
) -> dict[str, Any]:
    course = analysis.course
    course_work = analysis.course_work
    counts = analysis.counts()
    content = "\n".join(
        [
            f"# {course.name} 提出状況レポート",
            "",
            "## 概要",
            f"- 対象コース: {_course_label(course)}",
            f"- 対象課題: {course_work.title}",
            f"- 作成日時: {_format_timestamp(analysis.generated_at)}",
            f"- 総対象者数: {counts['totalStudents']}名",
            f"- 未提出者数: {counts['unsubmittedCount']}名",
            f"- 期限接近者数: {counts['dueSoonCount']}名",
            f"- 遅延提出者数: {counts['lateCount']}名",
            "",
            "## 未提出者一覧",
            _markdown_table(
                analysis.unsubmitted,
                empty_text="該当者はいません。",
            ),
            "",
            "## 遅延提出者一覧",
            _markdown_table(
                analysis.late_submissions,
                empty_text="該当者はいません。",
            ),
            "",
            "## 添付確認が必要な提出物",
            _markdown_table(
                analysis.attachment_flags,
                empty_text="該当者はいません。",
            ),
            "",
            "## AIによる提案",
            analysis.recommended_action(),
        ]
    )

    return {
        "fileName": _safe_filename(course.name, "submission_report", "md"),
        "title": f"{course.name} 提出状況レポート",
        "content": content,
    }


def _build_submission_pdf_output(
    analysis: SubmissionAnalysis,
) -> dict[str, Any]:
    course = analysis.course
    counts = analysis.counts()
    return {
        "fileName": _safe_filename(course.name, "submission_report", "pdf"),
        "title": f"{course.name} 提出状況レポート",
        "layout": "report",
        "sections": [
            {
                "heading": "概要",
                "body": (
                    f"{_course_label(course)} の課題 "
                    f"「{analysis.course_work.title}」に関する提出状況レポートです。"
                ),
            },
            {
                "heading": "集計",
                "table": {
                    "columns": ["指標", "値"],
                    "rows": [
                        ["総対象者数", str(counts["totalStudents"])],
                        ["未提出者数", str(counts["unsubmittedCount"])],
                        ["期限接近者数", str(counts["dueSoonCount"])],
                        ["遅延提出者数", str(counts["lateCount"])],
                        [
                            "添付確認必要数",
                            str(counts["attachmentMissingPossibleCount"]),
                        ],
                    ],
                },
            },
            {
                "heading": "未提出者一覧",
                "table": _pdf_table(analysis.unsubmitted),
            },
            {
                "heading": "遅延提出者一覧",
                "table": _pdf_table(analysis.late_submissions),
            },
            {
                "heading": "AIによる提案",
                "body": analysis.recommended_action(),
            },
        ],
    }


def _build_submission_google_document_output(
    analysis: SubmissionAnalysis,
) -> dict[str, Any]:
    course = analysis.course
    counts = analysis.counts()
    return {
        "title": f"{course.name} 提出状況レポート {analysis.generated_at.date().isoformat()}",
        "documentType": "report",
        "blocks": [
            {"type": "heading1", "text": f"{course.name} 提出状況レポート"},
            {
                "type": "paragraph",
                "text": (
                    f"{_course_label(course)} の課題 "
                    f"「{analysis.course_work.title}」に関する提出状況レポートです。"
                ),
            },
            {"type": "heading2", "text": "集計"},
            {
                "type": "table",
                "columns": ["指標", "値"],
                "rows": [
                    ["総対象者数", str(counts["totalStudents"])],
                    ["未提出者数", str(counts["unsubmittedCount"])],
                    ["期限接近者数", str(counts["dueSoonCount"])],
                    ["遅延提出者数", str(counts["lateCount"])],
                    [
                        "添付確認必要数",
                        str(counts["attachmentMissingPossibleCount"]),
                    ],
                ],
            },
            {"type": "heading2", "text": "未提出者一覧"},
            _google_table_block(analysis.unsubmitted),
            {"type": "heading2", "text": "遅延提出者一覧"},
            _google_table_block(analysis.late_submissions),
            {"type": "heading2", "text": "AIによる提案"},
            {"type": "paragraph", "text": analysis.recommended_action()},
        ],
    }


def _build_reminder_markdown_output(
    analysis: SubmissionAnalysis,
    *,
    reminder_title: str,
    reminder_body: str,
    tone: str,
) -> dict[str, Any]:
    course = analysis.course
    target_count = len(analysis.unsubmitted)
    content = "\n".join(
        [
            f"# {reminder_title}",
            "",
            "## 対象",
            f"- コース: {_course_label(course)}",
            f"- 課題: {analysis.course_work.title}",
            f"- 未提出者数: {target_count}名",
            f"- 口調: {tone}",
            "",
            "## 投稿案",
            reminder_body,
            "",
            "## 教師向け注意",
            "- Classroom投稿前に内容と対象コースを確認してください。",
            "- 生徒個人名は本文に含めない想定です。",
        ]
    )

    return {
        "fileName": _safe_filename(course.name, "reminder_draft", "md"),
        "title": reminder_title,
        "content": content,
    }


def _build_reminder_pdf_output(
    analysis: SubmissionAnalysis,
    *,
    reminder_title: str,
    reminder_body: str,
    tone: str,
) -> dict[str, Any]:
    course = analysis.course
    return {
        "fileName": _safe_filename(course.name, "reminder_draft", "pdf"),
        "title": reminder_title,
        "layout": "notice",
        "sections": [
            {
                "heading": "対象",
                "body": (
                    f"{_course_label(course)} / 課題「{analysis.course_work.title}」"
                    f" / 未提出者 {len(analysis.unsubmitted)}名 / 口調 {tone}"
                ),
            },
            {
                "heading": "投稿案",
                "body": reminder_body,
            },
            {
                "heading": "注意事項",
                "body": "Classroomへ投稿する前に、教師による承認が必要です。",
            },
        ],
    }


def _build_reminder_google_document_output(
    analysis: SubmissionAnalysis,
    *,
    reminder_title: str,
    reminder_body: str,
    tone: str,
) -> dict[str, Any]:
    course = analysis.course
    return {
        "title": f"{reminder_title} {analysis.generated_at.date().isoformat()}",
        "documentType": "announcement_draft",
        "blocks": [
            {"type": "heading1", "text": reminder_title},
            {
                "type": "paragraph",
                "text": (
                    f"対象: {_course_label(course)} / 課題「{analysis.course_work.title}」"
                ),
            },
            {
                "type": "paragraph",
                "text": f"未提出者数: {len(analysis.unsubmitted)}名 / 口調: {tone}",
            },
            {"type": "heading2", "text": "投稿案"},
            {"type": "paragraph", "text": reminder_body},
            {"type": "heading2", "text": "注意事項"},
            {
                "type": "bulletList",
                "items": [
                    "Classroomへ投稿する前に教師が承認すること。",
                    "他の生徒の提出状況が分かる表現を避けること。",
                ],
            },
        ],
    }


def _markdown_table(
    rows: Iterable[SubmissionEvaluation],
    *,
    empty_text: str,
) -> str:
    rows = list(rows)
    if not rows:
        return empty_text

    lines = [
        "| 生徒名 | 状態 | 締切 | 提出日時 | 備考 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.student_name or row.student_id,
                    row.status_label,
                    _format_date(row.due_at),
                    _format_timestamp(row.submitted_at),
                    " / ".join(row.notes),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _pdf_table(rows: Iterable[SubmissionEvaluation]) -> dict[str, Any]:
    rows = list(rows)
    return {
        "columns": ["生徒名", "状態", "締切", "提出日時", "備考"],
        "rows": [
            [
                row.student_name or row.student_id,
                row.status_label,
                _format_date(row.due_at),
                _format_timestamp(row.submitted_at),
                " / ".join(row.notes),
            ]
            for row in rows
        ],
    }


def _google_table_block(rows: Iterable[SubmissionEvaluation]) -> dict[str, Any]:
    table = _pdf_table(rows)
    return {
        "type": "table",
        "columns": table["columns"],
        "rows": table["rows"],
    }


def _format_date(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.date().isoformat()


def _format_timestamp(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.isoformat(timespec="minutes")


def _safe_filename(course_name: str, stem: str, suffix: str) -> str:
    cleaned = course_name.replace(" ", "_")
    return f"{cleaned}_{stem}.{suffix}"


def _course_label(course: Course) -> str:
    if course.section:
        return f"{course.name} / {course.section}"
    return course.name
