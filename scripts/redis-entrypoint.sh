#!/bin/sh
set -e

ACL_FILE="/data/etc/.users/users.acl"
mkdir -p "$(dirname "$ACL_FILE")"

USER_NAME="vaultadmin:redis"
USER_PASS="${REDIS_ADMIN_PASSWORD:-changeme}"

if [ ! -f "$ACL_FILE" ]; then
    chown -R redis:redis $ACL_FILE
    echo "Initializing Redis ACL file at $ACL_FILE..."
    
    # --- ACL user definitions ONLY go here ---
    
    if [ "$DEFAULT_USER" = "on" ]; then
        # user default on nopass ~* &* +@all
        echo "user default on nopass ~* &* +@all" > "$ACL_FILE" 
        echo "default user mode: on"
    else
        # user default off
        echo "user default off" > "$ACL_FILE" 
        echo "default user mode: off"
    fi

    # Create the custom user
    echo "user $USER_NAME on >$USER_PASS ~* &* +@all" >> "$ACL_FILE"
    echo "ACL file created."
else
    echo "ACL file already exists at $ACL_FILE. Skipping creation."
fi

# --- IMPORTANT CHANGE: Configuration directives moved to the EXEC line ---
# We now load the module and set AOF/appendfsync as command-line arguments.
# We also use the --aclfile argument to load your user definitions.

exec docker-entrypoint.sh redis-server \
    --aclfile "$ACL_FILE" \
    --appendonly yes \
    --appendfsync everysec \
    "$@"