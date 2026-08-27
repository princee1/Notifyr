#!/bin/bash
set -e

VOLUME_DIR=/data/db
INIT_FILE="$VOLUME_DIR/init.lock"

mongosh \
    --username "$MONGO_INITDB_ROOT_USERNAME" \
    --password "$MONGO_INITDB_ROOT_PASSWORD" \
    --authenticationDatabase admin \
    --eval "
        const adminDb = db.getSiblingDB('admin');

        db = db.getSiblingDB('agentic-notifyr');
        db = db.getSiblingDB('app-notifyr');

        // Task administrator
        adminDb.createUser({
            user: '${NOTIFYR_MONGO_USERNAME}',
            pwd: '${NOTIFYR_MONGO_PASSWORD}',
            roles: [
                { role: 'dbOwner', db: 'notifyr' }
            ]
        });
    "

echo -n "done" > $INIT_FILE
chown mongodb:mongodb $INIT_FILE
chmod 400 $INIT_FILE
