#!/usr/bin/env bash

# Start cron in the background (as root)
crond -f & 
CRON_PID=$!

VAULT_CONFIG=/vault/config/vault.hcl
VAULT_SECRETS_DIR=/vault/secrets

wait_for_server() {
  # Wait for listener
  for i in {1..30}; do
    if curl -sSf http://127.0.0.1:8200/v1/sys/health >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
}

unseal_vault(){

  IS_SEALED=$(vault status -format=json | jq -r '.sealed')
  if [ "$IS_SEALED" = "true" ]; then

    UNSEAL_KEY=$(cat "$VAULT_SECRETS_DIR/unseal_key.b64")
    vault operator unseal "$UNSEAL_KEY"
  fi
}

# Start Vault in background
vault server -config="${VAULT_CONFIG}" &
VAULT_PID=$!

wait_for_server 

unseal_vault

export VAULT_CONTAINER_READY="true"

# Bring it to the foreground
wait "$VAULT_PID"
