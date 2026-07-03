# sansan-competition

`kimu` 担当の土台として、Google Classroom の提出状況を正規化し、判定し、GUI 班へ返す構造化 JSON を生成する実装を追加しています。

## 含めたもの

- `sansan_competition/normalization.py`
  - `Course` / `CourseWork` / `StudentSubmission` の正規化
  - 部分失敗を許容する `normalize_submission_batch`
- `sansan_competition/analysis.py`
  - 未提出
  - 期限接近未提出
  - 遅延提出
  - 添付不足の可能性
  の判定ロジック
- `sansan_competition/contract.py`
  - `schemaVersion=1.0.0` の共通レスポンス組み立て
  - 正常系、部分成功、異常系の返却
  - GUI 向け `summary` / `gui` / `outputs` / `approval` / `errors`
  - 契約検証用のバリデータ
- `sansan_competition/outputs.py`
  - Markdown / PDF / Google Document 用の構造化データ
  - Classroom 投稿 payload
- `schemas/agent-output-v1.0.0.json`
  - GUI 班との契約として渡せる JSON Schema
- `samples/*.json`
  - 正常系と異常系のサンプル JSON

## 設計上の前提

- エラー時も GUI の分岐を減らすため、`gui` / `outputs` / `approval` を空で返す固定形にしています。
- `添付不足の可能性` は、`ASSIGNMENT` または `SHORT_ANSWER_QUESTION` で `TURNED_IN` / `RETURNED` だが添付ゼロの場合のヒューリスティックです。実際の提出内容確認は別途必要です。
- `partial_success` を導入し、一部データだけ正規化できたケースを `errors` と `warnings` に残します。

## 実行例

```bash
python3 main.py
```

## テスト

```bash
python3 -m unittest discover -s tests
```

## PR Automation

GitHub Actions based PR automation lives in [`.github/workflows/pr-automation.yml`](/Users/suzukiakiramuki/projects/sansan-competition/.github/workflows/pr-automation.yml).

- Trigger: `pull_request_target`
- Loop: auto-fix cache artifacts, rerun validation, post a PR report comment
- Pass condition: `pytest`, CLI sample generation, and shared JSON contract checks all pass
- Merge behavior: by default the workflow stops at a review result; add the `automerge` label to allow squash merge after a green run
- Fork PRs: validation and report comments run, but auto-fix commits are only pushed for same-repository branches

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

## Review And Merge Scope Agent

Run the review-triggered implementation agent once:

```bash
python3 scripts/review_implementation_agent.py
```

By default the agent runs in `all` mode. It can:

- watch the current branch PR for newly submitted actionable reviews and implement the requested fixes
- watch newly merged PRs on the default branch, absorb what landed, and continue the next concrete task inside its assigned role scope from `ROLE.md`

The agent writes prompts under `.review-implementation-agent/prompts/` and invokes `codex exec` locally.

Local dry-run:

```bash
python3 scripts/review_implementation_agent.py --dry-run
```

Continuous monitor:

```bash
bash scripts/monitor_review_implementation_agent.sh
```

Optional overrides:

- `REVIEW_IMPLEMENT_INTERVAL_SECONDS=300` sets the polling interval.
- `REVIEW_IMPLEMENT_REPO_DIR=/path/to/repo` sets the repository directory.
- `REVIEW_IMPLEMENT_MODE=review|merged-progress|all` selects which trigger types to process.
- `REVIEW_IMPLEMENT_ROLE_NAME=hinata` selects the ownership scope from `ROLE.md` for post-merge progression.
- `REVIEW_IMPLEMENT_AGENT_COMMAND='codex exec --cd {repo_root} --sandbox workspace-write --ask-for-approval never'` overrides the implementation command.
