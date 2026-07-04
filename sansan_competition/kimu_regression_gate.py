from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

from .analysis import analyze_submissions
from .contract import (
    build_reminder_generation_response,
    build_submission_analysis_response,
    validate_agent_output,
)
from .execution.sample_data import COURSES, COURSEWORK, SUBMISSIONS
from .models import JST, SubmissionAnalysis
from .normalization import (
    normalize_course,
    normalize_coursework,
    normalize_submission_batch,
)

FIXED_NOW = datetime(2026, 7, 4, 12, 0, tzinfo=JST)
EXPECTED_COUNTS = {
    "totalStudents": 30,
    "submittedCount": 18,
    "unsubmittedCount": 12,
    "dueSoonCount": 12,
    "lateCount": 2,
    "attachmentMissingPossibleCount": 18,
}
REMINDER_TITLE = "二次関数プリント 提出リマインド"
REMINDER_BODY = (
    "課題「二次関数プリント」の提出期限は7月5日です。"
    "未提出の人は、内容を確認して期限内に提出してください。"
)


@dataclass(frozen=True, slots=True)
class RegressionArtifacts:
    analysis: SubmissionAnalysis
    submission_payload: dict[str, Any]
    reminder_payload: dict[str, Any]
    target_student_ids: list[str]


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    details: list[str]
    errors: list[str]


def build_regression_artifacts() -> RegressionArtifacts:
    raw_course = COURSES[0]
    raw_course_work = COURSEWORK[raw_course["id"]][0]
    raw_submissions = SUBMISSIONS[raw_course_work["id"]]

    course = normalize_course(raw_course)
    course_work = normalize_coursework(raw_course_work)
    submissions, issues = normalize_submission_batch(raw_submissions)
    analysis = analyze_submissions(
        course,
        course_work,
        submissions,
        now=FIXED_NOW,
        normalization_issues=issues,
    )
    target_student_ids = [entry.student_id for entry in analysis.unsubmitted]

    submission_payload = build_submission_analysis_response(
        "req_kimu_regression_submission",
        analysis,
    )
    reminder_payload = build_reminder_generation_response(
        "req_kimu_regression_reminder",
        analysis,
        reminder_title=REMINDER_TITLE,
        reminder_body=REMINDER_BODY,
        tone="polite",
        target_student_ids=target_student_ids,
    )

    return RegressionArtifacts(
        analysis=analysis,
        submission_payload=submission_payload,
        reminder_payload=reminder_payload,
        target_student_ids=target_student_ids,
    )


