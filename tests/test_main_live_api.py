from __future__ import annotations

from http.cookies import SimpleCookie
import json
import os
import threading
import tempfile
import types
import unittest
from pathlib import Path
from urllib import error, request
from unittest.mock import patch

import main as app_main
import sansan_competition.oauth as oauth_module
from sansan_competition.contract import (
    build_reminder_generation_response,
    build_submission_analysis_response,
    validate_agent_output,
)
from sansan_competition.execution.errors import AgentError, ErrorCode


class FakeCourseClient:
    def __init__(
        self,
        *,
        courses: list[dict] | None = None,
        coursework: list[dict] | None = None,
        courses_error: Exception | None = None,
        coursework_error: Exception | None = None,
    ) -> None:
        self._courses = courses or []
        self._coursework = coursework or []
        self._courses_error = courses_error
        self._coursework_error = coursework_error
        self.list_courses_calls: list[dict] = []
        self.list_coursework_calls: list[dict] = []

    def list_courses(self, **kwargs) -> list[dict]:
        self.list_courses_calls.append(kwargs)
        if self._courses_error is not None:
            raise self._courses_error
        return list(self._courses)

    def list_coursework(self, course_id: str, **kwargs) -> list[dict]:
        self.list_coursework_calls.append({"course_id": course_id, **kwargs})
        if self._coursework_error is not None:
            raise self._coursework_error
        return list(self._coursework)


class FakePostClient:
    def __init__(self) -> None:
        self.created_payloads: list[dict] = []

    def create_announcement_from_output(self, reminder_output: dict) -> dict:
        self.created_payloads.append(reminder_output)
        return {
            "id": "announcement_001",
            "alternateLink": "https://classroom.google.com/announcement_001",
        }


class LiveApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_log_message = app_main.ClassroomPrototypeHandler.log_message
        app_main.ClassroomPrototypeHandler.log_message = lambda *args: None
        with app_main.OAUTH_SESSIONS_LOCK:
            app_main.OAUTH_SESSIONS.clear()
        self.server = app_main.ReusableTCPServer(
            ("127.0.0.1", 0),
            app_main.ClassroomPrototypeHandler,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"
        self.course, self.course_work, self.analysis = app_main.build_sample_analysis()
        self.oauth_config = app_main.GoogleOAuthConfig(
            credentials_path=Path("credentials.json"),
            token_path=Path("token.json"),
        )
        self.direct_oauth_plan = types.SimpleNamespace(
            config=self.oauth_config,
            authorization_mode="direct_redirect",
            authorization_hint="Google の認可画面をこのブラウザで開きます。",
        )

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        with app_main.OAUTH_SESSIONS_LOCK:
            app_main.OAUTH_SESSIONS.clear()
        app_main.ClassroomPrototypeHandler.log_message = self._original_log_message

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict | None = None,
        headers: dict | None = None,
        return_headers: bool = False,
    ) -> tuple[int, dict] | tuple[int, dict, dict[str, str]]:
        body = None
        request_headers = dict(headers or {})
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with request.urlopen(req) as response:
                status_code = response.status
                response_body = response.read()
        except error.HTTPError as exc:
            status_code = exc.code
            response_body = exc.read()
            response_headers = dict(exc.headers.items())
            exc.close()
        else:
            response_headers = dict(response.headers.items())

        payload_dict = json.loads(response_body.decode("utf-8"))
        if return_headers:
            return status_code, payload_dict, response_headers
        return status_code, payload_dict

    def _request_raw(
        self,
        path: str,
        *,
        headers: dict | None = None,
    ) -> tuple[int, str]:
        req = request.Request(
            f"{self.base_url}{path}",
            headers=dict(headers or {}),
            method="GET",
        )
        try:
            with request.urlopen(req) as response:
                status_code = response.status
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            status_code = exc.code
            response_body = exc.read().decode("utf-8")
            exc.close()

        return status_code, response_body

    def _session_cookie_header(self, value: str) -> dict[str, str]:
        return {"Cookie": f"{app_main.OAUTH_BROWSER_SESSION_COOKIE_NAME}={value}"}

    def test_courses_endpoint_returns_normalized_items(self) -> None:
        fake_client = FakeCourseClient(
            courses=[
                {
                    "id": "course_001",
                    "name": "情報I",
                    "section": "1年B組",
                    "description": "情報の授業",
                    "state": "ACTIVE",
                    "teacherIds": ["teacher_001"],
                    "studentCount": 34,
                }
            ]
        )

        with patch.object(
            app_main.GoogleClassroomClient,
            "from_oauth",
            return_value=fake_client,
        ):
            status_code, payload = self._request_json("/api/live/courses")

        self.assertEqual(status_code, 200)
        self.assertEqual(fake_client.list_courses_calls, [{"course_states": ["ACTIVE"]}])
        self.assertEqual(payload["items"][0]["courseId"], "course_001")
        self.assertEqual(payload["items"][0]["studentCount"], 34)

    def test_courses_endpoint_returns_standardized_error_payload(self) -> None:
        fake_client = FakeCourseClient(
            courses_error=AgentError(ErrorCode.GOOGLE_AUTH_EXPIRED)
        )

        with patch.object(
            app_main.GoogleClassroomClient,
            "from_oauth",
            return_value=fake_client,
        ):
            status_code, payload = self._request_json("/api/live/courses")

        self.assertEqual(status_code, 500)
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["error"]["code"], "GOOGLE_AUTH_EXPIRED")

    def test_coursework_endpoint_returns_normalized_items(self) -> None:
        fake_client = FakeCourseClient(
            coursework=[
                {
                    "id": "cw_001",
                    "courseId": "course_001",
                    "title": "二次関数プリント",
                    "description": "配布プリントを解いて提出",
                    "workType": "ASSIGNMENT",
                    "state": "PUBLISHED",
                }
            ]
        )

        with patch.object(
            app_main.GoogleClassroomClient,
            "from_oauth",
            return_value=fake_client,
        ):
            status_code, payload = self._request_json(
                "/api/live/coursework?courseId=course_001"
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(
            fake_client.list_coursework_calls,
            [{"course_id": "course_001", "course_work_states": ["PUBLISHED"]}],
        )
        self.assertEqual(payload["items"][0]["courseWorkId"], "cw_001")
        self.assertEqual(payload["items"][0]["title"], "二次関数プリント")

    def test_coursework_endpoint_returns_standardized_error_payload(self) -> None:
        fake_client = FakeCourseClient(
            coursework_error=AgentError(ErrorCode.CLASSROOM_API_NOT_FOUND)
        )

        with patch.object(
            app_main.GoogleClassroomClient,
            "from_oauth",
            return_value=fake_client,
        ):
            status_code, payload = self._request_json(
                "/api/live/coursework?courseId=course_001"
            )

        self.assertEqual(status_code, 500)
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["error"]["code"], "CLASSROOM_API_NOT_FOUND")

    def test_oauth_start_reports_authorized_when_cached_token_is_ready(self) -> None:
        with (
            patch.object(
                app_main,
                "resolve_google_oauth_runtime_plan",
                return_value=self.direct_oauth_plan,
            ),
            patch.object(
                app_main,
                "load_google_user_credentials",
                return_value=object(),
            ),
        ):
            status_code, payload = self._request_json("/api/live/oauth/start?intent=read")

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "authorized")
        self.assertEqual(payload["intent"], "read")

    def test_oauth_check_reports_authorized_when_cached_token_is_ready(self) -> None:
        with (
            patch.object(
                app_main,
                "resolve_google_oauth_runtime_plan",
                return_value=self.direct_oauth_plan,
            ),
            patch.object(
                app_main,
                "load_google_user_credentials",
                return_value=object(),
            ),
        ):
            status_code, payload = self._request_json("/api/live/oauth/check?intent=read")

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "authorized")
        self.assertEqual(payload["intent"], "read")

    def test_oauth_check_reports_authorization_required_without_creating_session(self) -> None:
        with (
            patch.object(
                app_main,
                "resolve_google_oauth_runtime_plan",
                return_value=self.direct_oauth_plan,
            ),
            patch.object(
                app_main,
                "load_google_user_credentials",
                side_effect=app_main.GoogleOAuthAuthorizationRequiredError("required"),
            ),
        ):
            status_code, payload = self._request_json("/api/live/oauth/check?intent=read")

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "authorization_required")
        self.assertEqual(payload["intent"], "read")
        with app_main.OAUTH_SESSIONS_LOCK:
            self.assertEqual(app_main.OAUTH_SESSIONS, {})

    def test_oauth_config_sets_browser_session_cookie(self) -> None:
        status_code, payload, headers = self._request_json(
            "/api/live/oauth/config",
            return_headers=True,
        )

        self.assertEqual(status_code, 200)
        self.assertIn("Set-Cookie", headers)
        cookie = SimpleCookie()
        cookie.load(headers["Set-Cookie"])
        self.assertIn(app_main.OAUTH_BROWSER_SESSION_COOKIE_NAME, cookie)
        self.assertEqual(payload["browserSessionScoped"], True)

    def test_oauth_start_returns_authorization_url_when_grant_is_required(self) -> None:
        browser_session_id = "browser-session-123456"
        auth_request = types.SimpleNamespace(
            authorization_url="https://accounts.example.test/auth",
            state="oauth-state-123",
            scopes=app_main.OAUTH_INTENT_SCOPES["read"],
            code_verifier="verifier-123",
        )
        direct_plan_factory = lambda _redirect_uri, *, remote_browser_session, config=None: types.SimpleNamespace(
            config=config,
            authorization_mode="direct_redirect",
            authorization_hint="Google の認可画面をこのブラウザで開きます。",
        )

        with (
            patch.object(
                app_main,
                "resolve_google_oauth_runtime_plan",
                side_effect=direct_plan_factory,
            ),
            patch.object(
                app_main,
                "load_google_user_credentials",
                side_effect=app_main.GoogleOAuthAuthorizationRequiredError("required"),
            ),
            patch.object(
                app_main,
                "start_google_oauth_authorization",
                return_value=auth_request,
            ),
        ):
            status_code, payload = self._request_json(
                "/api/live/oauth/start?intent=read",
                headers=self._session_cookie_header(browser_session_id),
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "authorization_required")
        self.assertEqual(payload["authorizationMode"], "direct_redirect")
        self.assertEqual(
            payload["authorizationUrl"],
            "https://accounts.example.test/auth",
        )
        self.assertEqual(
            payload["statusUrl"],
            "/api/live/oauth/status?state=oauth-state-123",
        )
        with app_main.OAUTH_SESSIONS_LOCK:
            self.assertEqual(
                app_main.OAUTH_SESSIONS["oauth-state-123"]["scopes"],
                app_main.OAUTH_INTENT_SCOPES["read"],
            )
            self.assertEqual(
                app_main.OAUTH_SESSIONS["oauth-state-123"]["redirectUri"],
                f"{self.base_url}{app_main.OAUTH_CALLBACK_PATH}",
            )
            self.assertEqual(
                app_main.OAUTH_SESSIONS["oauth-state-123"]["codeVerifier"],
                "verifier-123",
            )
            self.assertEqual(
                app_main.OAUTH_SESSIONS["oauth-state-123"]["browserSessionId"],
                browser_session_id,
            )
            self.assertEqual(
                app_main.OAUTH_SESSIONS["oauth-state-123"]["tokenPath"],
                str(
                    app_main.build_browser_session_token_path(
                        browser_session_id,
                        base_config=app_main.GoogleOAuthConfig(),
                    )
                ),
            )

    def test_oauth_config_reports_missing_client_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {
                    "SANSAN_GOOGLE_OAUTH_CONFIG_DIR": temp_dir,
                    "SANSAN_GOOGLE_OAUTH_CLIENT_FILE": str(Path(temp_dir) / "credentials.json"),
                    "SANSAN_GOOGLE_OAUTH_TOKEN_FILE": str(Path(temp_dir) / "token.json"),
                },
                clear=False,
            ):
                status_code, payload = self._request_json("/api/live/oauth/config")

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "configuration_required")
        self.assertFalse(payload["clientFilePresent"])
        self.assertEqual(
            payload["redirectUri"],
            f"{self.base_url}{app_main.OAUTH_CALLBACK_PATH}",
        )

    def test_oauth_config_upload_persists_web_client_and_marks_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {
                    "SANSAN_GOOGLE_OAUTH_CONFIG_DIR": temp_dir,
                    "SANSAN_GOOGLE_OAUTH_CLIENT_FILE": str(Path(temp_dir) / "credentials.json"),
                    "SANSAN_GOOGLE_OAUTH_TOKEN_FILE": str(Path(temp_dir) / "token.json"),
                },
                clear=False,
            ):
                status_code, payload = self._request_json(
                    "/api/live/oauth/config",
                    method="POST",
                    payload={
                        "clientFileContent": json.dumps(
                            {
                                "web": {
                                    "client_id": "web-client-id",
                                    "client_secret": "secret",
                                    "redirect_uris": [
                                        f"{self.base_url}{app_main.OAUTH_CALLBACK_PATH}"
                                    ],
                                }
                            }
                        )
                    },
                )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["clientFilePresent"])
        self.assertEqual(payload["clientType"], "web")

    def test_oauth_config_supports_local_browser_assist_for_remote_installed_client(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_path = Path(temp_dir) / "credentials.json"
            credentials_path.write_text(
                json.dumps({"installed": {"client_id": "desktop-client-id"}}),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "SANSAN_GOOGLE_OAUTH_CONFIG_DIR": temp_dir,
                    "SANSAN_GOOGLE_OAUTH_CLIENT_FILE": str(credentials_path),
                    "SANSAN_GOOGLE_OAUTH_TOKEN_FILE": str(Path(temp_dir) / "token.json"),
                },
                clear=False,
            ):
                status_code, payload = self._request_json(
                    "/api/live/oauth/config",
                    headers={"Host": "classroom.example.test"},
                )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["authorizationMode"], "local_browser_assisted")
        self.assertIn("サーバーを実行している端末", payload["authorizationHint"])

    def test_oauth_config_prefers_forwarded_host_for_redirect_uri(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {
                    "SANSAN_GOOGLE_OAUTH_CONFIG_DIR": temp_dir,
                    "SANSAN_GOOGLE_OAUTH_CLIENT_FILE": str(Path(temp_dir) / "credentials.json"),
                    "SANSAN_GOOGLE_OAUTH_TOKEN_FILE": str(Path(temp_dir) / "token.json"),
                },
                clear=False,
            ):
                status_code, payload = self._request_json(
                    "/api/live/oauth/config",
                    headers={
                        "Host": "fh-example---service-a.run.app",
                        "X-Forwarded-Proto": "https",
                        "X-Forwarded-Host": "classroom-ai-kmc.web.app",
                    },
                )

        self.assertEqual(status_code, 200)
        self.assertEqual(
            payload["redirectUri"],
            "https://classroom-ai-kmc.web.app/oauth/google/callback",
        )
        self.assertEqual(payload["serverBaseUrl"], "https://classroom-ai-kmc.web.app")

    def test_oauth_config_prefers_legacy_installed_client_for_loopback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            (config_dir / "credentials.json").write_text(
                json.dumps(
                    {
                        "web": {
                            "client_id": "web-client-id",
                            "client_secret": "secret",
                            "redirect_uris": [],
                        }
                    }
                ),
                encoding="utf-8",
            )
            legacy_client_path = Path(temp_dir) / "repo-credentials.json"
            legacy_client_path.write_text(
                json.dumps(
                    {
                        "installed": {
                            "client_id": "desktop-client-id",
                            "redirect_uris": ["http://localhost"],
                        }
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "SANSAN_GOOGLE_OAUTH_CONFIG_DIR": str(config_dir),
                },
                clear=False,
            ), patch.object(
                oauth_module,
                "LEGACY_GOOGLE_OAUTH_CLIENT_PATH",
                legacy_client_path,
            ), patch.object(
                oauth_module,
                "LEGACY_GOOGLE_OAUTH_TOKEN_PATH",
                Path(temp_dir) / "repo-token.json",
            ):
                status_code, payload = self._request_json("/api/live/oauth/config")

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["clientType"], "installed")
        self.assertEqual(payload["clientFilePath"], str(legacy_client_path))

    def test_oauth_start_prefers_forwarded_host_for_redirect_uri(self) -> None:
        auth_request = types.SimpleNamespace(
            authorization_url="https://accounts.example.test/auth",
            state="oauth-state-123",
            code_verifier="verifier-123",
            scopes=app_main.OAUTH_INTENT_SCOPES["read"],
        )
        with patch.object(
            app_main,
            "resolve_google_oauth_runtime_plan",
            return_value=self.direct_oauth_plan,
        ), patch.object(
            app_main,
            "load_google_user_credentials",
            side_effect=app_main.GoogleOAuthAuthorizationRequiredError("required"),
        ), patch.object(
            app_main,
            "start_google_oauth_authorization",
            return_value=auth_request,
        ):
            status_code, payload = self._request_json(
                "/api/live/oauth/start?intent=read",
                headers={
                    "Host": "fh-example---service-a.run.app",
                    "X-Forwarded-Proto": "https",
                    "X-Forwarded-Host": "classroom-ai-kmc.web.app",
                },
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "authorization_required")
        with app_main.OAUTH_SESSIONS_LOCK:
            self.assertEqual(
                app_main.OAUTH_SESSIONS["oauth-state-123"]["redirectUri"],
                "https://classroom-ai-kmc.web.app/oauth/google/callback",
            )

    def test_oauth_start_uses_local_browser_assist_for_remote_installed_client(self) -> None:
        browser_session_id = "browser-session-654321"
        local_browser_plan = types.SimpleNamespace(
            config=self.oauth_config,
            authorization_mode="local_browser_assisted",
            authorization_hint=(
                "この端末ではなく、サーバーを実行している端末の既定ブラウザで "
                "Google の認可画面を開きます。"
            ),
        )
        with patch.object(
            app_main,
            "resolve_google_oauth_runtime_plan",
            return_value=local_browser_plan,
        ), patch.object(
            app_main,
            "load_google_user_credentials",
            side_effect=app_main.GoogleOAuthAuthorizationRequiredError("required"),
        ), patch.object(
            app_main,
            "start_local_browser_oauth_session",
        ) as start_local_browser:
            status_code, payload = self._request_json(
                "/api/live/oauth/start?intent=read",
                headers={
                    "Host": "192.168.1.20:8000",
                    **self._session_cookie_header(browser_session_id),
                },
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "authorization_required")
        self.assertEqual(payload["authorizationMode"], "local_browser_assisted")
        self.assertIn("サーバーを実行している端末", payload["authorizationHint"])
        self.assertIn("/api/live/oauth/status?state=", payload["statusUrl"])
        start_local_browser.assert_called_once()
        with app_main.OAUTH_SESSIONS_LOCK:
            self.assertEqual(len(app_main.OAUTH_SESSIONS), 1)
            state, session = next(iter(app_main.OAUTH_SESSIONS.items()))
            self.assertEqual(payload["statusUrl"], f"/api/live/oauth/status?state={state}")
            self.assertEqual(session["authorizationMode"], "local_browser_assisted")
            self.assertEqual(session["status"], "pending")
            self.assertEqual(session["browserSessionId"], browser_session_id)

    def test_oauth_status_returns_pending_session(self) -> None:
        with app_main.OAUTH_SESSIONS_LOCK:
            app_main.OAUTH_SESSIONS["oauth-state-123"] = {
                "createdAt": 9999999999.0,
                "browserSessionId": "browser-session-123456",
                "intent": "read",
                "redirectUri": "http://127.0.0.1:8000/oauth/google/callback",
                "scopes": app_main.OAUTH_INTENT_SCOPES["read"],
                "status": "pending",
            }

        status_code, payload = self._request_json(
            "/api/live/oauth/status?state=oauth-state-123",
            headers=self._session_cookie_header("browser-session-123456"),
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["intent"], "read")

    def test_oauth_status_rejects_other_browser_session(self) -> None:
        with app_main.OAUTH_SESSIONS_LOCK:
            app_main.OAUTH_SESSIONS["oauth-state-123"] = {
                "createdAt": 9999999999.0,
                "browserSessionId": "browser-session-123456",
                "intent": "read",
                "redirectUri": "http://127.0.0.1:8000/oauth/google/callback",
                "scopes": app_main.OAUTH_INTENT_SCOPES["read"],
                "status": "pending",
            }

        status_code, payload = self._request_json(
            "/api/live/oauth/status?state=oauth-state-123",
            headers=self._session_cookie_header("browser-session-OTHER999"),
        )

        self.assertEqual(status_code, 404)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "GOOGLE_AUTH_EXPIRED")

    def test_oauth_callback_marks_session_completed(self) -> None:
        with app_main.OAUTH_SESSIONS_LOCK:
            app_main.OAUTH_SESSIONS["oauth-state-123"] = {
                "createdAt": 9999999999.0,
                "browserSessionId": "browser-session-123456",
                "intent": "read",
                "redirectUri": "http://localhost:8000",
                "scopes": app_main.OAUTH_INTENT_SCOPES["read"],
                "codeVerifier": "verifier-123",
                "status": "pending",
            }

        with patch.object(
            app_main,
            "complete_google_oauth_authorization",
            return_value=object(),
        ) as complete_auth:
            status_code, body = self._request_raw(
                "/?state=oauth-state-123&code=example",
                headers=self._session_cookie_header("browser-session-123456"),
            )

        self.assertEqual(status_code, 200)
        self.assertIn("Google Classroom への接続が完了しました", body)
        complete_auth.assert_called_once()
        self.assertEqual(
            complete_auth.call_args.kwargs["code_verifier"],
            "verifier-123",
        )
        with app_main.OAUTH_SESSIONS_LOCK:
            self.assertEqual(
                app_main.OAUTH_SESSIONS["oauth-state-123"]["status"],
                "completed",
            )

    def test_oauth_logout_clears_browser_scoped_token_and_rotates_cookie(self) -> None:
        browser_session_id = "browser-session-123456"
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {
                    "SANSAN_GOOGLE_OAUTH_CONFIG_DIR": temp_dir,
                    "SANSAN_GOOGLE_OAUTH_CLIENT_FILE": str(Path(temp_dir) / "credentials.json"),
                    "SANSAN_GOOGLE_OAUTH_TOKEN_FILE": str(Path(temp_dir) / "token.json"),
                },
                clear=False,
            ):
                token_path = app_main.build_browser_session_token_path(
                    browser_session_id,
                    base_config=app_main.GoogleOAuthConfig(),
                )
                token_path.parent.mkdir(parents=True, exist_ok=True)
                token_path.write_text('{"token":"cached"}', encoding="utf-8")
                status_code, payload, headers = self._request_json(
                    "/api/live/oauth/logout",
                    method="POST",
                    headers=self._session_cookie_header(browser_session_id),
                    return_headers=True,
                )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "logged_out")
        self.assertFalse(token_path.exists())
        self.assertIn("Set-Cookie", headers)
        self.assertNotIn(browser_session_id, headers["Set-Cookie"])

    def test_courses_endpoint_uses_browser_scoped_oauth_config(self) -> None:
        fake_client = FakeCourseClient(courses=[])
        browser_session_id = "browser-session-123456"

        with patch.object(
            app_main.GoogleClassroomClient,
            "from_oauth",
            return_value=fake_client,
        ) as from_oauth:
            status_code, _payload = self._request_json(
                "/api/live/courses",
                headers=self._session_cookie_header(browser_session_id),
            )

        self.assertEqual(status_code, 200)
        oauth_config = from_oauth.call_args.kwargs["oauth_config"]
        self.assertEqual(
            oauth_config.token_path,
            app_main.build_browser_session_token_path(
                browser_session_id,
                base_config=app_main.GoogleOAuthConfig(),
            ),
        )

    def test_submission_analysis_endpoint_returns_contract_valid_payload(self) -> None:
        with (
            patch.object(app_main.GoogleClassroomClient, "from_oauth", return_value=object()),
            patch.object(
                app_main,
                "fetch_submission_analysis",
                return_value=self.analysis,
            ),
        ):
            status_code, payload = self._request_json(
                "/api/live/submission-analysis?courseId=course_001&courseWorkId=cw_001"
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["agentTaskType"], "SUBMISSION_ANALYSIS")
        self.assertEqual(payload["status"], "success")
        self.assertEqual(validate_agent_output(payload), [])
        self.assertEqual(
            payload,
            build_submission_analysis_response(payload["requestId"], self.analysis),
        )

    def test_submission_analysis_endpoint_maps_agent_error_to_contract_error(self) -> None:
        with (
            patch.object(app_main.GoogleClassroomClient, "from_oauth", return_value=object()),
            patch.object(
                app_main,
                "fetch_submission_analysis",
                side_effect=AgentError(ErrorCode.GOOGLE_AUTH_EXPIRED),
            ),
        ):
            status_code, payload = self._request_json(
                "/api/live/submission-analysis?courseId=course_001&courseWorkId=cw_001"
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["errors"][0]["code"], "GOOGLE_AUTH_EXPIRED")
        self.assertEqual(validate_agent_output(payload), [])

    def test_submission_analysis_endpoint_returns_partial_success_payload(self) -> None:
        _, _, partial_analysis = app_main.build_partial_sample_analysis()

        with (
            patch.object(app_main.GoogleClassroomClient, "from_oauth", return_value=object()),
            patch.object(
                app_main,
                "fetch_submission_analysis",
                return_value=partial_analysis,
            ),
        ):
            status_code, payload = self._request_json(
                "/api/live/submission-analysis?courseId=course_001&courseWorkId=cw_001"
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "partial_success")
        self.assertEqual(payload["errors"][0]["code"], "PARTIAL_CLASSROOM_DATA")
        self.assertEqual(validate_agent_output(payload), [])

    def test_reminder_generation_endpoint_returns_contract_valid_payload(self) -> None:
        with (
            patch.object(app_main.GoogleClassroomClient, "from_oauth", return_value=object()),
            patch.object(
                app_main,
                "fetch_submission_analysis",
                return_value=self.analysis,
            ),
        ):
            status_code, payload = self._request_json(
                "/api/live/reminder-generation?courseId=course_001&courseWorkId=cw_001"
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["agentTaskType"], "REMINDER_GENERATION")
        self.assertTrue(payload["approval"]["required"])
        self.assertEqual(validate_agent_output(payload), [])
        self.assertEqual(
            payload,
            build_reminder_generation_response(
                payload["requestId"],
                self.analysis,
                reminder_title=app_main.build_default_reminder_title(
                    self.analysis.course_work
                ),
                reminder_body=app_main.build_default_reminder_body(self.analysis),
            ),
        )

    def test_reminder_generation_endpoint_returns_partial_success_payload(self) -> None:
        _, _, partial_analysis = app_main.build_partial_sample_analysis()

        with (
            patch.object(app_main.GoogleClassroomClient, "from_oauth", return_value=object()),
            patch.object(
                app_main,
                "fetch_submission_analysis",
                return_value=partial_analysis,
            ),
        ):
            status_code, payload = self._request_json(
                "/api/live/reminder-generation?courseId=course_001&courseWorkId=cw_001"
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "partial_success")
        self.assertEqual(payload["errors"][0]["code"], "PARTIAL_CLASSROOM_DATA")
        self.assertTrue(payload["approval"]["required"])
        self.assertEqual(validate_agent_output(payload), [])

    def test_missing_query_parameter_returns_400(self) -> None:
        status_code, payload = self._request_json(
            "/api/live/submission-analysis?courseId=course_001"
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "INVALID_AGENT_OUTPUT")

    def test_coursework_endpoint_missing_query_parameter_returns_400(self) -> None:
        status_code, payload = self._request_json("/api/live/coursework")

        self.assertEqual(status_code, 400)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "INVALID_AGENT_OUTPUT")

    def test_post_reminder_requires_teacher_approval(self) -> None:
        fake_post_client = FakePostClient()
        reminder_payload = build_reminder_generation_response(
            "req_post_test",
            self.analysis,
            reminder_title="課題提出リマインド",
            reminder_body="まだ提出していない人は提出してください。",
        )["outputs"]["classroomReminder"]

        with patch.object(
            app_main,
            "build_post_only_client",
            return_value=fake_post_client,
        ):
            status_code, payload = self._request_json(
                "/api/live/post-reminder",
                method="POST",
                payload={
                    "approved": False,
                    "classroomReminder": reminder_payload,
                },
            )

        self.assertEqual(status_code, 500)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "CLASSROOM_POST_FAILED")
        self.assertEqual(fake_post_client.created_payloads, [])

    def test_post_reminder_rejects_invalid_payload_shape(self) -> None:
        fake_post_client = FakePostClient()

        with patch.object(
            app_main,
            "build_post_only_client",
            return_value=fake_post_client,
        ):
            status_code, payload = self._request_json(
                "/api/live/post-reminder",
                method="POST",
                payload={
                    "approved": True,
                    "classroomReminder": "invalid",
                },
            )

        self.assertEqual(status_code, 500)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "INVALID_AGENT_OUTPUT")
        self.assertEqual(fake_post_client.created_payloads, [])

    def test_post_reminder_success_posts_only_after_approval(self) -> None:
        fake_post_client = FakePostClient()
        reminder_payload = build_reminder_generation_response(
            "req_post_success",
            self.analysis,
            reminder_title="課題提出リマインド",
            reminder_body="まだ提出していない人は提出してください。",
        )["outputs"]["classroomReminder"]

        with patch.object(
            app_main,
            "build_post_only_client",
            return_value=fake_post_client,
        ):
            status_code, payload = self._request_json(
                "/api/live/post-reminder",
                method="POST",
                payload={
                    "approved": True,
                    "classroomReminder": reminder_payload,
                },
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["announcementId"], "announcement_001")
        self.assertEqual(fake_post_client.created_payloads, [reminder_payload])
