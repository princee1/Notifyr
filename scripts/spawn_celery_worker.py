import multiprocessing
import time
import os

# Define the function that each process will run
def worker(task_id):
    """Simulates a long-running task."""
    print(f"Process {task_id} started (PID: {os.getpid()})")
    for i in range(5):  # Simulating work
        print(f"Process {task_id}: Working... {i}")
        time.sleep(1)
    print(f"Process {task_id} finished.")

if __name__ == "__main__":
    num_processes = os.getenv('CELERY_WORKERS_COUNT',10)  # Set the number of processes you want to spawn

    print(f"Starting {num_processes} processes in parallel.")

    processes = []
    for i in range(num_processes):
        p = multiprocessing.Process(target=worker, args=(i,))
        p.start()
        processes.append(p)

    # Wait for all processes to finish
    for p in processes:
        p.join()

    print("All processes have completed.")
