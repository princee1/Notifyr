from app.container import build_container, Get
from app.services import ConfigService, FileService, FTPService, GitCloneRepoService

build_container(dep=[ConfigService,FileService,FTPService,GitCloneRepoService])

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
def on_starting(server):
    server.log.info("Gunicorn server is starting...")

def on_reload(server):
    server.log.info("Gunicorn server is reloading...")

def when_ready(server):
    server.log.info("Gunicorn server is ready. Workers spawned.")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal.")

def worker_abort(worker):
    worker.log.info("Worker received SIGABRT signal.")