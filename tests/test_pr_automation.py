from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sansan_competition.pr_automation import (
    CheckResult,
    build_report,
    collect_cache_artifacts,
    remove_cache_artifacts,
    run_cli_contract_checks,
    validate_common_contract,
)


class PrAutomationTests(unittest.TestCase):
    def test_validate_common_contract_requires_fixed_sections(self) -> None:
        issues = validate_common_contract(
            {
                "schemaVersion": "1.0.0",
                "requestId": "req",
                "generatedAt": "2026-07-03T13:00:00+09:00",
                "agentTaskType": "REMINDER_GENERATION",
                "status": "success",
                "summary": {
                    "title": "t",
                    "shortSummary": "s",
                    "teacherActionRequired": True,
                    "recommendedAction": "r",
                },
            }
        )
        self.assertIn("course must be an object", issues)
        self.assertIn("gui must be an object", issues)
        self.assertIn("outputs must be an object", issues)
        self.assertIn("approval must be an object", issues)
        self.assertIn("errors must be an array", issues)

    def test_collect_and_remove_cache_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cache_dir = root / "__pycache__"
            cache_dir.mkdir()
            pyc_file = cache_dir / "module.cpython-314.pyc"
            pyc_file.write_bytes(b"cache")

            artifacts = collect_cache_artifacts(root)
            self.assertIn(cache_dir, artifacts)

            removed = remove_cache_artifacts(artifacts)
            self.assertTrue(removed)
            self.assertFalse(cache_dir.exists())

    def test_cli_contract_checks_use_tool_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            tool_root = temp_root / ".workflow-tools"
            scripts_dir = tool_root / "scripts"
            scripts_dir.mkdir(parents=True)
            for script_name in ("review_implementation_agent.py", "pr_automation.py"):
                (scripts_dir / script_name).write_text(
                    "print('usage: tool')\n",
                    encoding="utf-8",
                )

            result = run_cli_contract_checks(tool_root)

            self.assertTrue(result.passed)
            self.assertTrue(any("help output valid" in detail for detail in result.details))
    def test_build_report_apply_fixes_cleans_post_check_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cache_dir = root / "__pycache__"
            cache_dir.mkdir()
            (cache_dir / "module.cpython-314.pyc").write_bytes(b"cache")

            def fake_pytest(repo_root: Path) -> CheckResult:
                recreated = repo_root / "__pycache__"
                recreated.mkdir(exist_ok=True)
                (recreated / "new.cpython-314.pyc").write_bytes(b"cache")
                return CheckResult(name="pytest", passed=True, details=["ok"])

            with (
                patch(
                    "sansan_competition.pr_automation.run_pytest",
                    side_effect=fake_pytest,
                ),
                patch(
                    "sansan_competition.pr_automation.run_cli_contract_checks",
                    return_value=CheckResult(
                        name="cli-contract",
                        passed=True,
                        details=["ok"],
                    ),
                ),
                patch(
                    "sansan_competition.pr_automation.run_agent_task_contract_checks",
                    return_value=CheckResult(
                        name="agent-contract",
                        passed=True,
                        details=["ok"],
                    ),
                ),
            ):
                report = build_report(root, apply_fixes=True)

            self.assertTrue(report.fixes_applied)
            self.assertFalse(cache_dir.exists())


if __name__ == "__main__":
    unittest.main()
