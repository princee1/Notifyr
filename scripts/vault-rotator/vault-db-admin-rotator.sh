#!/usr/bin/env bash
set -euo pipefail


VAULT_SECRETS_DIR=/vault/secrets

echo "++++++++++++++++++++++++++++++++++  ++++++++++++++++++++++++++++++++++++++"
echo "              ---- Current date: $(date) -----"
X_VAULT_TOKEN=$(cat "$VAULT_SECRETS_DIR/rotate-token.txt")

$RESP=(curl --header "X-Vault-Token: $X_VAULT_TOKEN" \
    --request POST \
    "http://localhost:8200/v1/notifyr-database/rotate-root/mongodb")

$RESP=(curl --header "X-Vault-Token: $X_VAULT_TOKEN" \
    --request POST \
    "http://localhost:8200/v1/notifyr-database/rotate-root/postgres")

$RESP=(curl --header "X-Vault-Token: $X_VAULT_TOKEN" \
    --request POST \
    "http://localhost:8200/v1/notifyr-database/rotate-root/redis")

echo "++++++++++++++++++++++++++++++++++  ++++++++++++++++++++++++++++++++++++++"
