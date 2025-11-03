from app.utils.constant import StreamConstant
from app.definition._service import StateProtocol
from app.services import RedisService
from app.container import Get

async def S3_Event_Stream(entries:list[tuple[str,dict]]):

    redisService = Get(RedisService)
    valid_entries = set()
    invalid_entries = set()

    print(entries)
    for ids,val in entries:
        valid_entries.add(ids)
        
    return valid_entries



Webhook_Stream = {
    StreamConstant.S3_EVENT_STREAM: S3_Event_Stream
}