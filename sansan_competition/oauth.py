from __future__ import annotations

from contextlib import contextmanager
import os
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Iterable
from urllib.parse import SplitResult, urlsplit, urlunsplit

CLASSROOM_COURSES_READONLY_SCOPE = "https://www.googleapis.com/auth/classroom.courses.readonly"
CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE = (
    "https://www.googleapis.com/auth/classroom.coursework.students.readonly"
)
CLASSROOM_STUDENT_SUBMISSIONS_STUDENTS_READONLY_SCOPE = (
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly"
)
CLASSROOM_ROSTERS_READONLY_SCOPE = "https://www.googleapis.com/auth/classroom.rosters.readonly"
CLASSROOM_ANNOUNCEMENTS_SCOPE = "https://www.googleapis.com/auth/classroom.announcements"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DOCUMENTS_SCOPE = "https://www.googleapis.com/auth/documents"
GOOGLE_OAUTH_CONFIG_DIR_ENV = "SANSAN_GOOGLE_OAUTH_CONFIG_DIR"
GOOGLE_OAUTH_CLIENT_FILE_ENV = "SANSAN_GOOGLE_OAUTH_CLIENT_FILE"
GOOGLE_OAUTH_TOKEN_FILE_ENV = "SANSAN_GOOGLE_OAUTH_TOKEN_FILE"
GOOGLE_OAUTH_CONFIG_DIR_NAME = "sansan-competition"
GOOGLE_OAUTH_CLIENT_FILENAME = "credentials.json"
GOOGLE_OAUTH_TOKEN_FILENAME = "token.json"
LEGACY_GOOGLE_OAUTH_CLIENT_PATH = Path("credentials.json")
LEGACY_GOOGLE_OAUTH_TOKEN_PATH = Path("token.json")


@dataclass(slots=True)
class GoogleOAuthConfig:
    credentials_path: Path | None = None
    token_path: Path | None = None
    local_server_port: int = 0

    def __post_init__(self) -> None:
        self.credentials_path = _resolve_google_oauth_credentials_path(self.credentials_path)
        self.token_path = _resolve_google_oauth_token_path(
            self.token_path,
            credentials_path=self.credentials_path,
        )


class GoogleOAuthAuthorizationRequiredError(RuntimeError):
    """Raised when an interactive OAuth grant is required but disabled."""


class GoogleOAuthConfigurationError(RuntimeError):
    """Raised when the configured OAuth client cannot satisfy the current flow."""


@dataclass(slots=True)
class GoogleOAuthClientInfo:
    path: Path
    exists: bool
    client_type: str | None
    client_id: str | None
    redirect_uris: tuple[str, ...]


@dataclass(slots=True)
class GoogleOAuthAuthorizationRequest:
    authorization_url: str
    state: str
    scopes: tuple[str, ...]
    code_verifier: str | None


def default_classroom_read_scopes(*, include_rosters: bool = True) -> tuple[str, ...]:
    scopes = [
        CLASSROOM_COURSES_READONLY_SCOPE,
        CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE,
    ]
    if include_rosters:
        scopes.append(CLASSROOM_ROSTERS_READONLY_SCOPE)
    return tuple(scopes)


def default_classroom_post_scopes() -> tuple[str, ...]:
    return (CLASSROOM_ANNOUNCEMENTS_SCOPE,)


