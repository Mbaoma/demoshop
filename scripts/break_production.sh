#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh

echo "==> Revisions before the incident:"
gcloud run revisions list --service "$SERVICE" --project "$PROJECT" --region "$REGION"

echo
echo "==> Injecting latency + failure via --update-env-vars (merges; does not replace)"
gcloud run services update "$SERVICE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --update-env-vars "APP_VERSION=v2,CHECKOUT_EXTRA_LATENCY_MS=4000,CHECKOUT_FAILURE_RATE=0.35"

echo
echo "==> Production is now broken. Revisions after:"
gcloud run revisions list --service "$SERVICE" --project "$PROJECT" --region "$REGION"
