#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Production rollback script
#
# Tag strategy (semver 2.0 + build metadata):
#   v{Major}.{Minor}.{Patch}+build.{BuildId}
#     e.g.  v1.2.3+build.45678
#
# Release tags:
#   releases/v{Major}.{Minor}.{Patch}
#     e.g.  releases/v1.2.3
#
# Deploy tracking tags:
#   deploy/{env}/{image-tag}
#     e.g.  deploy/production/v1.2.3+build.45678
#
# Usage:
#   ./rollback.sh staging        → roll back staging to latest tagged release
#   ./rollback.sh production 3   → roll back production 3 releases
#
# Rollback flow:
#   1. List deploy tags for target env, sorted by creation date
#   2. Pick the Nth-from-last as rollback target
#   3. Re-deploy that image tag
#   4. Stamp deploy/{env}/{rollback-tag} for audit trail
# ──────────────────────────────────────────────────────────────

set -euo pipefail

ENVIRONMENT="${1:?Usage: $0 <environment> [steps-back]}"
STEPS_BACK="${2:-1}"
ACR_NAME="${ACR_NAME:-mycompany.azurecr.io}"
REPO_NAME="${REPO_NAME:-myapp}"
NAMESPACE="${NAMESPACE:-$ENVIRONMENT}"

echo "🔍  Rollback initiated"
echo "    Environment : $ENVIRONMENT"
echo "    Steps back  : $STEPS_BACK"

# ── Resolve what to rollback to ──────────────────────────────
# Deploy tags are:  deploy/{env}/v{Major}.{Minor}.{Patch}+build.{BuildId}
echo ":: Fetching deploy tags for '$ENVIRONMENT'..."

ROLLBACK_TAG=$(git tag -l "deploy/${ENVIRONMENT}/v*" \
  | sort -V \
  | tail -n "${STEPS_BACK}" \
  | head -n 1)

if [ -z "$ROLLBACK_TAG" ]; then
  echo "❌  No deploy tag found for environment '$ENVIRONMENT' (${STEPS_BACK} step(s) back)."
  echo "    Existing tags:"
  git tag -l "deploy/${ENVIRONMENT}/*" | tail -5
  exit 1
fi

# Extract the image tag from the deploy tag:
#   deploy/production/v1.2.3+build.45678  →  v1.2.3+build.45678
IMAGE_TAG="${ROLLBACK_TAG#deploy/${ENVIRONMENT}/}"
echo "✅  Rollback target image tag: $IMAGE_TAG (from $ROLLBACK_TAG)"

# ── Verify the image exists in ACR ──────────────────────────
echo ":: Verifying image in ACR..."
if ! az acr repository show-tags \
  --name "$ACR_NAME" \
  --repository "$REPO_NAME" \
  --query "contains(@, '$IMAGE_TAG')" \
  --output tsv | grep -q true; then
  echo "❌  Image $ACR_NAME/$REPO_NAME:$IMAGE_TAG not found in ACR!"
  echo "    Available tags (recent 5):"
  az acr repository show-tags --name "$ACR_NAME" --repository "$REPO_NAME" --top 5 --orderby time_desc
  exit 1
fi

# ── Deploy the image ───────────────────────────────────────
echo ":: Rolling back $ENVIRONMENT to $IMAGE_TAG ..."

kubectl set image "deployment/$REPO_NAME" \
  --namespace "$NAMESPACE" \
  "*=$ACR_NAME/$REPO_NAME:$IMAGE_TAG"

kubectl rollout status "deployment/$REPO_NAME" \
  --namespace "$NAMESPACE" \
  --timeout=300s

# ── Stamp the rollback event ─────────────────────────────────
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
ROLLBACK_EVENT_TAG="deploy/${ENVIRONMENT}/rollback-${IMAGE_TAG}-${TIMESTAMP}"
git tag -a "$ROLLBACK_EVENT_TAG" \
  -m "rollback: $ENVIRONMENT → $IMAGE_TAG at $TIMESTAMP"

echo "✅  Rollback complete"
echo "    Tag created: $ROLLBACK_EVENT_TAG"

# ── Health check ────────────────────────────────────────────
if [ -n "${HEALTH_ENDPOINT:-}" ]; then
  echo ":: Running health check against $HEALTH_ENDPOINT..."
  for i in 1 2 3; do
    if curl -sf --max-time 10 "$HEALTH_ENDPOINT" > /dev/null 2>&1; then
      echo "✅  Health check passed"
      break
    fi
    echo "    Retrying (${i}/3)..."
    sleep 5
  done
fi
