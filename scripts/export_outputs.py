#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sansan_competition.exporters import (
    create_google_document_from_output,
    extract_output_payload,
    save_markdown_output,
)
from sansan_competition.oauth import GoogleOAuthConfig


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute markdown or Google Document exports from an agent output JSON.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a full agent output JSON or a standalone export payload JSON.",
    )
    parser.add_argument(
        "--format",
        required=True,
        choices=("markdown", "googleDocument"),
        help="Which export payload to execute.",
    )
    parser.add_argument(
        "--output-dir",
        default="exports",
        help="Directory for markdown exports.",
    )
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
        "--share-email",
        action="append",
        dest="share_emails",
        help="Email to share the created Google Document with. Repeatable.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        export_payload = extract_output_payload(payload, args.format)
    except Exception as exc:
        print(f"Failed to load export payload: {exc}", file=sys.stderr)
        return 1

    try:
        if args.format == "markdown":
            result = save_markdown_output(
                export_payload,
                output_dir=args.output_dir,
            )
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
            return 0

        result = create_google_document_from_output(
            export_payload,
            oauth_config=GoogleOAuthConfig(
                credentials_path=args.credentials,
                token_path=args.token,
            ),
            share_emails=args.share_emails,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Failed to execute {args.format} export: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
