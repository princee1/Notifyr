import functools
from typing import Callable
from app.container import Get, InjectInFunction
from app.models.email_model import EmailTrackingORM
from app.models.link_model import LinkEventORM,LinkSessionORM
from app.services.reactive_service import ReactiveService
from app.services.celery_service import CeleryService
from app.utils.constant import StreamConstant
from tortoise.models import Model
from tortoise.transactions import in_transaction
from app.utils.helper import uuid_v1_mc
from app.utils.transformer import empty_str_to_none


async def bulk_creates(entries,orm:type[Model]):
    valid_entries = set()
    invalid_entries = set()
    objs = []
    for ids,val in entries:
        try:
            empty_str_to_none(val)
            objs.append(orm(**val))
            valid_entries.add(ids)
        except Exception as e:
            invalid_entries.add(ids)
    
    try:
        await orm.bulk_create(objs)
        return list(valid_entries.union(invalid_entries))
    except Exception as e:
        print(e)
        return list(invalid_entries)


async def Add_Link_Event(entries:list[str,dict]):
    async with in_transaction():
        await bulk_creates(entries,LinkEventORM)
    

async def Add_Email_Tracking(entries:list[str,dict]):
    async with in_transaction():
        await bulk_creates(entries,EmailTrackingORM)

    
async def Add_Email_Event(entries:list[str,dict]):
    ...
    
async def Add_Link_Session(entries:list[str,dict]):
    uuid = uuid_v1_mc()
    print(entries)
    return entries.keys()


Callbacks_Stream = {
    StreamConstant.EMAIL_EVENT_STREAM:Add_Email_Event,
    StreamConstant.EMAIL_TRACKING:Add_Email_Tracking,
    StreamConstant.LINKS_EVENT_STREAM:Add_Link_Event,
    StreamConstant.LINKS_SESSION_STREAM:Add_Link_Session
}