"""Google OAuth 2.0 認証 (REQUIREMENTS 11.3, 12.1)。

- 必要最小限のスコープのみ要求する。
- 投稿/作成(WRITE)スコープは読み取り専用(READ)スコープと分離する。
- トークンはログ・GUIへそのまま出さない。

MVPはモック実装。実Google OAuthは同じ AuthProvider インターフェースで差し替える。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .errors import AgentError, ErrorCode


class Scopes:
    # 読み取り専用
    COURSES_READONLY = "https://www.googleapis.com/auth/classroom.courses.readonly"
    COURSEWORK_READONLY = (
        "https://www.googleapis.com/auth/classroom.coursework.students.readonly"
    )
    ROSTERS_READONLY = "https://www.googleapis.com/auth/classroom.rosters.readonly"
    SUBMISSIONS_READONLY = (
        "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly"
    )
    # 書き込み(投稿/作成)
    ANNOUNCEMENTS = "https://www.googleapis.com/auth/classroom.announcements"
    DOCUMENTS = "https://www.googleapis.com/auth/documents"
    DRIVE_FILE = "https://www.googleapis.com/auth/drive.file"
    DRIVE_READONLY = "https://www.googleapis.com/auth/drive.readonly"
    CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.readonly"
    TOPICS_READONLY = "https://www.googleapis.com/auth/classroom.topics.readonly"
    TOPICS = "https://www.googleapis.com/auth/classroom.topics"
    COURSEWORK_MATERIALS_READONLY = (
        "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly"
    )
    COURSEWORK_MATERIALS = "https://www.googleapis.com/auth/classroom.courseworkmaterials"
    COURSEWORK_STUDENTS = "https://www.googleapis.com/auth/classroom.coursework.students"


READ_SCOPES = (
    Scopes.COURSES_READONLY,
    Scopes.COURSEWORK_READONLY,
    Scopes.ROSTERS_READONLY,
    Scopes.SUBMISSIONS_READONLY,
)

WRITE_SCOPES = (
    Scopes.ANNOUNCEMENTS,
    Scopes.DOCUMENTS,
    Scopes.DRIVE_FILE,
)


@dataclass
class Credentials:
    token: str
    scopes: tuple[str, ...] = field(default_factory=tuple)
    email: str = ""
    expired: bool = False

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def masked_token(self) -> str:
        """ログ表示用にトークンをマスクする (12.1)。"""
        if len(self.token) <= 6:
            return "***"
        return f"{self.token[:3]}***{self.token[-2:]}"


@runtime_checkable
class AuthProvider(Protocol):
    def login(self, scopes: tuple[str, ...]) -> Credentials: ...
    def credentials(self) -> Credentials: ...
    def require_scope(self, scope: str) -> None: ...


class MockAuthProvider:
    """オフラインで認証フローを再現するモック。

    simulate_expired=True で GOOGLE_AUTH_EXPIRED を再現できる。
    """

    def __init__(
        self,
        email: str = "teacher@example.com",
        simulate_expired: bool = False,
    ) -> None:
        self._email = email
        self._simulate_expired = simulate_expired
        self._creds: Credentials | None = None

    def login(self, scopes: tuple[str, ...] = READ_SCOPES) -> Credentials:
        self._creds = Credentials(
            token="mock-oauth-token-abcdef",
            scopes=tuple(scopes),
            email=self._email,
            expired=self._simulate_expired,
        )
        return self._creds

    def credentials(self) -> Credentials:
        if self._creds is None:
            raise AgentError(ErrorCode.GOOGLE_AUTH_EXPIRED, detail="not logged in")
        if self._creds.expired:
            raise AgentError(ErrorCode.GOOGLE_AUTH_EXPIRED, detail="token expired")
        return self._creds

    def require_scope(self, scope: str) -> None:
        creds = self.credentials()
        if not creds.has_scope(scope):
            raise AgentError(
                ErrorCode.CLASSROOM_API_PERMISSION_DENIED,
                detail=f"missing scope: {scope}",
            )
