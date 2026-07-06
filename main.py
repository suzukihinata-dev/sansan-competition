from __future__ import annotations

import argparse
import html
import http.server
from http.cookies import SimpleCookie
import json
import re
import socketserver
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import parse_qs, urlparse

from sansan_competition import (
    AgentTaskType,
    Course,
    CourseWork,
    StudentSubmission,
    analyze_submissions,
    build_agent_output,
    build_error_response,
    build_ai_task_input,
    build_reminder_generation_response,
    build_submission_analysis_response,
    normalize_course,
    normalize_coursework,
    normalize_submission_batch,
    validate_agent_output,
)
from sansan_competition.classroom import (
    GoogleClassroomClient,
    build_post_only_client,
    fetch_submission_analysis,
)
from sansan_competition.execution.errors import AgentError, ErrorCode
from sansan_competition.models import JST
from sansan_competition.oauth import (
    GoogleOAuthConfig,
    GoogleOAuthConfigurationError,
    GoogleOAuthAuthorizationRequiredError,
    authorize_google_user_via_local_browser,
    clear_google_oauth_token,
    complete_google_oauth_authorization,
    default_classroom_post_scopes,
    default_classroom_read_scopes,
    inspect_google_oauth_client,
    load_google_user_credentials,
    resolve_google_oauth_runtime_plan,
    save_google_oauth_client_file,
    start_google_oauth_authorization,
)


ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
OAUTH_CALLBACK_PATH = "/oauth/google/callback"
OAUTH_SESSION_TTL_SECONDS = 10 * 60
OAUTH_LOCAL_BROWSER_TIMEOUT_SECONDS = 5 * 60
OAUTH_BROWSER_SESSION_COOKIE_NAME = "sansan_browser_session"
OAUTH_BROWSER_SESSION_COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
OAUTH_BROWSER_SESSION_TOKEN_DIRNAME = "browser-session-tokens"
OAUTH_BROWSER_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
OAUTH_INTENT_SCOPES = {
    "read": default_classroom_read_scopes(),
    "post": default_classroom_post_scopes(),
}
OAUTH_SESSIONS: dict[str, dict[str, Any]] = {}
OAUTH_SESSIONS_LOCK = threading.Lock()


class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def build_browser_session_token_path(
    session_id: str,
    *,
    base_config: GoogleOAuthConfig | None = None,
) -> Path:
    resolved_config = base_config or GoogleOAuthConfig()
    base_token_path = resolved_config.token_path
    suffix = base_token_path.suffix or ".json"
    return (
        base_token_path.parent
        / OAUTH_BROWSER_SESSION_TOKEN_DIRNAME
        / f"{base_token_path.stem}-{session_id}{suffix}"
    )


def clear_browser_session_oauth_tokens(
    *,
    base_config: GoogleOAuthConfig | None = None,
) -> None:
    resolved_config = base_config or GoogleOAuthConfig()
    clear_google_oauth_token(path=resolved_config.token_path)

    session_dir = resolved_config.token_path.parent / OAUTH_BROWSER_SESSION_TOKEN_DIRNAME
    suffix = resolved_config.token_path.suffix or ".json"
    pattern = f"{resolved_config.token_path.stem}-*{suffix}"
    for token_path in session_dir.glob(pattern):
        try:
            token_path.unlink()
        except FileNotFoundError:
            continue


def build_sample_analysis():
    course = normalize_course(
        {
            "id": "123456789",
            "name": "数学I",
            "section": "1年A組",
            "description": "二次関数の基礎",
            "teacherIds": ["teacher_001"],
            "studentCount": 3,
        }
    )
    course_work = normalize_coursework(
        {
            "id": "987654321",
            "courseId": "123456789",
            "title": "二次関数プリント",
            "description": "配布プリントを解いて提出",
            "workType": "ASSIGNMENT",
            "dueDate": "2026-07-05",
            "dueTime": "23:59",
        }
    )
    submissions, issues = normalize_submission_batch(
        [
            {
                "id": "sub_001",
                "courseId": "123456789",
                "courseWorkId": "987654321",
                "studentId": "student_001",
                "studentName": "山田太郎",
                "state": "NEW",
            },
            {
                "id": "sub_002",
                "courseId": "123456789",
                "courseWorkId": "987654321",
                "studentId": "student_002",
                "studentName": "佐藤花子",
                "state": "TURNED_IN",
                "submissionTime": "2026-07-05T20:15:00+09:00",
                "attachments": [{"driveFile": {"id": "file_001"}}],
            },
            {
                "id": "sub_003",
                "courseId": "123456789",
                "courseWorkId": "987654321",
                "studentId": "student_003",
                "studentName": "鈴木一郎",
                "state": "TURNED_IN",
                "submissionTime": "2026-07-06T00:30:00+09:00",
                "late": True,
            },
        ]
    )

    analysis = analyze_submissions(
        course,
        course_work,
        submissions,
        now=datetime(2026, 7, 3, 13, 0, tzinfo=JST),
        normalization_issues=issues,
    )
    return course, course_work, analysis


