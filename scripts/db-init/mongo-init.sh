#!/bin/bash
set -e

VOLUME_DIR=/data/db
INIT_FILE="$VOLUME_DIR/init.lock"

mongosh \
    --username "$MONGO_INITDB_ROOT_USERNAME" \
    --password "$MONGO_INITDB_ROOT_PASSWORD" \
    --authenticationDatabase admin \
    /notifyr/notifyr.js

echo -n "done" > $INIT_FILE
chown mongodb:mongodb $INIT_FILE
chmod 400 $INIT_FILE
