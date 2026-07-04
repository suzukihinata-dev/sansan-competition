from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .models import (
    ATTACHMENT_EXPECTED_WORK_TYPES,
    AgentTaskType,
    Course,
    CourseWork,
    JST,
    SubmissionState,
    StudentSubmission,
    SubmissionAnalysis,
    SubmissionEvaluation,
    SUBMITTED_STATES,
    UNSUBMITTED_STATES,
)

DEFAULT_DUE_SOON_WINDOW = timedelta(days=2)
TASK_GOALS = {
    AgentTaskType.COURSE_SUMMARY: "コース全体の状況を教師向けに簡潔に要約する",
    AgentTaskType.COURSEWORK_SUMMARY: "課題単位の情報を整理し、重要点を抜き出す",
    AgentTaskType.SUBMISSION_ANALYSIS: "提出状況を分類し、教師が確認すべき点を明確にする",
    AgentTaskType.REMINDER_GENERATION: "未提出者向けのリマインド文を作るための事実を渡す",
    AgentTaskType.WEEKLY_REPORT: "週次レポート向けに、進捗と注意点を整理する",
    AgentTaskType.ANNOUNCEMENT_DRAFT: "Classroom お知らせ案に必要な事実だけを渡す",
    AgentTaskType.DOCUMENT_EXPORT: "Markdown、PDF、Google Document 用の構造を作る前提データを渡す",
    AgentTaskType.RUBRIC_SUPPORT: "提出済みデータをもとにルーブリック補助の前提情報を渡す",
    AgentTaskType.ERROR_ANALYSIS: "取得失敗や欠損を踏まえて説明用の事実を整理する",
}
TASK_DEFAULT_OUTPUT_FORMATS = {
    AgentTaskType.COURSE_SUMMARY: ["summary", "gui"],
    AgentTaskType.COURSEWORK_SUMMARY: ["summary", "gui"],
    AgentTaskType.SUBMISSION_ANALYSIS: ["summary", "gui", "markdown", "pdf", "googleDocument"],
    AgentTaskType.REMINDER_GENERATION: ["classroomReminder", "markdown", "pdf", "googleDocument"],
    AgentTaskType.WEEKLY_REPORT: ["markdown", "pdf", "googleDocument"],
    AgentTaskType.ANNOUNCEMENT_DRAFT: ["classroomReminder", "markdown", "googleDocument"],
    AgentTaskType.DOCUMENT_EXPORT: ["markdown", "pdf", "googleDocument"],
    AgentTaskType.RUBRIC_SUPPORT: ["summary", "gui"],
    AgentTaskType.ERROR_ANALYSIS: ["summary", "gui"],
}
TASK_REQUIRED_FIELDS = {
    AgentTaskType.COURSE_SUMMARY: ["summary.title", "summary.shortSummary", "gui.cards"],
    AgentTaskType.COURSEWORK_SUMMARY: ["summary", "gui.tables"],
    AgentTaskType.SUBMISSION_ANALYSIS: ["summary", "gui.tables", "outputs.markdown"],
    AgentTaskType.REMINDER_GENERATION: [
        "summary",
        "gui.editableFields",
        "outputs.classroomReminder",
    ],
    AgentTaskType.WEEKLY_REPORT: ["summary", "outputs.markdown", "outputs.pdf"],
    AgentTaskType.ANNOUNCEMENT_DRAFT: [
        "summary",
        "gui.editableFields",
        "outputs.classroomReminder",
    ],
    AgentTaskType.DOCUMENT_EXPORT: ["outputs.markdown", "outputs.pdf", "outputs.googleDocument"],
    AgentTaskType.RUBRIC_SUPPORT: ["summary", "gui.tables"],
    AgentTaskType.ERROR_ANALYSIS: ["summary", "errors", "gui.warnings"],
}
COMMON_PROHIBITED_ITEMS = [
    "不明な締切日や課題名を推測して補わない",
    "他の生徒の提出状況が分かる表現を生徒向け本文に入れない",
    "教師承認前に投稿済みであるかのように書かない",
]


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
    output_formats: list[str] | None = None,
    tone: str = "polite",
    teacher_instruction: str = "",
    prohibited_items: list[str] | None = None,
    include_student_names: bool = False,
) -> dict[str, Any]:
    resolved_task = AgentTaskType(task_type)
    selected_evaluations = _select_evaluations_for_task(resolved_task, analysis)
    student_entries = [
        _build_task_student_entry(
            task_type=resolved_task,
            evaluation=evaluation,
            index=index,
            include_student_names=include_student_names,
        )
        for index, evaluation in enumerate(selected_evaluations, start=1)
    ]

    normalized_teacher_instruction = teacher_instruction.strip()
    target_summary = _summarize_evaluations(selected_evaluations)
    requested_detail_mode = (
        "identified_targets"
        if include_student_names
        else "minimal_targets_only"
    )
    contains_student_identifiers = any(
        "studentId" in entry or "studentName" in entry
        for entry in student_entries
    )
    if contains_student_identifiers:
        applied_detail_mode = "identified_targets"
        student_identifier_mode = "real_student_id_and_name"
    elif student_entries:
        applied_detail_mode = "pseudonymized_targets_only"
        student_identifier_mode = "pseudonymized_student_ref_only"
    else:
        applied_detail_mode = "aggregate_only"
        student_identifier_mode = "no_student_identifiers"

    return {
        "taskType": resolved_task.value,
        "focus": {
            "goal": TASK_GOALS[resolved_task],
            "selectionMode": _selection_mode_label(resolved_task),
            "requiredOutputFields": TASK_REQUIRED_FIELDS[resolved_task],
        },
        "facts": {
            "course": analysis.course.to_contract(),
            "courseWork": analysis.course_work.to_contract(),
            "submissionSummary": analysis.counts(),
            "targetSummary": target_summary,
            "submissions": student_entries,
            "warnings": _build_input_warnings(analysis),
        },
        "delivery": {
            "outputFormats": output_formats or TASK_DEFAULT_OUTPUT_FORMATS[resolved_task],
            "tone": tone,
            "teacherInstruction": normalized_teacher_instruction,
            "approvalRequired": resolved_task
            in {
                AgentTaskType.REMINDER_GENERATION,
                AgentTaskType.ANNOUNCEMENT_DRAFT,
            },
        },
        "constraints": {
            "mustUseOnlyProvidedFacts": True,
            "mustSeparateFactsAndSuggestions": True,
            "mustNotInventUnknownInformation": True,
            "prohibitedItems": COMMON_PROHIBITED_ITEMS + list(prohibited_items or []),
        },
        "privacy": {
            "requestedDetailMode": requested_detail_mode,
            "appliedDetailMode": applied_detail_mode,
            "containsStudentNames": any(
                "studentName" in entry for entry in student_entries
            ),
            "containsStudentIds": any(
                "studentId" in entry for entry in student_entries
            ),
            "studentIdentifierMode": student_identifier_mode,
            "recommendedForExternalAI": not contains_student_identifiers,
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
    is_returned = submission.state == SubmissionState.RETURNED.value
    is_exempt_like = (
        submission.state in UNSUBMITTED_STATES
        and _has_grading_signal(submission)
    )
    is_missing = not is_submitted and not is_exempt_like

    deadline_passed = False
    is_due_soon = False
    if due_at is not None:
        deadline_passed = now > due_at
        is_due_soon = is_missing and not deadline_passed and (due_at - now) <= due_soon_window

    is_late = False
    if is_submitted:
        is_late = submission.late
        if not is_late and due_at and submitted_at:
            is_late = submitted_at > due_at

    attachment_missing_possible = (
        is_submitted
        and course_work.work_type in ATTACHMENT_EXPECTED_WORK_TYPES
        and len(submission.attachments) == 0
    )

    notes: list[str] = []
    if is_exempt_like:
        status_label = "提出免除の可能性"
        notes.append(
            "未提出状態ですが採点情報があるため、提出免除または教師処理済みの可能性があります。"
        )
    elif is_missing and deadline_passed:
        status_label = "期限超過未提出"
        notes.append("締切を過ぎても未提出です。")
    elif is_missing and is_due_soon:
        status_label = "期限接近未提出"
        notes.append("締切が近いため優先確認が必要です。")
    elif is_missing:
        status_label = "未提出"
    elif is_returned and is_late:
        status_label = "返却済み（遅延提出）"
        notes.append("締切後に提出されています。")
    elif is_late:
        status_label = "遅延提出"
        notes.append("締切後に提出されています。")
    elif is_returned:
        status_label = "返却済み"
    else:
        status_label = "提出済み"

    if is_returned:
        notes.append("教師によって返却済みです。")
    if attachment_missing_possible:
        notes.append("提出済みですが添付不足の可能性があります。")

    return SubmissionEvaluation(
        student_id=submission.student_id,
        student_name=submission.student_name,
        submission_state=submission.state,
        status_label=status_label,
        due_at=due_at,
        submitted_at=submitted_at,
        is_submitted=is_submitted,
        is_missing=is_missing,
        is_due_soon=is_due_soon,
        is_late=is_late,
        is_returned=is_returned,
        is_exempt_like=is_exempt_like,
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


def _select_evaluations_for_task(
    task_type: AgentTaskType,
    analysis: SubmissionAnalysis,
) -> list[SubmissionEvaluation]:
    if task_type in {
        AgentTaskType.COURSE_SUMMARY,
        AgentTaskType.COURSEWORK_SUMMARY,
        AgentTaskType.DOCUMENT_EXPORT,
        AgentTaskType.ERROR_ANALYSIS,
    }:
        return []
    if task_type in {
        AgentTaskType.REMINDER_GENERATION,
        AgentTaskType.ANNOUNCEMENT_DRAFT,
    }:
        return list(analysis.unsubmitted)
    if task_type is AgentTaskType.WEEKLY_REPORT:
        return _deduplicate_evaluations(
            [
                *analysis.unsubmitted,
                *analysis.late_submissions,
                *analysis.attachment_flags,
            ]
        )
    if task_type is AgentTaskType.RUBRIC_SUPPORT:
        return list(analysis.actual_submitted)
    return list(analysis.evaluations)


def _build_task_student_entry(
    *,
    task_type: AgentTaskType,
    evaluation: SubmissionEvaluation,
    index: int,
    include_student_names: bool,
) -> dict[str, Any]:
    entry = _build_student_identity_entry(
        evaluation=evaluation,
        index=index,
        include_student_names=include_student_names,
    )
    if task_type in {
        AgentTaskType.REMINDER_GENERATION,
        AgentTaskType.ANNOUNCEMENT_DRAFT,
    }:
        entry.update(
            {
                "status": evaluation.status_label,
                "isMissing": evaluation.is_missing,
                "isDueSoon": evaluation.is_due_soon,
                "notes": evaluation.notes,
            }
        )
        return entry
    if task_type is AgentTaskType.WEEKLY_REPORT:
        entry.update(
            {
                "status": evaluation.status_label,
                "isMissing": evaluation.is_missing,
                "isDueSoon": evaluation.is_due_soon,
                "isLate": evaluation.is_late,
                "attachmentMissingPossible": evaluation.attachment_missing_possible,
                "notes": evaluation.notes,
            }
        )
        return entry
    if task_type is AgentTaskType.RUBRIC_SUPPORT:
        entry.update(
            {
                "status": evaluation.status_label,
                "submissionState": evaluation.submission_state,
                "isLate": evaluation.is_late,
                "attachmentMissingPossible": evaluation.attachment_missing_possible,
                "attachmentCount": evaluation.attachment_count,
                "notes": evaluation.notes,
            }
        )
        return entry
    entry.update(
        {
            "status": evaluation.status_label,
            "submissionState": evaluation.submission_state,
            "isMissing": evaluation.is_missing,
            "isDueSoon": evaluation.is_due_soon,
            "isLate": evaluation.is_late,
            "attachmentMissingPossible": evaluation.attachment_missing_possible,
            "attachmentCount": evaluation.attachment_count,
            "notes": evaluation.notes,
        }
    )
    return entry


def _build_student_identity_entry(
    *,
    evaluation: SubmissionEvaluation,
    index: int,
    include_student_names: bool,
) -> dict[str, Any]:
    entry = {
        "studentRef": f"student_{index:03d}",
    }
    if include_student_names:
        entry["studentId"] = evaluation.student_id
        entry["studentName"] = evaluation.student_name
    return entry


def _selection_mode_label(task_type: AgentTaskType) -> str:
    if task_type in {
        AgentTaskType.COURSE_SUMMARY,
        AgentTaskType.COURSEWORK_SUMMARY,
        AgentTaskType.DOCUMENT_EXPORT,
        AgentTaskType.ERROR_ANALYSIS,
    }:
        return "aggregate_only"
    if task_type in {
        AgentTaskType.REMINDER_GENERATION,
        AgentTaskType.ANNOUNCEMENT_DRAFT,
    }:
        return "unsubmitted_targets"
    if task_type is AgentTaskType.WEEKLY_REPORT:
        return "flagged_students_only"
    if task_type is AgentTaskType.RUBRIC_SUPPORT:
        return "submitted_students_only"
    return "all_students"


def _build_input_warnings(analysis: SubmissionAnalysis) -> list[str]:
    warnings: list[str] = []
    if analysis.normalization_issues:
        warnings.append("一部データの正規化に失敗しているため、集計は完全でない可能性があります。")
    if analysis.exempt_like:
        warnings.append(
            "採点済みの未提出状態が含まれるため、提出免除または個別対応済みの可能性があります。"
        )
    if analysis.attachment_flags:
        warnings.append("添付不足の可能性は推定であり、実際の提出内容確認が必要です。")
    return warnings


def _summarize_evaluations(
    evaluations: list[SubmissionEvaluation],
) -> dict[str, int]:
    return {
        "targetStudentCount": len(evaluations),
        "missingCount": sum(entry.is_missing for entry in evaluations),
        "dueSoonCount": sum(entry.is_due_soon for entry in evaluations),
        "lateCount": sum(entry.is_late for entry in evaluations),
        "attachmentMissingPossibleCount": sum(
            entry.attachment_missing_possible for entry in evaluations
        ),
    }


def _deduplicate_evaluations(
    evaluations: list[SubmissionEvaluation],
) -> list[SubmissionEvaluation]:
    unique_entries: list[SubmissionEvaluation] = []
    seen_student_ids: set[str] = set()
    for entry in evaluations:
        if entry.student_id in seen_student_ids:
            continue
        seen_student_ids.add(entry.student_id)
        unique_entries.append(entry)
    return unique_entries


def _has_grading_signal(submission: StudentSubmission) -> bool:
    return (
        submission.assigned_grade is not None
        or submission.draft_grade is not None
    )