def default_google_oauth_config_dir() -> Path:
    override = os.environ.get(GOOGLE_OAUTH_CONFIG_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / GOOGLE_OAUTH_CONFIG_DIR_NAME


def default_google_oauth_client_path() -> Path:
    return default_google_oauth_config_dir() / GOOGLE_OAUTH_CLIENT_FILENAME


def default_google_oauth_token_path() -> Path:
    return default_google_oauth_config_dir() / GOOGLE_OAUTH_TOKEN_FILENAME


def inspect_google_oauth_client(
    config: GoogleOAuthConfig | None = None,
) -> GoogleOAuthClientInfo:
    resolved_config = config or GoogleOAuthConfig()
    path = resolved_config.credentials_path
    if not path.exists():
        return GoogleOAuthClientInfo(
            path=path,
            exists=False,
            client_type=None,
            client_id=None,
            redirect_uris=(),
        )

    payload = _load_google_oauth_payload(path)
    client_type, client_section = _extract_google_oauth_client_section(payload)
    redirect_uris = ()
    if client_type == "web":
        redirect_uris = tuple(
            str(item).strip()
            for item in client_section.get("redirect_uris", [])
            if str(item).strip()
        )
    client_id = str(client_section.get("client_id") or "").strip() or None
    return GoogleOAuthClientInfo(
        path=path,
        exists=True,
        client_type=client_type,
        client_id=client_id,
        redirect_uris=redirect_uris,
    )


def save_google_oauth_client_file(
    content: str,
    *,
    path: Path | None = None,
) -> GoogleOAuthClientInfo:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise GoogleOAuthConfigurationError("OAuth client JSON はオブジェクトである必要があります。")
    _extract_google_oauth_client_section(payload)

    target_path = Path(path or default_google_oauth_client_path()).expanduser()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return inspect_google_oauth_client(
        GoogleOAuthConfig(
            credentials_path=target_path,
            token_path=default_google_oauth_token_path(),
        )
    )


def clear_google_oauth_token(
    *,
    path: Path | None = None,
) -> None:
    target_path = Path(path or default_google_oauth_token_path()).expanduser()
    try:
        target_path.unlink()
    except FileNotFoundError:
        return


def validate_google_oauth_client_for_redirect_uri(
    redirect_uri: str,
    *,
    config: GoogleOAuthConfig | None = None,
) -> GoogleOAuthClientInfo:
    client_info = inspect_google_oauth_client(config)
    if not client_info.exists:
        raise FileNotFoundError(f"OAuth client file not found: {client_info.path}")

    if client_info.client_type == "installed":
        if not _is_loopback_redirect_uri(redirect_uri):
            raise GoogleOAuthConfigurationError(
                "現在の OAuth client は desktop app 用です。"
                "別端末のブラウザから使うには Google Cloud で Web application の OAuth client を作成し、"
                f"Authorized redirect URI に {redirect_uri} を追加した JSON を登録してください。"
            )
        return client_info

    if client_info.client_type == "web":
        if redirect_uri not in client_info.redirect_uris:
            raise GoogleOAuthConfigurationError(
                "OAuth client の Authorized redirect URI に "
                f"{redirect_uri} を追加してください。"
            )
        return client_info

    raise GoogleOAuthConfigurationError(
        "OAuth client JSON に `web` または `installed` 設定がありません。"
    )


def load_google_user_credentials(
    scopes: Iterable[str],
    *,
    config: GoogleOAuthConfig | None = None,
    allow_interactive: bool = True,
) -> Any:
    resolved_config = config or GoogleOAuthConfig()
    normalized_scopes = _normalize_scopes(scopes)
    if not normalized_scopes:
        raise ValueError("At least one OAuth scope is required.")

    Request, Credentials, InstalledAppFlow = _import_google_clients()

    if not resolved_config.credentials_path.exists():
        raise FileNotFoundError(
            f"OAuth client file not found: {resolved_config.credentials_path}"
        )

    creds = None
    if resolved_config.token_path.exists():
        stored_scopes = _read_token_scopes(resolved_config.token_path)
        if stored_scopes and _scopes_cover_requested_scopes(stored_scopes, normalized_scopes):
            effective_scopes = _normalize_scopes([*stored_scopes, *normalized_scopes])
            creds = Credentials.from_authorized_user_file(
                str(resolved_config.token_path),
                effective_scopes,
            )
            if not _credentials_cover_scopes(creds, normalized_scopes):
                creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not allow_interactive:
                raise GoogleOAuthAuthorizationRequiredError(
                    "Google OAuth authorization is required. Start it from the GUI "
                    "or run the CLI OAuth setup flow."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(resolved_config.credentials_path),
                normalized_scopes,
            )
            creds = _run_local_server_relaxing_scope_changes(
                flow,
                port=resolved_config.local_server_port,
            )
        _write_google_oauth_token(resolved_config.token_path, creds.to_json())

    return creds


def start_google_oauth_authorization(
    scopes: Iterable[str],
    *,
    redirect_uri: str,
    config: GoogleOAuthConfig | None = None,
) -> GoogleOAuthAuthorizationRequest:
    resolved_config = config or GoogleOAuthConfig()
    normalized_scopes = _merge_requested_and_cached_scopes(
        scopes,
        token_path=resolved_config.token_path,
    )
    if not normalized_scopes:
        raise ValueError("At least one OAuth scope is required.")

    _, _, InstalledAppFlow = _import_google_clients()

    if not resolved_config.credentials_path.exists():
        raise FileNotFoundError(
            f"OAuth client file not found: {resolved_config.credentials_path}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(resolved_config.credentials_path),
        normalized_scopes,
    )
    flow.redirect_uri = redirect_uri
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return GoogleOAuthAuthorizationRequest(
        authorization_url=authorization_url,
        state=state,
        scopes=normalized_scopes,
        code_verifier=getattr(flow, "code_verifier", None),
    )


def complete_google_oauth_authorization(
    scopes: Iterable[str],
    *,
    state: str,
    authorization_response: str,
    redirect_uri: str,
    code_verifier: str | None = None,
    config: GoogleOAuthConfig | None = None,
) -> Any:
    resolved_config = config or GoogleOAuthConfig()
    normalized_scopes = _merge_requested_and_cached_scopes(
        scopes,
        token_path=resolved_config.token_path,
    )
    if not normalized_scopes:
        raise ValueError("At least one OAuth scope is required.")

    _, _, InstalledAppFlow = _import_google_clients()

    if not resolved_config.credentials_path.exists():
        raise FileNotFoundError(
            f"OAuth client file not found: {resolved_config.credentials_path}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(resolved_config.credentials_path),
        normalized_scopes,
        state=state,
    )
    flow.redirect_uri = redirect_uri
    if code_verifier is not None:
        flow.code_verifier = code_verifier
    with _relax_oauthlib_token_scope_check():
        flow.fetch_token(
            authorization_response=_coerce_loopback_authorization_response_to_https(
                authorization_response
            )
        )
    creds = flow.credentials
    if not _granted_scopes_cover_requested_scopes(creds, normalized_scopes):
        granted_scopes = _normalize_scopes(getattr(creds, "scopes", ()) or ())
        raise RuntimeError(
            "Granted OAuth scopes do not cover the requested access. "
            f"requested={normalized_scopes!r} granted={granted_scopes!r}"
        )
    _write_google_oauth_token(resolved_config.token_path, creds.to_json())
    return creds


def _import_google_clients() -> tuple[Any, Any, Any]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "Missing Google client libraries. Install them with "
            "`uv sync --extra google` and run this project with "
            "`uv run python ...`."
        ) from exc

    return Request, Credentials, InstalledAppFlow


