#!/bin/bash

INSTALL_DOCLING="$1"

echo "[INFO] INSTALL_DOCLING=${INSTALL_DOCLING}"

if [ "$INSTALL_DOCLING" = "true" ]; then
    echo "[INFO] Installing Docling packages..."
    pip install llama-index-readers-docling
    pip install llama-index-node-parser-docling
    echo "[INFO] Docling installation step completed"
else
    echo "[INFO] Docling installation skipped"
fi
