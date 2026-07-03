from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

ALLOWED_AGENT_TASK_TYPES = {
    "COURSE_SUMMARY",
    "COURSEWORK_SUMMARY",
    "SUBMISSION_ANALYSIS",
    "REMINDER_GENERATION",
    "WEEKLY_REPORT",
    "ANNOUNCEMENT_DRAFT",
    "DOCUMENT_EXPORT",
    "RUBRIC_SUPPORT",
    "ERROR_ANALYSIS",
}

COMMON_TOP_LEVEL_KEYS = {
    "schemaVersion",
    "requestId",
    "generatedAt",
    "agentTaskType",
    "status",
    "course",
    "summary",
    "gui",
    "outputs",
    "approval",
    "errors",
}
COMMON_GUI_KEYS = {"cards", "tables", "warnings", "editableFields"}
COMMON_OUTPUT_KEYS = {"markdown", "pdf", "googleDocument", "classroomReminder"}
COMMON_APPROVAL_KEYS = {"required", "reason", "actions"}
CACHE_DIR_NAME = "__pycache__"
CACHE_SUFFIXES = {".pyc", ".pyo"}
COMMENT_MARKER = "<!-- pr-automation-report -->"


@dataclass(frozen=True, slots=True)
class Course:
    course_id: str
    name: str
    section: str = ""
    description: str = ""
    state: str = ""
    teacher_ids: list[str] | None = None
    student_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "courseId": self.course_id,
            "name": self.name,
            "section": self.section,
            "description": self.description,
            "state": self.state,
            "teacherIds": list(self.teacher_ids or []),
            "studentCount": self.student_count,
        }


@dataclass(frozen=True, slots=True)
class CourseWork:
    course_work_id: str
    course_id: str
    title: str
    description: str = ""
    work_type: str = ""
    max_points: int | float | None = None
    due_date: str = ""
    due_time: str = ""
    state: str = ""
    materials: list[dict[str, Any]] | None = None
    topic_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "courseWorkId": self.course_work_id,
            "courseId": self.course_id,
            "title": self.title,
            "description": self.description,
            "workType": self.work_type,
            "maxPoints": self.max_points,
            "dueDate": self.due_date,
            "dueTime": self.due_time,
            "state": self.state,
            "materials": list(self.materials or []),
            "topicId": self.topic_id,
        }


@dataclass(frozen=True, slots=True)
class StudentSubmission:
    student_submission_id: str
    course_id: str
    course_work_id: str
    student_id: str
    student_name: str
    state: str
    late: bool = False
    assigned_grade: int | float | None = None
    draft_grade: int | float | None = None
    attachments: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "studentSubmissionId": self.student_submission_id,
            "courseId": self.course_id,
            "courseWorkId": self.course_work_id,
            "studentId": self.student_id,
            "studentName": self.student_name,
            "state": self.state,
            "late": self.late,
            "assignedGrade": self.assigned_grade,
            "draftGrade": self.draft_grade,
            "attachments": list(self.attachments or []),
        }


@dataclass(frozen=True, slots=True)
class Summary:
    title: str
    short_summary: str
    teacher_action_required: bool
    recommended_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "shortSummary": self.short_summary,
            "teacherActionRequired": self.teacher_action_required,
            "recommendedAction": self.recommended_action,
        }


@dataclass(frozen=True, slots=True)
class Approval:
    required: bool
    reason: str
    actions: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "reason": self.reason,
            "actions": list(self.actions),
        }


@dataclass(frozen=True, slots=True)
class AgentError:
    code: str
    message: str
    recoverable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "recoverable": self.recoverable,
        }


@dataclass(frozen=True, slots=True)
class AgentOutput:
    request_id: str
    generated_at: str
    agent_task_type: str
    status: str
    summary: Summary
    course: Course
    gui: dict[str, Any]
    outputs: dict[str, Any]
    approval: Approval
    errors: list[AgentError]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": "1.0.0",
            "requestId": self.request_id,
            "generatedAt": self.generated_at,
            "agentTaskType": self.agent_task_type,
            "status": self.status,
            "course": self.course.to_dict(),
            "summary": self.summary.to_dict(),
            "gui": self.gui,
            "outputs": self.outputs,
            "approval": self.approval.to_dict(),
            "errors": [error.to_dict() for error in self.errors],
        }


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    passed: bool
    details: list[str]