def _resolve_google_oauth_credentials_path(path: Path | None) -> Path:
    if path is not None:
        return Path(path).expanduser()

    override = os.environ.get(GOOGLE_OAUTH_CLIENT_FILE_ENV, "").strip()
    if override:
        return Path(override).expanduser()

    default_path = default_google_oauth_client_path()
    if default_path.exists():
        return default_path
    if LEGACY_GOOGLE_OAUTH_CLIENT_PATH.exists():
        return LEGACY_GOOGLE_OAUTH_CLIENT_PATH
    return default_path


def _resolve_google_oauth_token_path(
    path: Path | None,
    *,
    credentials_path: Path,
) -> Path:
    if path is not None:
        return Path(path).expanduser()

    override = os.environ.get(GOOGLE_OAUTH_TOKEN_FILE_ENV, "").strip()
    if override:
        return Path(override).expanduser()

    default_path = default_google_oauth_token_path()
    if credentials_path == default_google_oauth_client_path():
        return default_path
    if credentials_path == LEGACY_GOOGLE_OAUTH_CLIENT_PATH and LEGACY_GOOGLE_OAUTH_TOKEN_PATH.exists():
        return LEGACY_GOOGLE_OAUTH_TOKEN_PATH
    if default_path.exists():
        return default_path
    if LEGACY_GOOGLE_OAUTH_TOKEN_PATH.exists():
        return LEGACY_GOOGLE_OAUTH_TOKEN_PATH
    return default_path


def _load_google_oauth_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GoogleOAuthConfigurationError(
            f"OAuth client JSON を読み取れませんでした: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise GoogleOAuthConfigurationError(
            f"OAuth client JSON はオブジェクトである必要があります: {path}"
        )
    return payload


def _write_google_oauth_token(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _extract_google_oauth_client_section(
    payload: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    if isinstance(payload.get("web"), dict):
        return "web", payload["web"]
    if isinstance(payload.get("installed"), dict):
        return "installed", payload["installed"]
    raise GoogleOAuthConfigurationError(
        "OAuth client JSON に `web` または `installed` セクションが必要です。"
    )


def _is_loopback_redirect_uri(redirect_uri: str) -> bool:
    parsed = urlsplit(redirect_uri)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }


def _normalize_scopes(scopes: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(scope).strip() for scope in scopes if str(scope).strip()))


