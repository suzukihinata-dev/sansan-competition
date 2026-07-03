from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .contracts import (
    AgentError,
    AgentOutput,
    Approval,
    ApprovalAction,
    ClassroomReminder,
    Course,
    CourseWork,
    EditableField,
    GuiCard,
    GuiTable,
    GuiTableColumn,
    GuiWarning,
    GoogleDocumentOutput,
    MarkdownOutput,
    PdfOutput,
    Summary,
    StudentSubmission,
    count_states,
    normalize_due_datetime,
    now_jst_iso,
)


def build_course_summary_output(
    *,
    request_id: str,
    course: Course,
    coursework: CourseWork,
    submissions: list[StudentSubmission],
) -> AgentOutput:
    counts = count_states(submissions)
    summary = Summary(
        title="課題概要の整理",
        short_summary=(
            f"{course.name} の課題「{coursework.title}」について、"
            f"提出済み {counts['submitted']} 件、未提出 {counts['missing']} 件です。"
        ),
        teacher_action_required=counts["missing"] > 0,
        recommended_action=(
            "未提出者へのリマインドを検討してください。"
            if counts["missing"] > 0
            else "提出状況は安定しています。"
        ),
    )
    gui = {
        "cards": [
            GuiCard(
                card_id="card_submitted",
                type="metric",
                title="提出済み",
                value=str(counts["submitted"]),
                description="提出済みの件数です。",
            ).to_dict(),
            GuiCard(
                card_id="card_missing",
                type="metric",
                title="未提出",
                value=str(counts["missing"]),
                description="未提出の件数です。",
            ).to_dict(),
        ],
        "tables": [],
        "warnings": [],
        "editableFields": [],
    }
    outputs = {
        "markdown": _build_markdown_output(course, coursework, submissions, counts).to_dict(),
        "pdf": _build_pdf_output(course, coursework, submissions, counts).to_dict(),
        "googleDocument": _build_google_document_output(course, coursework, submissions, counts).to_dict(),
        "classroomReminder": None,
    }
    approval = Approval(
        required=False,
        reason="コース概要の整理のみで、Classroomへの投稿は含みません。",
        actions=[
            ApprovalAction(
                action_id="action_export_markdown",
                type="EXPORT_MARKDOWN",
                label="Markdownとして出力",
                requires_confirmation=False,
                payload_ref="outputs.markdown",
            ),
            ApprovalAction(
                action_id="action_export_pdf",
                type="EXPORT_PDF",
                label="PDFとして出力",
                requires_confirmation=False,
                payload_ref="outputs.pdf",
            ),
        ],
    )
    return AgentOutput(
        request_id=request_id,
        generated_at=now_jst_iso(),
        agent_task_type="COURSE_SUMMARY",
        status="success",
        course=course,
        summary=summary,
        gui=gui,
        outputs=outputs,
        approval=approval,
    )


