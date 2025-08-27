#!/usr/bin/env bash
set -euo pipefail

VAULT_ADDR="http://127.0.0.1:8200"
VAULT_SECRETS_DIR=/vault/secrets
VAULT_SHARED_DIR=/vault/shared

ROOT_TOKEN=$(cat "$VAULT_SECRETS_DIR/root_token.txt")

RESP=$(
  curl -sS -X POST \
    -H "X-Vault-Token: ${ROOT_TOKEN}" \
    "${VAULT_ADDR}/v1/auth/approle/role/my-app-role/secret-id"
)

SECRET_ID=$(echo "$RESP" | jq -r '.data.secret_id')

umask 177
TMP="$VAULT_SHARED_DIR/secret_id.tmp"
OUT="$VAULT_SHARED_DIR/secret_id"
echo -n "$SECRET_ID" > "$TMP"
mv -f "$TMP" "$OUT"
chmod 600 "$OUT"
