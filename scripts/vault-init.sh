#!/usr/bin/env bash
set -euo pipefail

VAULT_CONFIG=/vault/config/vault.hcl
VAULT_SECRETS_DIR=/vault/secrets
VAULT_SHARED_DIR=/vault/shared
export VAULT_ADDR="http://127.0.0.1:8200"

# Start Vault in background (root)
vault server -config="${VAULT_CONFIG}" &
VAULT_PID=$!

# wait for Vault listener
for i in {1..30}; do
  if curl -sSf http://127.0.0.1:8200/v1/sys/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Initialize Vault if not already
if vault status 2>/dev/null | grep -q 'Initialized.*false'; then
  INIT_OUT=$(vault operator init -format=json -key-shares=1 -key-threshold=1)
  
  # Export unseal key & root token to secure files only
  UNSEAL_KEY=$(echo "$INIT_OUT" | jq -r '.unseal_keys_b64[0]')
  ROOT_TOKEN=$(echo "$INIT_OUT" | jq -r '.root_token')

  echo -n "$UNSEAL_KEY" > "$VAULT_SECRETS_DIR/unseal_key.b64"
  echo -n "$ROOT_TOKEN" > "$VAULT_SECRETS_DIR/root_token.txt"
  chmod 600 "$VAULT_SECRETS_DIR"/*

  vault operator unseal "$UNSEAL_KEY"
else
  # Vault already initialized
  ROOT_TOKEN=$(cat "$VAULT_SECRETS_DIR/root_token.txt")
  if vault status 2>/dev/null | grep -q 'Sealed.*true'; then
    vault operator unseal "$(cat "$VAULT_SECRETS_DIR/unseal_key.b64")"
  fi
fi

export VAULT_TOKEN="$ROOT_TOKEN"


# Setup AppRole and policy
vault auth enable approle || true
vault secrets enable -path=secret -version=2 kv || true

vault policy write app-policy /vault/policies/app-policy.hcl

vault write auth/approle/role/my-app-role \
  token_policies="app-policy" \
  token_ttl="30m" \
  token_max_ttl="24h" \
  secret_id_ttl="30m" \
  secret_id_num_uses=1 \
  enable_local_secret_ids=true

ROLE_ID=$(vault read -format=json auth/approle/role/my-app-role/role-id | jq -r .data.role_id)
echo -n "$ROLE_ID" > "$VAULT_SECRETS_DIR/role_id.txt"
chmod 600 "$VAULT_SECRETS_DIR/role_id.txt"

#/usr/local/bin/setup-approle.sh "$VAULT_SECRETS_DIR"

# Start cron job as root for secret_id rotation
crond

unset VAULT_TOKEN

# Drop privileges to vaultuser for the main Vault process
echo "Dropping Vault process to vaultuser..."
exec su-exec vaultuser vault server -config="${VAULT_CONFIG}"
