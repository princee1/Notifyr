#!/bin/bash
set -e

VOLUME_DIR=/data/db
INIT_FILE="$VOLUME_DIR/init.lock"

echo -n "done" > $INIT_FILE
chown mongodb:mongodb $INIT_FILE
chmod 400 $INIT_FILE
