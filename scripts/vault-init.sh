#!/usr/bin/env bash
set -e

VAULT_CONFIG=/vault/config/vault.hcl
VAULT_SECRETS_DIR=/tmp/.secrets
VAULT_SHARED_DIR=/vault/shared

NOTIFYR_APP_ROLE="notifyr-app-role"
NOTIFYR_DMZ_APP_ROLE="notifyr-dmz-role"

export VAULT_ADDR="http://127.0.0.1:8200"
SETUP_CONFIG_PATH="setup-config/data/initialization-status"

################################# ##############################################
# Core functions
wait_for_server() {
  # Wait for listener
  for i in {1..30}; do
    if curl -sSf http://127.0.0.1:8200/v1/sys/health >/dev/null 2>&1; then
      break
    fi
    sleep 2
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

init_vault(){
  # Check if Vault is already initialized
  if [ -f "/run/secrets/vault-root.json" ]; then
    echo "Vault appears already initialized. Unsealing..."
    # TODO
    return
  fi

  if [ -f "$VAULT_SECRETS_DIR/unseal_key.json" ]; then
    echo "Vault appears already initialized. Unsealing..."
    
    cat "$VAULT_SECRETS_DIR/unseal_key.json"

    local uk1=$(cat "$VAULT_SECRETS_DIR/unseal_key.json" | jq -r '.uk1')
    local uk2=$(cat "$VAULT_SECRETS_DIR/unseal_key.json" | jq -r '.uk2')

    vault operator unseal "$uk1"
    vault operator unseal "$uk2"

    # Try to retrieve root token if initialization already happened
    ROOT_TOKEN=$(jq -r '.root_token' "$VAULT_SECRETS_DIR/vault-root.json" 2>/dev/null || true)
    if [ -n "$ROOT_TOKEN" ]; then
      echo "Root Token retrieved from file."
    fi
    return
  fi

  echo "Initializing Vault..."
  INIT_OUT=$(vault operator init -format=json -key-shares=3 -key-threshold=2)
  mkdir -p "$VAULT_SECRETS_DIR"
  echo "$INIT_OUT" > "$VAULT_SECRETS_DIR/vault-root.json" # Save output

  local uk1=$(echo "$INIT_OUT" | jq -r '.unseal_keys_b64[0]')
  local uk2=$(echo "$INIT_OUT" | jq -r '.unseal_keys_b64[1]')

  ROOT_TOKEN=$(echo "$INIT_OUT" | jq -r '.root_token')

  # The root_token and the unseal key will stay in the container as secrets
  cat <<EOF > "$VAULT_SECRETS_DIR/unseal_key.json"
  { "uk1":"$uk1",
    "uk2":"$uk2"
  }
EOF
  vault operator unseal "$uk1"
  vault operator unseal "$uk2"
  return
}
################################# ##############################################

# KV v2 checkpoint management function
setup_config_kv2() {
  local STEP_NAME=$1
  local MODE=$2 # 'check' or 'set'

  if [ -z "$STEP_NAME" ] || [ -z "$SETUP_CONFIG_PATH" ]; then
    echo "🚨 ERROR: STEP_NAME or SETUP_CONFIG_PATH is not set." >&2
    return 1
  fi

  # --- CHECK MODE ---
  if [ "$MODE" = "check" ]; then
    STATUS=$(vault kv get -field="$STEP_NAME" "$SETUP_CONFIG_PATH" 2>/dev/null || echo "not_done")
    
    if [ "$STATUS" = "done" ]; then
      echo "✅ Checkpoint '$STEP_NAME' found. Skipping."
      return 0 # Success, already done
    else
      echo "➡️  Checkpoint '$STEP_NAME' not found. Executing..."
      return 1 # Failure, must be executed
    fi

  # --- SET MODE ---
  elif [ "$MODE" = "set" ]; then
    echo "💾 Setting checkpoint '$STEP_NAME'..."

    local CURRENT_DATA
    CURRENT_DATA=$(vault kv get -format=json "$SETUP_CONFIG_PATH" 2>/dev/null | jq -r '.data.data')
    
    if [ "$CURRENT_DATA" == "null" ] || [ -z "$CURRENT_DATA" ]; then
        CURRENT_DATA="{}"
    fi

    local NEW_DATA
    NEW_DATA=$(echo "$CURRENT_DATA" | jq --arg key "$STEP_NAME" '. + {($key): "done"}')

    local PUT_ARGS
    PUT_ARGS=$(echo "$NEW_DATA" | jq -r 'to_entries[] | "\(.key)=\(.value)"' | tr '\n' ' ')

    if [ -z "$PUT_ARGS" ]; then
        echo "🚨 ERROR: Failed to generate data arguments for vault kv put." >&2
        return 1
    fi
    
    vault kv put "$SETUP_CONFIG_PATH" $PUT_ARGS >/dev/null
    echo "Checkpoint '$STEP_NAME' set."
    return 0
  fi
}


################################# ##############################################
# Configuration functions with checkpointing

setup_engine(){
 
  # Enable the setup config engine (KV v2). Ignore error 1 if the path already exists.
  vault secrets enable -path=setup-config -version=2 kv >/dev/null 2>&1 || {
    if [ $? -eq 1 ]; then
      echo "Info: setup-config engine already exists. Continuing."
      return
    fi
  }
  
  echo "Enabling secrets engines..."

  # Enable core KV, Transit, Database, RabbitMQ, AWS engines
  vault secrets enable -path=notifyr-generation -seal-wrap -version=2 kv
  vault secrets enable -path=notifyr-secrets -seal-wrap -version=1 kv
  vault secrets enable -path=notifyr-transit -seal-wrap transit
  vault secrets enable -path=notifyr-database -seal-wrap database
  vault secrets enable -path=notifyr-rabbitmq -seal-wrap rabbitmq
  vault secrets enable -path=notifyr-aws -seal-wrap aws

  # Minio plugin registration
  local CHECKSUM=$( sha256sum /etc/vault/plugins/vault-plugin-secrets-minio 2>/dev/null | cut -d " " -f 1 )
  [[ -n "$CHECKSUM" ]] || die "Could not calculate plugin sha256 sum"
  vault plugin register -sha256="$CHECKSUM" -command="vault-plugin-secrets-minio" secret vault-plugin-secrets-minio

  # Minio secrets engine enablement
  vault secrets enable \
    -path=notifyr-minio \
    -plugin-name=vault-plugin-secrets-minio \
    -description="Instance of the Minio plugin" \
    plugin

  # Transit keys creation
  vault write -f notifyr-transit/keys/profiles-key
  vault write -f notifyr-transit/keys/messages-key
  vault write -f notifyr-transit/keys/chat-key
  vault write -f notifyr-transit/keys/s3-rest-key
}

set_approle(){
  if setup_config_kv2 "approle" "check"; then
    return
  fi
  echo "Setting up AppRoles..."

  # Setup AppRole and policy
  vault auth enable approle || true

  vault policy write app-policy /vault/policies/app-policy.hcl
  vault policy write dmz-policy /vault/policies/dmz-policy.hcl

  # Write AppRole for application
  vault write auth/approle/role/"$NOTIFYR_APP_ROLE" \
    token_policies="app-policy" \
    token_ttl="24h" \
    token_max_ttl="36h" \
    secret_id_ttl="72h" \
    secret_id_num_uses=0 \
    enable_local_secret_ids=true

  # Write AppRole for DMZ
  vault write auth/approle/role/"$NOTIFYR_DMZ_APP_ROLE" \
    token_policies="dmz-policy" \
    token_ttl="24h" \
    token_max_ttl="36h" \
    secret_id_ttl="72h" \
    secret_id_num_uses=0 \
    enable_local_secret_ids=true

  # Store Role IDs (for app container secrets) and Secret IDs (for shared volume)
  local APP_ROLE_ID=$(vault read -format=json auth/approle/role/"$NOTIFYR_APP_ROLE"/role-id | jq -r .data.role_id)
  local APP_SECRET_ID=$(vault write -format=json -force auth/approle/role/"$NOTIFYR_APP_ROLE"/secret-id | jq -r .data.secret_id)

  local DMZ_ROLE_ID=$(vault read -format=json auth/approle/role/"$NOTIFYR_DMZ_APP_ROLE"/role-id | jq -r .data.role_id)
  local DMZ_SECRET_ID=$(vault write -format=json -force auth/approle/role/"$NOTIFYR_DMZ_APP_ROLE"/secret-id | jq -r .data.secret_id)


  TIMESTAMP=$(date +%s)

  echo -n "$APP_ROLE_ID" > "$VAULT_SECRETS_DIR/app-role_id.txt"
  echo -n "$DMZ_ROLE_ID" > "$VAULT_SECRETS_DIR/dmz-role_id.txt"

  echo -n "$APP_SECRET_ID" > "$VAULT_SHARED_DIR/app-secret-id.txt"
  echo -n "$DMZ_SECRET_ID" > "$VAULT_SHARED_DIR/dmz-secret-id.txt"

  echo -n "secret=$TIMESTAMP" > "$VAULT_SHARED_DIR/seed-time.txt"

  chown root:vaultuser "$VAULT_SHARED_DIR"/*.txt
  chmod 664 "$VAULT_SHARED_DIR"/*.txt

  chmod 644 "$VAULT_SECRETS_DIR"/*-role_id.txt

  setup_config_kv2 "approle" "set"
}

set_credit_topup_token() {
  if setup_config_kv2 "credit_token" "check"; then
    return
  fi
  echo "Setting up Credit Vault Token..."

  vault policy write credit-policy /vault/policies/credit-policy.hcl
  
  local CREDIT_TOKEN=$(vault token create -policy=credit-policy -ttl=0 -orphan -format=json | jq -r .auth.client_token)

  echo -n "$CREDIT_TOKEN" > "$VAULT_SECRETS_DIR/credit_token.txt"

  chown root:vaultuser "$VAULT_SECRETS_DIR/credit_token.txt"  

  chmod 644 "$VAULT_SECRETS_DIR/credit_token.txt"

  setup_config_kv2 "credit_token" "set"

}

set_rotate_approle() {
  if setup_config_kv2 "rotate_approle" "check"; then
    return
  fi
  echo "Setting up Rotate App Role Token..."

  vault policy write rotator-policy /vault/policies/rotate-approle.hcl

  TOKEN=$(vault token create -policy=rotator-policy -ttl=0 -orphan -format=json | jq -r .auth.client_token)

  echo -n "$TOKEN" > "$VAULT_SECRETS_DIR/rotate-token.txt"

  chown root:vaultuser "$VAULT_SECRETS_DIR/rotate-token.txt"

  chmod 640 "$VAULT_SECRETS_DIR/rotate-token.txt"

  setup_config_kv2 "rotate_approle" "set"
}

create_default_token(){
  if setup_config_kv2 "default_token" "check"; then
    return
  fi
  echo "Creating default keys and API keys..."

  TOKENS="JWT_SECRET_KEY ON_TOP_SECRET_KEY CONTACTS_HASH_KEY CONTACT_JWT_SECRET_KEY CLIENT_PASSWORD_HASH_KEY RSA_SECRET_PASSWORD API_ENCRYPT_TOKEN WS_SECRET_JWT_KEY"

  ARGS=""
  for token in $TOKENS
  do
    TEMP=$(pwgen -s 60 1)
    ARGS="$ARGS $token=$TEMP"
  done

  vault kv put notifyr-secrets/tokens $ARGS

  local dmz_api_key="dmz:$(pwgen -s 70 1)"
  local dashboard_api_key="dashboard:$(pwgen -s 70 1)"
  local balancer_exchange_token="balancer_exchange:$(pwgen -s 80 1)"

  vault kv put notifyr-secrets/internal-api/DMZ API_KEY="$dmz_api_key"
  vault kv put notifyr-secrets/internal-api/BALANCER API_KEY="$balancer_exchange_token"
  vault kv put notifyr-secrets/internal-api/DASHBOARD API_KEY="$dashboard_api_key"

  echo -n "$dmz_api_key" > "$VAULT_SECRETS_DIR/dmz-api-key.txt"
  echo -n "$dashboard_api_key" > "$VAULT_SECRETS_DIR/dashboard-api-key.txt"
  echo -n "$balancer_exchange_token" > "$VAULT_SECRETS_DIR/balancer-exchange-token.txt"

  vault kv put notifyr-secrets/setting @/vault/config/settings_db.json

  local generation_id=$(pwgen -s 32 1)

  vault kv put notifyr-generation/generation-id GENERATION_ID="$generation_id"

  local generated_at=$(date +%Y-%m-%dT%H:%M:%S)

  vault kv metadata put -custom-metadata=generated_at="$generated_at" notifyr-generation/generation-id

  setup_config_kv2 "default_token" "set"
}

setup_database_config(){
  # This function sets up ROLES for all database engines (Postgres, Mongo, Redis, Minio, RabbitMQ)

  # --- POSTGRES ROLES ---
  if ! setup_config_kv2 "postgres_roles" "check"; then
    echo "Configuring Postgres roles..."
    vault write notifyr-database/roles/app-postgres-ntfr-role \
        db_name="postgres" \
        default_ttl="12h" \
        max_ttl="16h" \
        creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
                      GRANT vault_ntrfyr_app_role TO \"{{name}}\";" \
        rollback_statements="DROP ROLE IF EXISTS \"{{name}}\";" \
        revocation_statements="REVOKE vault_ntrfyr_app_role FROM \"{{name}}\";
                        DROP ROLE IF EXISTS \"{{name}}\";"

    vault write notifyr-database/roles/admin-postgres-ntfr-role \
      db_name="postgres" \
      default_ttl="3h" \
      max_ttl="5h" \
      creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN SUPERUSER PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
                          GRANT vault_ntrfyr_admin_role TO \"{{name}}\";" \
      rollback_statements="DROP ROLE IF EXISTS \"{{name}}\";" \
      revocation_statements="REVOKE vault_ntrfyr_admin_role FROM \"{{name}}\"; \
                            DROP ROLE IF EXISTS \"{{name}}\";"
    setup_config_kv2 "postgres_roles" "set"
  fi

  # --- MONGO ROLES ---
  if ! setup_config_kv2 "mongo_roles" "check"; then
    echo "Configuring Mongo roles..."
    vault write notifyr-database/roles/app-mongo-ntfr-role \
      db_name="mongodb" \
      creation_statements='{ "db": "notifyr", "roles": [
      { "role": "readWrite", "db": "notifyr", "collection":"agent" },
      { "role": "readWrite", "db": "notifyr", "collection":"communication" },
      { "role": "readWrite", "db": "notifyr", "collection":"webhook" },
      { "role": "readWrite", "db": "notifyr", "collection":"workflow" },
      { "role": "readWrite", "db": "notifyr", "collection":"chat" }]}' \
      default_ttl="12h" \
      max_ttl="16h"

    vault write notifyr-database/roles/admin-mongo-ntfr-role \
      db_name="mongodb" \
      default_ttl="30m" \
      max_ttl="1h" \
      creation_statements='{ "db": "notifyr", "roles": [
          { "role": "dbOwner", "db": "notifyr" }
      ]}'
    setup_config_kv2 "mongo_roles" "set"
  fi

  # --- REDIS ROLES ---
  if ! setup_config_kv2 "redis_roles" "check"; then
    echo "Configuring Redis roles..."
    vault write notifyr-database/roles/app-redis-ntfr-role \
      db_name="redis" \
      default_ttl="365d" \
      max_ttl="365d" \
      creation_statements='["~*", "+@string", "+@hash", "+@list", "+@set", "+@sortedset", "+@stream","+@keyspace", "+@pubsub", "-@admin", "-@dangerous", "-@connection", "+PING","+SELECT"]'

    vault write notifyr-database/roles/admin-redis-ntfr-role \
      db_name="redis" \
      default_ttl="3h" \
      max_ttl="5h" \
      creation_statements='["~*","+@all"]'

    vault write notifyr-database/roles/credit-redis-ntfr-role \
      db_name="redis" \
      default_ttl="10m" \
      max_ttl="20m" \
      creation_statements='["~notifyr/credit:*", "+GET", "+SET", "+INCRBY", "+LPUSH", "+LTRIM", "+LRANGE","+SELECT", "+FCALL"]'
    setup_config_kv2 "redis_roles" "set"
  fi
  
  # --- MINIO ROLES ---
  if ! setup_config_kv2 "minio_roles" "check"; then
    echo "Configuring Minio roles..."
    vault write notifyr-minio/roles/app-static-minio-ntfr-role \
        policy_name=app-access \
        user_name_prefix="vault-static-temp" \
        credential_type=static \
        default_ttl=12h \
        max_ttl=16h

    vault write notifyr-minio/roles/app-sts-minio-ntfr-role \
        policy_name=app-access \
        credential_type=sts \
        default_ttl=12h \
        max_ttl=16h \
        max_sts_ttl=12h

    vault write notifyr-minio/roles/dmz-static-minio-ntfr-role \
        policy_name=dmz-access \
        user_name_prefix="dmz-static-temp" \
        credential_type=static \
        default_ttl=1h \
        max_ttl=2h

    vault write notifyr-minio/roles/dmz-sts-minio-ntfr-role \
        policy_name=dmz-access \
        credential_type=sts \
        default_ttl=1h \
        max_ttl=2h \
        max_sts_ttl=2h
    setup_config_kv2 "minio_roles" "set"
  fi

  # --- RABBITMQ ROLES ---
  if ! setup_config_kv2 "rabbitmq_roles" "check"; then
    echo "Configuring RabbitMQ roles and lease..."
    vault write notifyr-rabbitmq/config/lease \
      ttl=30d \
      max_ttl=30d \

    vault write notifyr-rabbitmq/roles/celery-ntfr-role \
      vhosts='{
          "celery": {
              "configure": ".*",
              "write": ".*",
              "read": ".*"
          }
      }'
    setup_config_kv2 "rabbitmq_roles" "set"
  fi
}

create_database_config(){
  # This function sets up CONNECTION CONFIGURATIONS for all database engines

  local PG_HOST=${POSTGRES_HOST:-postgres}
  local M_HOST=${MONGO_HOST:-mongodb}
  local STHREE_HOST=${S3_HOST:-minio}
  local RMQ_HOST=${RABBITMQ_HOST:-rabbitmq}
  local R_HOST=${REDIS_HOST:-redis}
  
  # --- POSTGRES CONNECTION ---
  if ! setup_config_kv2 "postgres_connection" "check"; then
    echo "Configuring Postgres connection..."
    vault write notifyr-database/config/postgres \
      plugin_name="postgresql-database-plugin" \
      allowed_roles="admin-postgres-ntfr-role, app-postgres-ntfr-role" \
      connection_url="postgresql://{{username}}:{{password}}@$PG_HOST:5432/notifyr" \
      max_open_connections=50 \
      max_idle_connections=20 \
      username="$POSTGRES_USER" \
      password="$POSTGRES_PASSWORD"

    vault write -f notifyr-database/rotate-root/postgres
    setup_config_kv2 "postgres_connection" "set"
  fi

  # --- MONGODB CONNECTION ---
  if ! setup_config_kv2 "mongodb_connection" "check"; then
    echo "Configuring MongoDB connection..."
    vault write notifyr-database/config/mongodb \
      plugin_name="mongodb-database-plugin" \
      allowed_roles="admin-mongo-ntfr-role, app-mongo-ntfr-role" \
      connection_url="mongodb://{{username}}:{{password}}@$M_HOST:27017/admin" \
      username="$MONGO_INITDB_ROOT_USERNAME" \
      password="$MONGO_INITDB_ROOT_PASSWORD"

    vault write -f notifyr-database/rotate-root/mongodb
    setup_config_kv2 "mongodb_connection" "set"
  fi

  # --- REDIS CONNECTION ---
  if ! setup_config_kv2 "redis_connection" "check"; then
    echo "Configuring Redis connection and static role..."
    vault write notifyr-database/config/redis \
        plugin_name="redis-database-plugin" \
        host="$R_HOST" \
        port=6379 \
        username="vaultadmin-redis" \
        password="$REDIS_ADMIN_PASSWORD" \
        allowed_roles="admin-redis-ntfr-role, app-redis-ntfr-role, credit-redis-ntfr-role"
    
    vault write -f notifyr-database/rotate-root/redis
    setup_config_kv2 "redis_connection" "set"
  fi

  # --- MINIO CONNECTION ---
  if ! setup_config_kv2 "minio_connection" "check"; then
    echo "Configuring Minio connection..."
    vault write notifyr-minio/config/root \
        endpoint="$STHREE_HOST:9000" \
        accessKeyId="vaultadmin-minio" \
        secretAccessKey="$MINIO_VAULT_PASSWORD" \
        sts_region="us-east-1" \
        ssl=false
    setup_config_kv2 "minio_connection" "set"
  fi

  # --- RABBITMQ CONNECTION ---
  if ! setup_config_kv2 "rabbitmq_connection" "check"; then
    echo "Configuring RabbitMQ connection..."
    vault write notifyr-rabbitmq/config/connection \
      connection_uri="http://$RMQ_HOST:15672" \
      username="$RABBITMQ_DEFAULT_USER" \
      password="$RABBITMQ_DEFAULT_PASS" \
      verify_connection=true
    setup_config_kv2 "rabbitmq_connection" "set"
  fi
}

create_aws_engine(){
  if setup_config_kv2 "aws_engine" "check"; then
    return
  fi
  echo "Configuring AWS engine..."

  local AWS_USER=${AWS_VAULT_USER:-"notifyr-s3-user"}
  local AWS_PASSWORD=${AWS_VAULT_PASSWORD:-"notifyr-s3-password"}

  vault write notifyr-aws/config/root \
      access_key="$AWS_USER" \
      secret_key="$AWS_PASSWORD" \
      endpoint="https://$AWS_HOST" \
      iam_endpoint="https://$AWS_HOST" \
      sts_endpoint="https://$AWS_HOST" \
      region=us-east-1 \
      sts_region="us-east-1"

    vault write notifyr-aws/roles/assets-role \
      credential_type=iam_user \
      policy_arns="assets-access" \
      ttl=15m \
      max_ttl=1h\

    vault write notifyr-aws/config/lease \
      lease=15m \
      lease_max=1h

  setup_config_kv2 "aws_engine" "set"
}

################################# EXECUTION ##############################################
# Start Vault as root in background
vault server -config="${VAULT_CONFIG}" &
VAULT_PID=$!

echo "*************************** WAIT FOR SERVER *********************"
wait_for_server

echo "*************************** INIT VAULT *********************"
init_vault

echo "*************************** WAIT ACTIVE SERVER *********************"
wait_active_server

# If the root token is still empty, we cannot proceed.
if [ -z "$ROOT_TOKEN" ]; then
    echo "ERROR: Root Token not found. Cannot proceed with configuration."
    kill "$VAULT_PID" || true
    exit 1
fi

export VAULT_TOKEN="$ROOT_TOKEN"

echo "*************************** SETUP ENGINE & SETUP CONFIG *********************"
setup_engine

echo "*************************** SET APPROLE *********************"
set_approle

echo "*************************** SET ROTATE APPROLE *********************"
set_rotate_approle

echo "*************************** SET CREDIT TOPUP TOKEN *********************"
set_credit_topup_token

echo "*************************** CREATE DEFAULT TOKEN/KEYS *********************"
create_default_token

echo "*************************** SETUP DATABASE ROLES (Checkpoints: postgres_roles, mongo_roles, redis_roles, minio_roles, rabbitmq_roles) *********************"
setup_database_config

echo "*************************** CREATE DATABASE CONNECTIONS (Checkpoints: postgres_connection, mongodb_connection, redis_connection, minio_connection, rabbitmq_connection) *********************"
create_database_config

echo "*************************** CREATE AWS ENGINE *********************"
# create_aws_engine

echo "*************************** FINISHING UP VAULT CONFIG *********************"

vault token revoke $ROOT_TOKEN || true
unset VAULT_TOKEN
ROOT_TOKEN=""

kill "$VAULT_PID" || true
wait "$VAULT_PID" || true
echo "Vault Initialization finished"
echo -n "Vault Init Done at $(date +%s)" > "$VAULT_SHARED_DIR/vault.lock"


chown vaultuser:vaultuser -R /vault/data/*
chmod 700 -R /vault/data/*

chmod 744 "$VAULT_SHARED_DIR/vault.lock"
echo "Exiting..."
################################# ##############################################