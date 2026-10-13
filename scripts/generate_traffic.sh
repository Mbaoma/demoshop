#!/usr/bin/env bash
# PART 3 -- Observe it.
# Generates a boring, healthy baseline so the dashboard has a "before" to
# compare the incident against. Run this for a few minutes before Part 3
# starts, and leave a second terminal running it in a loop through Part 4.
#
# Usage:
#   ./scripts/generate_traffic.sh                 # against a deployed service
#   SERVICE_URL=http://localhost:8080 ./scripts/generate_traffic.sh   # locally
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -z "${SERVICE_URL:-}" ]]; then
  source scripts/env.sh
  SERVICE_URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')
fi

ROUNDS="${1:-10}"
healthy=0
checkout=0
errors=0

echo "==> Sending traffic to $SERVICE_URL for $ROUNDS rounds (Ctrl+C to stop early)"

for ((i = 1; i <= ROUNDS; i++)); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$SERVICE_URL/")
  echo -n "$code "
  healthy=$((healthy + 1))

  code=$(curl -s -o /dev/null -w '%{http_code}' "$SERVICE_URL/checkout?account=demo-$i&amount=10.00")
  checkout=$((checkout + 1))
  if [[ "$code" != "200" ]]; then
    errors=$((errors + 1))
  fi

  sleep 1
done

echo
echo "==> healthy=$healthy checkout=$checkout errors=$errors"
