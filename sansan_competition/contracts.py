from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any, Literal


SCHEMA_VERSION = "1.0.0"

AgentTaskType = Literal[
    "COURSE_SUMMARY",
    "COURSEWORK_SUMMARY",
    "SUBMISSION_ANALYSIS",
    "REMINDER_GENERATION",
    "WEEKLY_REPORT",
    "ANNOUNCEMENT_DRAFT",
    "DOCUMENT_EXPORT",
    "RUBRIC_SUPPORT",
    "ERROR_ANALYSIS",
]

OutputStatus = Literal["success", "error"]


def _omit_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _omit_none(inner) for key, inner in value.items() if inner is not None}
    if isinstance(value, list):
        return [_omit_none(item) for item in value if item is not None]
    return value


def now_jst_iso() -> str:
    return datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Tokyo")).isoformat()


@dataclass(frozen=True, slots=True)
class Course:
    course_id: str
    name: str
    section: str = ""
    description: str = ""
    state: str = ""
    teacher_ids: list[str] = field(default_factory=list)
    student_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "courseId": self.course_id,
            "name": self.name,
            "section": self.section,
            "description": self.description,
            "state": self.state,
            "teacherIds": list(self.teacher_ids),
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
    materials: list[dict[str, Any]] = field(default_factory=list)
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
            "materials": list(self.materials),
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
    assigned_grade: float | None = None
    draft_grade: float | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)

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
            "attachments": list(self.attachments),
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
class GuiCard:
    card_id: str
    type: str
    title: str
    value: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cardId": self.card_id,
            "type": self.type,
            "title": self.title,
            "value": self.value,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class GuiTableColumn:
    key: str
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "label": self.label}


@dataclass(frozen=True, slots=True)
class GuiTable:
    table_id: str
    title: str
    columns: list[GuiTableColumn]
    rows: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tableId": self.table_id,
            "title": self.title,
            "columns": [column.to_dict() for column in self.columns],
            "rows": list(self.rows),
        }


@dataclass(frozen=True, slots=True)
class GuiWarning:
    level: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"level": self.level, "message": self.message}


@dataclass(frozen=True, slots=True)
class EditableField:
    field_id: str
    label: str
    type: str
    value: str
    required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "fieldId": self.field_id,
            "label": self.label,
            "type": self.type,
            "value": self.value,
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class MarkdownOutput:
    file_name: str
    title: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fileName": self.file_name,
            "title": self.title,
            "content": self.content,
        }


@dataclass(frozen=True, slots=True)
class PdfOutput:
    file_name: str
    title: str
    layout: str
    sections: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fileName": self.file_name,
            "title": self.title,
            "layout": self.layout,
            "sections": list(self.sections),
        }


@dataclass(frozen=True, slots=True)
class GoogleDocumentOutput:
    title: str
    document_type: str
    blocks: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "documentType": self.document_type,
            "blocks": list(self.blocks),
        }


@dataclass(frozen=True, slots=True)
class ClassroomReminder:
    target: dict[str, Any]
    post_type: str
    title: str
    text: str
    materials: list[dict[str, Any]] = field(default_factory=list)
    scheduled_time: str | None = None
    assignee_mode: str = "ALL_STUDENTS"
    target_student_ids: list[str] = field(default_factory=list)
    requires_teacher_approval: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": dict(self.target),
            "postType": self.post_type,
            "title": self.title,
            "text": self.text,
            "materials": list(self.materials),
            "scheduledTime": self.scheduled_time,
            "assigneeMode": self.assignee_mode,
            "targetStudentIds": list(self.target_student_ids),
            "requiresTeacherApproval": self.requires_teacher_approval,
        }


@dataclass(frozen=True, slots=True)
class ApprovalAction:
    action_id: str
    type: str
    label: str
    requires_confirmation: bool
    payload_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "actionId": self.action_id,
            "type": self.type,
            "label": self.label,
            "requiresConfirmation": self.requires_confirmation,
            "payloadRef": self.payload_ref,
        }


@dataclass(frozen=True, slots=True)
class Approval:
    required: bool
    reason: str
    actions: list[ApprovalAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "reason": self.reason,
            "actions": [action.to_dict() for action in self.actions],
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
    agent_task_type: AgentTaskType
    status: OutputStatus
    summary: Summary
    course: Course | None = None
    gui: dict[str, Any] | None = None
    outputs: dict[str, Any] | None = None
    approval: Approval | None = None
    errors: list[AgentError] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "requestId": self.request_id,
            "generatedAt": self.generated_at,
            "agentTaskType": self.agent_task_type,
            "status": self.status,
            "summary": self.summary.to_dict(),
        }
        if self.course is not None:
            payload["course"] = self.course.to_dict()
        if self.gui is not None:
            payload["gui"] = _omit_none(self.gui)
        if self.outputs is not None:
            payload["outputs"] = _omit_none(self.outputs)
        if self.approval is not None:
            payload["approval"] = self.approval.to_dict()
        if self.errors:
            payload["errors"] = [error.to_dict() for error in self.errors]
        return payload


REQUIRED_AGENT_OUTPUT_KEYS = {
    "schemaVersion",
    "requestId",
    "generatedAt",
    "agentTaskType",
    "status",
    "summary",
}


def validate_agent_output_dict(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_AGENT_OUTPUT_KEYS - payload.keys()
    if missing:
        errors.append(f"missing required top-level keys: {', '.join(sorted(missing))}")
        return errors

    if payload.get("schemaVersion") != SCHEMA_VERSION:
        errors.append(f"unsupported schemaVersion: {payload.get('schemaVersion')}")

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
    else:
        required_summary_keys = {
            "title",
            "shortSummary",
            "teacherActionRequired",
            "recommendedAction",
        }
        missing_summary = required_summary_keys - summary.keys()
        if missing_summary:
            errors.append(f"summary missing keys: {', '.join(sorted(missing_summary))}")

    generated_at = payload.get("generatedAt")
    if isinstance(generated_at, str):
        try:
            datetime.fromisoformat(generated_at)
        except ValueError:
            errors.append("generatedAt must be an ISO-8601 datetime string")
    else:
        errors.append("generatedAt must be a string")

    return errors


def normalize_due_datetime(due_date: str, due_time: str) -> str:
    if due_date and due_time:
        return f"{due_date} {due_time}"
    if due_date:
        return due_date
    return due_time


def count_states(submissions: list[StudentSubmission]) -> dict[str, int]:
    counts = {
        "submitted": 0,
        "missing": 0,
        "late": 0,
    }
    for submission in submissions:
        if submission.state in {"TURNED_IN", "RETURNED"}:
            counts["submitted"] += 1
        else:
            counts["missing"] += 1
        if submission.late:
            counts["late"] += 1
    return counts
