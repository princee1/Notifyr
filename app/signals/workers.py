from celery.signals import worker_init,worker_ready,worker_shutdown,worker_shutting_down
from app.container import Get
from app.services import ProfileService
from app.services import MongooseService
from app.services import RedisService
from app.services import VaultService
from app.services import ConfigService
from app.utils.constant import CeleryConstant
from app.utils.globals import CAPABILITIES

profileService = Get(ProfileService)


def on_worker_init():
    ...

@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    configService = Get(ConfigService)
    app = sender.app
    hostname = sender.hostname
    
    for id,p in profileService.MiniServiceStore:
        if configService.BROKER_PROVIDER =='redis':
            queue_name:str = CeleryConstant.REDIS_QUEUE_NAME_RESOLVER(p.queue_name)
        else:
            queue_name=p.queue_name
        app.control.add_consumer(queue_name, destination=[hostname])

    print(f"Worker {hostname} synced {len(profileService.MiniServiceStore)} dynamic queues.")


@worker_shutdown.connect
def on_worker_shutdown(sender=None, signal=None, **kwargs):
    mongooseService: MongooseService = Get(MongooseService)
    redisService = Get(RedisService)
    vaultService = Get(VaultService)

    mongooseService.revoke_lease()
    redisService.revoke_lease()

    vaultService.revoke_auth_token()
    

def on_worker_shutting_down():
    ...