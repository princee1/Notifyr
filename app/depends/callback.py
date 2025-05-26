import functools
from typing import Callable
from app.container import Get, InjectInFunction
from app.models.email_model import EmailStatus, EmailTrackingORM,TrackingEmailEventORM, upsert_email_analytics
from app.models.link_model import LinkEventORM,bulk_upsert_analytics, bulk_upsert_links_vc
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

#############################################        ############################################

async def Add_Link_Event(entries:list[tuple[str,dict]]):
    valid_entries = set()
    invalid_entries = set()
    objs = []

    event_count = {
    }
    analytics = {
    }

    print('Link Event Callback:','Treating',len(entries), 'entries')
    for ids,val in entries:
        try:
            empty_str_to_none(val)
            link_id = val['link_id']
            
            if link_id not in event_count:
                event_count[link_id] =0
            
            event_count[link_id]+=1
            dd = DeviceDetector(val['user_agent']).parse()
            device_type = dd.device_type()
            device_type = device_type.strip()
            if not device_type:
                device_type = 'unknown'

            analytics_key = (link_id,val['country'],val['region'],val['city'],device_type)

            if analytics_key not in analytics:
                analytics[analytics_key] = 0

            analytics[analytics_key]+=1

            objs.append(LinkEventORM(**val))

            valid_entries.add(ids)
        except Exception as e:
            invalid_entries.add(ids)

    analytics_inputs = []


    for key,val in analytics.items():
        key = list(key)
        key.append(val)
        analytics_inputs.append(key)
    
    link_visit_input = []
    for key,val in event_count.items():
        link_visit_input.append((key,val))

    try:
        async with in_transaction():
            await LinkEventORM.bulk_create(objs)
            await bulk_upsert_links_vc(link_visit_input)
        
        async with in_transaction():
            await bulk_upsert_analytics(analytics_inputs)
        
        return list(valid_entries.union(invalid_entries))
    except Exception as e:
        print(e)
        return list(invalid_entries)
    
async def Add_Email_Tracking(entries:list[str,dict]):
    print(f'Treating: {len(entries)} entries for Email Tracking Stream')
    async with in_transaction():
        return await simple_bulk_creates(entries,EmailTrackingORM)
    
async def Add_Email_Event(entries: list[tuple[str, dict]]):
    valid_entries = set()
    invalid_entries = set()
    objs = []

    analytics = {
        'sent': 0,
        'delivered': 0,
        'opened': 0,
        'bounced': 0,
        'replied': 0
    }

    opens_per_email = {}

    for ids, val in entries:
        try:
            empty_str_to_none(val)
            email_id = val['email_id']
            event = TrackingEmailEventORM(**val)
            objs.append(event)

            # Match the current event to the most accurate EmailStatus
            match event.current_event:
                case EmailStatus.SENT.value:
                    analytics['sent'] += 1
                case EmailStatus.DELIVERED.value:
                    analytics['delivered'] += 1
                case EmailStatus.OPENED.value | EmailStatus.LINK_CLICKED.value:
                    # Ensure only one open event is tracked per email_id
                    if email_id not in opens_per_email:
                        analytics['opened'] += 1
                        opens_per_email[email_id] = True
                case EmailStatus.SOFT_BOUNCE | EmailStatus.HARD_BOUNCE | EmailStatus.MAILBOX_FULL:
                    analytics['bounced'] += 1
                case EmailStatus.REPLIED:
                    analytics['replied'] += 1

            valid_entries.add(ids)
        except Exception as e:
            invalid_entries.add(ids)

    try:
        async with in_transaction():
            await TrackingEmailEventORM.bulk_create(objs)
            await upsert_email_analytics(analytics)
                        
        return list(valid_entries.union(invalid_entries))
    except Exception as e:
        print(e)
        return list(invalid_entries)
async def Add_Link_Session(entries:list[str,dict]):
    uuid = uuid_v1_mc()
    print(entries)
    return entries.keys()

#############################################        ############################################

Callbacks_Stream = {
    StreamConstant.EMAIL_EVENT_STREAM:Add_Email_Event,
    StreamConstant.EMAIL_TRACKING:Add_Email_Tracking,
    StreamConstant.LINKS_EVENT_STREAM:Add_Link_Event,
    StreamConstant.LINKS_SESSION_STREAM:Add_Link_Session
    
}