def build_partial_sample_analysis():
    course = normalize_course(
        {
            "id": "123456789",
            "name": "数学I",
            "section": "1年A組",
            "description": "二次関数の基礎",
            "teacherIds": ["teacher_001"],
            "studentCount": 4,
        }
    )
    course_work = normalize_coursework(
        {
            "id": "987654321",
            "courseId": "123456789",
            "title": "二次関数プリント",
            "description": "配布プリントを解いて提出",
            "workType": "ASSIGNMENT",
            "dueDate": "2026-07-05",
            "dueTime": "23:59",
        }
    )
    submissions, issues = normalize_submission_batch(
        [
            {
                "id": "sub_001",
                "courseId": "123456789",
                "courseWorkId": "987654321",
                "studentId": "student_001",
                "studentName": "山田太郎",
                "state": "NEW",
            },
            {
                "id": "sub_002",
                "courseId": "123456789",
                "courseWorkId": "987654321",
                "studentId": "student_002",
                "studentName": "佐藤花子",
                "state": "TURNED_IN",
                "submissionTime": "2026-07-05T20:15:00+09:00",
                "attachments": [{"driveFile": {"id": "file_001"}}],
            },
            {
                "id": "sub_003",
                "courseWorkId": "987654321",
                "studentId": "student_003",
                "studentName": "鈴木一郎",
                "state": "TURNED_IN",
            },
            {
                "id": "sub_004",
                "courseId": "123456789",
                "courseWorkId": "987654321",
                "studentId": "student_004",
                "studentName": "高橋未来",
                "state": "TURNED_IN",
                "submissionTime": "2026-07-06T00:30:00+09:00",
                "late": True,
            },
        ]
    )

    analysis = analyze_submissions(
        course,
        course_work,
        submissions,
        now=datetime(2026, 7, 3, 13, 0, tzinfo=JST),
        normalization_issues=issues,
    )
    return course, course_work, analysis


def build_gui_sample_payload(agent_task_type: AgentTaskType | str) -> dict[str, object]:
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
        course_id=course.course_id,
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
            course_id=course.course_id,
            course_work_id=coursework.course_work_id,
            student_id="student_1",
            student_name="山田太郎",
            state="NEW",
            late=False,
        ),
        StudentSubmission(
            student_submission_id="sub_2",
            course_id=course.course_id,
            course_work_id=coursework.course_work_id,
            student_id="student_2",
            student_name="佐藤花子",
            state="TURNED_IN",
            late=False,
        ),
    ]
    return build_agent_output(
        agent_task_type,
        request_id=f"req_{AgentTaskType(agent_task_type).value.lower()}",
        course=course,
        coursework=coursework,
        submissions=submissions,
        tone="polite",
    ).to_dict()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve the GUI prototype or emit sample contract payloads."
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=(
            "serve",
            "demo",
            "sample-reminder",
            "sample-course-summary",
            "sample-ai-input-course-summary",
            "sample-ai-input-reminder",
            "sample-ai-input-weekly-report",
            "sample-partial-analysis",
            "sample-partial-reminder",
        ),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args(argv)


def build_live_request_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def build_course_list_payload(courses: list[Course]) -> dict[str, object]:
    items = sorted(
        (course.to_contract() for course in courses),
        key=lambda item: (
            str(item.get("name") or "").casefold(),
            str(item.get("section") or "").casefold(),
        ),
    )
    return {
        "requestId": build_live_request_id("courses"),
        "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
        "items": items,
    }


def build_coursework_list_payload(coursework_items: list[CourseWork]) -> dict[str, object]:
    def sort_key(item: CourseWork) -> tuple[int, str, str]:
        due_at = (
            item.due_at.isoformat()
            if item.due_at is not None
            else "9999-12-31T23:59:59+09:00"
        )
        return (0 if item.due_at is not None else 1, due_at, item.title.casefold())

    items = [item.to_contract() for item in sorted(coursework_items, key=sort_key)]
    return {
        "requestId": build_live_request_id("coursework"),
        "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
        "items": items,
    }


def build_default_reminder_title(course_work: CourseWork) -> str:
    return f"{course_work.title} 提出リマインド"


def build_default_reminder_body(analysis: Any) -> str:
    due_parts = [
        value
        for value in (analysis.course_work.due_date, analysis.course_work.due_time)
        if value
    ]
    due_label = " ".join(due_parts)
    sentences = [f"課題「{analysis.course_work.title}」の提出状況を確認しました。"]
    if due_label:
        sentences.append(
            f"まだ提出していない人は、{due_label} までに提出してください。"
        )
    else:
        sentences.append("まだ提出していない人は、できるだけ早く提出してください。")
    sentences.append("分からない点があれば、早めに相談してください。")
    if analysis.normalization_issues:
        sentences.append("一部データが未取得のため、投稿前に内容を再確認してください。")
    return " ".join(sentences)


def normalize_live_courses(raw_courses: list[dict[str, Any]]) -> list[Course]:
    return [normalize_course(item) for item in raw_courses if isinstance(item, dict)]


def normalize_live_coursework(raw_coursework: list[dict[str, Any]]) -> list[CourseWork]:
    return [
        normalize_coursework(item)
        for item in raw_coursework
        if isinstance(item, dict)
    ]


def resolve_agent_error(exc: Exception, *, fallback_code: str) -> AgentError:
    if isinstance(exc, AgentError):
        return exc

    if isinstance(exc, FileNotFoundError):
        return AgentError(
            ErrorCode.GOOGLE_AUTH_EXPIRED,
            message="OAuth client JSON が見つかりません。GUI から OAuth client を登録してください。",
            detail=str(exc),
        )

    if isinstance(exc, GoogleOAuthConfigurationError):
        return AgentError(
            ErrorCode.GOOGLE_AUTH_EXPIRED,
            message=str(exc),
            detail=str(exc),
        )

    if isinstance(exc, RuntimeError):
        return AgentError(
            ErrorCode.GOOGLE_AUTH_EXPIRED,
            message=str(exc),
            detail=str(exc),
        )

    status = getattr(getattr(exc, "resp", None), "status", None)
    try:
        status_code = int(status)
    except (TypeError, ValueError):
        status_code = None

    mapping = {
        400: ErrorCode.INVALID_AGENT_OUTPUT,
        401: ErrorCode.GOOGLE_AUTH_EXPIRED,
        403: ErrorCode.CLASSROOM_API_PERMISSION_DENIED,
        404: ErrorCode.CLASSROOM_API_NOT_FOUND,
        429: ErrorCode.CLASSROOM_API_RATE_LIMITED,
    }
    return AgentError(mapping.get(status_code, fallback_code), detail=str(exc))


