#!/usr/bin/env bash

TARGET_PATH="$1"

if [[ -z "$TARGET_PATH" ]]; then
    echo "Error: Output path is required."
    echo "Usage: $0 /path/to/output.json"
    exit 1
fi

if [[ -f "$TARGET_PATH" ]]; then
    echo "File '$TARGET_PATH' already exists. Skipping form."
    exit 0
fi

read -r -p "Enter admin username: " CLIENT_USERNAME
read -r -p "Enter admin name: " CLIENT_NAME
read -r -p "Enter admin email: " CLIENT_EMAIL

echo "Select Client Scope:"
echo "1) Free"
echo "2) SoloDolo"
echo "3) Organization"
read -r -p "Scope Choice [1-3] (default 1): " SCOPE_CHOICE

case "$SCOPE_CHOICE" in
    2)
        CLIENT_SCOPE="SoloDolo"
        read -r -p "Enter issued_for (IPv4 address): " ISSUED_FOR
        ;;
    3)
        CLIENT_SCOPE="Organization"
        read -r -p "Enter issued_for (IPv4 subnet): " ISSUED_FOR
        ;;
    *)
        CLIENT_SCOPE="Free"
        ISSUED_FOR=""
        ;;
esac

read -r -s -p "Enter password: " PASSWORD
echo ""

if [[ -z "$ISSUED_FOR" ]]; then
    ISSUED_FOR_JSON="null"
else
    ISSUED_FOR_JSON="\"$ISSUED_FOR\""
fi

mkdir -p "$(dirname "$TARGET_PATH")"

cat <<EOF > "$TARGET_PATH"
{   
  "client_email": "$CLIENT_EMAIL",
  "client_username": "$CLIENT_USERNAME",
  "issued_for": $ISSUED_FOR_JSON,
  "client_name": "$CLIENT_NAME",
  "client_scope": "$CLIENT_SCOPE",
  "password": "$PASSWORD"
}
EOF

echo "JSON created at '$TARGET_PATH'."