@dataclass(frozen=True, slots=True)
class AutomationReport:
    fixes_applied: list[str]
    checks: list[CheckResult]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_markdown(self) -> str:
        lines = [
            COMMENT_MARKER,
            "# PR Automation Report",
            "",
            f"- Overall: {'PASS' if self.passed else 'FAIL'}",
        ]
        if self.fixes_applied:
            lines.extend(["- Auto fixes:", *[f"  - {item}" for item in self.fixes_applied]])
        else:
            lines.append("- Auto fixes: none")
        lines.extend(["", "## Checks"])
        for check in self.checks:
            status = "PASS" if check.passed else "FAIL"
            lines.append(f"- {check.name}: {status}")
            for detail in check.details:
                lines.append(f"  - {detail}")
        lines.append("")
        return "\n".join(lines)


def build_sample_context() -> tuple[Course, CourseWork, list[StudentSubmission]]:
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
            assigned_grade=None,
            draft_grade=None,
            attachments=[],
        ),
        StudentSubmission(
            student_submission_id="sub_2",
            course_id="123456789",
            course_work_id="987654321",
            student_id="student_2",
            student_name="佐藤花子",
            state="TURNED_IN",
            late=False,
            assigned_grade=92,
            draft_grade=92,
            attachments=[{"type": "driveFile", "name": "answer.pdf"}],
        ),
    ]
    return course, coursework, submissions


def build_submission_snapshot(
    submissions: Sequence[StudentSubmission] | None,
) -> dict[str, Any]:
    submissions = submissions or []
    submitted_states = {"TURNED_IN", "RETURNED", "CREATED"}
    missing = [submission for submission in submissions if submission.state not in submitted_states]
    submitted = [submission for submission in submissions if submission.state in submitted_states]
    late = [submission for submission in submissions if submission.late]
    attachment_gaps = [
        submission
        for submission in submissions
        if submission.state in submitted_states and not (submission.attachments or [])
    ]
    return {
        "total": len(submissions),
        "missing": missing,
        "submitted": submitted,
        "late": late,
        "attachment_gaps": attachment_gaps,
    }


def infer_tone_label(tone: str) -> str:
    normalized = tone.strip().lower()
    if normalized in {"strict", "firm", "stern"}:
        return "厳しめ"
    if normalized in {"friendly", "gentle", "soft"}:
        return "やさしい"
    if normalized in {"short", "brief"}:
        return "短文"
    return "丁寧"


def build_teacher_note(*parts: str) -> str:
    fragments = [part.strip() for part in parts if part.strip()]
    return "\n".join(f"- {fragment}" for fragment in fragments)


def build_submission_rows(
    submissions: Sequence[StudentSubmission] | None,
    coursework: CourseWork | None,
) -> list[dict[str, Any]]:
    due_date = coursework.due_date if coursework else ""
    rows: list[dict[str, Any]] = []
    for submission in submissions or []:
        status = "提出済み" if submission.state in {"TURNED_IN", "RETURNED", "CREATED"} else "未提出"
        if submission.late:
            status = f"{status}（遅延）"
        rows.append(
            {
                "studentName": submission.student_name,
                "status": status,
                "dueDate": due_date,
            }
        )
    return rows


def build_markdown_report(
    *,
    title: str,
    course: Course,
    coursework: CourseWork | None,
    snapshot: dict[str, Any],
    recommendation: str,
    teacher_note: str = "",
) -> dict[str, Any]:
    coursework_title = coursework.title if coursework else "なし"
    missing_names = ", ".join(item.student_name for item in snapshot["missing"]) or "なし"
    late_names = ", ".join(item.student_name for item in snapshot["late"]) or "なし"
    lines = [
        f"# {title}",
        "",
        "## 概要",
        f"- 対象コース: {course.name}",
        f"- 対象課題: {coursework_title}",
        f"- 未提出者数: {snapshot['missing_count']}",
        f"- 遅延提出者数: {snapshot['late_count']}",
        "",
        "## 提出状況",
        f"- 未提出者: {missing_names}",
        f"- 遅延提出者: {late_names}",
        "",
        "## AIによる提案",
        recommendation,
        "",
        "## 注意事項",
        teacher_note or "教師確認後に利用してください。",
    ]
    slug = course.name.lower().replace(" ", "_")
    return {
        "fileName": f"{slug}_report_20260703.md",
        "title": title,
        "content": "\n".join(lines),
    }


