#!/usr/bin/env bash
set -euo pipefail

VAULT_ADDR="http://127.0.0.1:8200"
VAULT_SECRETS_DIR=/vault/secrets

echo "++++++++++++++++++++++++++++++++++  ++++++++++++++++++++++++++++++++++++++"

echo "              ---- Current date: $(date) -----"

VAULT_TOKEN=$(cat "$VAULT_SECRETS_DIR/rotate-token.txt")
rotate_all_transit_keys() {
    
    local keys
    keys=$(curl -s --header "X-Vault-Token: $VAULT_TOKEN" \
        "$VAULT_ADDR/v1/notifyr-transit/keys?list=true" | jq -r '.data.keys[]')

    for key in $keys; do
        echo "Rotating key: $key"
        curl -s --header "X-Vault-Token: $VAULT_TOKEN" \
            --request POST \
            "$VAULT_ADDR/v1/$mount_path/keys/$key/rotate"
        
    done
}

rotate_all_transit_keys

echo "++++++++++++++++++++++++++++++++++  ++++++++++++++++++++++++++++++++++++++"
