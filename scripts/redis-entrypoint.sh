#!/bin/sh
set -e

ACL_FILE="/data/etc/.users/users.acl"
mkdir -p "$(dirname "$ACL_FILE")"

USER_NAME="vaultadmin-redis"
USER_PASS="${REDIS_ADMIN_PASSWORD:-changeme}"
URL="redis://$USER_NAME:$USER_PASS@localhost:6379/1"

TO_LOAD_FUNC="false"

if [ ! -f "$ACL_FILE" ]; then
    TO_LOAD_FUNC="true"
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
    chown -R redis:redis $ACL_FILE
    echo "ACL file created."
else
    echo "ACL file already exists at $ACL_FILE. Skipping creation."
fi

# --- IMPORTANT CHANGE: Configuration directives moved to the EXEC line ---

if [ "$TO_LOAD_FUNC" = "true" ]; then
    echo "[AUDIT] Starting temporary Redis server..."
    su -s /bin/sh redis -c "redis-server --aclfile '$ACL_FILE' --appendonly yes --bind 127.0.0.1 --protected-mode yes" &    
    _REDIS_PID=$!
    
    until redis-cli -u "$URL" PING > /dev/null 2>&1; do
        sleep 0.5
    done

    echo "[AUDIT] Loading Redis functions..."
    redis-cli -u "$URL" FUNCTION LOAD REPLACE "$(cat /functions/ncs-lib.lua)"
    echo "[AUDIT] Functions loaded successfully."

    echo "[AUDIT] Shutting down temporary Redis server..."
    redis-cli -u "$URL" SAVE
    redis-cli -u "$URL" SHUTDOWN NOSAVE    
    wait "$_REDIS_PID"
    echo "[AUDIT] Redis server stopped."

    [ -t 1 ] && clear
fi

    
exec docker-entrypoint.sh redis-server \
    --aclfile "$ACL_FILE" \
    --appendonly yes \
    --appendfsync everysec \
    "$@"