def build_pdf_report(
    *,
    title: str,
    course: Course,
    coursework: CourseWork | None,
    snapshot: dict[str, Any],
    recommendation: str,
    teacher_note: str = "",
) -> dict[str, Any]:
    rows = [
        [submission.student_name, "未提出", coursework.due_date if coursework else ""]
        for submission in snapshot["missing"]
    ] or [["なし", "-", coursework.due_date if coursework else ""]]
    return {
        "fileName": f"{course.name.lower().replace(' ', '_')}_report_20260703.pdf",
        "title": title,
        "layout": "report",
        "sections": [
            {
                "heading": "概要",
                "body": f"{course.name}の提出状況をまとめたレポートです。",
            },
            {
                "heading": "未提出者一覧",
                "table": {
                    "columns": ["生徒名", "状態", "締切"],
                    "rows": rows,
                },
            },
            {
                "heading": "AIによる提案",
                "body": recommendation,
            },
            {
                "heading": "注意事項",
                "body": teacher_note or "教師確認後に利用してください。",
            },
        ],
    }


def build_google_document_report(
    *,
    title: str,
    course: Course,
    coursework: CourseWork | None,
    snapshot: dict[str, Any],
    recommendation: str,
    teacher_note: str = "",
) -> dict[str, Any]:
    rows = [
        [submission.student_name, "未提出", coursework.due_date if coursework else ""]
        for submission in snapshot["missing"]
    ] or [["なし", "-", coursework.due_date if coursework else ""]]
    return {
        "title": f"{title} 2026-07-03",
        "documentType": "report",
        "blocks": [
            {"type": "heading1", "text": title},
            {
                "type": "paragraph",
                "text": f"{course.name}の提出状況をもとにAIが作成したレポートです。",
            },
            {"type": "heading2", "text": "未提出者一覧"},
            {
                "type": "table",
                "columns": ["生徒名", "状態", "締切"],
                "rows": rows,
            },
            {"type": "heading2", "text": "AIによる提案"},
            {"type": "paragraph", "text": recommendation},
            {"type": "heading2", "text": "注意事項"},
            {"type": "paragraph", "text": teacher_note or "教師確認後に利用してください。"},
        ],
    }


def build_error_summary(error_code: str, error_message: str, recoverable: bool) -> Summary:
    recommendations = {
        "CLASSROOM_API_PERMISSION_DENIED": "Googleアカウントの権限を確認し、再度実行してください。",
        "CLASSROOM_API_NOT_FOUND": "対象コースまたは課題の指定を確認してください。",
        "CLASSROOM_API_RATE_LIMITED": "時間を置いてから再試行してください。",
        "GOOGLE_AUTH_EXPIRED": "再ログインして認証を更新してください。",
        "AI_GENERATION_FAILED": "入力条件を見直し、必要なら短い指示にして再実行してください。",
        "INVALID_AGENT_OUTPUT": "生成結果の形式を確認し、再生成してください。",
    }
    return Summary(
        title="処理中にエラーが発生しました",
        short_summary=error_message,
        teacher_action_required=recoverable,
        recommended_action=recommendations.get(
            error_code,
            "入力条件と認証状態を確認したうえで再実行してください。",
        ),
    )


