from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sansan_competition.classroom import build_post_only_client
from sansan_competition.oauth import GoogleOAuthConfig


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Post an approved Classroom reminder payload to Google Classroom.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a full agent output JSON or a standalone classroomReminder JSON.",
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
        "--approved",
        action="store_true",
        help="Required safety flag before posting to Classroom.",
    )
    return parser.parse_args(argv)


def _load_reminder_output(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        outputs = payload.get("outputs")
        if isinstance(outputs, dict) and isinstance(outputs.get("classroomReminder"), dict):
            return outputs["classroomReminder"]
    if isinstance(payload, dict):
        return payload
    raise ValueError("Input JSON must be an object.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.approved:
        print(
            "Refusing to post without explicit approval. Re-run with --approved.",
            file=sys.stderr,
        )
        return 2

    try:
        reminder_output = _load_reminder_output(Path(args.input))
    except Exception as exc:
        print(f"Failed to load reminder payload: {exc}", file=sys.stderr)
        return 1

    oauth_config = GoogleOAuthConfig(
        credentials_path=args.credentials,
        token_path=args.token,
    )

    try:
        client = build_post_only_client(oauth_config=oauth_config)
        created = client.create_announcement_from_output(reminder_output)
    except Exception as exc:
        print(f"Failed to create Classroom announcement: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "announcementId": created.get("id"),
                "alternateLink": created.get("alternateLink"),
                "state": created.get("state"),
                "courseId": created.get("courseId"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