def validate_or_rebuild_contract(
    payload: dict[str, Any],
    *,
    request_id: str,
    agent_task_type: AgentTaskType,
    course: Course | None = None,
) -> dict[str, Any]:
    validation_errors = validate_agent_output(payload)
    if not validation_errors:
        return payload

    return build_error_response(
        request_id,
        agent_task_type,
        title="AIアウトプットJSONの検証に失敗しました",
        short_summary="内部で生成したレスポンスが契約に一致しませんでした。",
        recommended_action="JSON契約とレスポンス生成処理を確認してください。",
        error_code=ErrorCode.INVALID_AGENT_OUTPUT,
        error_message=" / ".join(validation_errors),
        recoverable=False,
        course=course,
    )


def build_contract_error_payload(
    *,
    request_id: str,
    agent_task_type: AgentTaskType,
    error: AgentError,
    title: str,
    short_summary: str,
    recommended_action: str,
    course: Course | None = None,
) -> dict[str, Any]:
    return build_error_response(
        request_id,
        agent_task_type,
        title=title,
        short_summary=short_summary,
        recommended_action=recommended_action,
        error_code=error.code,
        error_message=error.message,
        recoverable=error.recoverable,
        course=course,
    )


def cleanup_expired_oauth_sessions() -> None:
    cutoff = time.time() - OAUTH_SESSION_TTL_SECONDS
    with OAUTH_SESSIONS_LOCK:
        expired_states = [
            state
            for state, session in OAUTH_SESSIONS.items()
            if float(session.get("createdAt", 0.0)) < cutoff
        ]
        for state in expired_states:
            OAUTH_SESSIONS.pop(state, None)


