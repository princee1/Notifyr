#!/bin/sh

SECRET_DIR="./.secrets"
CONFIG_FILE="$SECRET_DIR/api_key.txt"

mkdir -p "$SECRET_DIR"

FORCE=0
if [ "$1" = "-f" ] || [ "$1" = "--force" ]; then
    FORCE=1
fi

if [ -f "$CONFIG_FILE" ]; then
    if [ "$FORCE" -eq 1 ]; then
        echo "🚨 **Force flag detected.** Overwriting existing API key file: $CONFIG_FILE"
    else
        echo "⚠️ **API key file already exists:** $CONFIG_FILE"
        echo "To overwrite it, run the script with the '-f' or '--force' flag."
        exit 0
    fi
fi

echo "✨ Generating new API key and saving it to $CONFIG_FILE"
KEY="api_key:$(pwgen -s 100 1)"

echo -n "$KEY" > "$CONFIG_FILE"

chmod 600 "$CONFIG_FILE"

echo "✅ **New API key successfully created/updated.**"
echo "Key stored in: $CONFIG_FILE"