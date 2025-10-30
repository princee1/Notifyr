#!/usr/bin/env bash
set -e

unset MINIO_ROOT_USER
unset MINIO_ROOT_PASSWORD

# === Redis event configuration ===
export MINIO_NOTIFY_REDIS_ENABLE_NOTIFYR="${NOTIFY_REDIS_ENABLE:-on}"
export MINIO_NOTIFY_REDIS_ADDRESS_NOTIFYR="${NOTIFY_REDIS_ADDRESS:-redis}:6379"
export MINIO_NOTIFY_REDIS_KEY_NOTIFYR="${NOTIFY_REDIS_KEY:-s3_object_events}"
export MINIO_NOTIFY_REDIS_QUEUE_LIMIT_NOTIFYR="${NOTIFY_REDIS_QUEUE_LIMIT:-1000}"

minio server /data --config-dir /minio/secrets --console-address ":9001" &
MINIO_PID=$!

sleep 9
echo "Minio is UP!"

accessKey=$(cat /minio/secrets/config.json | jq -r '.credential.accessKey')
secretKey=$(cat /minio/secrets/config.json | jq -r '.credential.secretKey')

mc alias set notifyr http://localhost:9000 "$accessKey" "$secretKey" >/dev/null

notifyr_event_status=$(mc event list notifyr/assets --json | jq -r '.status')

if [ "$notifyr_event_status" = "success" ];then
  echo "Notifyr events already addeed"
else
  mc event add notifyr/assets arn:minio:sqs::NOTIFYR:redis --event put,delete
fi

mc alias remove notifyr >/dev/null

wait "$MINIO_PID"