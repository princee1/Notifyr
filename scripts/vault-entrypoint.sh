#!/usr/bin/env bash
set -e

VAULT_CONFIG=/vault/config/vault.hcl
VAULT_SECRETS_DIR=/run/secrets
VAULT_SHARED_DIR=/vault/shared

export VAULT_CONTAINER_READY="false"


# Start Vault in background
vault server -config="${VAULT_CONFIG}" &
VAULT_PID=$!

for i in {1..30}; do
    if curl -sSf http://127.0.0.1:8200/v1/sys/health >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done


IS_SEALED=$(vault status -format=json | jq -r '.sealed')
if [ "$IS_SEALED" = "true" ]; then

  UNSEAL_KEY_1=$(cat "$VAULT_SECRETS_DIR/unseal_key.json" | jq -r '.uk1')
  UNSEAL_KEY_2=$(cat "$VAULT_SECRETS_DIR/unseal_key.json" | jq -r '.uk2')

  vault operator unseal "$UNSEAL_KEY_1"
  vault operator unseal "$UNSEAL_KEY_2"

  UNSEAL_KEY_1=""
  UNSEAL_KEY_2=""
fi

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
  #echo "Waiting for Vault to become active..."
  sleep 2
done

echo "++++++++++++++++++++++++++++++++++++++++++++++       +++++++++++++++++++++++++++++++++++++++++"
echo "                                    Server active!"

# Start the Cron deamon
echo "Starting the cron task"
supercronic -debug /vault/cron/crontab >> /vault/logs/supercronic.log 2>&1 &

TIMESTAMP=$(date +%s)
echo -n "supercronic=$TIMESTAMP" > "$VAULT_SHARED_DIR/seed-time.txt"

echo "++++++++++++++++++++++++++++++++++++++++++++++       +++++++++++++++++++++++++++++++++++++++++"

export VAULT_CONTAINER_READY="true"

# Bring it to the foreground
wait "$VAULT_PID"

