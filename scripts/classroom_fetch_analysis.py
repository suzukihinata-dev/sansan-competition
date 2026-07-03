from __future__ import annotations

import argparse
from datetime import datetime
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sansan_competition.classroom import GoogleClassroomClient, fetch_submission_analysis
from sansan_competition.contract import build_submission_analysis_response
from sansan_competition.models import JST
from sansan_competition.oauth import GoogleOAuthConfig


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch live Google Classroom data and build the shared submission analysis JSON.",
    )
    parser.add_argument("--course-id", required=True, help="Classroom course ID.")
    parser.add_argument("--course-work-id", required=True, help="Classroom courseWork ID.")
    parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to the OAuth client secret JSON file.",
    )
    parser.add_argument(
        "--token",
        default="token.json",
        help="Path to the cached user token JSON file.",
    )
    parser.add_argument(
        "--request-id",
        default="",
        help="Optional request ID for the output contract.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    oauth_config = GoogleOAuthConfig(
        credentials_path=args.credentials,
        token_path=args.token,
    )

    try:
        client = GoogleClassroomClient.from_oauth(oauth_config=oauth_config)
        analysis = fetch_submission_analysis(
            client,
            course_id=args.course_id,
            course_work_id=args.course_work_id,
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