def build_agent_output(
    task_type: str,
    *,
    request_id: str,
    course: Course,
    coursework: CourseWork | None = None,
    submissions: Sequence[StudentSubmission] | None = None,
    tone: str = "polite",
    teacher_instruction: str = "",
    extra_notes: str = "",
    **kwargs: Any,
) -> AgentOutput:
    snapshot = build_submission_snapshot(submissions)
    snapshot["missing_count"] = len(snapshot["missing"])
    snapshot["submitted_count"] = len(snapshot["submitted"])
    snapshot["late_count"] = len(snapshot["late"])
    teacher_note = build_teacher_note(teacher_instruction, extra_notes)
    gui = {"cards": [], "tables": [], "warnings": [], "editableFields": []}
    outputs = {
        "markdown": None,
        "pdf": None,
        "googleDocument": None,
        "classroomReminder": None,
    }
    approval = Approval(required=False, reason="No approval required for this generated sample.", actions=[])
    errors: list[AgentError] = []
    course_name = course.name
    coursework_title = coursework.title if coursework else "課題"
    due_text = coursework.due_date if coursework and coursework.due_date else "期限未設定"
    tone_label = infer_tone_label(tone)
    recommendation = teacher_instruction.strip() or "内容を確認し、必要に応じて教師が調整してください。"

    summary = Summary(
        title=f"{course_name} {task_type}",
        short_summary=f"{course_name}向けに{task_type}の出力を生成しました。",
        teacher_action_required=task_type != "COURSE_SUMMARY",
        recommended_action=recommendation,
    )

    if task_type == "REMINDER_GENERATION":
        missing_count = snapshot["missing_count"]
        reminder_text = (
            f"{course_name}の課題「{coursework_title}」の提出期限は{due_text}です。"
            f"まだ提出していない人は、期限までに提出してください。"
        )
        if tone_label == "厳しめ":
            reminder_text = (
                f"{course_name}の課題「{coursework_title}」は{due_text}が締切です。"
                "未提出のままにせず、必ず期限内に提出してください。"
            )
        elif tone_label == "やさしい":
            reminder_text = (
                f"{course_name}の課題「{coursework_title}」の締切は{due_text}です。"
                "まだの人は、無理のない範囲で早めに提出してください。"
            )
        elif tone_label == "短文":
            reminder_text = f"課題「{coursework_title}」は{due_text}締切です。未提出の人は提出してください。"
        if teacher_instruction.strip():
            reminder_text = f"{reminder_text} {teacher_instruction.strip()}"
        summary = Summary(
            title="未提出課題リマインド案",
            short_summary=f"{course_name}の課題「{coursework_title}」に未提出者が{missing_count}名います。",
            teacher_action_required=True,
            recommended_action="本文を確認し、必要に応じて修正してから投稿してください。",
        )
        gui = {
            "cards": [
                {
                    "cardId": "card_missing_count",
                    "type": "metric",
                    "title": "未提出者数",
                    "value": str(missing_count),
                    "description": f"課題「{coursework_title}」の未提出者数です。",
                }
            ],
            "tables": [
                {
                    "tableId": "table_missing_students",
                    "title": "未提出者一覧",
                    "columns": [
                        {"key": "studentName", "label": "生徒名"},
                        {"key": "status", "label": "状態"},
                        {"key": "dueDate", "label": "締切"},
                    ],
                    "rows": [
                        row
                        for row in build_submission_rows(snapshot["missing"], coursework)
                    ],
                }
            ],
            "warnings": [
                {
                    "level": "medium",
                    "message": "個別の生徒名は教師確認画面でのみ扱い、投稿本文には含めないでください。",
                }
            ],
            "editableFields": [
                {
                    "fieldId": "reminder_body",
                    "label": "リマインド本文",
                    "type": "textarea",
                    "value": reminder_text,
                    "required": True,
                }
            ],
        }
        outputs["classroomReminder"] = {
            "target": {"courseId": course.course_id, "courseWorkId": coursework.course_work_id if coursework else ""},
            "postType": "announcement",
            "title": "課題提出リマインド",
            "text": reminder_text,
            "materials": [],
            "scheduledTime": None,
            "assigneeMode": "ALL_STUDENTS",
            "targetStudentIds": [],
            "requiresTeacherApproval": True,
        }
        approval = Approval(
            required=True,
            reason="Classroomへの投稿を行うため、教師の承認が必要です。",
            actions=[
                {
                    "actionId": "action_create_announcement",
                    "type": "CREATE_CLASSROOM_ANNOUNCEMENT",
                    "label": "Classroomにリマインドを投稿",
                    "requiresConfirmation": True,
                    "payloadRef": "outputs.classroomReminder",
                }
            ],
        )
    elif task_type == "COURSE_SUMMARY":
        summary = Summary(
            title=f"{course_name} コース概要",
            short_summary=f"{course_name}には{course.student_count}名の受講者がいます。",
            teacher_action_required=False,
            recommended_action="コース構成と公開状態を確認してください。",
        )
        gui = {
            "cards": [
                {
                    "cardId": "card_course_students",
                    "type": "metric",
                    "title": "受講者数",
                    "value": str(course.student_count),
                    "description": "現在の登録生徒数です。",
                },
                {
                    "cardId": "card_course_state",
                    "type": "status",
                    "title": "コース状態",
                    "value": course.state or "UNKNOWN",
                    "description": "Classroom上のコース状態です。",
                },
            ],
            "tables": [],
            "warnings": [],
            "editableFields": [],
        }
        outputs.update(
            {
                "markdown": build_markdown_report(
                    title=f"{course_name} コース概要",
                    course=course,
                    coursework=coursework,
                    snapshot=snapshot,
                    recommendation="コース情報と担当範囲を確認してください。",
                    teacher_note=teacher_note,
                ),
                "pdf": build_pdf_report(
                    title=f"{course_name} コース概要",
                    course=course,
                    coursework=coursework,
                    snapshot=snapshot,
                    recommendation="コース情報と担当範囲を確認してください。",
                    teacher_note=teacher_note,
                ),
                "googleDocument": build_google_document_report(
                    title=f"{course_name} コース概要",
                    course=course,
                    coursework=coursework,
                    snapshot=snapshot,
                    recommendation="コース情報と担当範囲を確認してください。",
                    teacher_note=teacher_note,
                ),
            }
        )
    elif task_type == "COURSEWORK_SUMMARY":
        summary = Summary(
            title=f"{coursework_title} 課題概要",
            short_summary=f"{coursework_title}の締切は{due_text}です。",
            teacher_action_required=True,
            recommended_action="締切と課題説明に問題がないか確認してください。",
        )
        gui = {
            "cards": [
                {
                    "cardId": "card_coursework_due",
                    "type": "metric",
                    "title": "締切",
                    "value": due_text,
                    "description": "課題の締切日です。",
                },
                {
                    "cardId": "card_coursework_points",
                    "type": "metric",
                    "title": "満点",
                    "value": str(coursework.max_points if coursework else ""),
                    "description": "設定された満点です。",
                },
            ],
            "tables": [],
            "warnings": [],
            "editableFields": [],
        }
    elif task_type == "SUBMISSION_ANALYSIS":
        summary = Summary(
            title="提出状況分析",
            short_summary=(
                f"{course_name}の課題「{coursework_title}」は"
                f"未提出{snapshot['missing_count']}名、遅延{snapshot['late_count']}名です。"
            ),
            teacher_action_required=True,
            recommended_action="未提出者の確認後、必要ならリマインドを作成してください。",
        )
        gui = {
            "cards": [
                {
                    "cardId": "card_submission_missing",
                    "type": "metric",
                    "title": "未提出者数",
                    "value": str(snapshot["missing_count"]),
                    "description": "未提出の生徒数です。",
                },
                {
                    "cardId": "card_submission_late",
                    "type": "metric",
                    "title": "遅延提出者数",
                    "value": str(snapshot["late_count"]),
                    "description": "遅延提出の生徒数です。",
                },
            ],
            "tables": [
                {
                    "tableId": "table_submission_status",
                    "title": "提出状況一覧",
                    "columns": [
                        {"key": "studentName", "label": "生徒名"},
                        {"key": "status", "label": "状態"},
                        {"key": "dueDate", "label": "締切"},
                    ],
                    "rows": build_submission_rows(submissions, coursework),
                }
            ],
            "warnings": [
                {
                    "level": "medium",
                    "message": "個別名を含むため、共有範囲を教師向けに限定してください。",
                }
            ],
            "editableFields": [],
        }
        outputs.update(
            {
                "markdown": build_markdown_report(
                    title=f"{course_name} 提出状況レポート",
                    course=course,
                    coursework=coursework,
                    snapshot=snapshot,
                    recommendation="未提出者の確認とリマインド対象の選定を進めてください。",
                    teacher_note=teacher_note,
                ),
                "pdf": build_pdf_report(
                    title=f"{course_name} 提出状況レポート",
                    course=course,
                    coursework=coursework,
                    snapshot=snapshot,
                    recommendation="未提出者の確認とリマインド対象の選定を進めてください。",
                    teacher_note=teacher_note,
                ),
                "googleDocument": build_google_document_report(
                    title=f"{course_name} 提出状況レポート",
                    course=course,
                    coursework=coursework,
                    snapshot=snapshot,
                    recommendation="未提出者の確認とリマインド対象の選定を進めてください。",
                    teacher_note=teacher_note,
                ),
            }
        )
    elif task_type == "WEEKLY_REPORT":
        summary = Summary(
            title="週次レポート",
            short_summary=(
                f"{course_name}では今週、未提出{snapshot['missing_count']}名、"
                f"遅延提出{snapshot['late_count']}名が確認されました。"
            ),
            teacher_action_required=True,
            recommended_action="今週の優先対応を確認し、必要な連絡文を確定してください。",
        )
        outputs.update(
            {
                "markdown": build_markdown_report(
                    title=f"{course_name} 週次レポート",
                    course=course,
                    coursework=coursework,
                    snapshot=snapshot,
                    recommendation="期限接近課題の再案内と未提出者フォローを優先してください。",
                    teacher_note=teacher_note,
                ),
                "pdf": build_pdf_report(
                    title=f"{course_name} 週次レポート",
                    course=course,
                    coursework=coursework,
                    snapshot=snapshot,
                    recommendation="期限接近課題の再案内と未提出者フォローを優先してください。",
                    teacher_note=teacher_note,
                ),
                "googleDocument": build_google_document_report(
                    title=f"{course_name} 週次レポート",
                    course=course,
                    coursework=coursework,
                    snapshot=snapshot,
                    recommendation="期限接近課題の再案内と未提出者フォローを優先してください。",
                    teacher_note=teacher_note,
                ),
            }
        )
    elif task_type == "ANNOUNCEMENT_DRAFT":
        announcement_text = (
            f"{course_name}の皆さんへ。課題「{coursework_title}」の締切は{due_text}です。"
            "必要な提出物を確認し、期限までに対応してください。"
        )
        if teacher_instruction.strip():
            announcement_text = f"{announcement_text} {teacher_instruction.strip()}"
        summary = Summary(
            title="お知らせ文案",
            short_summary=f"{course_name}向けのお知らせ文案を生成しました。",
            teacher_action_required=True,
            recommended_action="本文を確認し、公開範囲を決めてから投稿してください。",
        )
        gui["editableFields"] = [
            {
                "fieldId": "announcement_body",
                "label": "お知らせ本文",
                "type": "textarea",
                "value": announcement_text,
                "required": True,
            }
        ]
        outputs["classroomReminder"] = {
            "target": {"courseId": course.course_id, "courseWorkId": coursework.course_work_id if coursework else ""},
            "postType": "announcement",
            "title": f"{coursework_title}のお知らせ",
            "text": announcement_text,
            "materials": coursework.materials if coursework else [],
            "scheduledTime": None,
            "assigneeMode": "ALL_STUDENTS",
            "targetStudentIds": [],
            "requiresTeacherApproval": True,
        }
        approval = Approval(
            required=True,
            reason="Classroomへ投稿する操作が含まれています。",
            actions=[
                {
                    "actionId": "action_create_announcement",
                    "type": "CREATE_CLASSROOM_ANNOUNCEMENT",
                    "label": "Classroomにお知らせを投稿",
                    "requiresConfirmation": True,
                    "payloadRef": "outputs.classroomReminder",
                }
            ],
        )
    elif task_type == "DOCUMENT_EXPORT":
        summary = Summary(
            title="出力ドキュメント案",
            short_summary=f"{course_name}向けの出力データを整形しました。",
            teacher_action_required=True,
            recommended_action="用途に応じて Markdown、PDF、Google Document を選択してください。",
        )
        outputs.update(
            {
                "markdown": build_markdown_report(
                    title=f"{course_name} 出力ドキュメント",
                    course=course,
                    coursework=coursework,
                    snapshot=snapshot,
                    recommendation="共有前に機微情報の有無を確認してください。",
                    teacher_note=teacher_note,
                ),
                "pdf": build_pdf_report(
                    title=f"{course_name} 出力ドキュメント",
                    course=course,
                    coursework=coursework,
                    snapshot=snapshot,
                    recommendation="共有前に機微情報の有無を確認してください。",
                    teacher_note=teacher_note,
                ),
                "googleDocument": build_google_document_report(
                    title=f"{course_name} 出力ドキュメント",
                    course=course,
                    coursework=coursework,
                    snapshot=snapshot,
                    recommendation="共有前に機微情報の有無を確認してください。",
                    teacher_note=teacher_note,
                ),
            }
        )
    elif task_type == "RUBRIC_SUPPORT":
        summary = Summary(
            title="ルーブリック補助案",
            short_summary=f"{coursework_title}向けの評価観点案を整理しました。",
            teacher_action_required=True,
            recommended_action="授業目的に合う観点だけを採用してください。",
        )
        outputs["markdown"] = {
            "fileName": "rubric_support_20260703.md",
            "title": f"{coursework_title} ルーブリック補助",
            "content": "\n".join(
                [
                    f"# {coursework_title} ルーブリック補助",
                    "",
                    "## 提案観点",
                    "- 内容理解",
                    "- 根拠の明確さ",
                    "- 提出形式の遵守",
                    "",
                    "## 注意事項",
                    teacher_note or "最終的な評価観点は教師が確定してください。",
                ]
            ),
        }
    elif task_type == "ERROR_ANALYSIS":
        errors = [
            AgentError(
                code=str(kwargs.get("error_code", "AI_GENERATION_FAILED")),
                message=str(kwargs.get("error_message", "AI output could not be generated.")),
                recoverable=bool(kwargs.get("recoverable", True)),
            )
        ]
        summary = build_error_summary(
            errors[0].code,
            errors[0].message,
            errors[0].recoverable,
        )
        return AgentOutput(
            request_id=request_id,
            generated_at="2026-07-03T13:00:00+09:00",
            agent_task_type=task_type,
            status="error",
            course=course,
            summary=summary,
            gui=gui,
            outputs=outputs,
            approval=approval,
            errors=errors,
        )

    return AgentOutput(
        request_id=request_id,
        generated_at="2026-07-03T13:00:00+09:00",
        agent_task_type=task_type,
        status="success",
        course=course,
        summary=summary,
        gui=gui,
        outputs=outputs,
        approval=approval,
        errors=errors,
    )


