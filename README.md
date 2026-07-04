# sansan-competition

Google Classroom 運用支援 AI エージェントのプロトタイプです。
現在の実装は、Google Classroom から課題と提出状況を取得し、`kimu` 担当の正規化・判定・JSON 契約を通して GUI に返し、教師承認後に Classroom 投稿まで進める流れを中心にしています。

## 現在できること

- Google Classroom への OAuth 接続
- コース一覧取得
- コース配下の課題一覧取得
- 課題ごとの提出状況分析
- AI アウトプット JSON の GUI 表示
- リマインド案の確認と承認フロー
- 承認後の Classroom お知らせ投稿
- CLI からの OAuth 疎通確認
- CLI からの提出分析、Markdown 保存、Google Document 作成

未実装または限定的なもの:

- PDF の実バイナリ生成
- 本格的なフロントエンドフレームワーク化
- Classroom 以外の LMS 連携

## クイックスタート

依存を入れます。

```bash
uv sync --extra google
```

ローカルで GUI を起動します。

```bash
uv run python main.py --host 127.0.0.1 --port 8000
```

ブラウザで `http://127.0.0.1:8000` を開きます。

別端末ブラウザから確認したい場合は、サーバを外向きに bind してください。

```bash
uv run python main.py --host 0.0.0.0 --port 8000
```

## OAuth / Google Classroom セットアップ

このリポジトリは、repo 直下の `credentials.json` を必須にしない構成です。
OAuth client JSON は GUI から登録するか、端末ごとの設定ディレクトリに置きます。

端末ごとの設定ディレクトリ:

- macOS: `~/Library/Application Support/sansan-competition/`
- Linux: `~/.config/sansan-competition/`
- Windows: `%APPDATA%/sansan-competition/`

OAuth client の使い分け:

- 同一端末で CLI またはローカル GUI を使うだけなら `Desktop app`
- 別端末ブラウザから GUI を使うなら `Web application`

別端末ブラウザ利用時は、Google Cloud 側の Authorized redirect URI に、実際のアクセス先に合わせて次を追加してください。

- `http://<host>:<port>/oauth/google/callback`
- または `https://<host>/oauth/google/callback`

GUI のログイン画面では、現在必要な redirect URI と設定不足の理由が表示されます。
OAuth consent screen の Audience が `External` かつ Publishing status が `Testing` の場合は、利用する Google アカウントを `Test users` に追加してください。未追加だと 403 `access_denied` になります。

詳しい手順:

- [docs/google-classroom-cli-oauth-setup.md](docs/google-classroom-cli-oauth-setup.md)
- [docs/google_api_setup.md](docs/google_api_setup.md)
- [docs/firebase-hosting-cloud-run-setup.md](docs/firebase-hosting-cloud-run-setup.md)

## GUI の起動と動作

`main.py` は静的 GUI と `/api/live/*` の簡易 API を同時に提供します。

主な live endpoint:

- `/api/live/oauth/config`
- `/api/live/oauth/check`
- `/api/live/oauth/start`
- `/api/live/oauth/status`
- `/api/live/courses`
- `/api/live/coursework`
- `/api/live/submission-analysis`
- `/api/live/reminder-generation`
- `/api/live/post-reminder`

ログイン画面からは次の流れで使います。

1. 必要なら OAuth client JSON を登録する
2. Google Classroom に接続する
3. コースを選ぶ
4. 課題を選ぶ
5. 提出状況分析やリマインド案を確認する
6. 承認後に Classroom 投稿を実行する

## Firebase / Cloud Run 配備

別端末ブラウザから安定して使う場合は、Firebase Hosting の `*.web.app` または custom domain を入口にし、`/api/**` と `/oauth/google/callback` を Cloud Run 上の Python バックエンドへ流す構成を推奨します。

追加済みファイル:

- `Dockerfile`
- `firebase.json`
- `scripts/deploy_firebase_cloud_run.sh`
- `docs/firebase-hosting-cloud-run-setup.md`

