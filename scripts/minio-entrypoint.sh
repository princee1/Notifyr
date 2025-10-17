#!/usr/bin/env bash
set -e

unset MINIO_ROOT_USER
unset MINIO_ROOT_PASSWORD

minio server /data --config-dir /minio/secrets --console-address ":9001"