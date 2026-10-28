#!/bin/sh

set -e

# Base secrets directory
SECRET_DIR="./.secrets"
mkdir -p "$SECRET_DIR"

# ---- Argument parsing ----
TYPE=""
FORCE=0

for arg in "$@"; do
    case "$arg" in
        minio|mongodb)
            TYPE="$arg"
            ;;
        -f|--force)
            FORCE=1
            ;;
    esac
done

if [ -z "$TYPE" ]; then
    echo "❌ **No secret type specified.**"
    echo "Usage:"
    echo "  $0 minio [--force]"
    echo "  $0 mongodb [--force]"

    exit 1
fi

# ---- Configuration per type ----
case "$TYPE" in
    minio)
        CONFIG_FILE="$SECRET_DIR/minio-root.json"
        DESCRIPTION="MinIO credentials file"
        ;;
    mongodb)
        CONFIG_FILE="$SECRET_DIR/mongo-keyfile.txt"
        DESCRIPTION="Mongo db replicas keyfile"

esac

# ---- Existing file handling ----
if [ -f "$CONFIG_FILE" ]; then
    if [ "$FORCE" -eq 1 ]; then
        echo "🚨 **Force flag detected.** Overwriting existing $DESCRIPTION: $CONFIG_FILE"
    else
        echo "⚠️ **$DESCRIPTION already exists:** $CONFIG_FILE"
        echo "To overwrite it, run the script with the '-f' or '--force' flag."
        exit 0
    fi
fi

# ---- Generation logic ----
case "$TYPE" in
    mongodb)
        echo "✨ Generating new API key and saving it to $CONFIG_FILE"
        openssl rand -base64 756 > "$CONFIG_FILE"
        ;;
    minio)
        echo "✨ Generating new MinIO root credentials and saving them to $CONFIG_FILE"
        ACCESS_KEY="minio-root-admin:$(pwgen -s 10 1)"
        SECRET_KEY="$(pwgen -s 40 1)"

        cat > "$CONFIG_FILE" <<EOF
{
  "credential": {
    "accessKey": "$ACCESS_KEY",
    "secretKey": "$SECRET_KEY"
  }
}
EOF
        ;;
esac

echo ""
echo "✅ **New $DESCRIPTION successfully created/updated.**"
echo "📁 Stored at: $CONFIG_FILE"
