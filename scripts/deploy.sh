#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh

echo "==> Deploying $SERVICE from source to $REGION (project: $PROJECT)"

gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT" \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "APP_VERSION=v1"

echo
echo "==> Revision history:"
gcloud run revisions list --service "$SERVICE" --project "$PROJECT" --region "$REGION"

SERVICE_URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')
echo
echo "==> Service URL: $SERVICE_URL"
echo "==> Smoke test:"
curl -s "$SERVICE_URL/" ; echo
