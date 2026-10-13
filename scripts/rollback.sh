#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh

TARGET_REVISION="${1:-}"

if [[ -z "$TARGET_REVISION" ]]; then
  TARGET_REVISION=$(gcloud run revisions list \
    --service "$SERVICE" --project "$PROJECT" --region "$REGION" \
    --sort-by='~metadata.creationTimestamp' \
    --format='value(metadata.name)' | sed -n '2p')
fi

if [[ -z "$TARGET_REVISION" ]]; then
  echo "Could not determine a previous revision. Pass one explicitly:" >&2
  echo "  ./scripts/rollback.sh demoshop-00002-xyz" >&2
  exit 1
fi

echo "==> Routing 100% of traffic to $TARGET_REVISION"
gcloud run services update-traffic "$SERVICE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --to-revisions "${TARGET_REVISION}=100"

SERVICE_URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')
echo
echo "==> Confirming:"
curl -s "$SERVICE_URL/config" ; echo
echo "The bad revision still exists in the list -- it's evidence, not deleted:"
gcloud run revisions list --service "$SERVICE" --project "$PROJECT" --region "$REGION"
