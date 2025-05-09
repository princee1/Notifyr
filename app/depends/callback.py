import functools
from typing import Callable
from app.container import Get, InjectInFunction
from app.models.email_model import EmailTrackingORM
from app.models.link_model import LinkEventORM,LinkSessionORM, LinkORM,LinkAnalyticsORM,bulk_upsert_analytics, bulk_upsert_links_vc
from app.services.reactive_service import ReactiveService
from app.services.celery_service import CeleryService
from app.utils.constant import StreamConstant
from tortoise.models import Model
from tortoise.transactions import in_transaction
from app.utils.helper import uuid_v1_mc
from app.utils.transformer import empty_str_to_none
from device_detector import DeviceDetector


async def simple_bulk_creates(entries,orm:type[Model]):
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

async def Add_Link_Event(entries:list[tuple[str,dict]]):
    valid_entries = set()
    invalid_entries = set()
    objs = []

    event_count = {
    }
    analytics = {
    }

    for ids,val in entries:
        try:
            empty_str_to_none(val)
            link_id = val['link_id']
            
            if link_id not in event_count:
                event_count[link_id] =0
            
            event_count[link_id]+=1

            dd = DeviceDetector(val['user-agent']).parse()
            device_type = dd.device_type()
            analytics_key = (link_id,val['country'],val['region'],val['city'],device_type)

            if analytics_key not in analytics:
                analytics[analytics_key] = 0

            analytics_key[analytics_key]+=1

            objs.append(LinkEventORM(**val))

            valid_entries.add(ids)
        except Exception as e:
            invalid_entries.add(ids)

    analytics_inputs = []

    for key,val in analytics:
        key = list(key)
        key.append(val)
        analytics_inputs.append(val)
    
    try:
        async with in_transaction():
            await LinkEventORM.bulk_create(objs)
            await bulk_upsert_analytics(analytics_inputs)
            await bulk_upsert_links_vc(event_count)
        
        return list(valid_entries.union(invalid_entries))
    except Exception as e:
        print(e)
        return list(invalid_entries)
    
async def Add_Email_Tracking(entries:list[str,dict]):
    async with in_transaction():
        return await simple_bulk_creates(entries,EmailTrackingORM)
    
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