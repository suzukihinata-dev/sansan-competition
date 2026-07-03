from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .models import (
    AgentTaskType,
    Course,
    JST,
    ResponseStatus,
    SubmissionAnalysis,
)
from .outputs import build_reminder_outputs, build_submission_report_outputs

SCHEMA_VERSION = "1.0.0"
STANDARD_ERROR_CODES = {
    "CLASSROOM_API_PERMISSION_DENIED",
    "CLASSROOM_API_NOT_FOUND",
    "CLASSROOM_API_RATE_LIMITED",
    "GOOGLE_AUTH_EXPIRED",
    "AI_GENERATION_FAILED",
    "INVALID_AGENT_OUTPUT",
    "DOCUMENT_EXPORT_FAILED",
    "PDF_EXPORT_FAILED",
    "CLASSROOM_POST_FAILED",
    "PARTIAL_CLASSROOM_DATA",
    "NORMALIZATION_FAILED",
}


def schema_file_path() -> Path:
    return Path(__file__).resolve().parent.parent / "schemas" / "agent-output-v1.0.0.json"


def load_contract_schema() -> dict[str, Any]:
    return json.loads(schema_file_path().read_text())


def build_submission_analysis_response(
    request_id: str,
    analysis: SubmissionAnalysis,
) -> dict[str, Any]:
    status = (
        ResponseStatus.PARTIAL_SUCCESS
        if analysis.normalization_issues
        else ResponseStatus.SUCCESS
    )
    counts = analysis.counts()
    response = {
        "schemaVersion": SCHEMA_VERSION,
        "requestId": request_id,
        "generatedAt": analysis.generated_at.isoformat(timespec="seconds"),
        "agentTaskType": AgentTaskType.SUBMISSION_ANALYSIS.value,
        "status": status.value,
        "course": analysis.course.to_contract(),
        "summary": {
            "title": f"{analysis.course_work.title} の提出状況分析",
            "shortSummary": (
                f"{analysis.course_work.title} の未提出者は "
                f"{counts['unsubmittedCount']}名、遅延提出者は {counts['lateCount']}名です。"
            ),
            "teacherActionRequired": analysis.teacher_action_required(),
            "recommendedAction": analysis.recommended_action(),
        },
        "gui": {
            "cards": _build_metric_cards(analysis),
            "tables": [_build_submission_table(analysis)],
            "warnings": _build_warnings(analysis),
            "editableFields": [],
        },
        "outputs": build_submission_report_outputs(analysis),
        "approval": {
            "required": False,
            "reason": "Classroom投稿を含まないため、教師承認は不要です。",
            "actions": [
                _approval_action(
                    action_id="action_export_markdown",
                    action_type="EXPORT_MARKDOWN",
                    label="Markdownとして出力",
                    payload_ref="outputs.markdown",
                ),
                _approval_action(
                    action_id="action_export_pdf",
                    action_type="EXPORT_PDF",
                    label="PDFとして出力",
                    payload_ref="outputs.pdf",
                ),
                _approval_action(
                    action_id="action_export_google_doc",
                    action_type="EXPORT_GOOGLE_DOCUMENT",
                    label="Google Documentとして出力",
                    payload_ref="outputs.googleDocument",
                ),
            ],
        },
        "errors": [
            {
                "code": issue.code,
                "message": issue.message,
                "recoverable": issue.recoverable,
            }
            for issue in analysis.normalization_issues
        ],
    }
    return response


