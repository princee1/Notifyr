#!/usr/bin/env bash
set -e

VAULT_CONFIG=/vault/config/vault.hcl
VAULT_SECRETS_DIR=/tmp/vault/secrets/
VAULT_SHARED_DIR=/vault/shared
VAULT_SECRETS_API_DIR=/tmp/vault/api-key/

NOTIFYR_APP_ROLE="notifyr-app-role"
NOTIFYR_DMZ_APP_ROLE="notifyr-dmz-role"


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

#################################               ##############################################


init_vault(){
  INIT_OUT=$(vault operator init -format=json -key-shares=2 -key-threshold=1)

  echo "$INIT_OUT"

  UNSEAL_KEY=$(echo "$INIT_OUT" | jq -r '.unseal_keys_b64[0]')
  UNSEAL_KEY_SHARE2=$(echo "$INIT_OUT" | jq -r '.unseal_keys_b64[1]')

  ROOT_TOKEN=$(echo "$INIT_OUT" | jq -r '.root_token')

  # The root_token and the unseal key will stay in the container as secrets
  echo -n "$UNSEAL_KEY" > "$VAULT_SECRETS_DIR/unseal_key.b64"
  echo -n "$UNSEAL_KEY_SHARE_2" > "$VAULT_SECRETS_DIR/unseal_key_2.b64" 

  vault operator unseal "$UNSEAL_KEY"
  UNSEAL_KEY=""
}

setup_engine(){
  vault secrets enable -path=notifyr-generation -seal-wrap -version=2 kv
  vault secrets enable -path=notifyr-secrets -seal-wrap -version=1 kv
  vault secrets enable -path=notifyr-transit -seal-wrap transit 
  vault secrets enable -path=notifyr-database -seal-wrap database
  vault secrets enable -path=notifyr-rabbitmq -seal-wrap rabbitmq
  vault secrets enable -path=notifyr-aws -seal-wrap aws

  vault secrets enable -path=setup-config kv

  local CHECKSUM=$( sha256sum /etc/vault/plugins/vault-plugin-secrets-minio 2>/dev/null | cut -d " " -f 1 )
  
  [[ -n "$CHECKSUM" ]] || die "Could not calculate plugin sha256 sum"

  vault plugin register -sha256="$CHECKSUM" -command="vault-plugin-secrets-minio" secret vault-plugin-secrets-minio

  vault secrets enable \
    -path=notifyr-minio \
    -plugin-name=vault-plugin-secrets-minio \
    -description="Instance of the Minio plugin" \
    plugin
  

  vault write -f notifyr-transit/keys/profiles-key
  vault write -f notifyr-transit/keys/messages-key
  vault write -f notifyr-transit/keys/chat-key
  vault write -f notifyr-transit/keys/s3-rest-key
}

