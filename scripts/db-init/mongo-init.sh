#!/bin/bash
set -e

VOLUME_DIR=/data/db
INIT_FILE="$VOLUME_DIR/init.lock"
INIT_NOTIFYR_DB=${INIT_NOTIFYR_DB:-off}

if [ "$INIT_NOTIFYR_DB" = "on" ]; then

    mongosh \
        --username "$MONGO_INITDB_ROOT_USERNAME" \
        --password "$MONGO_INITDB_ROOT_PASSWORD" \
        --authenticationDatabase admin \
        /notifyr/admin.js
    
    mongosh \
        --username "$MONGO_INITDB_ROOT_USERNAME" \
        --password "$MONGO_INITDB_ROOT_PASSWORD" \
        --authenticationDatabase admin \
        --eval 'db.getSiblingDB("notifyr").getUsers()'
fi

echo -n "done" > $INIT_FILE
chown mongodb:mongodb $INIT_FILE
chmod 400 $INIT_FILE
