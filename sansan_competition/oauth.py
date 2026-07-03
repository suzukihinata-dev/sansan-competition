from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

CLASSROOM_COURSES_READONLY_SCOPE = "https://www.googleapis.com/auth/classroom.courses.readonly"
CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE = (
    "https://www.googleapis.com/auth/classroom.coursework.students.readonly"
)
CLASSROOM_ROSTERS_READONLY_SCOPE = "https://www.googleapis.com/auth/classroom.rosters.readonly"
CLASSROOM_ANNOUNCEMENTS_SCOPE = "https://www.googleapis.com/auth/classroom.announcements"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DOCUMENTS_SCOPE = "https://www.googleapis.com/auth/documents"


@dataclass(slots=True)
class GoogleOAuthConfig:
    credentials_path: Path = Path("credentials.json")
    token_path: Path = Path("token.json")
    local_server_port: int = 0

    def __post_init__(self) -> None:
        self.credentials_path = Path(self.credentials_path)
        self.token_path = Path(self.token_path)


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


def load_google_user_credentials(
    scopes: Iterable[str],
    *,
    config: GoogleOAuthConfig | None = None,
) -> Any:
    resolved_config = config or GoogleOAuthConfig()
    normalized_scopes = tuple(dict.fromkeys(str(scope).strip() for scope in scopes if str(scope).strip()))
    if not normalized_scopes:
        raise ValueError("At least one OAuth scope is required.")

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "Missing Google client libraries. Install them with "
            "`python3 -m pip install -e '.[google]'` or "
            "`python3 -m pip install --upgrade google-api-python-client "
            "google-auth-httplib2 google-auth-oauthlib`."
        ) from exc

    if not resolved_config.credentials_path.exists():
        raise FileNotFoundError(
            f"OAuth client file not found: {resolved_config.credentials_path}"
        )

    creds = None
    if resolved_config.token_path.exists():
        creds = Credentials.from_authorized_user_file(
            str(resolved_config.token_path),
            normalized_scopes,
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(resolved_config.credentials_path),
                normalized_scopes,
            )
            creds = flow.run_local_server(port=resolved_config.local_server_port)
        resolved_config.token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def build_google_service(
    api_name: str,
    version: str,
    *,
    scopes: Iterable[str],
    config: GoogleOAuthConfig | None = None,
) -> Any:
    creds = load_google_user_credentials(scopes, config=config)
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Missing Google API discovery client. Install it with "
            "`python3 -m pip install -e '.[google]'`."
        ) from exc
    return build(api_name, version, credentials=creds)