def build_reminder_generation_response(
    request_id: str,
    analysis: SubmissionAnalysis,
    *,
    reminder_title: str,
    reminder_body: str,
    tone: str = "polite",
    target_student_ids: list[str] | None = None,
    scheduled_time: str | None = None,
) -> dict[str, Any]:
    status = (
        ResponseStatus.PARTIAL_SUCCESS
        if analysis.normalization_issues
        else ResponseStatus.SUCCESS
    )
    targets = analysis.unsubmitted
    target_ids = target_student_ids or []
    response = {
        "schemaVersion": SCHEMA_VERSION,
        "requestId": request_id,
        "generatedAt": analysis.generated_at.isoformat(timespec="seconds"),
        "agentTaskType": AgentTaskType.REMINDER_GENERATION.value,
        "status": status.value,
        "course": analysis.course.to_contract(),
        "summary": {
            "title": reminder_title,
            "shortSummary": (
                f"{analysis.course_work.title} の未提出者 {len(targets)}名に向けた"
                "リマインド案です。"
            ),
            "teacherActionRequired": True,
            "recommendedAction": "内容を確認し、必要に応じて教師承認後に投稿してください。",
        },
        "gui": {
            "cards": _build_metric_cards(analysis),
            "tables": [_build_submission_table(analysis, only_targets=True)],
            "warnings": _build_warnings(analysis, include_privacy_warning=True),
            "editableFields": [
                {
                    "fieldId": "reminder_title",
                    "label": "リマインドタイトル",
                    "type": "text",
                    "value": reminder_title,
                    "required": True,
                },
                {
                    "fieldId": "reminder_body",
                    "label": "リマインド本文",
                    "type": "textarea",
                    "value": reminder_body,
                    "required": True,
                },
            ],
        },
        "outputs": build_reminder_outputs(
            analysis,
            reminder_title=reminder_title,
            reminder_body=reminder_body,
            tone=tone,
            target_student_ids=target_ids,
            scheduled_time=scheduled_time,
        ),
        "approval": {
            "required": True,
            "reason": "Classroomへの投稿を行うため、教師の承認が必要です。",
            "actions": [
                _approval_action(
                    action_id="action_create_classroom_announcement",
                    action_type="CREATE_CLASSROOM_ANNOUNCEMENT",
                    label="Classroomにリマインドを投稿",
                    payload_ref="outputs.classroomReminder",
                    requires_confirmation=True,
                ),
                _approval_action(
                    action_id="action_export_markdown",
                    action_type="EXPORT_MARKDOWN",
                    label="Markdownとして出力",
                    payload_ref="outputs.markdown",
                ),
                _approval_action(
                    action_id="action_export_pdf",
                    action_type="EXPORT_PDF",
                    label="PDFとして出力",
                    payload_ref="outputs.pdf",
                ),
            ],
        },
        "errors": [
            {
                "code": issue.code,
                "message": issue.message,
                "recoverable": issue.recoverable,
            }
            for issue in analysis.normalization_issues
        ],
    }
    return response


def build_error_response(
    request_id: str,
    agent_task_type: AgentTaskType | str,
    *,
    title: str,
    short_summary: str,
    recommended_action: str,
    error_code: str,
    error_message: str,
    recoverable: bool = True,
    course: Course | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    resolved_task = AgentTaskType(agent_task_type)
    timestamp = generated_at or datetime.now(JST)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "requestId": request_id,
        "generatedAt": timestamp.isoformat(timespec="seconds"),
        "agentTaskType": resolved_task.value,
        "status": ResponseStatus.ERROR.value,
        "course": course.to_contract() if course else None,
        "summary": {
            "title": title,
            "shortSummary": short_summary,
            "teacherActionRequired": True,
            "recommendedAction": recommended_action,
        },
        "gui": {
            "cards": [],
            "tables": [],
            "warnings": [],
            "editableFields": [],
        },
        "outputs": {
            "markdown": None,
            "pdf": None,
            "googleDocument": None,
            "classroomReminder": None,
        },
        "approval": {
            "required": False,
            "reason": "失敗レスポンスのため承認操作はありません。",
            "actions": [],
        },
        "errors": [
            {
                "code": error_code,
                "message": error_message,
                "recoverable": recoverable,
            }
        ],
    }


