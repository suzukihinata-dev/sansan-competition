#!/usr/bin/env bash
set -euo pipefail

# Monitor the repository for open PRs at a fixed interval.
# The default interval is 5x a 60-second baseline.
interval_seconds="${PR_MONITOR_INTERVAL_SECONDS:-300}"
repo_dir="${PR_MONITOR_REPO_DIR:-$(pwd)}"
max_prs="${PR_MONITOR_LIMIT:-50}"

while true; do
  cd "$repo_dir"

  echo "checking open pull requests in $repo_dir"
  if ! prs_output="$(gh pr list --state open --limit "$max_prs")"; then
    echo "failed to query pull requests" >&2
    exit 1
  fi

  if [ -n "$prs_output" ]; then
    printf '%s\n' "$prs_output"
  else
    echo "no open pull requests"
  fi

  sleep "$interval_seconds"
done
