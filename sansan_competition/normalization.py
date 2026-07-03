from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time
from typing import Any

from .models import Course, CourseWork, JST, NormalizationIssue, StudentSubmission


def normalize_course(raw: Mapping[str, Any]) -> Course:
    course_id = _required_str(raw, "courseId", "id")
    name = _required_str(raw, "name")
    section = _optional_str(raw, "section")
    description = _optional_str(raw, "description", "descriptionHeading")
    state = _optional_str(raw, "state", "courseState", default="ACTIVE")

    teacher_ids = [
        str(item)
        for item in raw.get("teacherIds", [])
        if str(item).strip()
    ]
    if not teacher_ids and isinstance(raw.get("teachers"), list):
        teacher_ids = [
            str(teacher.get("userId", "")).strip()
            for teacher in raw["teachers"]
            if str(teacher.get("userId", "")).strip()
        ]

    student_count = raw.get("studentCount", raw.get("studentsCount", 0))
    if not isinstance(student_count, int):
        raise ValueError("studentCount must be an integer.")

    return Course(
        course_id=course_id,
        name=name,
        section=section,
        description=description,
        state=state,
        teacher_ids=teacher_ids,
        student_count=student_count,
    )


def normalize_coursework(raw: Mapping[str, Any]) -> CourseWork:
    course_work_id = _required_str(raw, "courseWorkId", "id")
    course_id = _required_str(raw, "courseId")
    title = _required_str(raw, "title")
    description = _optional_str(raw, "description")
    work_type = _optional_str(raw, "workType", default="ASSIGNMENT")
    max_points = _optional_number(raw, "maxPoints")
    due_at, due_date, due_time = _parse_due_fields(
        raw.get("dueDate"),
        raw.get("dueTime"),
    )
    state = _optional_str(raw, "state", default="PUBLISHED")
    materials = _optional_list(raw, "materials")
    topic_id = _optional_str(raw, "topicId")
    has_rubric = bool(raw.get("rubric") or raw.get("rubricId") or raw.get("hasRubric"))

    return CourseWork(
        course_work_id=course_work_id,
        course_id=course_id,
        title=title,
        description=description,
        work_type=work_type,
        max_points=max_points,
        due_at=due_at,
        due_date=due_date,
        due_time=due_time,
        state=state,
        materials=materials,
        topic_id=topic_id,
        has_rubric=has_rubric,
    )


def normalize_submission(
    raw: Mapping[str, Any],
    *,
    student_name: str | None = None,
) -> StudentSubmission:
    student_submission_id = _required_str(raw, "studentSubmissionId", "id")
    course_id = _required_str(raw, "courseId")
    course_work_id = _required_str(raw, "courseWorkId")
    student_id = _required_str(raw, "studentId", "userId")
    resolved_student_name = student_name or _optional_str(raw, "studentName", default="")
    state = _required_str(raw, "state")

    submitted_at = _parse_rfc3339(_submitted_at_value(raw))
    updated_at = _parse_rfc3339(raw.get("updateTime") or raw.get("updatedAt"))

    late = bool(raw.get("late", False))
    assigned_grade = _optional_number(raw, "assignedGrade")
    draft_grade = _optional_number(raw, "draftGrade")
    attachments = _submission_attachments(raw)

    return StudentSubmission(
        student_submission_id=student_submission_id,
        course_id=course_id,
        course_work_id=course_work_id,
        student_id=student_id,
        student_name=resolved_student_name,
        state=state,
        submitted_at=submitted_at,
        updated_at=updated_at,
        late=late,
        assigned_grade=assigned_grade,
        draft_grade=draft_grade,
        attachments=attachments,
    )


def normalize_submission_batch(
    raw_submissions: list[Mapping[str, Any]],
    *,
    student_names_by_id: Mapping[str, str] | None = None,
) -> tuple[list[StudentSubmission], list[NormalizationIssue]]:
    submissions: list[StudentSubmission] = []
    issues: list[NormalizationIssue] = []
    name_lookup = student_names_by_id or {}

    for index, raw in enumerate(raw_submissions):
        student_id = str(raw.get("studentId") or raw.get("userId") or "")
        try:
            submissions.append(
                normalize_submission(
                    raw,
                    student_name=name_lookup.get(student_id) or raw.get("studentName"),
                )
            )
        except ValueError as exc:
            issues.append(
                NormalizationIssue(
                    item_ref=f"submission[{index}]",
                    code="PARTIAL_CLASSROOM_DATA",
                    message=str(exc),
                )
            )

    return submissions, issues


