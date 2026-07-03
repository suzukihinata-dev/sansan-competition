from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sansan_competition.pr_automation import (
    collect_cache_artifacts,
    remove_cache_artifacts,
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


if __name__ == "__main__":
    unittest.main()