def _merge_requested_and_cached_scopes(
    scopes: Iterable[str],
    *,
    token_path: Path,
) -> tuple[str, ...]:
    requested = list(_normalize_scopes(scopes))
    cached = list(_read_token_scopes(token_path))
    return _normalize_scopes([*requested, *cached])


def _credentials_cover_scopes(creds: Any, scopes: Iterable[str]) -> bool:
    requested_scopes = tuple(str(scope).strip() for scope in scopes if str(scope).strip())
    if not requested_scopes:
        return True

    has_scopes = getattr(creds, "has_scopes", None)
    if callable(has_scopes):
        return bool(has_scopes(requested_scopes))

    granted_scopes = getattr(creds, "scopes", None)
    if granted_scopes is None:
        return True
    return set(requested_scopes).issubset({str(scope).strip() for scope in granted_scopes})


def _read_token_scopes(token_path: Path) -> tuple[str, ...]:
    try:
        payload = json.loads(token_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()

    scopes = payload.get("scopes")
    if not isinstance(scopes, list):
        return ()
    return tuple(str(scope).strip() for scope in scopes if str(scope).strip())


def _scopes_cover_requested_scopes(
    granted_scopes: Iterable[str],
    requested_scopes: Iterable[str],
) -> bool:
    granted = {str(scope).strip() for scope in granted_scopes if str(scope).strip()}
    requested = {str(scope).strip() for scope in requested_scopes if str(scope).strip()}
    return all(any(candidate in granted for candidate in _scope_equivalents(scope)) for scope in requested)


def _coerce_loopback_authorization_response_to_https(
    authorization_response: str,
) -> str:
    parsed = urlsplit(authorization_response)
    if parsed.scheme != "http":
        return authorization_response
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return authorization_response
    secure_parts = SplitResult(
        scheme="https",
        netloc=parsed.netloc,
        path=parsed.path,
        query=parsed.query,
        fragment=parsed.fragment,
    )
    return urlunsplit(secure_parts)


@contextmanager
def _relax_oauthlib_token_scope_check() -> Any:
    original = os.environ.get("OAUTHLIB_RELAX_TOKEN_SCOPE")
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("OAUTHLIB_RELAX_TOKEN_SCOPE", None)
        else:
            os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = original


def _granted_scopes_cover_requested_scopes(
    creds: Any,
    requested_scopes: Iterable[str],
) -> bool:
    if _credentials_cover_scopes(creds, requested_scopes):
        return True
    granted_scopes = _normalize_scopes(getattr(creds, "scopes", ()) or ())
    if not granted_scopes:
        return False
    return _scopes_cover_requested_scopes(granted_scopes, requested_scopes)


def _scope_equivalents(scope: str) -> tuple[str, ...]:
    normalized = str(scope).strip()
    if normalized == CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE:
        return (
            CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE,
            CLASSROOM_STUDENT_SUBMISSIONS_STUDENTS_READONLY_SCOPE,
        )
    if normalized == CLASSROOM_STUDENT_SUBMISSIONS_STUDENTS_READONLY_SCOPE:
        return (
            CLASSROOM_STUDENT_SUBMISSIONS_STUDENTS_READONLY_SCOPE,
            CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE,
        )
    return (normalized,)


def _run_local_server_relaxing_scope_changes(flow: Any, *, port: int) -> Any:
    previous = os.environ.get("OAUTHLIB_RELAX_TOKEN_SCOPE")
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    try:
        return flow.run_local_server(port=port)
    finally:
        if previous is None:
            os.environ.pop("OAUTHLIB_RELAX_TOKEN_SCOPE", None)
        else:
            os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = previous


def build_google_service(
    api_name: str,
    version: str,
    *,
    scopes: Iterable[str],
    config: GoogleOAuthConfig | None = None,
    allow_interactive: bool = True,
) -> Any:
    creds = load_google_user_credentials(
        scopes,
        config=config,
        allow_interactive=allow_interactive,
    )
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Missing Google API discovery client. Install it with "
            "`uv sync --extra google` and run this project with "
            "`uv run python ...`."
        ) from exc
    return build(api_name, version, credentials=creds)