def validate_agent_output_dict(payload: dict[str, Any]) -> list[str]:
    missing = COMMON_TOP_LEVEL_KEYS - payload.keys()
    errors: list[str] = []
    if missing:
        errors.append("missing required top-level keys: " + ", ".join(sorted(missing)))
        return errors
    if payload.get("schemaVersion") != "1.0.0":
        errors.append("unsupported schemaVersion")
    if payload.get("agentTaskType") not in ALLOWED_AGENT_TASK_TYPES:
        errors.append("unsupported agentTaskType")
    if payload.get("status") not in {"success", "error"}:
        errors.append("unsupported status")
    if not isinstance(payload.get("course"), dict):
        errors.append("course must be an object")
    if not isinstance(payload.get("gui"), dict):
        errors.append("gui must be an object")
    if not isinstance(payload.get("outputs"), dict):
        errors.append("outputs must be an object")
    if not isinstance(payload.get("approval"), dict):
        errors.append("approval must be an object")
    if not isinstance(payload.get("errors"), list):
        errors.append("errors must be an array")
    elif payload.get("status") == "error" and not payload["errors"]:
        errors.append("errors must be non-empty when status is error")
    return errors


def collect_cache_artifacts(repo_root: Path) -> list[Path]:
    artifacts: list[Path] = []
    for path in repo_root.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.name == CACHE_DIR_NAME and path.is_dir():
            artifacts.append(path)
            continue
        if path.is_file() and path.suffix in {".pyc", ".pyo"}:
            artifacts.append(path)
    return sorted(artifacts)


