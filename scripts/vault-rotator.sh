#!/usr/bin/env bash

set -euo pipefail

VAULT_ADDR="http://127.0.0.1:8200"
VAULT_SECRETS_DIR=/vault/secrets
VAULT_SHARED_DIR=/vault/shared
NOTIFYR_APP_ROLE="notifyr-app-role"


echo "++++++++++++++++++++++++++++++++++  ++++++++++++++++++++++++++++++++++++++"

echo "              ---- Current date: $(date) -----"

VAULT_TOKEN=$(cat "$VAULT_SECRETS_DIR/rotate-token.txt")

RESP=$(curl -s \
    --header "X-Vault-Token: $VAULT_TOKEN" \
    --request POST \
    "$VAULT_ADDR/v1/auth/approle/role/$NOTIFYR_APP_ROLE/secret-id")
    
NEW_SECRET=$(echo "$RESP" | jq -r .data.secret_id)

echo "Successfully got the secret_id"

# Store the new secret_id securely
echo -n "$NEW_SECRET" > "$VAULT_SHARED_DIR/secret-id.txt"

echo "Secret id stored successfully"

echo "++++++++++++++++++++++++++++++++++  ++++++++++++++++++++++++++++++++++++++"

echo ""

