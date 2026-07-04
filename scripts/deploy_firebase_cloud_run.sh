#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-${1:-}}"
REGION="${REGION:-asia-northeast1}"
SERVICE_ID="${SERVICE_ID:-sansan-competition}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Usage: PROJECT_ID=<gcp-project-id> $0" >&2
  echo "Example: PROJECT_ID=classroom-ai-kmc $0" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Using project: ${PROJECT_ID}"
echo "==> Using region: ${REGION}"
echo "==> Using Cloud Run service: ${SERVICE_ID}"

cd "${REPO_ROOT}"

gcloud config set project "${PROJECT_ID}"

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com

gcloud run deploy "${SERVICE_ID}" \
  --source . \
  --region "${REGION}" \
  --allow-unauthenticated

firebase use "${PROJECT_ID}"
firebase deploy --only hosting

echo
echo "Deploy complete."
echo "Firebase Hosting should now serve public/ and rewrite /api/** plus /oauth/google/callback to Cloud Run."
echo "Next: register https://${PROJECT_ID}.web.app/oauth/google/callback in the Google OAuth web client."
