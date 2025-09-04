#!/usr/bin/env bash

VAULT_ADDR="http://127.0.0.1:8200"
VAULT_SECRETS_DIR=/vault/secrets
VAULT_SHARED_DIR=/vault/shared
NOTIFYR_APP_ROLE="notifyr-app-role"


echo "++++++++++++++++++++++++++++++++++  ++++++++++++++++++++++++++++++++++++++"

echo "              ---- Current date: $(date) -----"

VAULT_TOKEN=$(cat "$VAULT_SECRETS_DIR/rotate-token.txt")

# First, renew the token so it never expires
vault token renew -address="$VAULT_ADDR" -increment=24h "$VAULT_TOKEN"

# Then, request a new secret_id
NEW_SECRET=$(vault write -address="$VAULT_ADDR" -format=json -token="$VAULT_TOKEN" auth/approle/role/$NOTIFYR_APP_ROLE/secret-id | jq -r .data.secret_id)

# Store the new secret_id securely
echo "$NEW_SECRET" > "$VAULT_SHARED_DIR/secret-id.txt"

echo "++++++++++++++++++++++++++++++++++  ++++++++++++++++++++++++++++++++++++++"

echo ""

