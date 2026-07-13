# 授業ナレッジ統合

この機能は、Calendarの授業予定を起点にDriveとClassroomのデータを`LessonBundle`へ統合します。

## GUIの流れ

1. 既存の`Google Classroomに接続`でClassroomの読み取りを許可する。
2. ダッシュボードの`Calendar予定を取得`を押し、`授業データを統合`用の授業を選ぶ。
3. Drive検索条件を確認する。初期値は`trashed = false`で、必要なら授業名などで絞る。
4. 必要な場合だけ`文字起こし本文も取得`を有効にする。
5. 統合結果の録画・文字起こし・補助資料リンクを確認する。
6. `教材として公開`または`課題として公開`を選び、教師承認してClassroomへ公開する。

公開処理は毎回最新のCalendar・Drive・Classroomデータを再取得します。既存の同名Topicと同じTopic内の同名項目は再作成せず、重複投稿を避けます。

## API

- `GET /api/live/calendar-events`
  - `calendarId`, `timeMin`, `timeMax`, `q` を指定できます。
- `GET /api/live/drive-files`
  - Drive APIの検索条件を`q`で指定できます。
- `GET /api/live/lesson-bundle?courseId=...&calendarEventId=...`
  - `driveQuery`と`includeTranscripts=true`を任意で指定できます。
- `POST /api/live/lesson-publish`
  - `approved: true`、`courseId`、`calendarEventId`、`items`が必須です。

## OAuthスコープ

読み取りと公開でOAuth intentを分けています。

- `lesson_read`
  - Calendar読み取り
  - Drive読み取り
  - Classroomのコース、課題、教材、Topic読み取り
- `lesson_publish`
  - `lesson_read`の全権限
  - Classroom Topic作成
  - Classroom課題作成
  - Classroom教材作成

Drive内の録画を自動検索するため、読み取りでは`drive.readonly`を使用します。公開サービスへ展開する場合、この権限はOAuth審査・利用者への説明・データ保持方針が必要です。対象ファイルを教師が選択する方式へ変更すれば、将来的に`drive.file`へ狭められます。

## AI用データ

`LessonBundle`は次の情報を保持します。

- CalendarイベントIDと授業日時
- Classroomコース、課題、教材、Topic
- DriveファイルID、タイトル、種類、リンク、更新日時
- 文字起こしセグメントと録画時刻
- AI入力用チャンクと出典情報
- `studentIdentifiersIncluded: false`

AI回答は出典リンクを必須とし、生徒の氏名やIDを授業ナレッジの入力へ含めない前提です。

## 現在の範囲

このブランチでは、Drive上に既に存在する文字起こし文書・テキストの読み取りまで対応しています。動画・音声からの自動文字起こしエンジンはまだ接続していません。録画自体はDrive出典として統合されるため、次の拡張でローカル文字起こしプロバイダを接続できます。
