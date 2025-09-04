#!/usr/bin/env bash

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

wait_active_server(){
  for i in {1..30}; do
    HA_STATUS=$(vault status -format=json | jq -r '.ha_enabled')
    IS_ACTIVE=$(vault status -format=json | jq -r '.active')
    if [ "$HA_STATUS" = "true" ] && [ "$IS_ACTIVE" = "true" ]; then
      echo "Vault node is active leader"
      break
    fi
    if [ "$HA_STATUS" = "false" ]; then
      echo "Vault is not running in HA mode (single node) — safe to continue"
      break
    fi
    echo "Waiting for Vault to become active..."
    sleep 2
  done
}


unseal_vault(){

  IS_SEALED=$(vault status -format=json | jq -r '.sealed')
  if [ "$IS_SEALED" = "true" ]; then

    UNSEAL_KEY=$(cat "$VAULT_SECRETS_DIR/unseal_key.b64")
    vault operator unseal "$UNSEAL_KEY"
  fi
}


echo "Starting cron in foreground..."
# Start the Cron deamon
crond -f -l 8 -d 8 -c /var/spool/cron/crontabs

