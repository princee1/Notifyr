#!/bin/bash

# Set the command to run (change this to your desired command)
COMMAND="make celery-docker > /dev/null"

# Set the number of processes to spawn
NUM_PROCESSES=$1
REDBEAT=${2:-"false"}


if [ "$REDBEAT" = "true" ]; then
    make redbeat &
    echo "Readbeat process started !"
    sleep 30
fi

echo "Spawning $NUM_PROCESSES processes..."

for i in $(seq 1 $NUM_PROCESSES); do
    sleep 5
    $COMMAND &  # Run in background
done


wait 

echo "All processes finished!"
