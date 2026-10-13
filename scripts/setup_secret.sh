#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh

echo "==> Creating secret: $SECRET_NAME"
if gcloud secrets describe "$SECRET_NAME" --project "$PROJECT" >/dev/null 2>&1; then
  echo "    already exists, skipping create"
else
  printf "pk_live_demoshop" | gcloud secrets create "$SECRET_NAME" \
    --project "$PROJECT" \
    --replication-policy=automatic \
    --data-file=-
fi

echo "==> Creating runtime service account: $RUNTIME_SA_NAME"
if gcloud iam service-accounts describe "$RUNTIME_SA" --project "$PROJECT" >/dev/null 2>&1; then
  echo "    already exists, skipping create"
else
  gcloud iam service-accounts create "$RUNTIME_SA_NAME" \
    --project "$PROJECT" \
    --display-name="DemoShop Cloud Run runtime"
fi

echo "==> Binding secretAccessor on the secret (not the project) to $RUNTIME_SA"
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --project "$PROJECT" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor"

echo "==> Attaching the identity and the secret reference to the service"
gcloud run services update "$SERVICE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --service-account="$RUNTIME_SA" \
  --update-env-vars "PAYMENT_API_KEY_SECRET=projects/${PROJECT}/secrets/${SECRET_NAME}"

echo
echo "==> Prove it, without printing the secret:"
SERVICE_URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')
curl -s "$SERVICE_URL/config" ; echo
