from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from sansan_competition.oauth import (
    CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE,
    CLASSROOM_STUDENT_SUBMISSIONS_STUDENTS_READONLY_SCOPE,
    GoogleOAuthConfig,
    load_google_user_credentials,
)


class FakeCreds:
    def __init__(
        self,
        *,
        valid: bool,
        scopes: tuple[str, ...],
        has_scopes_result: bool,
        expired: bool = False,
        refresh_token: str | None = None,
        token_json: str = '{"token":"cached"}',
    ) -> None:
        self.valid = valid
        self.scopes = scopes
        self.expired = expired
        self.refresh_token = refresh_token
        self._has_scopes_result = has_scopes_result
        self._token_json = token_json
        self.refreshed = False

    def has_scopes(self, scopes: tuple[str, ...]) -> bool:
        return self._has_scopes_result

    def refresh(self, _request: object) -> None:
        self.refreshed = True
        self.valid = True

    def to_json(self) -> str:
        return self._token_json


class FakeFlow:
    def __init__(self, returned_creds: FakeCreds) -> None:
        self._returned_creds = returned_creds
        self.run_local_server_calls: list[int] = []

    def run_local_server(self, *, port: int) -> FakeCreds:
        self.run_local_server_calls.append(port)
        return self._returned_creds


class OAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.credentials_path = Path(self.temp_dir.name) / "credentials.json"
        self.token_path = Path(self.temp_dir.name) / "token.json"
        self.credentials_path.write_text('{"installed":{"client_id":"dummy"}}', encoding="utf-8")
        self.token_path.write_text(
            '{"token":"old","scopes":["scope.a"]}',
            encoding="utf-8",
        )

    def _patch_google_modules(
        self,
        *,
        cached_creds: FakeCreds,
        refreshed_creds: FakeCreds,
    ):
        fake_flow = FakeFlow(refreshed_creds)
        fake_credentials_class = types.SimpleNamespace(
            from_authorized_user_file=lambda path, scopes: cached_creds
        )
        fake_flow_class = types.SimpleNamespace(
            from_client_secrets_file=lambda path, scopes: fake_flow
        )
        fake_request_class = type("FakeRequest", (), {})

        return patch.dict(
            sys.modules,
            {
                "google": types.ModuleType("google"),
                "google.auth": types.ModuleType("google.auth"),
                "google.auth.transport": types.ModuleType("google.auth.transport"),
                "google.auth.transport.requests": types.SimpleNamespace(Request=fake_request_class),
                "google.oauth2": types.ModuleType("google.oauth2"),
                "google.oauth2.credentials": types.SimpleNamespace(Credentials=fake_credentials_class),
                "google_auth_oauthlib": types.ModuleType("google_auth_oauthlib"),
                "google_auth_oauthlib.flow": types.SimpleNamespace(InstalledAppFlow=fake_flow_class),
            },
        ), fake_flow

    def test_reauthorizes_when_cached_token_lacks_requested_scopes(self) -> None:
        cached_creds = FakeCreds(
            valid=True,
            scopes=("scope.a",),
            has_scopes_result=True,
            token_json='{"token":"old"}',
        )
        refreshed_creds = FakeCreds(
            valid=True,
            scopes=("scope.a", "scope.b"),
            has_scopes_result=True,
            token_json='{"token":"new"}',
        )
        modules_patch, fake_flow = self._patch_google_modules(
            cached_creds=cached_creds,
            refreshed_creds=refreshed_creds,
        )

        with modules_patch:
            creds = load_google_user_credentials(
                ("scope.a", "scope.b"),
                config=GoogleOAuthConfig(
                    credentials_path=self.credentials_path,
                    token_path=self.token_path,
                ),
            )

        self.assertIs(creds, refreshed_creds)
        self.assertEqual(fake_flow.run_local_server_calls, [0])
        self.assertEqual(
            json.loads(self.token_path.read_text(encoding="utf-8"))["token"],
            "new",
        )

    def test_keeps_cached_token_when_requested_scopes_are_already_granted(self) -> None:
        cached_creds = FakeCreds(
            valid=True,
            scopes=("scope.a", "scope.b"),
            has_scopes_result=True,
            token_json='{"token":"old"}',
        )
        refreshed_creds = FakeCreds(
            valid=True,
            scopes=("scope.a", "scope.b"),
            has_scopes_result=True,
            token_json='{"token":"new"}',
        )
        self.token_path.write_text(
            '{"token":"old","scopes":["scope.a","scope.b"]}',
            encoding="utf-8",
        )
        modules_patch, fake_flow = self._patch_google_modules(
            cached_creds=cached_creds,
            refreshed_creds=refreshed_creds,
        )

        with modules_patch:
            creds = load_google_user_credentials(
                ("scope.a", "scope.b"),
                config=GoogleOAuthConfig(
                    credentials_path=self.credentials_path,
                    token_path=self.token_path,
                ),
            )

        self.assertIs(creds, cached_creds)
        self.assertEqual(fake_flow.run_local_server_calls, [])
        self.assertEqual(
            json.loads(self.token_path.read_text(encoding="utf-8"))["token"],
            "old",
        )

    def test_accepts_google_returned_submission_scope_for_coursework_readonly_request(self) -> None:
        cached_creds = FakeCreds(
            valid=True,
            scopes=(CLASSROOM_STUDENT_SUBMISSIONS_STUDENTS_READONLY_SCOPE,),
            has_scopes_result=True,
            token_json='{"token":"old"}',
        )
        refreshed_creds = FakeCreds(
            valid=True,
            scopes=(CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE,),
            has_scopes_result=True,
            token_json='{"token":"new"}',
        )
        self.token_path.write_text(
            json.dumps(
                {
                    "token": "old",
                    "scopes": [CLASSROOM_STUDENT_SUBMISSIONS_STUDENTS_READONLY_SCOPE],
                }
            ),
            encoding="utf-8",
        )
        modules_patch, fake_flow = self._patch_google_modules(
            cached_creds=cached_creds,
            refreshed_creds=refreshed_creds,
        )

        with modules_patch:
            creds = load_google_user_credentials(
                (CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE,),
                config=GoogleOAuthConfig(
                    credentials_path=self.credentials_path,
                    token_path=self.token_path,
                ),
            )

        self.assertIs(creds, cached_creds)
        self.assertEqual(fake_flow.run_local_server_calls, [])


if __name__ == "__main__":
    unittest.main()
