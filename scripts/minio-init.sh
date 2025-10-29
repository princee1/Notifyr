#!/usr/bin/env bash
set -e

APP_HOST=${1:-"app:8088"}

export MINIO_ROOT_USER="temp-access-key"
export MINIO_ROOT_PASSWORD="temp-secret-key"

# Start MinIO in background
minio server /data &
MINIO_PID=$!

# Wait for MinIO to start
echo "Waiting for MinIO to start..."
sleep 20
echo "MinIO is up!"

mc alias set myminio http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

mc mb myminio/static
mc version enable myminio/static

mc mb myminio/assets
mc version enable myminio/assets

mc cp --recursive /app/assets/ myminio/assets/

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
  },
  "notify_redis": {
    "2": {
      "enable": "on",
      "address": "redis:6379",
      "key": "minio-events",
      "queue_limit": 1000,
      "user": "",
      "password": ""
    }
  }
}
EOF

mc admin user add myminio "$VAULT_SECRET_ACCESS_KEY" "$VAULT_SECRET_KEY"

mc admin policy attach myminio consoleAdmin --user "$VAULT_SECRET_ACCESS_KEY"

mc admin policy create myminio assets-access /app/policy/assets-access.json

mc alias remove myminio

kill "$MINIO_PID"
wait "$MINIO_PID" || true

unset MINIO_ROOT_USER
unset MINIO_ROOT_PASSWORD