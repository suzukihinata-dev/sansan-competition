# sansan-competition

## PR Automation

GitHub Actions based PR automation lives in [`.github/workflows/pr-automation.yml`](/Users/suzukiakiramuki/projects/sansan-competition/.github/workflows/pr-automation.yml).

- Trigger: `pull_request_target`
- Loop: auto-fix cache artifacts, rerun validation, post a PR report comment
- Pass condition: `pytest`, CLI sample generation, and shared JSON contract checks all pass
- Merge behavior: by default the workflow stops at a review result; add the `automerge` label to allow squash merge after a green run

Local dry-run:

```bash
python3 scripts/pr_automation.py --apply-fixes
```

## PR Monitoring

Run the repository monitor with a 5x interval:

```bash
bash scripts/monitor_prs.sh
```

Optional overrides:

- `PR_MONITOR_INTERVAL_SECONDS=300` sets the poll interval.
- `PR_MONITOR_LIMIT=50` sets the maximum number of open PRs to fetch.
- `PR_MONITOR_REPO_DIR=/path/to/repo` sets the repository directory.
