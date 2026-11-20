from app.container import Get
from app.services.database.mongoose_service import MongooseService
from app.services.database.redis_service import RedisService


async def Store_Credit_Bill(entries:list[tuple[str,dict]]):
    valid_entries = set()
    invalid_entries = set()

    redisService:RedisService = Get(RedisService)
    mongooseService:MongooseService = Get(MongooseService)

    for ids,values in entries:
        ...