def remove_cache_artifacts(paths: Sequence[Path]) -> list[str]:
    removed: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(str(path))
    return removed

def validate_common_contract(payload: dict[str, Any]) -> list[str]:
    issues = validate_agent_output_dict(payload)

    missing_top_level = COMMON_TOP_LEVEL_KEYS - payload.keys()
    if missing_top_level:
        issues.append(
            "missing common top-level keys: "
            + ", ".join(sorted(missing_top_level))
        )

    course = payload.get("course")
    if not isinstance(course, dict):
        issues.append("course must be an object")

    gui = payload.get("gui")
    if not isinstance(gui, dict):
        issues.append("gui must be an object")
    else:
        missing_gui = COMMON_GUI_KEYS - gui.keys()
        if missing_gui:
            issues.append("gui missing keys: " + ", ".join(sorted(missing_gui)))

    outputs = payload.get("outputs")
    if not isinstance(outputs, dict):
        issues.append("outputs must be an object")
    else:
        missing_outputs = COMMON_OUTPUT_KEYS - outputs.keys()
        if missing_outputs:
            issues.append(
                "outputs missing keys: " + ", ".join(sorted(missing_outputs))
            )

    approval = payload.get("approval")
    if not isinstance(approval, dict):
        issues.append("approval must be an object")
    else:
        missing_approval = COMMON_APPROVAL_KEYS - approval.keys()
        if missing_approval:
            issues.append(
                "approval missing keys: " + ", ".join(sorted(missing_approval))
            )

    errors = payload.get("errors")
    if not isinstance(errors, list):
        issues.append("errors must be an array")

    return issues


