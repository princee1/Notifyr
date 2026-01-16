#!/bin/bash
set -e

echo "Waiting for MongoDB to start..."
until mongosh --quiet --eval "db.adminCommand('ping')" >/dev/null 2>&1; do
  sleep 1
done

IS_INITIATED=$(mongosh --quiet --eval "rs.status().ok" || echo 0)
if [ "$IS_INITIATED" != "1" ]; then
  echo "Initializing single-node replica set..."
  mongosh --eval "rs.initiate({_id: '$MONGO_REPLICA_NAME', members:[{_id: 0, host: 'mongodb:27017'}]})"
fi