def start_local_browser_oauth_session(
    state: str,
    *,
    intent: str,
    scopes: Sequence[str],
    oauth_config: Any = None,
) -> None:
    def worker() -> None:
        try:
            authorize_google_user_via_local_browser(
                scopes,
                config=oauth_config,
                timeout_seconds=OAUTH_LOCAL_BROWSER_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            error = resolve_agent_error(
                exc,
                fallback_code=ErrorCode.GOOGLE_AUTH_EXPIRED,
            )
            with OAUTH_SESSIONS_LOCK:
                if state in OAUTH_SESSIONS:
                    OAUTH_SESSIONS[state]["status"] = "error"
                    OAUTH_SESSIONS[state]["error"] = error.to_error_item()
                    OAUTH_SESSIONS[state]["completedAt"] = time.time()
            return

        with OAUTH_SESSIONS_LOCK:
            if state in OAUTH_SESSIONS:
                OAUTH_SESSIONS[state]["status"] = "completed"
                OAUTH_SESSIONS[state]["completedAt"] = time.time()
                OAUTH_SESSIONS[state].pop("error", None)

    thread = threading.Thread(
        target=worker,
        name=f"oauth-local-browser-{intent}-{state[:8]}",
        daemon=True,
    )
    thread.start()


class ClassroomPrototypeHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args: object, **kwargs: object) -> None:
        self._browser_session_id_cache: str | None = None
        self._browser_session_cookie_header: str | None = None
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if self._is_oauth_callback_request(parsed):
            self._handle_oauth_callback(parsed)
            return
        if parsed.path == "/api/live/oauth/check":
            self._handle_oauth_check(parsed)
            return
        if parsed.path == "/api/live/oauth/config":
            self._handle_oauth_config()
            return
        if parsed.path == "/api/live/oauth/start":
            self._handle_oauth_start(parsed)
            return
        if parsed.path == "/api/live/oauth/status":
            self._handle_oauth_status(parsed)
            return
        if parsed.path == OAUTH_CALLBACK_PATH:
            self._handle_oauth_callback(parsed)
            return
        if parsed.path == "/api/live/courses":
            self._handle_courses()
            return
        if parsed.path == "/api/live/coursework":
            self._handle_coursework(parsed)
            return
        if parsed.path == "/api/live/submission-analysis":
            self._handle_submission_analysis(parsed)
            return
        if parsed.path == "/api/live/reminder-generation":
            self._handle_reminder_generation(parsed)
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/live/oauth/config":
            self._handle_oauth_config_upload()
            return
        if parsed.path == "/api/live/oauth/logout":
            self._handle_oauth_logout()
            return
        if parsed.path == "/api/live/post-reminder":
            self._handle_post_reminder()
            return
        self.send_error(404, "Not Found")

    def _handle_courses(self) -> None:
        request_id = build_live_request_id("courses")
        try:
            client = GoogleClassroomClient.from_oauth(
                oauth_config=self._browser_oauth_config(),
                allow_interactive=False,
            )
            payload = build_course_list_payload(
                normalize_live_courses(client.list_courses(course_states=["ACTIVE"]))
            )
            payload["requestId"] = request_id
            self._send_json(200, payload)
        except Exception as exc:
            error = resolve_agent_error(
                exc,
                fallback_code=ErrorCode.CLASSROOM_API_PERMISSION_DENIED,
            )
            self._send_json(
                500,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "items": [],
                    "error": error.to_error_item(),
                },
            )

    def _handle_coursework(self, parsed: Any) -> None:
        request_id = build_live_request_id("coursework")
        course_id = self._require_query_value(parsed, "courseId")
        if course_id is None:
            return

        try:
            client = GoogleClassroomClient.from_oauth(
                oauth_config=self._browser_oauth_config(),
                allow_interactive=False,
            )
            payload = build_coursework_list_payload(
                normalize_live_coursework(
                    client.list_coursework(
                        course_id,
                        course_work_states=["PUBLISHED"],
                    )
                )
            )
            payload["requestId"] = request_id
            self._send_json(200, payload)
        except Exception as exc:
            error = resolve_agent_error(
                exc,
                fallback_code=ErrorCode.CLASSROOM_API_PERMISSION_DENIED,
            )
            self._send_json(
                500,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "items": [],
                    "error": error.to_error_item(),
                },
            )

    def _handle_submission_analysis(self, parsed: Any) -> None:
        request_id = build_live_request_id("submission_analysis")
        course_id = self._require_query_value(parsed, "courseId")
        course_work_id = self._require_query_value(parsed, "courseWorkId")
        if course_id is None or course_work_id is None:
            return

        try:
            client = GoogleClassroomClient.from_oauth(
                oauth_config=self._browser_oauth_config(),
                allow_interactive=False,
            )
            analysis = fetch_submission_analysis(
                client,
                course_id=course_id,
                course_work_id=course_work_id,
            )
            payload = validate_or_rebuild_contract(
                build_submission_analysis_response(request_id, analysis),
                request_id=request_id,
                agent_task_type=AgentTaskType.SUBMISSION_ANALYSIS,
                course=analysis.course,
            )
            self._send_json(200, payload)
        except Exception as exc:
            error = resolve_agent_error(
                exc,
                fallback_code=ErrorCode.CLASSROOM_API_PERMISSION_DENIED,
            )
            payload = build_contract_error_payload(
                request_id=request_id,
                agent_task_type=AgentTaskType.SUBMISSION_ANALYSIS,
                error=error,
                title="提出状況の取得に失敗しました",
                short_summary="Google Classroom から提出状況を取得できませんでした。",
                recommended_action="Google OAuth 設定とClassroom権限を確認して再試行してください。",
            )
            self._send_json(200, payload)

    def _handle_reminder_generation(self, parsed: Any) -> None:
        request_id = build_live_request_id("reminder_generation")
        course_id = self._require_query_value(parsed, "courseId")
        course_work_id = self._require_query_value(parsed, "courseWorkId")
        if course_id is None or course_work_id is None:
            return

        try:
            client = GoogleClassroomClient.from_oauth(
                oauth_config=self._browser_oauth_config(),
                allow_interactive=False,
            )
            analysis = fetch_submission_analysis(
                client,
                course_id=course_id,
                course_work_id=course_work_id,
            )
            payload = validate_or_rebuild_contract(
                build_reminder_generation_response(
                    request_id,
                    analysis,
                    reminder_title=build_default_reminder_title(analysis.course_work),
                    reminder_body=build_default_reminder_body(analysis),
                ),
                request_id=request_id,
                agent_task_type=AgentTaskType.REMINDER_GENERATION,
                course=analysis.course,
            )
            self._send_json(200, payload)
        except Exception as exc:
            error = resolve_agent_error(
                exc,
                fallback_code=ErrorCode.CLASSROOM_API_PERMISSION_DENIED,
            )
            payload = build_contract_error_payload(
                request_id=request_id,
                agent_task_type=AgentTaskType.REMINDER_GENERATION,
                error=error,
                title="リマインド生成に失敗しました",
                short_summary=(
                    "Google Classroom の事実データを取得できなかったため、"
                    "リマインド案を生成できませんでした。"
                ),
                recommended_action="Google OAuth 設定と対象課題の権限を確認して再試行してください。",
            )
            self._send_json(200, payload)

    def _handle_post_reminder(self) -> None:
        request_id = build_live_request_id("post_reminder")
        try:
            body = self._read_json_body()
            approved = bool(body.get("approved"))
            reminder_output = body.get("classroomReminder")
            if not approved:
                raise AgentError(
                    ErrorCode.CLASSROOM_POST_FAILED,
                    message="教師承認フラグがないため、Classroom 投稿を実行しませんでした。",
                    recoverable=True,
                )
            if not isinstance(reminder_output, dict):
                raise AgentError(
                    ErrorCode.INVALID_AGENT_OUTPUT,
                    message="classroomReminder payload が不正です。",
                    recoverable=False,
                )

            client = build_post_only_client(
                oauth_config=self._browser_oauth_config(),
                allow_interactive=False,
            )
            announcement = client.create_announcement_from_output(reminder_output)
            self._send_json(
                200,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "status": "success",
                    "announcementId": announcement.get("id"),
                    "alternateLink": announcement.get("alternateLink"),
                },
            )
        except Exception as exc:
            error = resolve_agent_error(exc, fallback_code=ErrorCode.CLASSROOM_POST_FAILED)
            self._send_json(
                500,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "status": "error",
                    "error": error.to_error_item(),
                },
            )

    def _build_oauth_config_payload(self, *, request_id: str) -> dict[str, Any]:
        redirect_uri = self._oauth_redirect_uri()
        oauth_config = self._browser_oauth_config()
        client_info = inspect_google_oauth_client(oauth_config)
        ready_for_oauth = False
        status = "configuration_required"
        recommended_action = ""
        authorization_mode = "unavailable"
        authorization_hint = ""

        try:
            plan = resolve_google_oauth_runtime_plan(
                redirect_uri,
                remote_browser_session=not self._is_loopback_request_host(),
                config=oauth_config,
            )
        except FileNotFoundError:
            recommended_action = (
                "Google Cloud からダウンロードした OAuth client JSON をこの画面で登録してください。"
            )
        except GoogleOAuthConfigurationError as exc:
            recommended_action = str(exc)
        else:
            client_info = plan.client_info
            ready_for_oauth = True
            status = "ready"
            authorization_mode = plan.authorization_mode
            authorization_hint = plan.authorization_hint

        return {
            "requestId": request_id,
            "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
            "status": status,
            "readyForOAuth": ready_for_oauth,
            "clientFilePresent": client_info.exists,
            "clientFilePath": str(client_info.path),
            "clientType": client_info.client_type,
            "clientId": client_info.client_id,
            "authorizedRedirectUris": list(client_info.redirect_uris),
            "browserSessionScoped": True,
            "redirectUri": redirect_uri,
            "serverBaseUrl": self._server_base_url(),
            "remoteBrowserSession": not self._is_loopback_request_host(),
            "authorizationMode": authorization_mode,
            "authorizationHint": authorization_hint,
            "recommendedAction": recommended_action,
        }

    def _handle_oauth_config(self) -> None:
        request_id = build_live_request_id("oauth_config")
        self._send_json(200, self._build_oauth_config_payload(request_id=request_id))

    def _handle_oauth_config_upload(self) -> None:
        request_id = build_live_request_id("oauth_config_upload")
        try:
            body = self._read_json_body()
            content = str(body.get("clientFileContent") or "")
            if not content.strip():
                raise AgentError(
                    ErrorCode.INVALID_AGENT_OUTPUT,
                    message="clientFileContent is required.",
                    recoverable=False,
                )
            save_google_oauth_client_file(content)
            clear_browser_session_oauth_tokens()
            self._send_json(200, self._build_oauth_config_payload(request_id=request_id))
        except Exception as exc:
            error = resolve_agent_error(
                exc,
                fallback_code=ErrorCode.GOOGLE_AUTH_EXPIRED,
            )
            self._send_json(
                400,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "status": "error",
                    "error": error.to_error_item(),
                },
            )

    def _handle_oauth_check(self, parsed: Any) -> None:
        request_id = build_live_request_id("oauth_check")
        intent = self._require_query_value(parsed, "intent")
        if intent is None:
            return

        scopes = OAUTH_INTENT_SCOPES.get(intent)
        if scopes is None:
            self._send_json(
                400,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "status": "error",
                    "error": {
                        "code": ErrorCode.INVALID_AGENT_OUTPUT,
                        "message": f"Unsupported OAuth intent: {intent}",
                        "recoverable": False,
                    },
                },
            )
            return

        try:
            oauth_config = self._browser_oauth_config()
            plan = resolve_google_oauth_runtime_plan(
                self._oauth_redirect_uri(),
                remote_browser_session=not self._is_loopback_request_host(),
                config=oauth_config,
            )
            load_google_user_credentials(scopes, config=plan.config, allow_interactive=False)
            self._send_json(
                200,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "status": "authorized",
                    "intent": intent,
                },
            )
        except (FileNotFoundError, GoogleOAuthConfigurationError):
            payload = self._build_oauth_config_payload(request_id=request_id)
            payload["intent"] = intent
            self._send_json(200, payload)
        except GoogleOAuthAuthorizationRequiredError:
            self._send_json(
                200,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "status": "authorization_required",
                    "intent": intent,
                },
            )
        except Exception as exc:
            error = resolve_agent_error(
                exc,
                fallback_code=ErrorCode.GOOGLE_AUTH_EXPIRED,
            )
            self._send_json(
                500,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "status": "error",
                    "error": error.to_error_item(),
                },
            )

    def _handle_oauth_start(self, parsed: Any) -> None:
        cleanup_expired_oauth_sessions()
        request_id = build_live_request_id("oauth_start")
        intent = self._require_query_value(parsed, "intent")
        if intent is None:
            return

        scopes = OAUTH_INTENT_SCOPES.get(intent)
        if scopes is None:
            self._send_json(
                400,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "status": "error",
                    "error": {
                        "code": ErrorCode.INVALID_AGENT_OUTPUT,
                        "message": f"Unsupported OAuth intent: {intent}",
                        "recoverable": False,
                    },
                },
            )
            return

        try:
            oauth_config = self._browser_oauth_config()
            plan = resolve_google_oauth_runtime_plan(
                self._oauth_redirect_uri(),
                remote_browser_session=not self._is_loopback_request_host(),
                config=oauth_config,
            )
            load_google_user_credentials(scopes, config=plan.config, allow_interactive=False)
            self._send_json(
                200,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "status": "authorized",
                    "intent": intent,
                },
            )
        except (FileNotFoundError, GoogleOAuthConfigurationError):
            payload = self._build_oauth_config_payload(request_id=request_id)
            payload["intent"] = intent
            self._send_json(200, payload)
        except GoogleOAuthAuthorizationRequiredError:
            if plan.authorization_mode == "local_browser_assisted":
                state = uuid.uuid4().hex
                with OAUTH_SESSIONS_LOCK:
                    OAUTH_SESSIONS[state] = {
                        "createdAt": time.time(),
                        "intent": intent,
                        "scopes": tuple(scopes),
                        "status": "pending",
                        "authorizationMode": plan.authorization_mode,
                        "authorizationHint": plan.authorization_hint,
                        "browserSessionId": self._browser_session_id(),
                        "credentialsPath": str(plan.config.credentials_path or ""),
                        "tokenPath": str(plan.config.token_path or ""),
                    }
                start_local_browser_oauth_session(
                    state,
                    intent=intent,
                    scopes=tuple(scopes),
                    oauth_config=plan.config,
                )
                self._send_json(
                    200,
                    {
                        "requestId": request_id,
                        "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                        "status": "authorization_required",
                        "intent": intent,
                        "authorizationMode": plan.authorization_mode,
                        "authorizationHint": plan.authorization_hint,
                        "statusUrl": f"/api/live/oauth/status?state={state}",
                    },
                )
                return

            redirect_uri = self._oauth_redirect_uri()
            auth_request = start_google_oauth_authorization(
                scopes,
                redirect_uri=redirect_uri,
                config=plan.config,
            )
            with OAUTH_SESSIONS_LOCK:
                OAUTH_SESSIONS[auth_request.state] = {
                    "createdAt": time.time(),
                    "intent": intent,
                    "redirectUri": redirect_uri,
                    "scopes": auth_request.scopes,
                    "codeVerifier": auth_request.code_verifier,
                    "status": "pending",
                    "authorizationMode": plan.authorization_mode,
                    "authorizationHint": plan.authorization_hint,
                    "browserSessionId": self._browser_session_id(),
                    "credentialsPath": str(plan.config.credentials_path or ""),
                    "tokenPath": str(plan.config.token_path or ""),
                }
            self._send_json(
                200,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "status": "authorization_required",
                    "intent": intent,
                    "authorizationMode": plan.authorization_mode,
                    "authorizationHint": plan.authorization_hint,
                    "authorizationUrl": auth_request.authorization_url,
                    "statusUrl": f"/api/live/oauth/status?state={auth_request.state}",
                },
            )
        except Exception as exc:
            error = resolve_agent_error(
                exc,
                fallback_code=ErrorCode.GOOGLE_AUTH_EXPIRED,
            )
            self._send_json(
                500,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "status": "error",
                    "error": error.to_error_item(),
                },
            )

    def _handle_oauth_status(self, parsed: Any) -> None:
        cleanup_expired_oauth_sessions()
        request_id = build_live_request_id("oauth_status")
        state = self._require_query_value(parsed, "state")
        if state is None:
            return

        with OAUTH_SESSIONS_LOCK:
            session = dict(OAUTH_SESSIONS.get(state, {}))

        if not session or not self._oauth_session_matches_browser(session):
            self._send_json(
                404,
                {
                    "requestId": request_id,
                    "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "status": "error",
                    "error": {
                        "code": ErrorCode.GOOGLE_AUTH_EXPIRED,
                        "message": "OAuth session が見つからないか、期限切れです。",
                        "recoverable": True,
                    },
                },
            )
            return

        payload: dict[str, Any] = {
            "requestId": request_id,
            "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
            "status": str(session.get("status") or "pending"),
            "intent": session.get("intent"),
            "authorizationMode": str(session.get("authorizationMode") or ""),
            "authorizationHint": str(session.get("authorizationHint") or ""),
        }
        error_item = session.get("error")
        if isinstance(error_item, dict):
            payload["error"] = error_item
        self._send_json(200, payload)

    def _handle_oauth_callback(self, parsed: Any) -> None:
        cleanup_expired_oauth_sessions()
        state = self._require_query_value(parsed, "state")
        if state is None:
            return

        with OAUTH_SESSIONS_LOCK:
            session = dict(OAUTH_SESSIONS.get(state, {}))

        if not session or not self._oauth_session_matches_browser(session):
            self._send_oauth_callback_page(
                title="OAuth セッションが見つかりませんでした",
                message="時間をおいて再度接続を開始してください。",
                success=False,
            )
            return

        query = parse_qs(parsed.query)
        oauth_error = next(
            (value.strip() for value in query.get("error", []) if value.strip()),
            "",
        )
        if oauth_error:
            description = next(
                (
                    value.strip()
                    for value in query.get("error_description", [])
                    if value.strip()
                ),
                oauth_error,
            )
            self._update_oauth_session_error(
                state,
                AgentError(
                    ErrorCode.GOOGLE_AUTH_EXPIRED,
                    message="Google OAuth の許可が完了しませんでした。",
                    detail=description,
                ),
            )
            self.log_error("OAuth callback denied: %s", description)
            self._send_oauth_callback_page(
                title="Google Classroom への接続に失敗しました",
                message=description,
                success=False,
            )
            return

        try:
            oauth_config = None
            credentials_path = str(session.get("credentialsPath") or "").strip()
            token_path = str(session.get("tokenPath") or "").strip()
            if credentials_path or token_path:
                oauth_config = GoogleOAuthConfig(
                    credentials_path=Path(credentials_path).expanduser() if credentials_path else None,
                    token_path=Path(token_path).expanduser() if token_path else None,
                )
            complete_google_oauth_authorization(
                session.get("scopes", ()),
                state=state,
                authorization_response=self._absolute_request_url(),
                redirect_uri=str(session.get("redirectUri") or ""),
                code_verifier=session.get("codeVerifier"),
                config=oauth_config,
            )
        except Exception as exc:
            error = resolve_agent_error(
                exc,
                fallback_code=ErrorCode.GOOGLE_AUTH_EXPIRED,
            )
            self._update_oauth_session_error(state, error)
            self.log_error(
                "OAuth callback failed: %s",
                getattr(error, "detail", None) or error.message,
            )
            self._send_oauth_callback_page(
                title="Google Classroom への接続に失敗しました",
                message=error.message,
                success=False,
            )
            return

        with OAUTH_SESSIONS_LOCK:
            if state in OAUTH_SESSIONS:
                OAUTH_SESSIONS[state]["status"] = "completed"
                OAUTH_SESSIONS[state]["completedAt"] = time.time()
                OAUTH_SESSIONS[state].pop("error", None)

        self._send_oauth_callback_page(
            title="Google Classroom への接続が完了しました",
            message="このウィンドウは自動で閉じます。閉じない場合は手動で閉じてください。",
            success=True,
        )

    def _handle_oauth_logout(self) -> None:
        request_id = build_live_request_id("oauth_logout")
        current_session_id = self._browser_session_id(create_if_missing=False)
        if current_session_id:
            clear_google_oauth_token(path=self._browser_oauth_config(current_session_id).token_path)
            with OAUTH_SESSIONS_LOCK:
                expired_states = [
                    state
                    for state, session in OAUTH_SESSIONS.items()
                    if str(session.get("browserSessionId") or "") == current_session_id
                ]
                for state in expired_states:
                    OAUTH_SESSIONS.pop(state, None)

        self._rotate_browser_session_id()
        self._send_json(
            200,
            {
                "requestId": request_id,
                "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                "status": "logged_out",
            },
        )

    def _update_oauth_session_error(self, state: str, error: AgentError) -> None:
        with OAUTH_SESSIONS_LOCK:
            if state in OAUTH_SESSIONS:
                OAUTH_SESSIONS[state]["status"] = "error"
                OAUTH_SESSIONS[state]["error"] = error.to_error_item()

    def _require_query_value(self, parsed: Any, key: str) -> str | None:
        values = parse_qs(parsed.query).get(key, [])
        for value in values:
            stripped = value.strip()
            if stripped:
                return stripped

        self._send_json(
            400,
            {
                "requestId": build_live_request_id("request_error"),
                "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
                "status": "error",
                "error": {
                    "code": ErrorCode.INVALID_AGENT_OUTPUT,
                    "message": f"Query parameter `{key}` is required.",
                    "recoverable": False,
                },
            },
        )
        return None

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length") or "0")
        if content_length <= 0:
            return {}
        raw_body = self.rfile.read(content_length)
        if not raw_body:
            return {}
        payload = json.loads(raw_body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise AgentError(
                ErrorCode.INVALID_AGENT_OUTPUT,
                message="JSON body must be an object.",
                recoverable=False,
            )
        return payload

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._browser_session_id()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_browser_session_cookie_header()
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status_code: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self._browser_session_id()
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self._send_browser_session_cookie_header()
        self.end_headers()
        self.wfile.write(encoded)

    def _browser_oauth_config(self, session_id: str | None = None) -> GoogleOAuthConfig:
        base_config = GoogleOAuthConfig()
        resolved_session_id = session_id or self._browser_session_id()
        return GoogleOAuthConfig(
            credentials_path=base_config.credentials_path,
            token_path=build_browser_session_token_path(
                resolved_session_id,
                base_config=base_config,
            ),
            local_server_port=base_config.local_server_port,
        )

    def _browser_session_id(self, *, create_if_missing: bool = True) -> str | None:
        if self._browser_session_id_cache:
            return self._browser_session_id_cache

        parsed_session_id = self._parse_browser_session_id()
        if parsed_session_id:
            self._browser_session_id_cache = parsed_session_id
            return parsed_session_id

        if not create_if_missing:
            return None

        self._browser_session_id_cache = uuid.uuid4().hex
        self._browser_session_cookie_header = self._build_browser_session_cookie_header(
            self._browser_session_id_cache
        )
        return self._browser_session_id_cache

    def _rotate_browser_session_id(self) -> str:
        self._browser_session_id_cache = uuid.uuid4().hex
        self._browser_session_cookie_header = self._build_browser_session_cookie_header(
            self._browser_session_id_cache
        )
        return self._browser_session_id_cache

    def _parse_browser_session_id(self) -> str | None:
        raw_cookie = self.headers.get("Cookie") or ""
        if not raw_cookie.strip():
            return None

        cookie = SimpleCookie()
        try:
            cookie.load(raw_cookie)
        except Exception:
            return None

        morsel = cookie.get(OAUTH_BROWSER_SESSION_COOKIE_NAME)
        if morsel is None:
            return None

        value = morsel.value.strip()
        if not OAUTH_BROWSER_SESSION_ID_PATTERN.fullmatch(value):
            return None
        return value

    def _build_browser_session_cookie_header(self, session_id: str) -> str:
        parts = [
            f"{OAUTH_BROWSER_SESSION_COOKIE_NAME}={session_id}",
            "Path=/",
            "HttpOnly",
            "SameSite=Lax",
            f"Max-Age={OAUTH_BROWSER_SESSION_COOKIE_MAX_AGE_SECONDS}",
        ]
        if urlparse(self._server_base_url()).scheme == "https":
            parts.append("Secure")
        return "; ".join(parts)

    def _send_browser_session_cookie_header(self) -> None:
        if self._browser_session_cookie_header:
            self.send_header("Set-Cookie", self._browser_session_cookie_header)
            self._browser_session_cookie_header = None

    def _oauth_session_matches_browser(self, session: dict[str, Any]) -> bool:
        expected_session_id = str(session.get("browserSessionId") or "").strip()
        if not expected_session_id:
            return True
        return expected_session_id == (self._browser_session_id(create_if_missing=False) or "")

    def _send_oauth_callback_page(
        self,
        *,
        title: str,
        message: str,
        success: bool,
    ) -> None:
        accent = "#188038" if success else "#b3261e"
        escaped_title = html.escape(title)
        escaped_message = html.escape(message)
        body = f"""<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escaped_title}</title>
  </head>
  <body style="margin:0;background:#f8fafd;color:#202124;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
    <main style="display:grid;min-height:100vh;place-items:center;padding:24px;">
      <section style="width:min(100%,520px);padding:28px;border:1px solid #dadce0;border-radius:12px;background:#ffffff;box-shadow:0 8px 22px rgba(60,64,67,0.08);">
        <p style="margin:0 0 8px;color:{accent};font-size:13px;font-weight:700;">Google Classroom OAuth</p>
        <h1 style="margin:0 0 12px;font-size:24px;">{escaped_title}</h1>
        <p style="margin:0;color:#5f6368;line-height:1.7;">{escaped_message}</p>
      </section>
    </main>
    <script>
      if (window.opener && window.location.origin === window.opener.location.origin) {{
        window.opener.postMessage({{ type: "sansan-oauth-complete", success: {str(success).lower()} }}, window.location.origin);
      }}
      if ({str(success).lower()}) {{
        setTimeout(() => window.close(), 1200);
      }}
    </script>
  </body>
</html>"""
        self._send_html(200, body)

    def _server_base_url(self) -> str:
        forwarded = self.headers.get("Forwarded") or ""
        forwarded_host = ""
        forwarded_proto = ""
        if forwarded:
            first_entry = forwarded.split(",")[0]
            for part in first_entry.split(";"):
                key, _, value = part.strip().partition("=")
                if not value:
                    continue
                normalized_key = key.lower()
                normalized_value = value.strip().strip('"')
                if normalized_key == "host" and not forwarded_host:
                    forwarded_host = normalized_value
                elif normalized_key == "proto" and not forwarded_proto:
                    forwarded_proto = normalized_value
        host = (
            forwarded_host
            or (self.headers.get("X-Forwarded-Host") or "").split(",")[0].strip()
            or (self.headers.get("X-Original-Host") or "").split(",")[0].strip()
            or (self.headers.get("Host") or "").strip()
        )
        if not host:
            server_host, server_port = self.server.server_address[:2]
            host = f"{server_host}:{server_port}"
        forwarded_proto = forwarded_proto or (self.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
        scheme = forwarded_proto if forwarded_proto in {"http", "https"} else "http"
        return f"{scheme}://{host}"

    def _absolute_request_url(self) -> str:
        return f"{self._server_base_url()}{self.path}"

    def _oauth_redirect_uri(self) -> str:
        return f"{self._server_base_url()}{OAUTH_CALLBACK_PATH}"

    def _is_loopback_request_host(self) -> bool:
        parsed = urlparse(self._server_base_url())
        return parsed.hostname in {"localhost", "127.0.0.1", "::1"}

    def _is_oauth_callback_request(self, parsed: Any) -> bool:
        if parsed.path == OAUTH_CALLBACK_PATH:
            return True
        if parsed.path not in ("", "/"):
            return False
        query = parse_qs(parsed.query)
        has_state = any(value.strip() for value in query.get("state", []))
        has_result = any(value.strip() for value in query.get("code", [])) or any(
            value.strip() for value in query.get("error", [])
        )
        return has_state and has_result


def serve_gui(host: str, port: int) -> None:
    with ReusableTCPServer((host, port), ClassroomPrototypeHandler) as server:
        url = f"http://{host}:{port}"
        print(f"Serving sansan-competition GUI at {url}")
        server.serve_forever()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    course, course_work, analysis = build_sample_analysis()

    if args.command == "serve":
        serve_gui(args.host, args.port)
        return 0

    if args.command == "sample-reminder":
        payload = build_gui_sample_payload(AgentTaskType.REMINDER_GENERATION)
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    if args.command == "sample-course-summary":
        payload = build_gui_sample_payload(AgentTaskType.COURSE_SUMMARY)
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    if args.command == "sample-ai-input-course-summary":
        payload = build_ai_task_input(
            AgentTaskType.COURSE_SUMMARY,
            analysis,
            tone="formal",
            teacher_instruction="未提出と遅延の傾向を簡潔に整理してください。",
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "sample-ai-input-reminder":
        payload = build_ai_task_input(
            AgentTaskType.REMINDER_GENERATION,
            analysis,
            output_formats=["classroomReminder", "markdown"],
            tone="polite",
            teacher_instruction="締切日を必ず明記してください。",
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "sample-ai-input-weekly-report":
        payload = build_ai_task_input(
            AgentTaskType.WEEKLY_REPORT,
            analysis,
            output_formats=["markdown", "pdf", "googleDocument"],
            tone="formal",
            teacher_instruction="事実と次のアクションを分けてください。",
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "sample-partial-analysis":
        _, _, partial_analysis = build_partial_sample_analysis()
        payload = build_submission_analysis_response(
            "req_20260703_demo_partial_analysis",
            partial_analysis,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "sample-partial-reminder":
        _, _, partial_analysis = build_partial_sample_analysis()
        payload = build_reminder_generation_response(
            "req_20260703_demo_partial_reminder",
            partial_analysis,
            reminder_title="課題提出リマインド",
            reminder_body=(
                "提出データの一部が取得できていません。"
                "確認できた範囲で、まだ提出していない人は7月5日までに提出してください。"
            ),
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "demo":
        payload = {
            "submissionAnalysis": build_submission_analysis_response(
                "req_20260703_demo_analysis",
                analysis,
            ),
            "reminderGeneration": build_reminder_generation_response(
                "req_20260703_demo_reminder",
                analysis,
                reminder_title="課題提出リマインド",
                reminder_body=(
                    "課題「二次関数プリント」の提出期限が近づいています。"
                    "まだ提出していない人は、7月5日までに提出してください。"
                ),
            ),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
