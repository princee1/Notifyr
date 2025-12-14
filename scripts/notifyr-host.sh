#!/bin/sh

# Define the entry and comment
HOST_ENTRY="127.0.0.54 api.notifyr.io dashboard.notifyr.io notifyr.io"
COMMENT="# Added for Notifyr testing"

# Check if the entry already exists
if ! grep -q "127.0.0.54" /etc/hosts; then
    # Append the comment and the entry
    echo "$COMMENT" | sudo tee -a /etc/hosts > /dev/null
    echo "$HOST_ENTRY" | sudo tee -a /etc/hosts > /dev/null
    echo "Hosts file updated."
else
    echo "Entry already exists in /etc/hosts."
fi
