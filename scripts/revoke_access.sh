#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh

echo "==> Removing secretAccessor binding on $SECRET_NAME for $RUNTIME_SA"
gcloud secrets remove-iam-policy-binding "$SECRET_NAME" \
  --project "$PROJECT" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor"

SERVICE_URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')
echo
echo "==> What does the service do on the very next request?"
curl -s "$SERVICE_URL/config" ; echo
curl -s -w "\nHTTP:%{http_code}\n" "$SERVICE_URL/checkout"
