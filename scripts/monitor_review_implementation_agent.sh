#!/usr/bin/env bash
set -euo pipefail

interval_seconds="${REVIEW_IMPLEMENT_INTERVAL_SECONDS:-300}"
repo_dir="${REVIEW_IMPLEMENT_REPO_DIR:-$(pwd)}"
mode="${REVIEW_IMPLEMENT_MODE:-all}"
role_name="${REVIEW_IMPLEMENT_ROLE_NAME:-hinata}"

while true; do
  cd "$repo_dir"

  echo "checking for new actionable reviews in $repo_dir"
  python3 scripts/review_implementation_agent.py \
    --mode "$mode" \
    --role-name "$role_name" \
    ${REVIEW_IMPLEMENT_DRY_RUN:+--dry-run}

  sleep "$interval_seconds"
done