set_approle(){
  
  # Setup AppRole and policy
  vault auth enable approle || true

  vault policy write app-policy /vault/policies/app-policy.hcl
  vault policy write dmz-policy /vault/policies/dmz-policy.hcl
  
  vault write auth/approle/role/"$NOTIFYR_APP_ROLE" \
    token_policies="app-policy" \
    token_ttl="24h" \
    token_max_ttl="36h" \
    secret_id_ttl="72h" \
    secret_id_num_uses=0 \
    enable_local_secret_ids=true

  vault write auth/approle/role/"$NOTIFYR_DMZ_APP_ROLE" \
    token_policies="dmz-policy" \
    token_ttl="24h" \
    token_max_ttl="36h" \
    secret_id_ttl="72h" \
    secret_id_num_uses=0 \
    enable_local_secret_ids=true

  # The role_id will be store in secrets and shared with the app container 
  # The secret_id will be store in a shared volume be shared with the container 
  APP_ROLE_ID=$(vault read -format=json auth/approle/role/"$NOTIFYR_APP_ROLE"/role-id | jq -r .data.role_id)
  APP_SECRET_ID=$(vault write -format=json -force auth/approle/role/"$NOTIFYR_APP_ROLE"/secret-id | jq -r .data.secret_id)

  DMZ_ROLE_ID=$(vault read -format=json auth/approle/role/"$NOTIFYR_DMZ_APP_ROLE"/role-id | jq -r .data.role_id)
  DMZ_SECRET_ID=$(vault write -format=json -force auth/approle/role/"$NOTIFYR_DMZ_APP_ROLE"/secret-id | jq -r .data.secret_id)


  TIMESTAMP=$(date +%s)

  echo -n "$APP_ROLE_ID" > "$VAULT_SECRETS_DIR/app-role_id.txt"
  echo -n "$DMZ_ROLE_ID" > "$VAULT_SECRETS_DIR/dmz-role_id.txt"

  echo -n "$APP_SECRET_ID" > "$VAULT_SHARED_DIR/app-secret-id.txt"
  echo -n "$DZM_SECRET_ID" > "$VAULT_SHARED_DIR/dmz-secret-id.txt"

  echo -n "secret=$TIMESTAMP" > "$VAULT_SHARED_DIR/seed-time.txt"

  chown root:vaultuser "$VAULT_SHARED_DIR/*secret-id.txt"
  chmod 664 "$VAULT_SHARED_DIR/*secret-id.txt"

  chown root:vaultuser "$VAULT_SHARED_DIR/seed-time.txt"
  chmod 664 "$VAULT_SHARED_DIR/seed-time.txt"

  chmod 644 "$VAULT_SECRETS_DIR/*role_id.txt"
  chown root:root "$VAULT_SECRETS_DIR/*role_id.txt"

}

set_rotate_approle() {
  vault policy write rotator /vault/policies/rotate-approle.hcl

  TOKEN=$(vault token create -policy=rotator -period=48h -format=json | jq -r .auth.client_token)

  echo -n "$TOKEN" > "$VAULT_SECRETS_DIR/rotate-token.txt"

  chown root:vaultuser "$VAULT_SECRETS_DIR/rotate-token.txt"

  chmod 640 "$VAULT_SECRETS_DIR/rotate-token.txt"

  echo "Setting up Rotate App Role"
}

create_default_token(){

  TOKENS="JWT_SECRET_KEY ON_TOP_SECRET_KEY CONTACTS_HASH_KEY CONTACT_JWT_SECRET_KEY CLIENT_PASSWORD_HASH_KEY RSA_SECRET_PASSWORD API_ENCRYPT_TOKEN WS_SECRET_JWT_KEY"

  ARGS=""
  for token in $TOKENS
  do
    TEMP=$(pwgen -s 128 1)
    ARGS="$ARGS $token=$TEMP"
  done

  vault kv put notifyr-secrets/tokens $ARGS

  local dmz_api_key="dmz:$(pwgen -s 100 1)"
  local dashboard_api_key="dashboard:$(pwgen -s 100 1)"

  vault kv put notifyr-secrets/internal-api/DMZ API_KEY="$dmz_api_key"
  vault kv put notifyr-secrets/internal-api/DASHBOARD API_KEY="$dashboard_api_key"
  
  echo -n "$dmz_api_key" > "$VAULT_SECRETS_API_DIR/dmz-api-key.txt"
  echo -n "$dashboard_api_key" > "$VAULT_SECRETS_API_DIR/dashboard-api-key.txt"

  vault kv put notifyr-secrets/setting @/vault/config/settings_db.json

  local generation_id=$(pwgen -s 32 1)

  vault kv put notifyr-generation/generation-id GENERATION_ID="$generation_id"

  local generated_at=$(date +%Y-%m-%dT%H:%M:%S)
  
  vault kv metadata put -custom-metadata=generated_at="$generated_at" notifyr-generation/generation-id

  echo "Creating default key"
}

