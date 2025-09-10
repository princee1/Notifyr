#!/usr/bin/env bash
set -e

POSTGRES_USER=$1
POSTGRES_PASSWORD=$2

MONGO_INITDB_ROOT_USERNAME=$3
MONGO_INITDB_ROOT_PASSWORD=$4

POSTGRES_HOST=${5:-postgres}
MONGO_HOST=${6:-mongodb}


echo "POSTGRES_USER=$POSTGRES_USER"
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD"

echo "MONGO_INITDB_ROOT_USERNAME=$MONGO_INITDB_ROOT_USERNAME"
echo "MONGO_INITDB_ROOT_PASSWORD=$MONGO_INITDB_ROOT_PASSWORD"

echo "MONGO_HOST=$MONGO_HOST"
echo "POSTGRES_HOST=$POSTGRES_HOST"


VAULT_CONFIG=/vault/config/vault.hcl
VAULT_SECRETS_DIR=/vault/secrets
VAULT_SHARED_DIR=/vault/shared

NOTIFYR_APP_ROLE="notifyr-app-role"

export VAULT_ADDR="http://127.0.0.1:8200"

#################################               ##############################################

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

  export VAULT_CONTAINER_READY = "true"
}

init_vault(){
  INIT_OUT=$(vault operator init -format=json -key-shares=1 -key-threshold=1)

  UNSEAL_KEY=$(echo "$INIT_OUT" | jq -r '.unseal_keys_b64[0]')
  ROOT_TOKEN=$(echo "$INIT_OUT" | jq -r '.root_token')

  # The root_token and the unseal key will stay in the container as secrets
  echo -n "$UNSEAL_KEY" > "$VAULT_SECRETS_DIR/unseal_key.b64" 
  echo -n "$ROOT_TOKEN" > "$VAULT_SECRETS_DIR/root_token.txt"

  chown root:root "$VAULT_SECRETS_DIR/root_token.txt"
  chmod 600 "$VAULT_SECRETS_DIR/root_token.txt"   # rw------- for root only

  chown root:vaultuser "$VAULT_SECRETS_DIR/unseal_key.b64"
  chmod 640 "$VAULT_SECRETS_DIR/unseal_key.b64"

  vault operator unseal "$UNSEAL_KEY"

}

setup_engine(){
  vault secrets enable -path=notifyr-secrets -seal-wrap -version=1 kv
  vault secrets enable -path=notifyr-transit transit 
  vault secrets enable -path=notifyr-database database

  vault write -f notifyr-transit/keys/profiles-key
  vault write -f notifyr-transit/keys/messages-key
  vault write -f notifyr-transit/keys/chat-key

}

set_approle(){
  
  # Setup AppRole and policy
  vault auth enable approle || true

  vault policy write app-policy /vault/policies/app-policy.hcl

  vault write auth/approle/role/"$NOTIFYR_APP_ROLE" \
    token_policies="app-policy" \
    token_ttl="45m" \
    token_max_ttl="90m" \
    secret_id_ttl="2h" \
    secret_id_num_uses=0 \
    enable_local_secret_ids=true

  # The role_id will be store in secrets and shared with the app container 
  # The secret_id will be store in a shared volume be shared with the container 
  ROLE_ID=$(vault read -format=json auth/approle/role/"$NOTIFYR_APP_ROLE"/role-id | jq -r .data.role_id)

  SECRET_ID=$(vault write -format=json -force auth/approle/role/"$NOTIFYR_APP_ROLE"/secret-id | jq -r .data.secret_id)

  TIMESTAMP=$(date +%s)

  echo -n "$ROLE_ID" > "$VAULT_SECRETS_DIR/role_id.txt"
  echo -n "$SECRET_ID" > "$VAULT_SHARED_DIR/secret-id.txt"
  echo -n "secret=$TIMESTAMP" > "$VAULT_SHARED_DIR/seed-time.txt"

  chown root:vaultuser "$VAULT_SHARED_DIR/secret-id.txt"
  chmod 664 "$VAULT_SHARED_DIR/secret-id.txt"

  chown root:vaultuser "$VAULT_SHARED_DIR/seed-time.txt"
  chmod 664 "$VAULT_SHARED_DIR/seed-time.txt"

  chmod 644 "$VAULT_SECRETS_DIR/role_id.txt"
  chown root:root "$VAULT_SECRETS_DIR/role_id.txt"

}

