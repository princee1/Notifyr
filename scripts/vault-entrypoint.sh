#!/usr/bin/env bash
set -e

VAULT_CONFIG=/vault/config/vault.hcl
VAULT_SECRETS_DIR=/vault/secrets
VAULT_SHARED_DIR=/vault/shared

PG_HOST=${POSTGRES_HOST:-postgres}
M_HOST=${MONGO_HOST:-mongodb}

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
    #echo "Waiting for Vault to become active..."
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

create_database_config(){


  ONE_SHOT_DB_TOKEN=$(cat "$VAULT_SECRETS_DIR/one_shot_db_token.txt")

  export VAULT_ADDR="http://127.0.0.1:8200"

  vault login -no-print "$ONE_SHOT_DB_TOKEN"

  vault write notifyr-database/config/postgres \
    plugin_name="postgresql-database-plugin" \
    allowed_roles="postgres-ntfr-role" \
    connection_url="postgresql://{{username}}:{{password}}@$PG_HOST:5432/notifyr" \
    max_open_connections=20 \
    max_idle_connections=10 \
    username="$POSTGRES_USER" \
    password="$POSTGRES_PASSWORD"

  #vault write -f notifyr-database/rotate-root/postgres
  
  vault write notifyr-database/config/mongodb \
    plugin_name="mongodb-database-plugin" \
    allowed_roles="mongo-ntfr-role" \
    connection_url="mongodb://{{username}}:{{password}}@$M_HOST:27017/admin" \
    username="$MONGO_INITDB_ROOT_USERNAME" \
    password="$MONGO_INITDB_ROOT_PASSWORD"

  # vault write -f notifyr-database/rotate-root/mongodb

  vault token revoke -self

  export VAULT_ADDR="http://0.0.0.0:8200"
}

# Start Vault in background
vault server -config="${VAULT_CONFIG}" &
VAULT_PID=$!

wait_for_server 

unseal_vault

wait_active_server

if grep -q "secret" "$VAULT_SHARED_DIR/seed-time.txt"; then
  create_database_config
else
  echo "database config already setup"
fi


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

