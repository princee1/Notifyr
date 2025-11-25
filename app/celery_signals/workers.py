from celery.signals import worker_init,worker_ready,worker_shutdown,worker_shutting_down


class WorkersSignals:

    @staticmethod
    def on_worker_init():
        ...
    
    @staticmethod
    def on_worker_ready():
        ...
    
    @staticmethod
    def on_worker_shutdown():
        ...
    
    @staticmethod
    def on_worker_shutting_down():
        ...