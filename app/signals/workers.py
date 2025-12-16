from celery.signals import worker_init,worker_ready,worker_shutdown,worker_shutting_down
from app.container import Get
from app.services import ProfileService
from app.services.aws_service import AmazonS3Service
from app.services.database_service import MongooseService, RedisService, TortoiseConnectionService
from app.services.secret_service import HCVaultService

profileService = Get(ProfileService)


def on_worker_init():
    ...

@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    app = sender.app
    hostname = sender.hostname
    
    for id,p in profileService.MiniServiceStore:
        app.control.add_consumer(p.queue_name, destination=[hostname])

    print(f"Worker {hostname} synced {len(profileService.MiniServiceStore)} dynamic queues.")


@worker_shutdown.connect
def on_worker_shutdown(sender=None, signal=None, **kwargs):
    mongooseService: MongooseService = Get(MongooseService)
    tortoiseConnService = Get(TortoiseConnectionService)
    awsS3Service = Get(AmazonS3Service)
    redisService = Get(RedisService)
    vaultService = Get(HCVaultService)

    mongooseService.revoke_lease()
    tortoiseConnService.revoke_lease()
    awsS3Service.revoke_lease()
    redisService.revoke_lease()

    vaultService.revoke_auth_token()
    

def on_worker_shutting_down():
    ...