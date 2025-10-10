from app.container import build_container, Get
from app.services import ConfigService, FileService, FTPService, GitCloneRepoService,AmazonS3Service,HCVaultService

build_container(dep=[ConfigService,FileService,FTPService,GitCloneRepoService,AmazonS3Service,HCVaultService])


"""
MASTER PROCESS LIFECYCLE
┌───────────────────────────────┐
│ on_starting(server)            │  <-- Master is starting (before config is loaded)
└───────────────┬───────────────┘
                │
                ▼
       ┌─────────────────┐
       │ pre_fork(server, worker) │ <-- Before each worker fork
       └─────────┬─────────┘
                 │
                 ▼
       ┌─────────────────┐
       │ post_fork(server, worker) │ <-- After each worker forked
       └─────────┬─────────┘
                 │
                 ▼
       ┌─────────────────┐
       │ when_ready(server)       │ <-- Master is ready, all workers spawned
       └─────────┬─────────┘
                 │
                 ▼
       ┌─────────────────┐
       │ nworkers_changed(server, new, old) │ <-- If workers changed dynamically
       └─────────┬─────────┘
                 │
                 ▼
       ┌─────────────────┐
       │ worker_exit(server, worker) │ <-- After a worker exits
       └─────────┬─────────┘
                 │
                 ▼
       ┌─────────────────┐
       │ on_reload(server) │ <-- During reloads (via SIGHUP)
       └─────────┬─────────┘
                 │
                 ▼
       ┌─────────────────┐
       │ pre_exec(server) │ <-- Before executing a new master process
       └─────────────────┘

WORKER PROCESS LIFECYCLE
┌───────────────────────────────┐
│ post_fork(server, worker)     │ <-- Worker initialized after fork
└───────────────┬───────────────┘
                │
                ▼
       ┌─────────────────┐
       │ worker_int(worker) │ <-- Worker receives SIGINT or SIGQUIT
       └─────────┬─────────┘
                 │
                 ▼
       ┌─────────────────┐
       │ worker_abort(worker) │ <-- Worker receives SIGABRT
       └─────────┬─────────┘
                 │
                 ▼
       ┌─────────────────┐
       │ pre_request(worker, req) │ <-- Before handling each request
       └─────────┬─────────┘
                 │
                 ▼
       ┌─────────────────┐
       │ post_request(worker, req, environ, resp) │ <-- After handling each request
       └─────────────────┘
      

"""

# =====================
# Daemonization (optional)
# =====================

# Run in background
# daemon = True

# =====================
# Preloading & Hooks
# =====================

# Preload the app before forking workers (saves memory with Copy-on-Write)
preload_app = True

# Hooks (optional)
def on_reload(server):
    server.log.info("Gunicorn server is reloading...")

def when_ready(server):
    server.log.info("Gunicorn server is ready. Workers spawned.")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal.")

def worker_abort(worker):
    worker.log.info("Worker received SIGABRT signal.")

def on_starting(server):
    server.log.info("Starting master process...")

def pre_fork(server, worker):
    server.log.info(f"About to fork worker {worker.pid}")

def post_fork(server, worker):
    worker.log.info(f"Worker {worker.pid} forked")

def pre_request(worker, req):
    worker.log.info(f"Handling request: {req.uri}")

def post_request(worker, req, environ, resp):
    worker.log.info(f"Finished request: {req.uri}")

def worker_exit(server, worker):
    server.log.info(f"Worker {worker.pid} exited")
