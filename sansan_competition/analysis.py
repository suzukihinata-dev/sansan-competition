from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .models import (
    ATTACHMENT_EXPECTED_WORK_TYPES,
    AgentTaskType,
    Course,
    CourseWork,
    JST,
    StudentSubmission,
    SubmissionAnalysis,
    SubmissionEvaluation,
    SUBMITTED_STATES,
)

DEFAULT_DUE_SOON_WINDOW = timedelta(days=2)


def analyze_submissions(
    course: Course,
    course_work: CourseWork,
    submissions: list[StudentSubmission],
    *,
    now: datetime | None = None,
    due_soon_window: timedelta = DEFAULT_DUE_SOON_WINDOW,
    normalization_issues: list[Any] | None = None,
) -> SubmissionAnalysis:
    generated_at = now or datetime.now(JST)
    evaluations = [
        _evaluate_submission(
            course_work=course_work,
            submission=submission,
            now=generated_at,
            due_soon_window=due_soon_window,
        )
        for submission in submissions
    ]
    evaluations.sort(key=_evaluation_sort_key)

    return SubmissionAnalysis(
        course=course,
        course_work=course_work,
        evaluations=evaluations,
        generated_at=generated_at,
        normalization_issues=list(normalization_issues or []),
    )


def build_ai_task_input(
    task_type: AgentTaskType | str,
    analysis: SubmissionAnalysis,
    *,
    include_student_names: bool = False,
) -> dict[str, Any]:
    resolved_task = AgentTaskType(task_type)
    student_entries: list[dict[str, Any]] = []

    for index, evaluation in enumerate(analysis.evaluations, start=1):
        entry = {
            "studentRef": f"student_{index:03d}",
            "status": evaluation.status_label,
            "submissionState": evaluation.submission_state,
            "isMissing": evaluation.is_missing,
            "isDueSoon": evaluation.is_due_soon,
            "isLate": evaluation.is_late,
            "attachmentMissingPossible": evaluation.attachment_missing_possible,
            "notes": evaluation.notes,
        }
        if include_student_names:
            entry["studentId"] = evaluation.student_id
            entry["studentName"] = evaluation.student_name
        student_entries.append(entry)

    return {
        "taskType": resolved_task.value,
        "facts": {
            "course": analysis.course.to_contract(),
            "courseWork": analysis.course_work.to_contract(),
            "submissionSummary": analysis.counts(),
            "submissions": student_entries,
        },
        "privacy": {
            "containsStudentNames": include_student_names,
            "recommendedForExternalAI": not include_student_names,
        },
    }


def _evaluate_submission(
    *,
    course_work: CourseWork,
    submission: StudentSubmission,
    now: datetime,
    due_soon_window: timedelta,
) -> SubmissionEvaluation:
    due_at = course_work.due_at
    submitted_at = submission.submitted_at
    is_submitted = submission.state in SUBMITTED_STATES
    is_missing = not is_submitted

    deadline_passed = False
    is_due_soon = False
    if due_at is not None:
        deadline_passed = now > due_at
        is_due_soon = is_missing and not deadline_passed and (due_at - now) <= due_soon_window

    is_late = submission.late
    if not is_late and is_submitted and due_at and submitted_at:
        is_late = submitted_at > due_at

    attachment_missing_possible = (
        is_submitted
        and course_work.work_type in ATTACHMENT_EXPECTED_WORK_TYPES
        and len(submission.attachments) == 0
    )

    notes: list[str] = []
    if is_missing and deadline_passed:
        status_label = "期限超過未提出"
        notes.append("締切を過ぎても未提出です。")
    elif is_missing and is_due_soon:
        status_label = "期限接近未提出"
        notes.append("締切が近いため優先確認が必要です。")
    elif is_missing:
        status_label = "未提出"
    elif is_late:
        status_label = "遅延提出"
        notes.append("締切後に提出されています。")
    else:
        status_label = "提出済み"

    if attachment_missing_possible:
        notes.append("提出済みですが添付不足の可能性があります。")

    return SubmissionEvaluation(
        student_id=submission.student_id,
        student_name=submission.student_name,
        submission_state=submission.state,
        status_label=status_label,
        due_at=due_at,
        submitted_at=submitted_at,
        is_missing=is_missing,
        is_due_soon=is_due_soon,
        is_late=is_late,
        attachment_missing_possible=attachment_missing_possible,
        attachment_count=len(submission.attachments),
        notes=notes,
    )


def _evaluation_sort_key(entry: SubmissionEvaluation) -> tuple[int, str]:
    if entry.is_missing and entry.is_due_soon:
        priority = 0
    elif entry.is_missing:
        priority = 1
    elif entry.is_late:
        priority = 2
    elif entry.attachment_missing_possible:
        priority = 3
    else:
        priority = 4
    return priority, entry.student_name
