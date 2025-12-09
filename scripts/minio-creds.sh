#!/bin/sh

SECRET_DIR="./.secrets"
CONFIG_FILE="$SECRET_DIR/minio-root.json"

mkdir -p "$SECRET_DIR"

# If credentials already exist, do NOT regenerate them
if [ -f "$CONFIG_FILE" ]; then
    echo "minio-root.json already exists — keeping existing root credentials."
    exit 0
fi

# Generate ONCE — stable for the lifetime of this environment
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

echo "Generated new MinIO root credentials in $CONFIG_FILE"