setup_database_config(){
  
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

  vault write notifyr-database/roles/app-redis-ntfr-role \
    db_name="redis" \
    default_ttl="365d" \
    max_ttl="365d" \
    creation_statements='[
        "ACL SETUSER {{name}} on >{{password}} \
          ~* \
          +@string +@hash +@list +@set +@sortedset +@stream +@pubsub \
          -@admin -@dangerous -@keys -@connection \
          +del +unlink"]' \
    revocation_statements='["ACL DELUSER {{name}}"]'

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

  vault write rabbitmq/config/lease \
    ttl=31536000 \
    max_ttl=31536000 \

  vault write notifyr-rabbitmq/roles/celery-ntfr-role \
    vhosts='{
        "/celery": {
            "configure": ".*",
            "write": ".*",
            "read": ".*"
        }
    }'
}

create_aws_engine(){
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
}

create_database_config(){
  
  local PG_HOST=${POSTGRES_HOST:-postgres}
  local M_HOST=${MONGO_HOST:-mongodb}
  local STHREE_HOST=${S3_HOST:-minio}
  local RMQ_HOST=${RABBITMQ_HOST:-rabbitmq}
  local R_HOST=${REDIS_HOST:-redis}
  
  local C_TYPE=${S3_CRED_TYPE:-MINIO}

  local MINIO_VAULT_PASSWORD=$(cat /minio/secrets/config.json | jq -r .credential.secretKey)
  local MINIO_VAULT_USER=$(cat /minio/secrets/config.json | jq  -r .credential.accessKey)

  vault write notifyr-database/config/postgres \
    plugin_name="postgresql-database-plugin" \
    allowed_roles="admin-postgres-ntfr-role, app-postgres-ntfr-role" \
    connection_url="postgresql://{{username}}:{{password}}@$PG_HOST:5432/notifyr" \
    max_open_connections=50 \
    max_idle_connections=20 \
    username="$POSTGRES_USER" \
    password="$POSTGRES_PASSWORD"

  vault write -f notifyr-database/rotate-root/postgres

  vault write notifyr-database/config/mongodb \
    plugin_name="mongodb-database-plugin" \
    allowed_roles="admin-mongo-ntfr-role, app-mongo-ntfr-role" \
    connection_url="mongodb://{{username}}:{{password}}@$M_HOST:27017/admin" \
    username="$MONGO_INITDB_ROOT_USERNAME" \
    password="$MONGO_INITDB_ROOT_PASSWORD"

  vault write -f notifyr-database/rotate-root/mongodb

  vault write notifyr-database/config/redis \
      plugin_name="redis-database-plugin" \
      host="$R_HOST" \
      port=6379 \
      username="vaultadmin:redis" \
      password="$REDIS_ADMIN_PASSWORD" \
      allowed_roles="admin-redis-static-role, app-redis-ntfr-role"

  vault write notifyr-database/static-roles/admin-redis-static-role \
    db_name="redis" \
    username="vaultadmin:redis" \
    rotation_period=168h \
    rotation_statements='["ACL SETUSER {{name}} >{{password}}", "ACL SAVE"]'

  vault write -f notifyr/static-roles/admin-admin-static-role/rotate

  vault write notifyr-minio/config/root \
      endpoint="$STHREE_HOST:9000" \
      accessKeyId="vaultadmin:minio" \
      secretAccessKey="$MINIO_VAULT_PASSWORD" \
      sts_region="us-east-1" \
      ssl=false
  
  vault write notifyr-rabbitmq/config/connection \
    connection_uri="http://$RABBITMQ_HOST:15672" \
    username="$RABBITMQ_DEFAULT_USER" \
    password="$RABBITMQ_DEFAULT_PASS" \
    password_policy="rabbitmq_policy" \
    verify_connection=true
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
vault logout "$ROOT_TOKEN"
ROOT_TOKEN=""


wait "$VAULT_PID" || true
echo "Vault Initialization finished"

#################################               ##############################################
