from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from sansan_competition.oauth import (
    CLASSROOM_ANNOUNCEMENTS_SCOPE,
    CLASSROOM_COURSES_READONLY_SCOPE,
    CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE,
    CLASSROOM_STUDENT_SUBMISSIONS_STUDENTS_READONLY_SCOPE,
    GoogleOAuthConfig,
    GoogleOAuthAuthorizationRequiredError,
    complete_google_oauth_authorization,
    load_google_user_credentials,
    start_google_oauth_authorization,
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
        self.credentials = returned_creds
        self.redirect_uri: str | None = None
        self.code_verifier: str | None = None
        self.require_relaxed_token_scope = False
        self.run_local_server_calls: list[int] = []
        self.authorization_url_calls: list[dict[str, object]] = []
        self.fetch_token_calls: list[str] = []

    def run_local_server(self, *, port: int) -> FakeCreds:
        self.run_local_server_calls.append(port)
        return self.credentials

    def authorization_url(self, **kwargs: object) -> tuple[str, str]:
        self.authorization_url_calls.append(kwargs)
        if self.code_verifier is None:
            self.code_verifier = "verifier-123"
        return ("https://accounts.example.test/auth", "state-123")

    def fetch_token(self, *, authorization_response: str) -> None:
        if self.require_relaxed_token_scope and not os.environ.get(
            "OAUTHLIB_RELAX_TOKEN_SCOPE"
        ):
            raise Warning("Scope has changed.")
        self.fetch_token_calls.append(authorization_response)


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
        requested_scopes_calls: list[tuple[str, ...]] = []
        fake_credentials_class = types.SimpleNamespace(
            from_authorized_user_file=lambda path, scopes: (
                requested_scopes_calls.append(tuple(scopes)),
                cached_creds,
            )[1]
        )
        fake_flow_class = types.SimpleNamespace(
            from_client_secrets_file=lambda path, scopes, state=None: fake_flow
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
        ), fake_flow, requested_scopes_calls

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
        modules_patch, fake_flow, _ = self._patch_google_modules(
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
        modules_patch, fake_flow, _ = self._patch_google_modules(
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
        modules_patch, fake_flow, _ = self._patch_google_modules(
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

    def test_noninteractive_mode_raises_authorization_required(self) -> None:
        cached_creds = FakeCreds(
            valid=False,
            scopes=(),
            has_scopes_result=False,
        )
        refreshed_creds = FakeCreds(
            valid=True,
            scopes=("scope.a",),
            has_scopes_result=True,
        )
        modules_patch, _, _ = self._patch_google_modules(
            cached_creds=cached_creds,
            refreshed_creds=refreshed_creds,
        )

        with modules_patch:
            with self.assertRaises(GoogleOAuthAuthorizationRequiredError):
                load_google_user_credentials(
                    ("scope.b",),
                    config=GoogleOAuthConfig(
                        credentials_path=self.credentials_path,
                        token_path=self.token_path,
                    ),
                    allow_interactive=False,
                )

    def test_start_google_oauth_authorization_returns_url_and_state(self) -> None:
        cached_creds = FakeCreds(
            valid=True,
            scopes=("scope.a",),
            has_scopes_result=True,
        )
        refreshed_creds = FakeCreds(
            valid=True,
            scopes=("scope.a",),
            has_scopes_result=True,
        )
        modules_patch, fake_flow, _ = self._patch_google_modules(
            cached_creds=cached_creds,
            refreshed_creds=refreshed_creds,
        )

        with modules_patch:
            request = start_google_oauth_authorization(
                ("scope.a",),
                redirect_uri="http://127.0.0.1:8000/oauth/google/callback",
                config=GoogleOAuthConfig(
                    credentials_path=self.credentials_path,
                    token_path=self.token_path,
                ),
            )

        self.assertEqual(request.authorization_url, "https://accounts.example.test/auth")
        self.assertEqual(request.state, "state-123")
        self.assertEqual(request.code_verifier, "verifier-123")
        self.assertEqual(
            fake_flow.redirect_uri,
            "http://127.0.0.1:8000/oauth/google/callback",
        )
        self.assertEqual(
            fake_flow.authorization_url_calls,
            [
                {
                    "access_type": "offline",
                    "include_granted_scopes": "true",
                    "prompt": "consent",
                }
            ],
        )

    def test_start_google_oauth_authorization_preserves_cached_scopes(self) -> None:
        cached_creds = FakeCreds(
            valid=True,
            scopes=(CLASSROOM_ANNOUNCEMENTS_SCOPE,),
            has_scopes_result=True,
        )
        refreshed_creds = FakeCreds(
            valid=True,
            scopes=(CLASSROOM_COURSES_READONLY_SCOPE, CLASSROOM_ANNOUNCEMENTS_SCOPE),
            has_scopes_result=True,
        )
        self.token_path.write_text(
            json.dumps(
                {
                    "token": "old",
                    "scopes": [CLASSROOM_ANNOUNCEMENTS_SCOPE],
                }
            ),
            encoding="utf-8",
        )
        modules_patch, _, _ = self._patch_google_modules(
            cached_creds=cached_creds,
            refreshed_creds=refreshed_creds,
        )

        with modules_patch:
            request = start_google_oauth_authorization(
                (CLASSROOM_COURSES_READONLY_SCOPE,),
                redirect_uri="http://127.0.0.1:8000/oauth/google/callback",
                config=GoogleOAuthConfig(
                    credentials_path=self.credentials_path,
                    token_path=self.token_path,
                ),
            )

        self.assertEqual(
            request.scopes,
            (
                CLASSROOM_COURSES_READONLY_SCOPE,
                CLASSROOM_ANNOUNCEMENTS_SCOPE,
            ),
        )

    def test_complete_google_oauth_authorization_writes_token(self) -> None:
        cached_creds = FakeCreds(
            valid=True,
            scopes=("scope.a",),
            has_scopes_result=True,
        )
        refreshed_creds = FakeCreds(
            valid=True,
            scopes=("scope.a", "scope.b"),
            has_scopes_result=True,
            token_json='{"token":"new","scopes":["scope.a","scope.b"]}',
        )
        modules_patch, fake_flow, _ = self._patch_google_modules(
            cached_creds=cached_creds,
            refreshed_creds=refreshed_creds,
        )

        with modules_patch:
            creds = complete_google_oauth_authorization(
                ("scope.a", "scope.b"),
                state="state-123",
                authorization_response=(
                    "http://127.0.0.1:8000/oauth/google/callback?state=state-123&code=abc"
                ),
                redirect_uri="http://127.0.0.1:8000/oauth/google/callback",
                code_verifier="verifier-123",
                config=GoogleOAuthConfig(
                    credentials_path=self.credentials_path,
                    token_path=self.token_path,
                ),
            )

        self.assertIs(creds, refreshed_creds)
        self.assertEqual(
            fake_flow.redirect_uri,
            "http://127.0.0.1:8000/oauth/google/callback",
        )
        self.assertEqual(
            fake_flow.fetch_token_calls,
            ["https://127.0.0.1:8000/oauth/google/callback?state=state-123&code=abc"],
        )
        self.assertEqual(fake_flow.code_verifier, "verifier-123")
        self.assertEqual(
            json.loads(self.token_path.read_text(encoding="utf-8"))["token"],
            "new",
        )

    def test_complete_google_oauth_authorization_coerces_loopback_response_to_https(self) -> None:
        cached_creds = FakeCreds(
            valid=True,
            scopes=("scope.a",),
            has_scopes_result=True,
        )
        refreshed_creds = FakeCreds(
            valid=True,
            scopes=("scope.a", "scope.b"),
            has_scopes_result=True,
            token_json='{"token":"new","scopes":["scope.a","scope.b"]}',
        )
        modules_patch, fake_flow, _ = self._patch_google_modules(
            cached_creds=cached_creds,
            refreshed_creds=refreshed_creds,
        )

        with modules_patch:
            complete_google_oauth_authorization(
                ("scope.a", "scope.b"),
                state="state-123",
                authorization_response=(
                    "http://127.0.0.1:8000/?state=state-123&code=abc"
                ),
                redirect_uri="http://localhost:8000",
                code_verifier="verifier-123",
                config=GoogleOAuthConfig(
                    credentials_path=self.credentials_path,
                    token_path=self.token_path,
                ),
            )

        self.assertEqual(
            fake_flow.fetch_token_calls,
            ["https://127.0.0.1:8000/?state=state-123&code=abc"],
        )

    def test_complete_google_oauth_authorization_accepts_google_scope_alias(self) -> None:
        self.token_path.write_text('{"token":"old","scopes":[]}', encoding="utf-8")
        cached_creds = FakeCreds(
            valid=True,
            scopes=("scope.a",),
            has_scopes_result=True,
        )
        refreshed_creds = FakeCreds(
            valid=True,
            scopes=(CLASSROOM_STUDENT_SUBMISSIONS_STUDENTS_READONLY_SCOPE,),
            has_scopes_result=False,
            token_json=json.dumps(
                {
                    "token": "new",
                    "scopes": [CLASSROOM_STUDENT_SUBMISSIONS_STUDENTS_READONLY_SCOPE],
                }
            ),
        )
        modules_patch, fake_flow, _ = self._patch_google_modules(
            cached_creds=cached_creds,
            refreshed_creds=refreshed_creds,
        )
        fake_flow.require_relaxed_token_scope = True

        with modules_patch:
            creds = complete_google_oauth_authorization(
                (CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE,),
                state="state-123",
                authorization_response="http://127.0.0.1:8000/?state=state-123&code=abc",
                redirect_uri="http://localhost:8000",
                code_verifier="verifier-123",
                config=GoogleOAuthConfig(
                    credentials_path=self.credentials_path,
                    token_path=self.token_path,
                ),
            )

        self.assertIs(creds, refreshed_creds)

    def test_complete_google_oauth_authorization_rejects_missing_granted_scope(self) -> None:
        self.token_path.write_text('{"token":"old","scopes":[]}', encoding="utf-8")
        cached_creds = FakeCreds(
            valid=True,
            scopes=("scope.a",),
            has_scopes_result=True,
        )
        refreshed_creds = FakeCreds(
            valid=True,
            scopes=("scope.unrelated",),
            has_scopes_result=False,
        )
        modules_patch, fake_flow, _ = self._patch_google_modules(
            cached_creds=cached_creds,
            refreshed_creds=refreshed_creds,
        )
        fake_flow.require_relaxed_token_scope = True

        with modules_patch:
            with self.assertRaises(RuntimeError):
                complete_google_oauth_authorization(
                    (CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE,),
                    state="state-123",
                    authorization_response="http://127.0.0.1:8000/?state=state-123&code=abc",
                    redirect_uri="http://localhost:8000",
                    code_verifier="verifier-123",
                    config=GoogleOAuthConfig(
                        credentials_path=self.credentials_path,
                        token_path=self.token_path,
                    ),
                )

    def test_refresh_preserves_cached_scope_union(self) -> None:
        cached_creds = FakeCreds(
            valid=False,
            expired=True,
            refresh_token="refresh-token",
            scopes=(
                CLASSROOM_COURSES_READONLY_SCOPE,
                CLASSROOM_ANNOUNCEMENTS_SCOPE,
            ),
            has_scopes_result=True,
            token_json=json.dumps(
                {
                    "token": "refreshed",
                    "scopes": [
                        CLASSROOM_COURSES_READONLY_SCOPE,
                        CLASSROOM_ANNOUNCEMENTS_SCOPE,
                    ],
                }
            ),
        )
        refreshed_creds = FakeCreds(
            valid=True,
            scopes=(
                CLASSROOM_COURSES_READONLY_SCOPE,
                CLASSROOM_ANNOUNCEMENTS_SCOPE,
            ),
            has_scopes_result=True,
        )
        self.token_path.write_text(
            json.dumps(
                {
                    "token": "old",
                    "refresh_token": "refresh-token",
                    "scopes": [
                        CLASSROOM_COURSES_READONLY_SCOPE,
                        CLASSROOM_ANNOUNCEMENTS_SCOPE,
                    ],
                }
            ),
            encoding="utf-8",
        )
        modules_patch, _, requested_scopes_calls = self._patch_google_modules(
            cached_creds=cached_creds,
            refreshed_creds=refreshed_creds,
        )

        with modules_patch:
            creds = load_google_user_credentials(
                (CLASSROOM_COURSES_READONLY_SCOPE,),
                config=GoogleOAuthConfig(
                    credentials_path=self.credentials_path,
                    token_path=self.token_path,
                ),
            )

        self.assertIs(creds, cached_creds)
        self.assertTrue(cached_creds.refreshed)
        self.assertEqual(
            requested_scopes_calls,
            [
                (
                    CLASSROOM_COURSES_READONLY_SCOPE,
                    CLASSROOM_ANNOUNCEMENTS_SCOPE,
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
