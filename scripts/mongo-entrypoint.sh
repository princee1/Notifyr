#!/bin/bash
set -e

VOLUME_DIR=/data/db
INIT_FILE="$VOLUME_DIR/init.lock"

KEYFILE_DIR=/tmp/repl
KEYFILE="$KEYFILE_DIR/mongo-keyfile.txt"

echo "Mongo replica set: $MONGO_REPLICA_NAME"


if [ ! -f $KEYFILE ];then

  echo "Keyfile dir: $KEYFILE_DIR"
  mkdir -p "$KEYFILE_DIR"

  cp /run/secrets/mongo-keyfile.txt "$KEYFILE"
  chown -R mongodb:mongodb "$KEYFILE_DIR"
  chmod 400 "$KEYFILE"

fi

# Wait until init file exists
if [ ! -f "$INIT_FILE" ]; then
  sleep 5

  docker-entrypoint.sh mongod \
    --replSet "$MONGO_REPLICA_NAME" \
    --keyFile "$KEYFILE" \
    --bind_ip_all &
  
  MONGO_PID=$!
  
  until [ -f "$INIT_FILE" ]; do
    sleep 2
  done

  sleep 20

  until mongosh \
      --username "$MONGO_INITDB_ROOT_USERNAME" \
      --password "$MONGO_INITDB_ROOT_PASSWORD" \
      --authenticationDatabase admin \
      --quiet \
      --eval "db.adminCommand('ping')" >/dev/null 2>&1; do
    sleep 1
  done

  echo "MongoDB Server Initialisation Step Done"


  IS_INITIATED=$(mongosh --quiet --eval "rs.status().ok" 2>/dev/null || echo 0)
  if [ "$IS_INITIATED" != "1" ]; then

    echo "MongoDB Server Replicas Server Initiation Step"

    mongosh \
      --username "$MONGO_INITDB_ROOT_USERNAME" \
      --password "$MONGO_INITDB_ROOT_PASSWORD" \
      --authenticationDatabase admin \
      --eval "rs.initiate({_id:'$MONGO_REPLICA_NAME',members:[{_id:0,host:'mongodb:27017'}]})"  
    
    echo "MongoDB Server Replicas Setting up..."
    sleep 10
  fi

  kill "$MONGO_PID"
  wait "$MONGO_PID"
fi

exec docker-entrypoint.sh mongod \
  --replSet "$MONGO_REPLICA_NAME" \
  --keyFile "$KEYFILE" \
  --bind_ip_all \
  "$@"