def build_reminder_generation_output(
    *,
    request_id: str,
    course: Course,
    coursework: CourseWork,
    submissions: list[StudentSubmission],
    tone: str = "polite",
    teacher_instruction: str = "",
) -> AgentOutput:
    counts = count_states(submissions)
    missing_students = [submission for submission in submissions if submission.state not in {"TURNED_IN", "RETURNED"}]
    due = normalize_due_datetime(coursework.due_date, coursework.due_time)
    reminder_text = _build_reminder_text(
        course_name=course.name,
        coursework_title=coursework.title,
        missing_count=counts["missing"],
        due=due,
        tone=tone,
        teacher_instruction=teacher_instruction,
    )
    summary = Summary(
        title="未提出課題リマインド案",
        short_summary=(
            f"{course.name} の課題「{coursework.title}」に未提出者が {counts['missing']} 名います。"
        ),
        teacher_action_required=True,
        recommended_action="内容を確認し、必要に応じてClassroomへ投稿してください。",
    )
    gui = {
        "cards": [
            GuiCard(
                card_id="card_missing",
                type="metric",
                title="未提出者数",
                value=str(counts["missing"]),
                description=f"課題「{coursework.title}」の未提出者数です。",
            ).to_dict(),
            GuiCard(
                card_id="card_late",
                type="metric",
                title="遅延提出",
                value=str(counts["late"]),
                description="遅延提出として扱われる件数です。",
            ).to_dict(),
        ],
        "tables": [
            GuiTable(
                table_id="table_missing_students",
                title="未提出者一覧",
                columns=[
                    GuiTableColumn(key="studentName", label="生徒名"),
                    GuiTableColumn(key="status", label="状態"),
                    GuiTableColumn(key="dueDate", label="締切"),
                ],
                rows=[
                    {
                        "studentName": submission.student_name,
                        "status": "未提出" if not submission.late else "遅延提出",
                        "dueDate": coursework.due_date,
                    }
                    for submission in missing_students
                ],
            ).to_dict()
        ],
        "warnings": [
            GuiWarning(
                level="medium",
                message="個別の生徒名を含むため、共有範囲に注意してください。",
            ).to_dict()
        ]
        if missing_students
        else [],
        "editableFields": [
            EditableField(
                field_id="reminder_body",
                label="リマインド本文",
                type="textarea",
                value=reminder_text,
                required=True,
            ).to_dict()
        ],
    }
    outputs = {
        "markdown": _build_markdown_output(course, coursework, submissions, counts, reminder_text).to_dict(),
        "pdf": _build_pdf_output(course, coursework, submissions, counts, reminder_text).to_dict(),
        "googleDocument": _build_google_document_output(course, coursework, submissions, counts, reminder_text).to_dict(),
        "classroomReminder": ClassroomReminder(
            target={"courseId": course.course_id, "courseWorkId": coursework.course_work_id},
            post_type="announcement",
            title="課題提出リマインド",
            text=reminder_text,
        ).to_dict(),
    }
    approval = Approval(
        required=True,
        reason="Classroomへの投稿を行うため、教師の承認が必要です。",
        actions=[
            ApprovalAction(
                action_id="action_create_announcement",
                type="CREATE_CLASSROOM_ANNOUNCEMENT",
                label="Classroomにリマインドを投稿",
                requires_confirmation=True,
                payload_ref="outputs.classroomReminder",
            ),
            ApprovalAction(
                action_id="action_export_markdown",
                type="EXPORT_MARKDOWN",
                label="Markdownとして出力",
                requires_confirmation=False,
                payload_ref="outputs.markdown",
            ),
        ],
    )
    return AgentOutput(
        request_id=request_id,
        generated_at=now_jst_iso(),
        agent_task_type="REMINDER_GENERATION",
        status="success",
        course=course,
        summary=summary,
        gui=gui,
        outputs=outputs,
        approval=approval,
    )


def build_error_output(
    *,
    request_id: str,
    task_type: str,
    title: str,
    short_summary: str,
    recommended_action: str,
    error_code: str,
    error_message: str,
    recoverable: bool,
) -> AgentOutput:
    return AgentOutput(
        request_id=request_id,
        generated_at=now_jst_iso(),
        agent_task_type=task_type,  # type: ignore[arg-type]
        status="error",
        summary=Summary(
            title=title,
            short_summary=short_summary,
            teacher_action_required=True,
            recommended_action=recommended_action,
        ),
        errors=[AgentError(code=error_code, message=error_message, recoverable=recoverable)],
    )


def _build_reminder_text(
    *,
    course_name: str,
    coursework_title: str,
    missing_count: int,
    due: str,
    tone: str,
    teacher_instruction: str,
) -> str:
    base = [
        f"{course_name} の課題「{coursework_title}」についてお知らせします。",
        f"提出期限は {due} です。",
    ]
    if missing_count > 0:
        base.append(f"まだ提出できていない人は、期限までに提出してください。")
    else:
        base.append("提出状況は良好です。")

    if tone == "strict":
        base.append("期限を過ぎないよう、必ず確認してください。")
    elif tone == "short":
        base = [
            f"{course_name} の課題「{coursework_title}」は {due} が締切です。",
            "未提出の人は早めに提出してください。",
        ]
    else:
        base.append("ご不明点があれば教師へ確認してください。")

    if teacher_instruction.strip():
        base.append(f"補足: {teacher_instruction.strip()}")

    return " ".join(base)


