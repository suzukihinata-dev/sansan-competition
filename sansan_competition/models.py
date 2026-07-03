from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


class AgentTaskType(StrEnum):
    COURSE_SUMMARY = "COURSE_SUMMARY"
    COURSEWORK_SUMMARY = "COURSEWORK_SUMMARY"
    SUBMISSION_ANALYSIS = "SUBMISSION_ANALYSIS"
    REMINDER_GENERATION = "REMINDER_GENERATION"
    WEEKLY_REPORT = "WEEKLY_REPORT"
    ANNOUNCEMENT_DRAFT = "ANNOUNCEMENT_DRAFT"
    DOCUMENT_EXPORT = "DOCUMENT_EXPORT"
    RUBRIC_SUPPORT = "RUBRIC_SUPPORT"
    ERROR_ANALYSIS = "ERROR_ANALYSIS"


class ResponseStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    ERROR = "error"


class SubmissionState(StrEnum):
    CREATED = "CREATED"
    NEW = "NEW"
    TURNED_IN = "TURNED_IN"
    RETURNED = "RETURNED"
    RECLAIMED_BY_STUDENT = "RECLAIMED_BY_STUDENT"


SUBMITTED_STATES = {
    SubmissionState.TURNED_IN.value,
    SubmissionState.RETURNED.value,
}
UNSUBMITTED_STATES = {
    SubmissionState.CREATED.value,
    SubmissionState.NEW.value,
    SubmissionState.RECLAIMED_BY_STUDENT.value,
}
ATTACHMENT_EXPECTED_WORK_TYPES = {
    "ASSIGNMENT",
}


@dataclass(slots=True)
class Course:
    course_id: str
    name: str
    section: str = ""
    description: str = ""
    state: str = "ACTIVE"
    teacher_ids: list[str] = field(default_factory=list)
    student_count: int = 0

    def to_contract(self) -> dict[str, Any]:
        return {
            "courseId": self.course_id,
            "name": self.name,
            "section": self.section,
            "description": self.description,
            "state": self.state,
            "teacherIds": self.teacher_ids,
            "studentCount": self.student_count,
        }


@dataclass(slots=True)
class CourseWork:
    course_work_id: str
    course_id: str
    title: str
    description: str = ""
    work_type: str = "ASSIGNMENT"
    max_points: float | None = None
    due_at: datetime | None = None
    due_date: str | None = None
    due_time: str | None = None
    state: str = "PUBLISHED"
    materials: list[dict[str, Any]] = field(default_factory=list)
    topic_id: str = ""
    has_rubric: bool = False

    def to_contract(self) -> dict[str, Any]:
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
            "materials": self.materials,
            "topicId": self.topic_id,
            "hasRubric": self.has_rubric,
        }


@dataclass(slots=True)
class StudentSubmission:
    student_submission_id: str
    course_id: str
    course_work_id: str
    student_id: str
    student_name: str
    state: str
    submitted_at: datetime | None = None
    updated_at: datetime | None = None
    late: bool = False
    assigned_grade: float | None = None
    draft_grade: float | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)

    def to_contract(self) -> dict[str, Any]:
        return {
            "studentSubmissionId": self.student_submission_id,
            "courseId": self.course_id,
            "courseWorkId": self.course_work_id,
            "studentId": self.student_id,
            "studentName": self.student_name,
            "state": self.state,
            "submittedAt": _datetime_or_none(self.submitted_at),
            "updatedAt": _datetime_or_none(self.updated_at),
            "late": self.late,
            "assignedGrade": self.assigned_grade,
            "draftGrade": self.draft_grade,
            "attachments": self.attachments,
        }


@dataclass(slots=True)
class NormalizationIssue:
    item_ref: str
    message: str
    code: str = "NORMALIZATION_FAILED"
    recoverable: bool = True

    def to_contract(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "recoverable": self.recoverable,
            "itemRef": self.item_ref,
        }


@dataclass(slots=True)
class SubmissionEvaluation:
    student_id: str
    student_name: str
    submission_state: str
    status_label: str
    due_at: datetime | None
    submitted_at: datetime | None
    is_missing: bool
    is_due_soon: bool
    is_late: bool
    attachment_missing_possible: bool
    attachment_count: int
    notes: list[str] = field(default_factory=list)

    def to_table_row(self) -> dict[str, Any]:
        return {
            "studentId": self.student_id,
            "studentName": self.student_name,
            "status": self.status_label,
            "rawState": self.submission_state,
            "dueDate": _date_or_none(self.due_at),
            "submittedAt": _datetime_or_none(self.submitted_at),
            "attachmentCount": self.attachment_count,
            "notes": " / ".join(self.notes),
        }


@dataclass(slots=True)
class SubmissionAnalysis:
    course: Course
    course_work: CourseWork
    evaluations: list[SubmissionEvaluation]
    generated_at: datetime
    normalization_issues: list[NormalizationIssue] = field(default_factory=list)

    @property
    def unsubmitted(self) -> list[SubmissionEvaluation]:
        return [entry for entry in self.evaluations if entry.is_missing]

    @property
    def due_soon(self) -> list[SubmissionEvaluation]:
        return [entry for entry in self.evaluations if entry.is_due_soon]

    @property
    def late_submissions(self) -> list[SubmissionEvaluation]:
        return [entry for entry in self.evaluations if entry.is_late]

    @property
    def attachment_flags(self) -> list[SubmissionEvaluation]:
        return [
            entry
            for entry in self.evaluations
            if entry.attachment_missing_possible
        ]

    @property
    def submitted(self) -> list[SubmissionEvaluation]:
        return [entry for entry in self.evaluations if not entry.is_missing]

    def counts(self) -> dict[str, int]:
        return {
            "totalStudents": len(self.evaluations),
            "submittedCount": len(self.submitted),
            "unsubmittedCount": len(self.unsubmitted),
            "dueSoonCount": len(self.due_soon),
            "lateCount": len(self.late_submissions),
            "attachmentMissingPossibleCount": len(self.attachment_flags),
        }

    def recommended_action(self) -> str:
        if self.unsubmitted:
            return (
                "未提出者を確認し、必要に応じてClassroomでリマインドを送信してください。"
            )
        if self.late_submissions:
            return "遅延提出者の内容を確認し、個別フォローが必要か判断してください。"
        if self.attachment_flags:
            return "添付不足の可能性がある提出物を確認してください。"
        return "大きな対応は不要です。必要ならレポートを出力して共有してください。"

    def teacher_action_required(self) -> bool:
        counts = self.counts()
        return any(
            counts[key] > 0
            for key in (
                "unsubmittedCount",
                "dueSoonCount",
                "lateCount",
                "attachmentMissingPossibleCount",
            )
        )


def _datetime_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds")


def _date_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.date().isoformat()
