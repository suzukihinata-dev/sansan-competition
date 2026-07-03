from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from . import (
    Course,
    CourseWork,
    StudentSubmission,
    build_agent_output,
    validate_agent_output_dict,
)
from .contracts import ALLOWED_AGENT_TASK_TYPES

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
        ),
        StudentSubmission(
            student_submission_id="sub_2",
            course_id="123456789",
            course_work_id="987654321",
            student_id="student_2",
            student_name="佐藤花子",
            state="TURNED_IN",
            late=False,
        ),
    ]
    return course, coursework, submissions


def collect_cache_artifacts(repo_root: Path) -> list[Path]:
    artifacts: list[Path] = []
    for path in repo_root.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.name == CACHE_DIR_NAME and path.is_dir():
            artifacts.append(path)
            continue
        if path.is_file() and path.suffix in CACHE_SUFFIXES:
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


def validate_common_contract(payload: dict[str, object]) -> list[str]:
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


def run_command(
    args: Sequence[str],
    *,
    repo_root: Path,
) -> tuple[int, str]:
    completed = subprocess.run(
        args,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout.strip()
    if completed.stderr.strip():
        if output:
            output = f"{output}\n{completed.stderr.strip()}"
        else:
            output = completed.stderr.strip()
    return completed.returncode, output


def run_pytest(repo_root: Path) -> CheckResult:
    returncode, output = run_command(
        [sys.executable, "-m", "pytest", "-q"],
        repo_root=repo_root,
    )
    if returncode != 0 and "No module named pytest" in output:
        returncode, output = run_command(["pytest", "-q"], repo_root=repo_root)
    details = [output or "pytest completed without output"]
    return CheckResult(name="pytest", passed=returncode == 0, details=details)


def run_cli_contract_checks(repo_root: Path) -> CheckResult:
    details: list[str] = []
    passed = True
    for command in (["main.py", "sample-reminder"], ["main.py", "sample-course-summary"]):
        returncode, output = run_command([sys.executable, *command], repo_root=repo_root)
        command_name = " ".join(command)
        if returncode != 0:
            passed = False
            details.append(f"{command_name}: command failed")
            if output:
                details.append(output)
            continue
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            passed = False
            details.append(f"{command_name}: invalid JSON ({exc})")
            continue
        issues = validate_common_contract(payload)
        if issues:
            passed = False
            details.append(f"{command_name}: " + "; ".join(issues))
        else:
            details.append(f"{command_name}: contract valid")
    return CheckResult(name="cli-contract", passed=passed, details=details)


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


def run_repo_hygiene_check(repo_root: Path) -> CheckResult:
    artifacts = collect_cache_artifacts(repo_root)
    if not artifacts:
        return CheckResult(
            name="repo-hygiene",
            passed=True,
            details=["no cache artifacts detected"],
        )
    return CheckResult(
        name="repo-hygiene",
        passed=False,
        details=[f"remove cache artifact: {path}" for path in artifacts],
    )


def build_report(repo_root: Path, *, apply_fixes: bool) -> AutomationReport:
    fixes_applied: list[str] = []
    if apply_fixes:
        cache_artifacts = collect_cache_artifacts(repo_root)
        removed = remove_cache_artifacts(cache_artifacts)
        fixes_applied.extend(f"removed {path}" for path in removed)

    checks = [
        run_repo_hygiene_check(repo_root),
        run_pytest(repo_root),
        run_cli_contract_checks(repo_root),
        run_agent_task_contract_checks(),
    ]
    return AutomationReport(fixes_applied=fixes_applied, checks=checks)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pr-automation")
    parser.add_argument("--apply-fixes", action="store_true")
    parser.add_argument("--report-path", default="")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    report = build_report(repo_root, apply_fixes=args.apply_fixes)
    markdown = report.to_markdown()
    if args.report_path:
        Path(args.report_path).write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
