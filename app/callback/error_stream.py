from app.classes.profiles import ProfileErrorProtocol
from app.utils.constant import StreamConstant,SubConstant
from app.models.profile_model import ErrorProfileModel
from app.container import Get
from app.services import MongooseService,RedisService

async def ProfileErrorStream(entries:list[tuple[str,ProfileErrorProtocol]]):
    mongooseService:MongooseService = Get(MongooseService)
    redisService:RedisService = Get(RedisService)

    async with mongooseService.statusLock.reader:
        ...



Profile_Error_Stream={

    StreamConstant.PROFILE_ERROR_STREAM: ProfileErrorStream
}
