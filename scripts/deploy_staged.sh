#!/usr/bin/env bash
# Zero-downtime staged deployment helper for Google Cloud Run.
# Deploys new revisions with 0% live traffic (--no-traffic --tag staging) so the
# current production service and Cloud Scheduler jobs remain completely unaffected
# until explicitly promoted.

set -euo pipefail

PROJECT_ID="stock-trading-agent-249477"
REGION="us-central1"
SERVICE_NAME="stock-trading-agent"
TAG_NAME="staging"

usage() {
  cat <<EOF
Usage: ./scripts/deploy_staged.sh <command>

Commands:
  preflight      Run local secret scanner, full pytest suite, and frontend production build check
  sync-secrets   Ensure 'gemini-api-key' exists in GCP Secret Manager (reads from local .env)
  prune-secrets  Destroy all obsolete (non-latest) secret versions across GCP Secret Manager to eliminate version storage fees
  stage          Build & deploy a new revision with --no-traffic and tag '${TAG_NAME}'
                 (0% impact on current live deployment; generates a dedicated preview URL)
  status         Show active Cloud Run revisions, traffic split, and tagged preview URLs
  promote        Route 100% of live traffic to the latest staged revision
  rollback       Route 100% of live traffic back to a specific revision
                 (e.g., ./scripts/deploy_staged.sh rollback stock-trading-agent-00038-q5l)
EOF
}

cmd="${1:-help}"

case "$cmd" in
  preflight)
    echo "=== [1/3] Running Pre-Commit Secret Scanner ==="
    python3 scripts/scan_secrets.py --all
    echo "=== [2/3] Running Hermetic Pytest Suite ==="
    pytest -v
    echo "=== [3/3] Verifying Frontend Production Bundle ==="
    (cd frontend && npm run build)
    echo "✅ Pre-flight checks passed!"
    ;;

  prune-secrets)
    python3 -c "
from google.cloud import secretmanager
client = secretmanager.SecretManagerServiceClient()
parent = 'projects/${PROJECT_ID}'
destroyed = 0
enabled_remaining = 0
for s in client.list_secrets(request={'parent': parent}):
    sec_name = s.name.split('/')[-1]
    versions = [v for v in client.list_secret_versions(request={'parent': s.name}) if v.state != secretmanager.SecretVersion.State.DESTROYED]
    versions.sort(key=lambda v: int(v.name.split('/')[-1]), reverse=True)
    for ov in versions[1:]:
        client.destroy_secret_version(request={'name': ov.name})
        destroyed += 1
    if versions:
        enabled_remaining += 1
    print(f'{sec_name:32s} | Active versions kept: {min(1, len(versions))} | Pruned: {max(0, len(versions)-1)}')
print(f'Done! Pruned {destroyed} obsolete versions. Total active versions remaining: {enabled_remaining}')
"
    ;;

  sync-secrets)
    if [ ! -f .env ]; then
      echo "❌ .env file not found."
      exit 1
    fi
    GEMINI_KEY=$(grep -E '^GEMINI_API_KEY=' .env | cut -d '=' -f2- | tr -d '"' | tr -d "'")
    if [ -z "$GEMINI_KEY" ]; then
      echo "❌ GEMINI_API_KEY not found in .env"
      exit 1
    fi
    if gcloud secrets describe gemini-api-key --project="$PROJECT_ID" >/dev/null 2>&1; then
      echo "Updating existing secret 'gemini-api-key' in project $PROJECT_ID..."
      printf "%s" "$GEMINI_KEY" | gcloud secrets versions add gemini-api-key --data-file=- --project="$PROJECT_ID"
    else
      echo "Creating secret 'gemini-api-key' in project $PROJECT_ID..."
      printf "%s" "$GEMINI_KEY" | gcloud secrets create gemini-api-key --replication-policy="automatic" --data-file=- --project="$PROJECT_ID"
      gcloud secrets add-iam-policy-binding gemini-api-key \
        --member="serviceAccount:1015953760510-compute@developer.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID" >/dev/null
    fi
    echo "✅ Secret 'gemini-api-key' synced to GCP Secret Manager."
    ;;

  stage)
    echo "=== Deploying Staged Revision (--no-traffic --tag ${TAG_NAME}) ==="
    echo "Current production revision will continue receiving 100% of traffic."
    gcloud run deploy "$SERVICE_NAME" \
      --source . \
      --project "$PROJECT_ID" \
      --region "$REGION" \
      --no-traffic \
      --tag "$TAG_NAME" \
      --update-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
      --update-env-vars="LLM_MODEL=gemini/gemini-4-argon,GRPC_ENABLE_FORK_SUPPORT=0,GRPC_POLL_STRATEGY=poll"
    echo ""
    echo "✅ Staged deployment complete! Live production traffic was NOT changed."
    gcloud run services describe "$SERVICE_NAME" --project "$PROJECT_ID" --region "$REGION" --format="table(status.traffic.revisionName,status.traffic.percent,status.traffic.tag,status.traffic.url)"
    ;;

  status)
    gcloud run services describe "$SERVICE_NAME" \
      --project "$PROJECT_ID" \
      --region "$REGION" \
      --format="table(status.traffic.revisionName,status.traffic.percent,status.traffic.tag,status.traffic.url)"
    ;;

  promote)
    echo "=== Promoting Latest Staged Revision to 100% Production Traffic ==="
    gcloud run services update-traffic "$SERVICE_NAME" \
      --project "$PROJECT_ID" \
      --region "$REGION" \
      --to-latest
    echo "✅ Traffic promoted to latest revision!"
    ;;

  rollback)
    TARGET_REV="${2:-}"
    if [ -z "$TARGET_REV" ]; then
      echo "❌ Please specify the target revision name to roll back to."
      echo "Available revisions:"
      gcloud run revisions list --service="$SERVICE_NAME" --project="$PROJECT_ID" --region="$REGION" --limit=5
      exit 1
    fi
    echo "=== Rolling back 100% traffic to $TARGET_REV ==="
    gcloud run services update-traffic "$SERVICE_NAME" \
      --project "$PROJECT_ID" \
      --region "$REGION" \
      --to-revisions="${TARGET_REV}=100"
    echo "✅ Rolled back to $TARGET_REV!"
    ;;

  *)
    usage
    ;;
esac