set_rotate_approle() {

  vault policy write rotator /vault/policies/rotate-approle.hcl

  TOKEN=$(vault token create -policy=rotator -period=24h -format=json | jq -r .auth.client_token)

  echo -n "$TOKEN" > "$VAULT_SECRETS_DIR/rotate-token.txt"

  chown root:vaultuser "$VAULT_SECRETS_DIR/rotate-token.txt"

  chmod 640 "$VAULT_SECRETS_DIR/rotate-token.txt"

  echo "Setting up Rotate App Role"

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

create_default_token(){

  TOKENS="JWT_SECRET_KEY ON_TOP_SECRET_KEY CONTACTS_HASH_KEY CONTACT_JWT_SECRET_KEY CLIENT_PASSWORD_HASH_KEY RSA_SECRET_PASSWORD API_ENCRYPT_TOKEN"

  ARGS=""
  for token in $TOKENS
  do
    TEMP=$(pwgen -s 128 1)
    ARGS="$ARGS $token=$TEMP"
  done

  vault kv put notifyr-secrets/tokens $ARGS

  echo "Creating default key"
}

setup_database_config(){

  echo "---- Postgres SQL ----"

  local pg_role
  pg_role="postgres-ntfr-role"
 
  vault write notifyr-database/config/postgres \
    plugin_name="postgresql-database-plugin" \
    allowed_roles="$pg_role" \
    connection_url="postgresql://{{username}}:{{password}}@$POSTGRES_HOST:5432/notifyr" \
    username="$POSTGRES_USER" \
    password="$POSTGRES_PASSWORD"

  vault write notifyr-database/roles/$pg_role \
      db_name="postgres" \
      default_ttl="2h" \
      max_ttl="4h" \
      creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
                          GRANT vault_ntrfyr_app_role TO \"{{name}}\";" \
      rollback_statements="DROP ROLE IF EXISTS \"{{name}}\";" \
      revocation_statements="REVOKE vault_ntrfyr_app_role FROM \"{{name}}\"; 
                            DROP ROLE IF EXISTS \"{{name}}\";" 

  vault write -f notifyr-database/rotate-root/postgres

  echo " ---- Mongo DB  ----"

  local mongo_role
  mongo_role="mongo-ntfy-role"

  vault write notifyr-database/config/mongodb \
    plugin_name="mongodb-database-plugin" \
    allowed_roles="$mongo_role"\
    connection_url="mongodb://{{username}}:{{password}}@$MONGO_HOST:27017/admin" \
    username="$MONGO_INITDB_ROOT_USERNAME" \
    password="$MONGO_INITDB_ROOT_PASSWORD"
  
  vault write notifyr-database/roles/$mongo_role \
    db_name="mongodb" \
    creation_statements='{ "db": "notifyr", "roles": [
    { "role": "readWrite", "db": "notifyr", "collection":"agent" },
    { "role": "readWrite", "db": "notifyr", "collection":"profile" },
    { "role": "readWrite", "db": "notifyr", "collection":"workflow" },
    { "role": "readWrite", "db": "notifyr", "collection":"chat" }]}' \
    default_ttl="2h" \
    max_ttl="4h"

    vault write -f notifyr-database/rotate-root/mongodb
}

#################################               ####################################y##########
# Start Vault as root in background
vault server -config="${VAULT_CONFIG}" &
VAULT_PID=$!

echo "***************************                     *********************"
wait_for_server 
echo "***************************                     *********************"

echo "***************************                     *********************"
init_vault
echo "***************************                     *********************"

echo "***************************                     *********************"
wait_active_server
echo "***************************                     *********************"

ROOT_TOKEN=$(cat "$VAULT_SECRETS_DIR/root_token.txt")

export VAULT_TOKEN="$ROOT_TOKEN"

echo "***************************                     *********************"
setup_engine
echo "***************************                     *********************"

echo "***************************                     *********************"
set_approle
echo "***************************                     *********************"

echo "***************************                     *********************"
set_rotate_approle
echo "***************************                     *********************"

echo "***************************                     *********************"
create_default_token
echo "***************************                     *********************"

echo "***************************                     *********************"
setup_database_config
echo "***************************                     *********************"

unset VAULT_TOKEN

chown -R vaultuser:vaultuser /vault/data
chmod 700 /vault/data

kill "$VAULT_PID"
wait "$VAULT_PID" || true

echo "Vault Initialization finished"

#################################               ##############################################
