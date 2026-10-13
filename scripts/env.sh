#!/usr/bin/env bash
export PROJECT="${PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
export REGION="${REGION:-us-central1}"
export SERVICE="${SERVICE:-demoshop}"
export SECRET_NAME="${SECRET_NAME:-payment-api-key}"
export RUNTIME_SA_NAME="${RUNTIME_SA_NAME:-demoshop-runtime}"
export RUNTIME_SA="${RUNTIME_SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

if [[ -z "$PROJECT" ]]; then
  echo "No project set. Run: gcloud config set project YOUR_PROJECT_ID" >&2
  return 1 2>/dev/null || exit 1
fi