def validate_agent_output(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if not isinstance(payload, dict):
        return ["Payload must be an object."]

    _require_string(payload, "schemaVersion", errors)
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        errors.append(f"schemaVersion must be {SCHEMA_VERSION}.")

    _require_string(payload, "requestId", errors)
    _require_string(payload, "generatedAt", errors)
    _require_iso_datetime(payload.get("generatedAt"), "generatedAt", errors)

    _require_string(payload, "agentTaskType", errors)
    if payload.get("agentTaskType") not in {member.value for member in AgentTaskType}:
        errors.append("agentTaskType is not a supported value.")

    _require_string(payload, "status", errors)
    if payload.get("status") not in {member.value for member in ResponseStatus}:
        errors.append("status is not a supported value.")

    course = payload.get("course")
    if course is not None:
        _validate_course(course, errors)

    _validate_summary(payload.get("summary"), errors)
    _validate_gui(payload.get("gui"), errors)
    _validate_outputs(payload.get("outputs"), errors)
    _validate_approval(payload.get("approval"), errors)
    _validate_errors(payload.get("errors"), errors)

    status = payload.get("status")
    if status == ResponseStatus.ERROR.value and not payload.get("errors"):
        errors.append("errors must contain at least one item when status=error.")

    outputs = payload.get("outputs") or {}
    approval = payload.get("approval") or {}
    if outputs.get("classroomReminder") is not None and not approval.get("required", False):
        errors.append(
            "approval.required must be true when outputs.classroomReminder is present."
        )

    return errors


def _build_metric_cards(analysis: SubmissionAnalysis) -> list[dict[str, Any]]:
    counts = analysis.counts()
    return [
        {
            "cardId": "card_unsubmitted_count",
            "type": "metric",
            "title": "未提出者数",
            "value": str(counts["unsubmittedCount"]),
            "description": f"{analysis.course_work.title} の未提出者数です。",
        },
        {
            "cardId": "card_due_soon_count",
            "type": "metric",
            "title": "期限接近者数",
            "value": str(counts["dueSoonCount"]),
            "description": "締切が近い未提出者数です。",
        },
        {
            "cardId": "card_late_count",
            "type": "metric",
            "title": "遅延提出者数",
            "value": str(counts["lateCount"]),
            "description": "締切後に提出された件数です。",
        },
    ]


def _build_submission_table(
    analysis: SubmissionAnalysis,
    *,
    only_targets: bool = False,
) -> dict[str, Any]:
    rows = analysis.unsubmitted if only_targets else analysis.evaluations
    return {
        "tableId": "table_submission_status",
        "title": "提出状況一覧" if not only_targets else "リマインド対象一覧",
        "columns": [
            {"key": "studentName", "label": "生徒名"},
            {"key": "status", "label": "状態"},
            {"key": "dueDate", "label": "締切"},
            {"key": "submittedAt", "label": "提出日時"},
            {"key": "notes", "label": "備考"},
        ],
        "rows": [entry.to_table_row() for entry in rows],
    }


def _build_warnings(
    analysis: SubmissionAnalysis,
    *,
    include_privacy_warning: bool = False,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []

    if analysis.attachment_flags:
        warnings.append(
            {
                "level": "medium",
                "message": (
                    "添付不足の可能性がある提出物があります。"
                    "必ず実際の提出内容を確認してください。"
                ),
            }
        )
    if analysis.normalization_issues:
        warnings.append(
            {
                "level": "high",
                "message": (
                    "一部データの正規化に失敗しました。"
                    "集計結果が完全でない可能性があります。"
                ),
            }
        )
    if include_privacy_warning:
        warnings.append(
            {
                "level": "medium",
                "message": (
                    "生徒個人名を含むため、共有範囲と投稿本文の内容に注意してください。"
                ),
            }
        )

    return warnings


def _approval_action(
    *,
    action_id: str,
    action_type: str,
    label: str,
    payload_ref: str,
    requires_confirmation: bool = False,
) -> dict[str, Any]:
    return {
        "actionId": action_id,
        "type": action_type,
        "label": label,
        "requiresConfirmation": requires_confirmation,
        "payloadRef": payload_ref,
    }


def _validate_course(course: Any, errors: list[str]) -> None:
    if not isinstance(course, dict):
        errors.append("course must be an object or null.")
        return
    for key in ("courseId", "name", "section", "description", "state"):
        _require_string(course, key, errors, prefix="course")
    _require_list(course, "teacherIds", errors, prefix="course")
    if not isinstance(course.get("studentCount"), int):
        errors.append("course.studentCount must be an integer.")


def _validate_summary(summary: Any, errors: list[str]) -> None:
    if not isinstance(summary, dict):
        errors.append("summary must be an object.")
        return
    _require_string(summary, "title", errors, prefix="summary")
    _require_string(summary, "shortSummary", errors, prefix="summary")
    if not isinstance(summary.get("teacherActionRequired"), bool):
        errors.append("summary.teacherActionRequired must be a boolean.")
    _require_string(summary, "recommendedAction", errors, prefix="summary")


def _validate_gui(gui: Any, errors: list[str]) -> None:
    if not isinstance(gui, dict):
        errors.append("gui must be an object.")
        return
    for key in ("cards", "tables", "warnings", "editableFields"):
        _require_list(gui, key, errors, prefix="gui")


def _validate_outputs(outputs: Any, errors: list[str]) -> None:
    if not isinstance(outputs, dict):
        errors.append("outputs must be an object.")
        return
    for key in ("markdown", "pdf", "googleDocument", "classroomReminder"):
        if key not in outputs:
            errors.append(f"outputs.{key} is required.")

    markdown = outputs.get("markdown")
    if markdown is not None:
        _validate_markdown_output(markdown, errors)

    pdf = outputs.get("pdf")
    if pdf is not None:
        _validate_pdf_output(pdf, errors)

    google_document = outputs.get("googleDocument")
    if google_document is not None:
        _validate_google_document_output(google_document, errors)

    classroom_reminder = outputs.get("classroomReminder")
    if classroom_reminder is not None:
        _validate_classroom_reminder_output(classroom_reminder, errors)


def _validate_approval(approval: Any, errors: list[str]) -> None:
    if not isinstance(approval, dict):
        errors.append("approval must be an object.")
        return
    if not isinstance(approval.get("required"), bool):
        errors.append("approval.required must be a boolean.")
    _require_string(approval, "reason", errors, prefix="approval")
    _require_list(approval, "actions", errors, prefix="approval")


def _validate_errors(items: Any, errors: list[str]) -> None:
    if not isinstance(items, list):
        errors.append("errors must be a list.")
        return
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"errors[{index}] must be an object.")
            continue
        code = item.get("code")
        if not isinstance(code, str) or not code.strip():
            errors.append(f"errors[{index}].code must be a non-empty string.")
        elif code not in STANDARD_ERROR_CODES:
            errors.append(f"errors[{index}].code is not standardized: {code}")
        message = item.get("message")
        if not isinstance(message, str) or not message.strip():
            errors.append(f"errors[{index}].message must be a non-empty string.")
        if not isinstance(item.get("recoverable"), bool):
            errors.append(f"errors[{index}].recoverable must be a boolean.")


def _validate_markdown_output(item: Any, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append("outputs.markdown must be an object or null.")
        return
    for key in ("fileName", "title", "content"):
        _require_string(item, key, errors, prefix="outputs.markdown")


def _validate_pdf_output(item: Any, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append("outputs.pdf must be an object or null.")
        return
    for key in ("fileName", "title", "layout"):
        _require_string(item, key, errors, prefix="outputs.pdf")
    _require_list(item, "sections", errors, prefix="outputs.pdf")


def _validate_google_document_output(item: Any, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append("outputs.googleDocument must be an object or null.")
        return
    for key in ("title", "documentType"):
        _require_string(item, key, errors, prefix="outputs.googleDocument")
    _require_list(item, "blocks", errors, prefix="outputs.googleDocument")


def _validate_classroom_reminder_output(item: Any, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append("outputs.classroomReminder must be an object or null.")
        return
    target = item.get("target")
    if not isinstance(target, dict):
        errors.append("outputs.classroomReminder.target must be an object.")
    else:
        _require_string(target, "courseId", errors, prefix="outputs.classroomReminder.target")
        _require_string(
            target,
            "courseWorkId",
            errors,
            prefix="outputs.classroomReminder.target",
        )
    for key in ("postType", "title", "text", "assigneeMode"):
        _require_string(item, key, errors, prefix="outputs.classroomReminder")
    _require_list(item, "materials", errors, prefix="outputs.classroomReminder")
    if item.get("scheduledTime") is not None:
        _require_iso_datetime(
            item.get("scheduledTime"),
            "outputs.classroomReminder.scheduledTime",
            errors,
        )
    _require_list(item, "targetStudentIds", errors, prefix="outputs.classroomReminder")
    if not isinstance(item.get("requiresTeacherApproval"), bool):
        errors.append(
            "outputs.classroomReminder.requiresTeacherApproval must be a boolean."
        )


def _require_string(
    obj: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    prefix: str | None = None,
) -> None:
    value = obj.get(key)
    label = f"{prefix}.{key}" if prefix else key
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string.")


def _require_list(
    obj: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    prefix: str | None = None,
) -> None:
    value = obj.get(key)
    label = f"{prefix}.{key}" if prefix else key
    if not isinstance(value, list):
        errors.append(f"{label} must be a list.")


def _require_iso_datetime(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{label} must be an ISO 8601 string.")
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label} must be a valid ISO 8601 string.")
