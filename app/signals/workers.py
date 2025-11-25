from celery.signals import worker_init,worker_ready,worker_shutdown,worker_shutting_down
from app.container import Get
from app.services import ProfileService

profileService = Get(ProfileService)

class WorkersSignals:

    @staticmethod
    def on_worker_init():
        ...

    @worker_ready.connect
    @staticmethod
    def on_worker_ready(sender, **kwargs):
        app = sender.app
        hostname = sender.hostname
        
        for id,p in profileService.MiniServiceStore:
            app.control.add_consumer(p.queue_name, destination=[hostname])
    
        print(f"Worker {hostname} synced {len(profileService.MiniServiceStore)} dynamic queues.")
    
    @staticmethod
    def on_worker_shutdown():
        ...
    
    @staticmethod
    def on_worker_shutting_down():
        ...