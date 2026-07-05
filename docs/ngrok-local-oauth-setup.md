# ngrok を使った無料の GUI OAuth セットアップ

この構成は、Cloud Run や Firebase を使わずに、ローカルで動かしている `main.py` を `https://...` の公開 URL に載せるためのものです。

目的:

- Google OAuth の `Web application` client を使う
- 別端末ブラウザ自身で Google 認可まで完了できるようにする
- 無料の範囲で、URL を毎回変えずに使う

## 前提

- `uv sync --extra google` 済み
- `brew install ngrok` 済み
- ngrok の無料アカウントがある

## 必要なもの

ngrok 側で最低限必要なのは次です。

1. `authtoken`

取得場所:

- `authtoken`: ngrok dashboard の Getting Started
- `dev domain`: 必要なら ngrok dashboard の Gateway > Domains で確認できます

## 起動

```bash
cd /Users/kimura/Desktop/SP活動/2年/後期/sansan-competition
export NGROK_AUTHTOKEN='YOUR_NGROK_AUTHTOKEN'
./scripts/start_gui_with_ngrok.sh
```

固定の dev domain を明示したい場合だけ、追加で次を設定してください。

```bash
export NGROK_DOMAIN='YOUR_ASSIGNED_NAME.ngrok-free.dev'
```

このスクリプトは次を行います。

- ローカル GUI を `127.0.0.1:8000` で起動
- ngrok の公開 URL を起動して自動検出
- 実際に Google Cloud へ登録すべき redirect URI を表示

## Google Cloud 側で必要な設定

OAuth client は `Web application` を使ってください。

Authorized redirect URI に次を追加します。

```text
https://<ngrok が表示した公開URL>/oauth/google/callback
```

重要:

- URI を保存したあとで、OAuth client JSON を再ダウンロードしてください
- 古い JSON をそのまま使うと `redirect_uris` が更新されません

## アプリ側でやること

1. スクリプトが表示した ngrok URL をブラウザで開く
2. ログイン画面の `OAuth client JSON を選択` から、再ダウンロードした Web client JSON を登録する
3. `Google Classroomに接続` を押す

## よくある詰まりどころ

- `ngrok is installed but not authenticated`
  - `NGROK_AUTHTOKEN` を設定していないか、`ngrok config add-authtoken ...` をしていません

- `OAuth client の Authorized redirect URI に ... を追加してください`
  - Google Cloud 側で redirect URI をまだ保存していないか、保存後の JSON を再ダウンロードしていません

- 403 `access_denied`
  - OAuth consent screen が `Testing` のままなら、使う Google アカウントを `Test users` に追加してください
