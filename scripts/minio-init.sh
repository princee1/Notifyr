#!/usr/bin/env bash
set -e

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

mc admin policy create notifyr app-access /app/policy/app-access.json
mc admin policy create notifyr dmz-access /app/policy/dmz-access.json

#mc admin policy create notifyr vault-admin /app/policy/vault-admin.json

mc alias remove notifyr

kill "$MINIO_PID"
wait "$MINIO_PID" || true

unset MINIO_ROOT_USER
unset MINIO_ROOT_PASSWORD