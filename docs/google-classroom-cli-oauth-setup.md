# Google Classroom / CLI OAuth セットアップメモ

## 1. 現状

2026-07-03 時点で、このリポジトリには以下を追加済みです。

- [sansan_competition/oauth.py](/Users/kimura/Desktop/SP活動/2年/後期/sansan-competition/sansan_competition/oauth.py)
  - Desktop app OAuth と Google API service 構築
- [sansan_competition/classroom.py](/Users/kimura/Desktop/SP活動/2年/後期/sansan-competition/sansan_competition/classroom.py)
  - Classroom データ取得、正規化接続、announcement 投稿
- [scripts/classroom_oauth_smoke.py](/Users/kimura/Desktop/SP活動/2年/後期/sansan-competition/scripts/classroom_oauth_smoke.py)
  - OAuth 疎通確認
- [scripts/classroom_fetch_analysis.py](/Users/kimura/Desktop/SP活動/2年/後期/sansan-competition/scripts/classroom_fetch_analysis.py)
  - Classroom 実データから提出分析 JSON を生成
- [scripts/classroom_post_reminder.py](/Users/kimura/Desktop/SP活動/2年/後期/sansan-competition/scripts/classroom_post_reminder.py)
  - 承認済み `classroomReminder` の投稿
- [scripts/export_outputs.py](/Users/kimura/Desktop/SP活動/2年/後期/sansan-competition/scripts/export_outputs.py)
  - `outputs.markdown` の保存と `outputs.googleDocument` の Google Document 作成
- [sansan_competition/exporters.py](/Users/kimura/Desktop/SP活動/2年/後期/sansan-competition/sansan_competition/exporters.py)
  - 実出力の共通処理

まだ入っていないもの:

- Web GUI 向け OAuth ログイン画面
- フロントエンド経由の OAuth コールバック処理
- PDF の実バイナリ生成

一方で、`kimu` 担当のデータ処理側は、Google API の実呼び出しがなくても進められる状態です。

- [sansan_competition/normalization.py](/Users/kimura/Desktop/SP活動/2年/後期/sansan-competition/sansan_competition/normalization.py)
  - Classroom 風の辞書データを正規化できる
- [tests/test_normalization.py](/Users/kimura/Desktop/SP活動/2年/後期/sansan-competition/tests/test_normalization.py)
  - Classroom の `dueDate` / `dueTime` 形式を前提にしたテストがある
- [main.py](/Users/kimura/Desktop/SP活動/2年/後期/sansan-competition/main.py)
  - サンプルデータだけで JSON 契約の確認ができる

## 2. セットアップが必要か

### `kimu` の作業だけなら

不要です。

以下は OAuth なしで進められます。

- 正規化ロジックの改善
- 提出判定ロジックの改善
- JSON Schema / サンプル JSON / テスト整備
- GUI 班向けの契約調整

### プロジェクト全体の MVP としては

必要です。

理由は、要件上で以下が必須だからです。

- Google アカウントでログインする
- Google Classroom からコース、課題、提出状況を取得する
- 教師承認後に Classroom へ投稿する
- 必要に応じて Google Document を作成する

したがって、`OAuth` と `Google API` の実装は `mocky` 主担当で必須です。現状は CLI ベースの最低限の確認・取得・投稿まで進んでいますが、GUI 結合はまだです。

## 3. 何をやればよいか

`mocky` または結合担当が、少なくとも次を実施する必要があります。

1. Google Cloud プロジェクトを作る
2. 必要 API を有効化する
3. OAuth consent screen を設定する
4. CLI 検証用の Desktop app クライアントを作る
5. `credentials.json` をローカルに置く
6. OAuth を 1 回通して `token.json` を作る
7. Classroom API で最低限の読み取りを確認する
8. その取得結果を `kimu` の正規化関数へ渡す

## 4. 有効化すべき API

最低限:

- Google Classroom API

必要に応じて:

- Google Docs API
- Google Drive API

初期の `kimu` テストだけなら Docs / Drive は不要です。`Classroom` の読み取り確認だけ先に通せば十分です。

## 5. 推奨スコープ

用途ごとに最小限で始めるべきです。

- コース一覧取得:
  - `https://www.googleapis.com/auth/classroom.courses.readonly`
- 課題一覧取得:
  - `https://www.googleapis.com/auth/classroom.coursework.students.readonly`
- 提出状況取得:
  - `https://www.googleapis.com/auth/classroom.coursework.students.readonly`
- Classroom お知らせ投稿:
  - `https://www.googleapis.com/auth/classroom.announcements`
- Google Document 系の出力:
  - まずは `https://www.googleapis.com/auth/drive.file` を優先
  - 実装上どうしても必要な場合のみ `https://www.googleapis.com/auth/documents` を検討

`drive.file` は Google 公式でも推奨寄りで、広すぎる `drive` より安全です。

## 6. CLI OAuth の最小確認手順

1. Google Cloud Console で Desktop app の OAuth クライアントを作る
2. ダウンロードした JSON を、このリポジトリ直下の `credentials.json` に置く
3. ライブラリを入れる
4. 疎通確認スクリプトを実行する

```bash
python3 -m pip install -e '.[google]'
python3 scripts/classroom_oauth_smoke.py
```

初回実行時はブラウザ認証が走り、成功すると `token.json` が生成されます。

## 6.5 実データで提出分析を確認する

OAuth が通ったら、次で Classroom 実データを `kimu` の JSON 契約へ通せます。

```bash
python3 scripts/classroom_fetch_analysis.py --course-id YOUR_COURSE_ID --course-work-id YOUR_COURSEWORK_ID
```

## 6.6 承認済みリマインドを投稿する

`classroomReminder` を含む JSON を使って、明示的承認付きで投稿できます。

```bash
python3 scripts/classroom_post_reminder.py --input samples/reminder_generation_success.json --approved
```

`--approved` なしでは投稿しません。これは要件にある「教師承認なしに投稿しない」を満たすためです。

## 6.7 Markdown を保存する

```bash
python3 scripts/export_outputs.py --input samples/submission_analysis_success.json --format markdown --output-dir exports
```

## 6.8 Google Document を作成する

Drive API を使って、`outputs.googleDocument` を実 Google Document に変換できます。

```bash
python3 scripts/export_outputs.py --input samples/submission_analysis_success.json --format googleDocument
```

必要なら共有先を追加できます。

```bash
python3 scripts/export_outputs.py --input samples/submission_analysis_success.json --format googleDocument --share-email teacher@example.com
```

## 7. このリポジトリでの次の結合ポイント

`OAuth` が通ったら、次は以下の順でつなぐのが妥当です。

1. `courses.list` でコース一覧取得
2. `courses.courseWork.list` で課題一覧取得
3. `courses.courseWork.studentSubmissions.list` で提出一覧取得
4. 取得した生データを `normalize_course` / `normalize_coursework` / `normalize_submission_batch` に渡す
5. `analyze_submissions` と JSON 契約出力へつなぐ

## 8. 判断

客観的に言うと、現時点では `OAuth` / `Classroom API` と `Markdown / Google Document の実出力` は CLI ベースで最低限の実装まで進んだ、が正確です。

ただし、これはまだ `mocky` 担当の全範囲を満たしたわけではありません。Web ログイン、GUI 結合、PDF 実生成、異常系強化は未完です。

実務上は次の整理が妥当です。

- `kimu` は OAuth なしで契約・判定・正規化を先に固める
- `mocky` は CLI 実装を足がかりに GUI 結合へ進める
- 結合時に、生 API レスポンスをこのリポジトリの正規化関数へ流す
