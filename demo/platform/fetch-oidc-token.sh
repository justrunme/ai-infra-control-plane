#!/usr/bin/env bash
# Fetch an OIDC access token from the platform demo Keycloak realm.
set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://127.0.0.1:8180}"
REALM="${OIDC_REALM:-ai-platform}"
CLIENT_ID="${OIDC_CLIENT_ID:-ai-gateway}"
USERNAME="${OIDC_USERNAME:-alice}"
PASSWORD="${OIDC_PASSWORD:-demo}"

curl -fsS -X POST "${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/token" \
  -H 'content-type: application/x-www-form-urlencoded' \
  -d "client_id=${CLIENT_ID}" \
  -d 'grant_type=password' \
  -d "username=${USERNAME}" \
  -d "password=${PASSWORD}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
