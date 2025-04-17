#!/bin/bash

# Set the command to run (change this to your desired command)
COMMAND="make celery > /dev/null"

# Set the number of processes to spawn
NUM_PROCESSES=$1

echo "Spawning $NUM_PROCESSES processes..."

for i in $(seq 1 $NUM_PROCESSES); do
    sleep 5
    $COMMAND &  # Run in background
done

wait  # Wait for all processes to finishe

echo "All processes started!"
