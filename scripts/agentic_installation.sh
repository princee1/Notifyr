#!/bin/bash

INSTALL_DOCLING="$1"
INSTALL_CRAWL4AI="$2"

echo "[INFO] INSTALL_DOCLING=${INSTALL_DOCLING}"
echo "[INFO] INSTALL_CRAWL4AI=${INSTALL_CRAWL4AI}"

if [ "$INSTALL_DOCLING" = "true" ]; then
    echo "[INFO] Installing Docling packages..."
    pip install llama-index-readers-docling
    pip install llama-index-node-parser-docling
    echo "[INFO] Docling installation step completed"
else
    echo "[INFO] Docling installation skipped"
fi

if [ "$INSTALL_CRAWL4AI" = "true" ]; then
    echo "[INFO] Installing Crawl4AI packages..."
    pip install crawl4ai
    crawl4ai-setup
    crawl4ai-doctor
    echo "[INFO] Crawl4AI installation step completed"
else
    echo "[INFO] Crawl4AI installation skipped"
fi
