#!/bin/sh

# --- 1. Environment Variable Checks (Required from outside) ---
: ${VAULT_ADDR:?"Error: VAULT_ADDR environment variable is not set."}
: ${REDIS_HOST:?"Error: REDIS_HOST environment variable is not set."}

# --- 2. Global Shell Variables (Configured inside the script) ---
COSTS_FILE="/run/secrets/costs.json"

VAULT_TOKEN_FILE="/run/secrets/credit_token.txt"
VAULT_REDIS_PATH="notifyr-database/creds/credit-redis-ntfr-role"

REDIS_PORT="6379"
REDIS_DB="1"

LEASE_ID=""
GLOBAL_VAULT_TOKEN=""

if ! command -v jq &> /dev/null; then
    echo "Error: 'jq' is required but not installed." >&2
    exit 1
fi

cleanup() {
    echo ""
    echo "--- Initiating Cleanup ---"
    
    if [ -n "$LEASE_ID" ]; then
        echo "🗑️ Revoking dynamic Redis secret lease: $LEASE_ID"
        
        REVOKE_RESPONSE=$(curl -s -X PUT \
            -H "X-Vault-Token: $GLOBAL_VAULT_TOKEN" \
            -d "{\"lease_id\": \"$LEASE_ID\"}" \
            "$VAULT_ADDR/v1/sys/leases/revoke"
        )
        
        if [ $? -eq 0 ] && ! echo "$REVOKE_RESPONSE" | grep 'errors'; then
            echo "✅ Lease successfully revoked."
        else
            echo "⚠️ Warning: Failed to revoke lease ID $LEASE_ID. Check Vault logs." >&2
        fi
    fi

    unset REDIS_USER REDIS_PASS GLOBAL_VAULT_TOKEN LEASE_ID
    echo "Cleanup complete."
}

# Set the trap: execute 'cleanup' function when the script exits (0) or fails (1, 2, etc.)
trap cleanup EXIT

get_redis_creds() {
    if [ ! -f "$VAULT_TOKEN_FILE" ]; then
        echo "Error: Vault token file not found at $VAULT_TOKEN_FILE" >&2
        exit 1
    fi
    
    local VAULT_TOKEN
    VAULT_TOKEN=$(cat "$VAULT_TOKEN_FILE" | tr -d '[:space:]')
    
    if [ -z "$VAULT_TOKEN" ]; then
        echo "Error: Vault token file is empty." >&2
        exit 1
    fi
    
    GLOBAL_VAULT_TOKEN="$VAULT_TOKEN"

    echo "🔑 Requesting Redis credentials from Vault: $VAULT_REDIS_PATH"
    
    local RESPONSE=$(curl -s -X GET \
        -H "X-Vault-Token: $VAULT_TOKEN" \
        "$VAULT_ADDR/v1/$VAULT_REDIS_PATH"
    )

    if [ $? -ne 0 ] || ! echo "$RESPONSE" | jq -e . &> /dev/null; then
        echo "Error: Failed to connect to Vault or receive a valid JSON response." >&2
        exit 1
    fi

    ERROR=$(echo "$RESPONSE" | jq -r '.errors // empty')
    if [ -n "$ERROR" ]; then
        echo "Error retrieving secret from Vault:" >&2
        echo "$ERROR" >&2
        exit 1
    fi
    
    REDIS_USER=$(echo "$RESPONSE" | jq -r '.data.username')
    REDIS_PASS=$(echo "$RESPONSE" | jq -r '.data.password')

    LEASE_ID=$(echo "$RESPONSE" | jq -r '.lease_id')

    if [ "$REDIS_USER" == "null" ] || [ "$REDIS_PASS" == "null" ]; then
        echo "Error: Vault response did not contain valid username/password." >&2
        exit 1
    fi

    echo "✅ Successfully retrieved credentials. Lease ID: $LEASE_ID"
}

# --- Function to Execute Redis Command ---
redis_exec() {
    if [ -z "$REDIS_PASS" ]; then
        echo "Error: Redis password not set. Cannot connect." >&2
        exit 1
    fi
    local command="$1"
    redis-cli -u "redis://$REDIS_USER:$REDIS_PASS@$REDIS_HOST:$REDIS_PORT" $command
}


# 1. topup: INCRBY for 'phone', 'sms', 'email'
topup_cost() {
    echo "🚀 Topping up phone, sms, email credits in Redis DB $REDIS_DB from $COSTS_FILE"
    
    JQ_FILTER='.credits | to_entries[] | select(.key=="phone" or .key=="sms" or .key=="email") | "\(.key)=\(.value)"'
    
    while IFS="=" read -r key val; do
        echo "+ $val -> $key"
        redis_exec "INCRBY credit:$key $val"
    done < <(jq -r "$JQ_FILTER" "$COSTS_FILE")
}

# 2. reset: SET for 'phone', 'sms', 'email'
reset_cost() {
    echo "🔄 Resetting phone, sms, email credits in Redis DB $REDIS_DB from $COSTS_FILE"
    
    JQ_FILTER='.credits | to_entries[] | select(.key=="phone" or .key=="sms" or .key=="email") | "\(.key)=\(.value)"'
    
    while IFS="=" read -r key val; do
        echo "SET $key -> $val"
        redis_exec "SET credit:$key $val"
    done < <(jq -r "$JQ_FILTER" "$COSTS_FILE")
}

# 3. reset-hard: SET for ALL keys in .credits
reset_cost_hard() {
    echo "🔥 HARD Resetting ALL credits in Redis DB $REDIS_DB from $COSTS_FILE"
    
    JQ_FILTER='.credits | to_entries[] | "\(.key)=\(.value)"'
    
    while IFS="=" read -r key val; do
        echo "SET $key -> $val"
        redis_exec "SET credit:$key $val"
    done < <(jq -r "$JQ_FILTER" "$COSTS_FILE")
}


if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <command>" >&2
    echo "  Commands: topup, reset, reset-hard" >&2
    exit 1
fi

COMMAND="$1"

get_redis_creds

case "$COMMAND" in
    topup)
        topup_cost
        ;;
    reset)
        reset_cost
        ;;
    reset-hard)
        reset_cost_hard
        ;;
    *)
        echo "Error: Invalid command '$COMMAND'." >&2
        echo "  Commands: topup, reset, reset-hard" >&2
        # No need to exit 1 here, the trap will still run
        ;;
esac

echo "Main task finished."