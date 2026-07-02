#!/usr/bin/env bash
# Full enterprise reference demo: production overlay + OIDC + platform verification.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

printf '[enterprise-demo] production overlay (Redis + Prometheus)\n'
bash "${SCRIPT_DIR}/verify-production-demo.sh"

printf '\n[enterprise-demo] OIDC / Keycloak JWT flow\n'
bash "${SCRIPT_DIR}/verify-oidc-demo.sh"

printf '\n[enterprise-demo] Enterprise reference verification passed.\n'