def run_command(args: Sequence[str], *, repo_root: Path) -> tuple[int, str]:
    pythonpath = os.environ.get("PYTHONPATH", "")
    pythonpath_parts = [str(repo_root)]
    if pythonpath:
        pythonpath_parts.append(pythonpath)
    try:
        completed = subprocess.run(
            list(args),
            cwd=repo_root,
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": os.pathsep.join(pythonpath_parts),
            },
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        return 127, str(exc)
    output = completed.stdout.strip()
    if completed.stderr.strip():
        output = f"{output}\n{completed.stderr.strip()}".strip()
    return completed.returncode, output


def run_pytest(repo_root: Path) -> CheckResult:
    returncode, output = run_command([sys.executable, "-m", "pytest", "-q"], repo_root=repo_root)
    if returncode != 0 and "No module named pytest" in output:
        returncode, output = run_command(["pytest", "-q"], repo_root=repo_root)
    return CheckResult(name="pytest", passed=returncode == 0, details=[output or "pytest completed without output"])


def run_cli_contract_checks(tool_root: Path) -> CheckResult:
    details: list[str] = []
    passed = True
    for command in (
        ["scripts/review_implementation_agent.py", "--help"],
        ["scripts/pr_automation.py", "--help"],
    ):
        returncode, output = run_command([sys.executable, *command], repo_root=tool_root)
        command_name = " ".join(command)
        if returncode != 0:
            passed = False
            details.append(f"{command_name}: command failed")
            if output:
                details.append(output)
            continue
        if "usage:" not in output.lower():
            passed = False
            details.append(f"{command_name}: help output missing usage text")
        else:
            details.append(f"{command_name}: help output valid")
    return CheckResult(name="cli-contract", passed=passed, details=details)


