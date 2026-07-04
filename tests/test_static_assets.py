from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StaticAssetTests(unittest.TestCase):
    def test_frontend_entrypoints_exist(self) -> None:
        for relative_path in [
            "public/index.html",
            "public/styles.css",
            "public/app.js",
        ]:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_agent_contract_terms_are_rendered(self) -> None:
        app_js = (ROOT / "public/app.js").read_text(encoding="utf-8")
        for term in [
            "schemaVersion",
            "REMINDER_GENERATION",
            "editableFields",
            "normalizeAgentOutput",
            "partial_success",
            "CLASSROOM_API_PERMISSION_DENIED",
            "/api/live/courses",
            "/api/live/coursework",
            "/api/live/oauth/config",
            "/api/live/submission-analysis",
            "/api/live/reminder-generation",
            "/api/live/post-reminder",
            "buildEditedReminderPayload",
            "Google Classroomに接続",
            "OAuth client JSON を選択",
            "data-action=\"retry\"",
            "data-action=\"toggle-developer\"",
            "renderContractChecklist",
            "renderApprovalActions",
            "Raw JSON",
            "Normalized JSON",
            "aria-current=\"page\"",
            "aria-invalid=\"true\"",
        ]:
            with self.subTest(term=term):
                self.assertIn(term, app_js)

    def test_state_styles_are_available(self) -> None:
        styles = (ROOT / "public/styles.css").read_text(encoding="utf-8")
        for term in [
            ".segmented",
            ".state-panel",
            ".empty-state",
            ".error-item",
            ".field-error",
            ".skeleton",
            ".contract-list",
            ".approval-action",
            ".developer-panel",
            ".json-preview",
        ]:
            with self.subTest(term=term):
                self.assertIn(term, styles)

    def test_server_serves_public_directory(self) -> None:
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("PUBLIC_DIR", main_py)
        self.assertIn("SimpleHTTPRequestHandler", main_py)
        self.assertIn("ClassroomPrototypeHandler", main_py)
        self.assertIn("/api/live/courses", main_py)


if __name__ == "__main__":
    unittest.main()
