# Firebase Hosting + Cloud Run セットアップ

この構成は、次の要件を満たすためのものです。

- Google OAuth の redirect URI を `HTTPS + ドメイン名` にする
- GUI の静的ファイルは Firebase Hosting から配信する
- `/api/live/*` と `/oauth/google/callback` は Python バックエンドで処理する

## 前提

- Firebase project がある
- Firebase Hosting site がある
- `gcloud auth list` に利用アカウントが出る
- `firebase login` 済み

## 現在の推奨構成

- Hosting site: `https://<site-id>.web.app`
- Python backend: Cloud Run service `sansan-competition`
- Hosting rewrites:
  - `/api/**` -> Cloud Run
  - `/oauth/google/callback` -> Cloud Run

`firebase.json` はその前提で追加済みです。

## まず必要なこと

少なくとも次を有効にしてください。

1. Billing を有効化する
2. Cloud Run Admin API を有効化する
3. Cloud Build API を有効化する
4. Artifact Registry API を有効化する

CLI からまとめて有効化する場合:

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

## デプロイ

この repo には Cloud Run 用の `Dockerfile` と、Firebase Hosting 用の `firebase.json` を追加しています。

デプロイは次で実行できます。

```bash
cd /Users/kimura/Desktop/SP活動/2年/後期/sansan-competition
PROJECT_ID=YOUR_PROJECT_ID ./scripts/deploy_firebase_cloud_run.sh
```

既定値:

- region: `asia-northeast1`
- serviceId: `sansan-competition`

必要なら環境変数で上書きしてください。

```bash
PROJECT_ID=YOUR_PROJECT_ID REGION=asia-northeast1 SERVICE_ID=sansan-competition ./scripts/deploy_firebase_cloud_run.sh
```

## OAuth client に登録する redirect URI

Web application OAuth client の Authorized redirect URI に次を追加してください。

```text
https://YOUR_SITE_ID.web.app/oauth/google/callback
```

もし custom domain を Firebase Hosting に接続しているなら、そちらでも構いません。

```text
https://your-domain.example.com/oauth/google/callback
```

## 注意

- `http://192.168.x.x:8000/...` のような生 IP + HTTP は Google OAuth の Web application client では使えません
- `Desktop app` client は同一端末ローカル確認用です
- 別端末ブラウザから使う場合は `Web application` client を使ってください
- OAuth client JSON は repo にコミットしないでください