def validate_common_contract(payload: dict[str, Any]) -> list[str]:
    issues = validate_agent_output_dict(payload)
    missing_top_level = COMMON_TOP_LEVEL_KEYS - payload.keys()
    if missing_top_level:
        issues.append("missing common top-level keys: " + ", ".join(sorted(missing_top_level)))
    course = payload.get("course")
    if not isinstance(course, dict):
        issues.append("course must be an object")
    gui = payload.get("gui")
    if not isinstance(gui, dict):
        issues.append("gui must be an object")
    elif COMMON_GUI_KEYS - gui.keys():
        issues.append("gui missing keys: " + ", ".join(sorted(COMMON_GUI_KEYS - gui.keys())))
    outputs = payload.get("outputs")
    if not isinstance(outputs, dict):
        issues.append("outputs must be an object")
    elif COMMON_OUTPUT_KEYS - outputs.keys():
        issues.append("outputs missing keys: " + ", ".join(sorted(COMMON_OUTPUT_KEYS - outputs.keys())))
    approval = payload.get("approval")
    if not isinstance(approval, dict):
        issues.append("approval must be an object")
    elif COMMON_APPROVAL_KEYS - approval.keys():
        issues.append("approval missing keys: " + ", ".join(sorted(COMMON_APPROVAL_KEYS - approval.keys())))
    errors = payload.get("errors")
    if not isinstance(errors, list):
        issues.append("errors must be an array")
    return issues


def run_agent_task_contract_checks() -> CheckResult:
    course, coursework, submissions = build_sample_context()
    details: list[str] = []
    passed = True
    for task_type in sorted(ALLOWED_AGENT_TASK_TYPES):
        payload = build_agent_output(
            task_type,
            request_id=f"req_{task_type.lower()}",
            course=course,
            coursework=coursework,
            submissions=submissions,
            tone="polite",
            teacher_instruction="必要があれば補足してください。",
            extra_notes="自動レビュー用のサンプルです。",
        ).to_dict()
        issues = validate_common_contract(payload)
        if issues:
            passed = False
            details.append(f"{task_type}: " + "; ".join(issues))
        else:
            details.append(f"{task_type}: contract valid")
    return CheckResult(name="agent-contract", passed=passed, details=details)


def is_git_ignored(repo_root: Path, path: Path) -> bool:
    try:
        relative_path = path.relative_to(repo_root)
    except ValueError:
        relative_path = path
    completed = subprocess.run(
        ["git", "check-ignore", "-q", "--", str(relative_path)],
        cwd=repo_root,
        check=False,
    )
    return completed.returncode == 0


def run_repo_hygiene_check(repo_root: Path) -> CheckResult:
    artifacts = [
        path
        for path in collect_cache_artifacts(repo_root)
        if not is_git_ignored(repo_root, path)
    ]
    if not artifacts:
        return CheckResult(name="repo-hygiene", passed=True, details=["no cache artifacts detected"])
    return CheckResult(
        name="repo-hygiene",
        passed=False,
        details=[f"remove cache artifact: {path}" for path in artifacts],
    )

def build_report(repo_root: Path, *, apply_fixes: bool, tool_root: Path | None = None) -> AutomationReport:
    tool_root = tool_root or repo_root
    fixes_applied: list[str] = []
    if apply_fixes:
        cache_artifacts = collect_cache_artifacts(repo_root)
        removed = remove_cache_artifacts(cache_artifacts)
        fixes_applied.extend(f"removed {path}" for path in removed)
    checks = [
        run_repo_hygiene_check(repo_root),
        run_pytest(repo_root),
        run_cli_contract_checks(tool_root),
        run_agent_task_contract_checks(),
    ]

    if apply_fixes:
        cache_artifacts = collect_cache_artifacts(repo_root)
        removed = remove_cache_artifacts(cache_artifacts)
        fixes_applied.extend(f"removed {path}" for path in removed)

    return AutomationReport(fixes_applied=fixes_applied, checks=checks)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pr-automation")
    parser.add_argument("--apply-fixes", action="store_true")
    parser.add_argument("--report-path", default="")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--tool-root", default="")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    tool_root = Path(args.tool_root).resolve() if args.tool_root else repo_root
    report = build_report(repo_root, apply_fixes=args.apply_fixes, tool_root=tool_root)
    markdown = report.to_markdown()
    if args.report_path:
        report_path = Path(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
