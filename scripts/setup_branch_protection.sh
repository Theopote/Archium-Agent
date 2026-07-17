#!/usr/bin/env bash
# Configure branch protection on master (requires gh CLI + repo admin).
set -euo pipefail

REPO="${ARCHIUM_GITHUB_REPO:-Theopote/Archium-Agent}"
BRANCH="${ARCHIUM_PROTECTED_BRANCH:-master}"
CHECKS="${ARCHIUM_CI_CHECKS:-test (3.11),test (3.12)}"

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: gh CLI not found. Install from https://cli.github.com/ or use docs/branch-protection.md (Web UI)." >&2
  exit 1
fi

IFS=',' read -r -a CONTEXTS <<< "$CHECKS"
export CHECKS

payload="$(python - <<'PY'
import json
import os

contexts = [c.strip() for c in os.environ["CHECKS"].split(",") if c.strip()]
print(
    json.dumps(
        {
            "required_status_checks": {
                "strict": True,
                "contexts": contexts,
            },
            "enforce_admins": True,
            "required_pull_request_reviews": None,
            "restrictions": None,
            "required_linear_history": False,
            "allow_force_pushes": False,
            "allow_deletions": False,
            "block_creations": False,
            "required_conversation_resolution": False,
        }
    )
)
PY
)"

echo "Applying branch protection to ${REPO}:${BRANCH}"
echo "Required checks: ${CHECKS}"

gh api "repos/${REPO}/branches/${BRANCH}/protection" -X PUT --input - <<< "$payload"

echo "Done. Verify at: https://github.com/${REPO}/settings/branches"
