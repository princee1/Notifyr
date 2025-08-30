#!/bin/bash

# Build the local Docker image first
docker build -t notifyr:fastapi .

# Base port for the first container
BASE_PORT=8088
NUM_CONTAINERS=5
IMAGE_NAME="notifyr:fastapi"

for i in $(seq 0 $((NUM_CONTAINERS - 1))); do
    PORT=$((BASE_PORT + i))
    CONTAINER_NAME="ntfyr-app-$PORT"

    echo "Starting container $CONTAINER_NAME on port $PORT..."

    docker run -d \
        --name "$CONTAINER_NAME" \
        -p "$PORT:8088" \
        -v "$(pwd)/rate_limits.json:/run/secrets/rate_limits:ro" \
        --env-file .env \
        -e MODE=prod \
        --label "com.docker.compose.service=app" \
        --link redis \
        --link mongodb \
        "$IMAGE_NAME" \
        python main.py -H 0.0.0.0 -p 8088 -t solo
done