def run_kimu_regression_gate() -> GateResult:
    artifacts = build_regression_artifacts()
    analysis = artifacts.analysis
    course = analysis.course
    course_work = analysis.course_work
    counts = analysis.counts()

    details = [
        (
            "normalize: "
            f"course={course.course_id} teacherIds={course.teacher_ids} "
            f"courseWork={course_work.course_work_id} submissions={len(analysis.evaluations)} "
            f"issues={len(analysis.normalization_issues)}"
        ),
        (
            "analysis: "
            f"total={counts['totalStudents']} submitted={counts['submittedCount']} "
            f"unsubmitted={counts['unsubmittedCount']} dueSoon={counts['dueSoonCount']} "
            f"late={counts['lateCount']} attachmentFlags={counts['attachmentMissingPossibleCount']}"
        ),
    ]
    errors: list[str] = []

    _expect(course.teacher_ids == ["teacher_001"], "teacherIds alias normalization regressed.", errors)
    _expect(course_work.due_date == "2026-07-05", "dueDate normalization regressed.", errors)
    _expect(course_work.due_time == "23:59", "dueTime normalization regressed.", errors)
    _expect(not analysis.normalization_issues, "sample normalization produced unexpected issues.", errors)
    _expect(counts == EXPECTED_COUNTS, f"analysis counts changed: {counts!r}", errors)
    _expect(
        all(entry.is_due_soon for entry in analysis.unsubmitted),
        "unsubmitted entries are no longer classified as due soon in the fixed scenario.",
        errors,
    )

    submission_details = _validate_submission_payload(artifacts.submission_payload, analysis, errors)
    reminder_details = _validate_reminder_payload(
        artifacts.reminder_payload,
        analysis,
        artifacts.target_student_ids,
        errors,
    )
    details.extend((submission_details, reminder_details))
    return GateResult(passed=not errors, details=details, errors=errors)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="kimu-regression-gate",
        description=(
            "Run the focused kimu regression path: normalization -> analysis -> "
            "contract -> representative outputs."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    parse_args(argv)
    result = run_kimu_regression_gate()
    for detail in result.details:
        print(detail)
    if result.passed:
        print("kimu regression gate: PASS")
        return 0

    print("kimu regression gate: FAIL")
    for error in result.errors:
        print(f"- {error}")
    return 1


def _validate_submission_payload(
    payload: dict[str, Any],
    analysis: SubmissionAnalysis,
    errors: list[str],
) -> str:
    _expect_valid_contract("submission analysis", payload, errors)
    outputs = payload.get("outputs") or {}
    markdown = outputs.get("markdown") or {}
    pdf = outputs.get("pdf") or {}
    google_document = outputs.get("googleDocument") or {}

    _expect(outputs.get("classroomReminder") is None, "submission analysis should not emit classroomReminder.", errors)
    _expect(
        analysis.course_work.title in str(markdown.get("content", "")),
        "submission markdown output no longer references the target coursework title.",
        errors,
    )
    _expect(
        _section_headings(pdf) == ["概要", "集計", "未提出者一覧", "遅延提出者一覧", "AIによる提案"],
        "submission pdf output headings changed unexpectedly.",
        errors,
    )
    _expect(
        _table_block_count(google_document) >= 3,
        "submission Google Document output is missing representative tables.",
        errors,
    )
    _expect(
        _payload_refs(payload) == {
            "outputs.markdown",
            "outputs.pdf",
            "outputs.googleDocument",
        },
        "submission approval payload refs changed unexpectedly.",
        errors,
    )
    return "submission contract: markdown/pdf/googleDocument verified"


def _validate_reminder_payload(
    payload: dict[str, Any],
    analysis: SubmissionAnalysis,
    target_student_ids: list[str],
    errors: list[str],
) -> str:
    _expect_valid_contract("reminder", payload, errors)
    outputs = payload.get("outputs") or {}
    markdown = outputs.get("markdown") or {}
    pdf = outputs.get("pdf") or {}
    google_document = outputs.get("googleDocument") or {}
    classroom_reminder = outputs.get("classroomReminder") or {}

    _expect(payload.get("approval", {}).get("required") is True, "reminder payload must require teacher approval.", errors)
    _expect(
        classroom_reminder.get("assigneeMode") == "INDIVIDUAL_STUDENTS",
        "reminder payload should stay targeted to individual students in this regression fixture.",
        errors,
    )
    _expect(
        classroom_reminder.get("targetStudentIds") == target_student_ids,
        "reminder targetStudentIds no longer match the analyzed unsubmitted list.",
        errors,
    )
    _expect(
        classroom_reminder.get("target") == {
            "courseId": analysis.course.course_id,
            "courseWorkId": analysis.course_work.course_work_id,
        },
        "reminder output target changed unexpectedly.",
        errors,
    )
    _expect(
        f"未提出者数: {len(analysis.unsubmitted)}名" in str(markdown.get("content", "")),
        "reminder markdown output no longer carries the unsubmitted count.",
        errors,
    )
    _expect(
        _section_headings(pdf) == ["対象", "投稿案", "注意事項"],
        "reminder pdf output headings changed unexpectedly.",
        errors,
    )
    _expect(
        any(block.get("type") == "bulletList" for block in google_document.get("blocks", [])),
        "reminder Google Document output is missing the approval/privacy guidance block.",
        errors,
    )
    _expect(
        _payload_refs(payload) == {
            "outputs.classroomReminder",
            "outputs.markdown",
            "outputs.pdf",
        },
        "reminder approval payload refs changed unexpectedly.",
        errors,
    )
    return (
        "reminder contract: "
        f"targets={len(target_student_ids)} assigneeMode={classroom_reminder.get('assigneeMode')}"
    )


def _payload_refs(payload: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    actions = payload.get("approval", {}).get("actions") or []
    for action in actions:
        if not isinstance(action, dict):
            continue
        payload_ref = action.get("payloadRef")
        if isinstance(payload_ref, str) and payload_ref:
            refs.add(payload_ref)
    return refs


def _section_headings(payload: dict[str, Any]) -> list[str]:
    sections = payload.get("sections", [])
    return [
        str(section.get("heading"))
        for section in sections
        if isinstance(section, dict) and isinstance(section.get("heading"), str)
    ]


def _table_block_count(payload: dict[str, Any]) -> int:
    blocks = payload.get("blocks", [])
    return sum(
        1
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "table"
    )


def _expect_valid_contract(
    label: str,
    payload: dict[str, Any],
    errors: list[str],
) -> None:
    issues = validate_agent_output(payload)
    _expect(
        not issues,
        f"{label} payload is not contract-valid: {'; '.join(issues)}",
        errors,
    )


def _expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)