def _build_markdown_output(
    course: Course,
    coursework: CourseWork,
    submissions: list[StudentSubmission],
    counts: dict[str, int],
    reminder_text: str | None = None,
) -> MarkdownOutput:
    lines = [
        f"# {course.name} {coursework.title}",
        "",
        "## 概要",
        f"- 提出済み: {counts['submitted']}",
        f"- 未提出: {counts['missing']}",
        f"- 遅延提出: {counts['late']}",
        "",
        "## 対象課題",
        f"- 課題名: {coursework.title}",
        f"- 締切: {normalize_due_datetime(coursework.due_date, coursework.due_time)}",
        "",
        "## 未提出者一覧",
    ]
    if submissions:
        for submission in submissions:
            if submission.state not in {"TURNED_IN", "RETURNED"}:
                lines.append(f"- {submission.student_name} / {'遅延提出' if submission.late else '未提出'}")
    else:
        lines.append("- 取得データなし")

    if reminder_text:
        lines.extend(["", "## リマインド案", reminder_text])

    lines.extend(
        [
            "",
            "## 注意事項",
            "- 本文は教師確認後にのみClassroomへ投稿してください。",
        ]
    )
    return MarkdownOutput(
        file_name="report.md",
        title=f"{course.name} {coursework.title} レポート",
        content="\n".join(lines),
    )


def _build_pdf_output(
    course: Course,
    coursework: CourseWork,
    submissions: list[StudentSubmission],
    counts: dict[str, int],
    reminder_text: str | None = None,
) -> PdfOutput:
    sections: list[dict[str, Any]] = [
        {
            "heading": "概要",
            "body": f"{course.name} の課題「{coursework.title}」の提出状況をまとめたレポートです。",
        },
        {
            "heading": "提出状況",
            "table": {
                "columns": ["提出済み", "未提出", "遅延提出"],
                "rows": [[str(counts["submitted"]), str(counts["missing"]), str(counts["late"])]],
            },
        },
    ]
    if reminder_text:
        sections.append({"heading": "リマインド案", "body": reminder_text})
    if submissions:
        sections.append(
            {
                "heading": "未提出者一覧",
                "table": {
                    "columns": ["生徒名", "状態", "締切"],
                    "rows": [
                        [
                            submission.student_name,
                            "遅延提出" if submission.late else "未提出",
                            coursework.due_date,
                        ]
                        for submission in submissions
                        if submission.state not in {"TURNED_IN", "RETURNED"}
                    ],
                },
            }
        )
    return PdfOutput(
        file_name="report.pdf",
        title=f"{course.name} {coursework.title} レポート",
        layout="report",
        sections=sections,
    )


def _build_google_document_output(
    course: Course,
    coursework: CourseWork,
    submissions: list[StudentSubmission],
    counts: dict[str, int],
    reminder_text: str | None = None,
) -> GoogleDocumentOutput:
    blocks: list[dict[str, Any]] = [
        {"type": "heading1", "text": f"{course.name} {coursework.title}"},
        {
            "type": "paragraph",
            "text": "このドキュメントは、Google Classroom の情報をもとに AI が作成したレポートです。",
        },
        {"type": "heading2", "text": "提出状況"},
        {
            "type": "table",
            "columns": ["提出済み", "未提出", "遅延提出"],
            "rows": [[str(counts["submitted"]), str(counts["missing"]), str(counts["late"])]],
        },
    ]
    if reminder_text:
        blocks.extend(
            [
                {"type": "heading2", "text": "リマインド案"},
                {"type": "paragraph", "text": reminder_text},
            ]
        )
    if submissions:
        blocks.extend(
            [
                {"type": "heading2", "text": "未提出者一覧"},
                {
                    "type": "table",
                    "columns": ["生徒名", "状態", "締切"],
                    "rows": [
                        [
                            submission.student_name,
                            "遅延提出" if submission.late else "未提出",
                            coursework.due_date,
                        ]
                        for submission in submissions
                        if submission.state not in {"TURNED_IN", "RETURNED"}
                    ],
                },
            ]
        )
    return GoogleDocumentOutput(
        title=f"{course.name} {coursework.title} レポート",
        document_type="report",
        blocks=blocks,
    )
