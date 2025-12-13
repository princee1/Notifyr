#!/bin/sh

# Usage: ./restart-service.sh <service>
SERVICE="$1"

if [[ -z "$SERVICE" ]]; then
    echo "Error: No service specified."
    echo "Usage: $0 <service>"
    exit 1
fi

if [[ "$SERVICE" != "app" && "$SERVICE" != "beat" && "$SERVICE" != "worker" ]]; then
    echo "Error: Invalid service '$SERVICE'. Must be one of: app, beat, worker."
    exit 1
fi

echo "Restarting containers for service: $SERVICE"

# Get container IDs matching the service label
CONTAINERS=$(curl -s --unix-socket /var/run/docker.sock \
  --get \
  --data-urlencode "filters={\"label\":[\"com.docker.compose.service=$SERVICE\"]}" \
  http://localhost/containers/json | jq -r '.[].Id')

echo "$CONTAINERS"

if [[ -z "$CONTAINERS" ]]; then
    echo "No running containers found for service '$SERVICE'."
    exit 0
fi

# Restart each container
for id in $CONTAINERS; do
    NAME=$(curl -s --unix-socket /var/run/docker.sock "http://localhost/containers/$id/json" | jq -r '.Name' | sed 's/^\/\(.*\)/\1/')
    echo "Restarting container: $NAME ($id)"
    curl -s -X POST --unix-socket /var/run/docker.sock "http://localhost/containers/$id/restart"
done

echo "Done."
