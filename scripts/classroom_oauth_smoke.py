from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sansan_competition.oauth import (
    GoogleOAuthConfig,
    build_google_service,
)

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a minimal Google Classroom OAuth flow and list courses.",
    )
    parser.add_argument(
        "--credentials",
        default=None,
        help="Path to the OAuth client secret JSON file. Omit to use the app default.",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Path to the cached user token JSON file. Omit to use the app default.",
    )
    parser.add_argument(
        "--scope",
        action="append",
        dest="scopes",
        help="OAuth scope to request. Repeat to request multiple scopes.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=10,
        help="Maximum number of courses to list.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scopes = args.scopes or list(DEFAULT_SCOPES)

    try:
        service = build_google_service(
            "classroom",
            "v1",
            scopes=scopes,
            config=GoogleOAuthConfig(
                credentials_path=args.credentials,
                token_path=args.token,
            ),
        )
        result = service.courses().list(pageSize=args.page_size).execute()
    except Exception as exc:
        print(f"Google Classroom API error: {exc}", file=sys.stderr)
        return 1

    courses = result.get("courses", [])
    if not courses:
        print("No courses found.")
        return 0

    for course in courses:
        course_id = course.get("id", "")
        name = course.get("name", "")
        section = course.get("section", "")
        suffix = f" ({section})" if section else ""
        print(f"{course_id}: {name}{suffix}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
