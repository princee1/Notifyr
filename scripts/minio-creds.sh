#!/bin/sh

# Configuration variables
SECRET_DIR="./.secrets"
CONFIG_FILE="$SECRET_DIR/minio-root.json"

mkdir -p "$SECRET_DIR"

FORCE=0
if [ "$1" = "-f" ] || [ "$1" = "--force" ]; then
    FORCE=1
fi

if [ -f "$CONFIG_FILE" ]; then
    if [ "$FORCE" -eq 1 ]; then
        echo "🚨 **Force flag detected.** Overwriting existing MinIO credentials file: $CONFIG_FILE"
        # Continue the script execution to regenerate credentials
    else
        echo "⚠️ **MinIO credentials file already exists:** $CONFIG_FILE"
        echo "To overwrite it, run the script with the '-f' or '--force' flag."
        exit 0
    fi
fi

VAULT_SECRET_ACCESS_KEY="minio-root-admin:$(pwgen -s 10 1)"
VAULT_SECRET_KEY="$(pwgen -s 40 1)"

cat > "$CONFIG_FILE" <<EOF
{
  "credential": {
    "accessKey": "$VAULT_SECRET_ACCESS_KEY",
    "secretKey": "$VAULT_SECRET_KEY"
  }
}
EOF

chmod 600 "$CONFIG_FILE"
echo "✅ **Generated new MinIO root credentials in $CONFIG_FILE**"