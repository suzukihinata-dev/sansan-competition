from __future__ import annotations

import json
import threading
import types
import unittest
from urllib import error, request
from unittest.mock import patch

import main as app_main
from sansan_competition.contract import (
    build_reminder_generation_response,
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
    ) -> tuple[int, dict]:
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with request.urlopen(req) as response:
                status_code = response.status
                response_body = response.read()
        except error.HTTPError as exc:
            status_code = exc.code
            response_body = exc.read()
            exc.close()

        return status_code, json.loads(response_body.decode("utf-8"))

    def _request_raw(self, path: str) -> tuple[int, str]:
        req = request.Request(f"{self.base_url}{path}", method="GET")
        try:
            with request.urlopen(req) as response:
                status_code = response.status
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            status_code = exc.code
            response_body = exc.read().decode("utf-8")
            exc.close()

        return status_code, response_body

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
        with patch.object(
            app_main,
            "load_google_user_credentials",
            return_value=object(),
        ):
            status_code, payload = self._request_json("/api/live/oauth/start?intent=read")

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "authorized")
        self.assertEqual(payload["intent"], "read")

    def test_oauth_check_reports_authorized_when_cached_token_is_ready(self) -> None:
        with patch.object(
            app_main,
            "load_google_user_credentials",
            return_value=object(),
        ):
            status_code, payload = self._request_json("/api/live/oauth/check?intent=read")

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "authorized")
        self.assertEqual(payload["intent"], "read")

    def test_oauth_check_reports_authorization_required_without_creating_session(self) -> None:
        with patch.object(
            app_main,
            "load_google_user_credentials",
            side_effect=app_main.GoogleOAuthAuthorizationRequiredError("required"),
        ):
            status_code, payload = self._request_json("/api/live/oauth/check?intent=read")

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "authorization_required")
        self.assertEqual(payload["intent"], "read")
        with app_main.OAUTH_SESSIONS_LOCK:
            self.assertEqual(app_main.OAUTH_SESSIONS, {})

    def test_oauth_start_returns_authorization_url_when_grant_is_required(self) -> None:
        auth_request = types.SimpleNamespace(
            authorization_url="https://accounts.example.test/auth",
            state="oauth-state-123",
            scopes=app_main.OAUTH_INTENT_SCOPES["read"],
            code_verifier="verifier-123",
        )

        with (
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
            status_code, payload = self._request_json("/api/live/oauth/start?intent=read")

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "authorization_required")
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
                app_main.OAUTH_SESSIONS["oauth-state-123"]["codeVerifier"],
                "verifier-123",
            )

    def test_oauth_status_returns_pending_session(self) -> None:
        with app_main.OAUTH_SESSIONS_LOCK:
            app_main.OAUTH_SESSIONS["oauth-state-123"] = {
                "createdAt": 9999999999.0,
                "intent": "read",
                "redirectUri": "http://127.0.0.1:8000/oauth/google/callback",
                "scopes": app_main.OAUTH_INTENT_SCOPES["read"],
                "status": "pending",
            }

        status_code, payload = self._request_json(
            "/api/live/oauth/status?state=oauth-state-123"
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["intent"], "read")

    def test_oauth_callback_marks_session_completed(self) -> None:
        with app_main.OAUTH_SESSIONS_LOCK:
            app_main.OAUTH_SESSIONS["oauth-state-123"] = {
                "createdAt": 9999999999.0,
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
                "/?state=oauth-state-123&code=example"
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
