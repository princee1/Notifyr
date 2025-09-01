#!/usr/bin/env bash

#set -euo pipefail

VAULT_CONFIG=/vault/config/vault.hcl
VAULT_SECRETS_DIR=/vault/secrets
export VAULT_ADDR="http://127.0.0.1:8200"

# Start Vault as root in background
vault server -config="${VAULT_CONFIG}" &
VAULT_PID=$!

# Wait for listener
for i in {1..30}; do
  if curl -sSf http://127.0.0.1:8200/v1/sys/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Check initialization
IS_INITIALIZED=$(vault status -format=json | jq -r '.initialized')

if [ "$IS_INITIALIZED" = "false" ]; then

  INIT_OUT=$(vault operator init -format=json -key-shares=1 -key-threshold=1)

  UNSEAL_KEY=$(echo "$INIT_OUT" | jq -r '.unseal_keys_b64[0]')
  ROOT_TOKEN=$(echo "$INIT_OUT" | jq -r '.root_token')

  echo -n "$UNSEAL_KEY" > "$VAULT_SECRETS_DIR/unseal_key.b64" 
  echo -n "$ROOT_TOKEN" > "$VAULT_SECRETS_DIR/root_token.txt"
  chmod 600 "$VAULT_SECRETS_DIR"/* || true

  # The root_token and the unseal key will stay in the container as secrets

  vault operator unseal "$UNSEAL_KEY"
  
else

  ROOT_TOKEN=$(cat "$VAULT_SECRETS_DIR/root_token.txt")
  if vault status 2>/dev/null | grep -q '"sealed": true'; then
    vault operator unseal "$(cat "$VAULT_SECRETS_DIR/unseal_key.b64")"
  fi
fi

export VAULT_TOKEN="$ROOT_TOKEN"


# Wait for this node to become active
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



# Setup AppRole and policy
vault auth enable approle || true
vault secrets enable -path=secret -version=2 kv || true

vault policy write app-policy /vault/policies/app-policy.hcl

vault write auth/approle/role/$NOTIFYR_APP_ROLE \
  token_policies="app-policy" \
  token_ttl="30m" \
  token_max_ttl="24h" \
  secret_id_ttl="30m" \
  secret_id_num_uses=0 \
  enable_local_secret_ids=true

ROLE_ID=$(vault read -format=json auth/approle/role/$NOTIFYR_APP_ROLE/role-id | jq -r .data.role_id)
echo -n "$ROLE_ID" > "$VAULT_SECRETS_DIR/role_id.txt"
chmod 600 "$VAULT_SECRETS_DIR/role_id.txt"

# The role_id will be store in secrets and shared with the app container 
# The secret_id will be store in a shared volume be shared with the container 

#/usr/local/bin/setup-approle.sh "$VAULT_SECRETS_DIR"

# Start cron job as root for secret_id rotation
crond

unset VAULT_TOKEN

kill "$VAULT_PID"
wait "$VAULT_PID" || true

chown -R vaultuser:vaultuser /vault/data
chmod 700 /vault/data

# Drop privileges to vaultuser for the main Vault process
echo "Dropping Vault process to vaultuser..."

export VAULT_CONTAINER_READY = "true"

exec su-exec vaultuser vault server -config="${VAULT_CONFIG}"
