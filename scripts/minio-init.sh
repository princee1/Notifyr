#!/usr/bin/env bash
set -e

ASSETS_STORAGE_LIMIT=$1
STATIC_STORAGE_LIMIT=$2
S3_PROD=$3

export MINIO_ROOT_USER="temp-access-key"
export MINIO_ROOT_PASSWORD="temp-secret-key"

# Start MinIO in background
minio server /data &
MINIO_PID=$!

# Wait for MinIO to start
echo "Waiting for MinIO to start..."
sleep 20
echo "MinIO is up!"

mc alias set notifyr http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

mc mb notifyr/static
mc version enable notifyr/static
mc quota set notifyr/static  --size "$STATIC_STORAGE_LIMIT"


mc mb notifyr/assets
mc version enable notifyr/assets
mc quota set notifyr/assets  --size "$ASSETS_STORAGE_LIMIT"

if [ "$S3_MODE" = "dev" ]; then
  mc cp --recursive /app/assets/ notifyr/assets/
fi

VAULT_SECRET_ACCESS_KEY="vaultuser-$(pwgen -s 10 1)"
VAULT_SECRET_KEY=$(pwgen -s 30 1)
S3_WEBHOOK_TOKEN="s3:$(pwgen -s 45 1)"

# echo -n "$VAULT_SECRET_KEY" > /minio/secrets/vault-secret-key.txt
# echo -n "$VAULT_SECRET_ACCESS_KEY" > /minio/secrets/vault-access-key.txt

cat > /minio/secrets/config.json <<EOF
{
  "credential": {
    "accessKey": "$VAULT_SECRET_ACCESS_KEY",
    "secretKey": "$VAULT_SECRET_KEY"
  }
}
EOF

mc admin user add notifyr "$VAULT_SECRET_ACCESS_KEY" "$VAULT_SECRET_KEY"

mc admin policy attach notifyr consoleAdmin --user "$VAULT_SECRET_ACCESS_KEY"

mc admin policy create notifyr assets-access /app/policy/assets-access.json

mc alias remove notifyr

kill "$MINIO_PID"
wait "$MINIO_PID" || true

unset MINIO_ROOT_USER
unset MINIO_ROOT_PASSWORD