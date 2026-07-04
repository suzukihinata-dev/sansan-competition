from __future__ import annotations

import unittest

from sansan_competition.contract import validate_agent_output
from sansan_competition.kimu_regression_gate import (
    EXPECTED_COUNTS,
    build_regression_artifacts,
    run_kimu_regression_gate,
)


class KimuRegressionGateTests(unittest.TestCase):
    def test_build_regression_artifacts_cover_contract_critical_path(self) -> None:
        artifacts = build_regression_artifacts()

        self.assertEqual(artifacts.analysis.counts(), EXPECTED_COUNTS)
        self.assertEqual(validate_agent_output(artifacts.submission_payload), [])
        self.assertEqual(validate_agent_output(artifacts.reminder_payload), [])
        self.assertEqual(
            artifacts.reminder_payload["outputs"]["classroomReminder"]["assigneeMode"],
            "INDIVIDUAL_STUDENTS",
        )
        self.assertEqual(
            artifacts.reminder_payload["outputs"]["classroomReminder"]["targetStudentIds"],
            artifacts.target_student_ids,
        )

    def test_run_kimu_regression_gate_passes(self) -> None:
        result = run_kimu_regression_gate()

        self.assertTrue(result.passed, result.errors)
        self.assertFalse(result.errors)
        self.assertTrue(any(detail.startswith("normalize:") for detail in result.details))
        self.assertTrue(any(detail.startswith("analysis:") for detail in result.details))


if __name__ == "__main__":
    unittest.main()
