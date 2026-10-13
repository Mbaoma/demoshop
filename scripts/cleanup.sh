#!/usr/bin/env bash
# Tear down everything this repo creates
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh

read -r -p "This deletes the $SERVICE Cloud Run service, the $SECRET_NAME secret, and the $RUNTIME_SA_NAME service account in project $PROJECT. Continue? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Aborted."
  exit 0
fi

gcloud run services delete "$SERVICE" --project "$PROJECT" --region "$REGION" --quiet || true
gcloud secrets delete "$SECRET_NAME" --project "$PROJECT" --quiet || true
gcloud iam service-accounts delete "$RUNTIME_SA" --project "$PROJECT" --quiet || true

echo "==> Done."