def _required_str(raw: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    joined = ", ".join(keys)
    raise ValueError(f"Missing required string field: {joined}.")


def _optional_str(
    raw: Mapping[str, Any],
    *keys: str,
    default: str = "",
) -> str:
    for key in keys:
        value = raw.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"Field {key} must be a string.")
        return value.strip()
    return default


def _optional_number(
    raw: Mapping[str, Any],
    key: str,
) -> float | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    raise ValueError(f"Field {key} must be numeric.")


def _optional_list(raw: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    value = raw.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"Field {key} must be a list.")
    return [item for item in value if isinstance(item, dict)]


def _submission_attachments(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    direct_attachments = raw.get("attachments")
    if isinstance(direct_attachments, list):
        return [item for item in direct_attachments if isinstance(item, dict)]

    assignment_submission = raw.get("assignmentSubmission")
    if isinstance(assignment_submission, Mapping):
        nested_attachments = assignment_submission.get("attachments")
        if isinstance(nested_attachments, list):
            return [item for item in nested_attachments if isinstance(item, dict)]

    return []


def _submitted_at_value(raw: Mapping[str, Any]) -> Any:
    explicit_value = (
        raw.get("submissionTime")
        or raw.get("submittedAt")
        or raw.get("turnInTime")
    )
    if explicit_value is not None:
        return explicit_value

    state_timestamp = _latest_submission_state_timestamp(raw.get("submissionHistory"))
    if state_timestamp is not None:
        return state_timestamp

    state = str(raw.get("state") or "").strip()
    if state in {"TURNED_IN", "RETURNED"}:
        return raw.get("updateTime") or raw.get("updatedAt")
    return None


def _latest_submission_state_timestamp(value: Any) -> str | None:
    if not isinstance(value, list):
        return None

    timestamps: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        state_history = item.get("stateHistory")
        if not isinstance(state_history, Mapping):
            continue
        state = str(state_history.get("state") or "").strip()
        timestamp = state_history.get("stateTimestamp")
        if state in {"TURNED_IN", "RETURNED"} and isinstance(timestamp, str) and timestamp.strip():
            timestamps.append(timestamp.strip())

    if not timestamps:
        return None
    return max(timestamps)


def _parse_due_fields(
    due_date_value: Any,
    due_time_value: Any,
) -> tuple[datetime | None, str | None, str | None]:
    if due_date_value is None:
        return None, None, None

    parsed_date = _parse_date(due_date_value)
    parsed_time = _parse_time(due_time_value)
    due_at = datetime.combine(parsed_date, parsed_time, tzinfo=JST)
    due_date = parsed_date.isoformat()
    due_time = parsed_time.strftime("%H:%M")
    return due_at, due_date, due_time


def _parse_date(value: Any) -> date:
    if isinstance(value, str):
        return date.fromisoformat(value)
    if isinstance(value, Mapping):
        return date(
            int(value["year"]),
            int(value["month"]),
            int(value["day"]),
        )
    raise ValueError("dueDate must be an ISO date string or Classroom date object.")


def _parse_time(value: Any) -> time:
    if value is None:
        return time(23, 59)
    if isinstance(value, str):
        text = value.strip()
        if len(text.split(":")) == 2:
            text = f"{text}:00"
        return time.fromisoformat(text)
    if isinstance(value, Mapping):
        return time(
            int(value.get("hours", 23)),
            int(value.get("minutes", 59)),
            int(value.get("seconds", 0)),
        )
    raise ValueError("dueTime must be an ISO time string or Classroom time object.")


def _parse_rfc3339(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Timestamp fields must be ISO 8601 strings.")
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=JST)
    return parsed.astimezone(JST)