概要:

1. Billing を有効化する
2. Cloud Run / Cloud Build / Artifact Registry API を有効化する
3. `PROJECT_ID=... ./scripts/deploy_firebase_cloud_run.sh` を実行する
4. Google OAuth の Web application client に `https://<site>.web.app/oauth/google/callback` を登録する

## CLI / サンプルコマンド

OAuth 疎通確認:

```bash
uv run python scripts/classroom_oauth_smoke.py
```

実データの提出分析:

```bash
uv run python scripts/classroom_fetch_analysis.py --course-id YOUR_COURSE_ID --course-work-id YOUR_COURSEWORK_ID
```

承認済みリマインド投稿:

```bash
uv run python scripts/classroom_post_reminder.py --input samples/reminder_generation_success.json --approved
```

Markdown 保存:

```bash
uv run python scripts/export_outputs.py --input samples/submission_analysis_success.json --format markdown --output-dir exports
```

Google Document 作成:

```bash
uv run python scripts/export_outputs.py --input samples/submission_analysis_success.json --format googleDocument
```

サンプル payload の出力:

```bash
uv run python main.py sample-reminder
uv run python main.py sample-course-summary
uv run python main.py sample-ai-input-course-summary
uv run python main.py sample-ai-input-reminder
uv run python main.py sample-ai-input-weekly-report
uv run python main.py sample-partial-analysis
uv run python main.py sample-partial-reminder
```

## kimu 担当範囲

`kimu` 担当として主に入っているもの:

- `sansan_competition/normalization.py`
  - `Course` / `CourseWork` / `StudentSubmission` の正規化
  - 部分失敗を許容する `normalize_submission_batch`
- `sansan_competition/analysis.py`
  - 未提出、期限接近、遅延提出、添付不足の可能性の判定
  - AI 入力 payload の組み立て
- `sansan_competition/contract.py`
  - 共通レスポンス組み立て
  - 正常系、部分成功、異常系の固定形
  - 契約バリデーション
- `sansan_competition/outputs.py`
  - Markdown / PDF / Google Document / Classroom handoff 用の構造化出力
- `schemas/agent-output-v1.0.0.json`
  - GUI 班との JSON 契約
- `samples/*.json`
  - 正常系・異常系サンプル

設計上の前提:

- エラー時も `gui` / `outputs` / `approval` を空で返す固定形を維持する
- `partial_success` で一部取得失敗を表現する
- 生徒向け投稿には不要な個人情報を含めない

## テスト

全体テスト:

```bash
uv run python -m unittest
```

kimu 回帰ゲート:

```bash
uv run python scripts/kimu_regression_gate.py
```

主に確認したいとき:

- `normalization.py` / `analysis.py` / `contract.py` / `outputs.py` を変えた直後
- 代表的な JSON 契約や GUI handoff を触った直後
- PR を更新する前

## PR 自動化 / モニタ

PR automation:

- workflow: `.github/workflows/pr-automation.yml`
- ローカル dry-run:

```bash
python3 scripts/pr_automation.py --apply-fixes
```

PR monitor:

```bash
bash scripts/monitor_prs.sh
```

review 実装エージェント:

```bash
python3 scripts/review_implementation_agent.py
```

dry-run:

```bash
python3 scripts/review_implementation_agent.py --dry-run
```

continuous monitor:

```bash
bash scripts/monitor_review_implementation_agent.sh
```

## 関連ドキュメント

- [REQUIREMENTS.md](REQUIREMENTS.md)
- [ROLE.md](ROLE.md)
- [docs/google-classroom-cli-oauth-setup.md](docs/google-classroom-cli-oauth-setup.md)
- [docs/google_api_setup.md](docs/google_api_setup.md)
- [docs/firebase-hosting-cloud-run-setup.md](docs/firebase-hosting-cloud-run-setup.md)
