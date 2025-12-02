#!/bin/sh
set -e

ACL_FILE="/data/users.acl"
USER_NAME="vaultadmin"
USER_PASS="${REDIS_ADMIN_PASSWORD:-changeme}"

if [ ! -f "$ACL_FILE" ]; then
    echo "Initializing Redis ACL file at $ACL_FILE..."
    
    touch "$ACL_FILE"
    echo "user default on nopass ~* &* +@all" >> "$ACL_FILE"
    
    echo "user $USER_NAME on >$USER_PASS ~* &* +@all" >> "$ACL_FILE"
    echo "ACL file created."
else
    echo "ACL file already exists at $ACL_FILE. Skipping creation."
fi

exec docker-entrypoint.sh redis-server --aclfile "$ACL_FILE" "$@"