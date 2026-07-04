from __future__ import annotations

import argparse
from datetime import datetime
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sansan_competition.classroom import (
    GoogleClassroomClient,
    fetch_submission_analysis,
    load_classroom_fetch_fixture,
)
from sansan_competition.contract import build_submission_analysis_response
from sansan_competition.models import JST
from sansan_competition.oauth import GoogleOAuthConfig


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Google Classroom data, or replay a raw fixture, and build the shared "
            "submission analysis JSON."
        ),
    )
    parser.add_argument("--course-id", help="Classroom course ID.")
    parser.add_argument("--course-work-id", help="Classroom courseWork ID.")
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
        "--request-id",
        default="",
        help="Optional request ID for the output contract.",
    )
    parser.add_argument(
        "--fixture",
        help=(
            "Path to a JSON fixture containing raw Classroom fetch responses. "
            "When provided, OAuth credentials are not used."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        if args.fixture:
            fixture = load_classroom_fetch_fixture(args.fixture)
            client = fixture.build_client()
            course_id = (args.course_id or "").strip() or fixture.course_id
            course_work_id = (args.course_work_id or "").strip() or fixture.course_work_id
        else:
            course_id = (args.course_id or "").strip()
            course_work_id = (args.course_work_id or "").strip()
            if not course_id or not course_work_id:
                raise ValueError("--course-id and --course-work-id are required.")
            oauth_config = GoogleOAuthConfig(
                credentials_path=args.credentials,
                token_path=args.token,
            )
            client = GoogleClassroomClient.from_oauth(oauth_config=oauth_config)
        analysis = fetch_submission_analysis(
            client,
            course_id=course_id,
            course_work_id=course_work_id,
            now=datetime.now(JST),
        )
    except Exception as exc:
        print(f"Failed to fetch Classroom analysis: {exc}", file=sys.stderr)
        return 1

    request_id = args.request_id.strip() or datetime.now(JST).strftime("req_%Y%m%d_%H%M%S_live")
    payload = build_submission_analysis_response(request_id, analysis)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
