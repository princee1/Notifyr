#!/bin/bash
set -e

KEYFILE_DIR=$(mktemp -d)
KEYFILE="$KEYFILE_DIR/mongo-keyfile.txt"

cp /run/secrets/mongo-keyfile.txt "$KEYFILE"
chown mongodb:mongodb "$KEYFILE"
chmod 400 "$KEYFILE"

exec docker-entrypoint.sh mongod \
  --replSet="$MONGO_REPLICA_NAME" \
  --keyFile="$KEYFILE" \
  --bind_ip_all