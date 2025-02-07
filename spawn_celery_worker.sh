#!/bin/bash

# Set the command to run (change this to your desired command)
COMMAND="make celery"

# Set the number of processes to spawn
NUM_PROCESSES=20

echo "Spawning $NUM_PROCESSES processes..."

for i in $(seq 1 $NUM_PROCESSES); do
    $COMMAND &  # Run in background
done

wait  # Wait for all processes to finish

echo "All processes started!"
