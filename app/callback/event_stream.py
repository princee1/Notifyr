import asyncio
import functools
import traceback
from typing import Callable
from app.container import Get
from app.definition._service import ServiceStatus
from app.depends.tools import LockLogicDecorator
from app.models.email_model import EmailStatus, EmailTrackingORM,TrackingEmailEventORM, bulk_upsert_email_analytics
from app.models.link_model import LinkEventORM,bulk_upsert_analytics, bulk_upsert_links_vc
from app.models.contacts_model import ContactORM, bulk_upsert_contact_analytics, bulk_upsert_contact_creation_analytics
from app.models.twilio_model import CallEventORM, CallStatusEnum, CallTrackingORM, SMSEventORM, SMSStatusEnum,SMSTrackingORM, bulk_upsert_call_analytics, bulk_upsert_sms_analytics
from app.services.database_service import TortoiseConnectionService
from app.utils.constant import StreamConstant
from tortoise.transactions import in_transaction
from app.utils.transformer import empty_str_to_none
from device_detector import DeviceDetector
from tortoise.exceptions import IntegrityError

Call_Ids:dict[str|dict]={}
N_A = 'N/A'


def inject_set(func:Callable):
    @functools.wraps(func)
    async def wrapper(*args,**kwargs):
        valid_entries = set()
        invalid_entries = set()
        kwargs['valid_entries'] = valid_entries
        kwargs['invalid_entries'] = invalid_entries

        return await wrapper(*args,**kwargs)

    return wrapper


def retry_logic(retry:int,sleep_time:int):
    def wrapper(func:Callable):
        async def callback(*args,**kwargs):
            retry_count = 0
            while retry_count < retry:
                try:
                    return await func(*args,**kwargs)
                    break  # Exit the loop if successful
                except IntegrityError as e:
                    retry_count += 1
                    if retry_count == retry:
                        raise e
                    else:
                        await asyncio.sleep(sleep_time)
                except Exception as e:
                    raise e
        return callback
    
    return wrapper


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
            user_agent = val.get('user_agent',None)
            if user_agent == None:
                device_type = 'unknown'
            else:
                dd = DeviceDetector(user_agent).parse()
                device_type = dd.device_type()
                device_type = device_type.strip()
                if not device_type:
                    device_type = 'unknown'

            if val.get('country',None) == None:
                analytics_key=(link_id,N_A,N_A,N_A,device_type)
            else:
                analytics_key = (link_id,val['country'],val['region'],val['city'],device_type)

            if analytics_key not in analytics:
                analytics[analytics_key] = 0

            analytics[analytics_key]+=1

            objs.append(LinkEventORM(**val))

            valid_entries.add(ids)
        except Exception as e:
            print(e)
            invalid_entries.add(ids)

    analytics_inputs = []


    for key,val in analytics.items():
        key = list(key)
        key.append(val)
        key = tuple(key)
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
        
async def Add_Email_Event(entries: list[tuple[str, dict]]):
    print(f'Treating: {len(entries)} entries for Email Tracking Event Stream')

    valid_entries = set()
    invalid_entries = set()
    objs = []

    analytics = {}
    contact_id_to_delete_from = set()
    contact_id_to_delete = []

    opens_per_email = {}
    delivered_per_email = {}

    index_tracking: dict[str,int] = {}

    replied_per_email = {}

    email_status = {}

    for i,(ids, val) in enumerate(entries):
        try:
            empty_str_to_none(val)
            email_id = val['email_id']
            esp_provider = val.get('esp_provider', 'Untracked Provider')  # Default to 'unknown' if not provided
            
            event = TrackingEmailEventORM(**val)
            objs.append(event)

            # Initialize analytics for the ESP provider if not already present
            if esp_provider not in analytics:
                analytics[esp_provider] = {
                    'sent': 0,
                    'received':0,
                    'delivered': 0,
                    'complaint':0,
                    'failed':0,
                    'opened': 0,
                    'bounced': 0,
                    'replied': 0,
                    'rejected':0,
                }

            factor = -1 if val.get('correction',False) else 1

            # Match the current event to the most accurate EmailStatus
            match event.current_event:
                case EmailStatus.RECEIVED.value:
                    analytics[esp_provider]['received']+=factor
                
                case EmailStatus.REJECTED.value:
                    analytics[esp_provider]['rejected']+=factor

                case EmailStatus.SENT.value:
                    analytics[esp_provider]['sent'] += factor

                case EmailStatus.DELIVERED.value:

                    if email_id not in delivered_per_email:
                        analytics[esp_provider]['delivered'] += factor
                        delivered_per_email[email_id] = True
                    
                case EmailStatus.OPENED.value | EmailStatus.LINK_CLICKED.value:
                    # Ensure only one open event is tracked per email_id
                    analytics[esp_provider]['opened'] += factor
                    
                    if email_id not in opens_per_email:
                        opens_per_email[email_id] = True
                
                case EmailStatus.SOFT_BOUNCE.value | EmailStatus.HARD_BOUNCE.value | EmailStatus.MAILBOX_FULL.value:
                    analytics[esp_provider]['bounced'] += factor
                    if event.current_event == EmailStatus.HARD_BOUNCE.value:
                        contact_id_to_delete_from.add(email_id)
                    
                case EmailStatus.REPLIED.value:
                    analytics[esp_provider]['replied'] += factor
                    analytics[esp_provider]['opened'] += factor

                    if email_id not in replied_per_email:
                        replied_per_email[email_id] = True
                    
                    if email_id not in opens_per_email:
                        opens_per_email[email_id] = True
                
                case EmailStatus.FAILED.value:
                    analytics[esp_provider]['failed'] += factor
                
                case EmailStatus.COMPLAINT.value:
                    analytics[esp_provider]['complaint'] += factor

            if opens_per_email.get(email_id, False):
                email_status[email_id] = EmailStatus.OPENED.value
            else:
                email_status[email_id] = event.current_event.value

            if replied_per_email.get(email_id, False):
                email_status[email_id] = EmailStatus.REPLIED.value
            else:
                email_status[email_id] = event.current_event.value

            valid_entries.add(ids)
        except Exception as e:
            print(e)
            traceback.print_exc()
            invalid_entries.add(ids)

    email_tracker = await EmailTrackingORM.filter(email_id__in=email_status.keys())
    for et in email_tracker:
        if et.email_current_status != 'REPLIED':
            et.email_current_status = email_status[str(et.email_id)]
        if et.email_id in contact_id_to_delete_from and et.contact != None:
            contact_id_to_delete.append(str(et.contact.contact_id))
        if et.email_id in delivered_per_email:
            if et.delivered:
                objs[index_tracking] = None
            

    @retry_logic(4,10)
    async def callback():
        async with in_transaction():
            await bulk_upsert_email_analytics(analytics)
            if len(email_tracker) > 0:
                await EmailTrackingORM.bulk_update(email_tracker, fields=['email_current_status'])
            await TrackingEmailEventORM.bulk_create(filter(lambda v : v!= None,objs))

    try:
        await callback()
        async with in_transaction():
            #await ContactORM.filter(contact_id__in=list(contact_id_to_delete_from)).delete()    
            ...
        
        return list(valid_entries.union(invalid_entries))
    except Exception as e:
       print(e.__class__, e)
       traceback.print_exc()
       return list(invalid_entries)
    
async def Add_Link_Session(entries:list[str,dict]):
    ...

async def Add_Twilio_Sms_Event(entries: list[tuple[str, dict]]):
    valid_entries = set()
    invalid_entries = set()
    obs= []

    analytics = {
        'I':{
            'received':0,
            'sent':0,
            'delivered':0,
            'failed':0,
            'bounce':0,
            'price':0,
            'rejected':0,
        },
        'O':{
            'received':0,
            'sent':0,
            'delivered':0,
            'failed':0,
            'bounce':0,
            'price':0,
            'rejected':0
        }

    } 

    prices:dict[str,dict] ={}

    sms_tracking_status= {

    }

    for ids,val in entries:
        try:
            empty_str_to_none(val)
            val = SMSEventORM.JSON(**val)
            val_copy = val.copy()

            del val_copy['correction']
            del val_copy['price']
            del val_copy['price_unit']

            event = SMSEventORM(**val_copy)

            obs.append(event)
            valid_entries.add(ids)

            factor = 1 if val.get('correction',False) else -1

            match val['current_event']:

                case SMSStatusEnum.RECEIVED.value:
                    analytics[val[analytics]]['received'] +=factor
                
                case SMSStatusEnum.REJECTED.value:
                    analytics[val[analytics]]['received'] +=factor
                
                case SMSStatusEnum.SENT.value:
                    analytics[val[analytics]]['sent'] +=factor
                    
                case SMSStatusEnum.FAILED.value:
                    analytics[val[analytics]]['failed'] +=factor
                    
                case SMSStatusEnum.BOUNCE.value:
                    analytics[val[analytics]]['bounce'] +=factor                
                
                case SMSStatusEnum.DELIVERED.value:
                    analytics[val[analytics]]['delivered'] +=factor
                    
            sms_id= val['sms_id']

            if sms_id not in prices:
                if val['price'] != None:
                    prices[sms_id]['price'] = val['price']
                    analytics[val['direction']]['price'] +=val['price']
                
                if val['price_unit'] != None:
                    prices[sms_id]['price_unit'] = val['price_unit']

            # if sms_id in sms_tracking_status:
            #     if sms_tracking_status[sms_id] == 'RECEIVED' or sms_tracking_status[sms_id] == 'SENT':
            #         sms_tracking_status[sms_id] = val['current_event']
            # else:
            #     sms_tracking_status[sms_id] = val['current_event']
            sms_tracking_status[sms_id] = val['current_event']

        except:
            invalid_entries.add(ids)

    sms_tracking = await SMSTrackingORM.filter(sms_id__in=sms_tracking_status.keys())
    for st in sms_tracking:
        st.sms_current_status = sms_tracking_status[str(st.sms_id)]
        if st.sms_id in prices:
            if prices['price']!=None:
                st.price = prices['price']
            if prices['price_unit'] !=None:
                st.price_unit = prices['price_unit']
    
    @retry_logic(4,2)
    async def callback():
        async with in_transaction():
            if len(sms_tracking) >0:
                await SMSTrackingORM.bulk_update(sms_tracking,fields=['sms_current_status','price','price_unit'])
            await SMSEventORM.bulk_create(obs)
            await bulk_upsert_sms_analytics('I',**analytics['I'])
            await bulk_upsert_sms_analytics('O',**analytics['O'])


    try:
        await callback()
        return list(valid_entries.union(invalid_entries))
    except:
        return invalid_entries

async def Add_Twilio_Call_Event(entries: list[tuple[str, dict]]):

    print(f'Treating: {len(entries)} entries for Add Twilio Call Event Stream')
    
    valid_entries = set()
    invalid_entries = set()
    in_memory_cache_entries = set()

    prices = {}
    duration = {}
    objs = []
    analytics = {}
    create_analytics = lambda: {
        'I':{'direction':'I',
            'received':0,
            'sent':0,
            'started':0,
            'delivered':0,
            'failed':0,
            'bounce':0,
            'price':0,
            'no_answer':0,
            'declined':0,
            'rejected':0,
            'call_duration':0,
            'total_duration':0,
        },
        'O':{
            'direction':'O',
            'received':0,
            'sent':0,
            'started':0,
            'delivered':0,
            'failed':0,
            'bounce':0,
            'price':0,
            'no_answer':0,
            'declined':0,
            'rejected':0,
            'call_duration':0,
            'total_duration':0,
        }

    } 

    call_tracking_status = {}
    

    for ids,val in entries:
        try:
            empty_str_to_none(val)
            val = CallEventORM.JSON(**val)
        
            call_id = val['call_id']

            key = None
            data:list[CallEventORM.JSON]= []

            if call_id not in Call_Ids:
                if val['city'] != None:
                    Call_Ids[call_id]['key']= key =(val['country'],val['state'],val['city'])
                    analytics[key] = create_analytics()
                    data.append(val)

                else:
                    if 'temp' not in Call_Ids[call_id]:
                        Call_Ids[call_id]['temp'] = []

                    Call_Ids[call_id]['temp'].append(val)
                    if val['current_event'] not in [CallStatusEnum.REJECTED.value,CallStatusEnum.FAILED.value]:
                        key= (N_A,N_A,N_A)
                        if key not in analytics:
                            analytics[key] = create_analytics()
                        
                        data.extend(Call_Ids[call_id]['temp'])

            else:
                if 'temp' in Call_Ids[call_id]:
                    if val['city'] != None:
                        analytics[key] = create_analytics()
                        data.extend(Call_Ids[call_id]['temp'])
                        Call_Ids[call_id]['temp'] = []
                    else:
                        Call_Ids[call_id]['temp'].append(val)
                else:
                    key = Call_Ids[call_id]['key']
                    data.append(val)


            if key!= None:
                try:
                    del Call_Ids[call_id]
                except:
                    ...

            call_tracking_status[call_id] = val['current_event']

            for v in data:
                val_copy = v.copy()

                del val_copy['correction']
                del val_copy['price']
                del val_copy['price_unit']

                event = CallEventORM(**val_copy)
                objs.append(event)

                factor = 1 if v.get('correction',False) else -1

                match v['current_event']:
                    case CallStatusEnum.RECEIVED.value:
                        analytics[key][v['direction']]['received'] +=factor
                    
                    case CallStatusEnum.SENT.value:
                        analytics[key][v['direction']]['sent'] +=factor

                    case CallStatusEnum.REJECTED.value:
                        analytics[key][v['direction']]['sent'] +=factor
                    
                    case CallStatusEnum.INITIATED:
                        analytics[key][v['direction']]['started'] +=factor
                        
                    case CallStatusEnum.COMPLETED.value:
                        analytics[key][v['direction']]['completed'] +=factor
                        analytics[key][v['direction']]['call_duration'] +=v['call_duration']
                        analytics[key][v['direction']]['total_duration'] +=v['total_duration']

                        duration[call_id]['duration']=v['call_duration']
                        duration[call_id]['total_duration']=v['total_duration']
                        
                    case CallStatusEnum.DECLINED.value:
                        analytics[key][v['direction']]['declined'] +=factor
                        analytics[key][v['direction']]['total_duration'] +=v['total_duration']

                        duration[call_id]['duration']=0
                        duration[call_id]['total_duration']=v['total_duration']

                    case  CallStatusEnum.FAILED.value:
                        analytics[key][v['direction']]['failed'] +=factor
                    
                    case CallStatusEnum.BOUNCE.value:
                        analytics[key][v['direction']]['bounce'] +=factor
                    
                    case CallStatusEnum.NO_ANSWER.value:
                        analytics[key][v['direction']]['no-answer'] +=factor


            valid_entries.add(ids)
        except:
            invalid_entries.add(ids)
    
    call_tracking = await CallTrackingORM.filter(sms_id__in=call_tracking_status.keys())
    for ct in call_tracking:
        ct.call_current_status = call_tracking_status[str(ct.call_id)]
        if ct.call_id in prices:
            if prices['price']!=None:
                ct.price = prices['price']
            if prices['price_unit'] !=None:
                ct.price_unit = prices['price_unit']
        if str(ct.call_id) in duration:
            ct.duration = duration[str(ct.call_id)]['duration']
            ct.total_duration = duration[str(ct.call_id)]['total_duration']

    @retry_logic(3,3)
    async def callback():
        async with in_transaction():
            # if len(call_tracking) >0:
            #     await CallTrackingORM.bulk_update(call_tracking,fields=['price','price_unit','duration','total_duration'])
            await CallEventORM.bulk_create(objs)
            await bulk_upsert_call_analytics(analytics,'I')
            await bulk_upsert_call_analytics(analytics,'O')


    try:
        async with in_transaction():
            if len(call_tracking) >0:
                await CallTrackingORM.bulk_update(call_tracking,fields=['price','price_unit','duration','total_duration'])
        await callback()
        return list(valid_entries.union(invalid_entries))
    except:
        return invalid_entries
    
async def Add_Contact_Subs_Event(entries:list[tuple[str,dict]]):
    valid_entries = set()
    invalid_entries = set()

    analytics ={}
    for ids,val in entries:
        
        try:
            empty_str_to_none(val)
            if val.get('country',None)!=None:

                key = (val['country'],val['state'],val['region'])
            else:
                key =(N_A,N_A,N_A)

            if key not in analytics:
                analytics[key]['sub']=0
                analytics[key]['unsub']=0

            analytics[key]+=val.get('subscription',0)
            analytics[key]+=val.get('unsubscription',0)
            valid_entries.add(ids)
        except:
            invalid_entries.add(ids)

    try:
        await bulk_upsert_contact_analytics(analytics)
        return list(valid_entries.union(invalid_entries))
    except:
        return invalid_entries

async def Add_Contact_Creation_Event(entries:list[tuple[str,dict]]):
    valid_entries = set()
    invalid_entries = set()

    analytics ={}
    for ids,val in entries:
        
        try:
            empty_str_to_none(val)
            if val['country']!=None:

                key = (val['country'],val['state'],val['region'])
            else:
                key =(N_A,N_A,N_A)

            if key not in analytics:
                analytics[key]=0

            analytics[key]+=1
            valid_entries.add(ids)
        except:
            invalid_entries.add(ids)

    try:
        await bulk_upsert_contact_creation_analytics(analytics)
        return list(valid_entries.union(invalid_entries))
    except:
        return invalid_entries

    
#############################################        ############################################

Events_Stream = {
    StreamConstant.EMAIL_EVENT_STREAM:Add_Email_Event,
    StreamConstant.LINKS_EVENT_STREAM:Add_Link_Event,
    StreamConstant.LINKS_SESSION_STREAM:Add_Link_Session,
    StreamConstant.TWILIO_EVENT_STREAM_CALL:Add_Twilio_Call_Event,
    StreamConstant.TWILIO_EVENT_STREAM_SMS:Add_Twilio_Sms_Event,
    StreamConstant.CONTACT_SUBS_EVENT:Add_Contact_Subs_Event,
    StreamConstant.CONTACT_CREATION_EVENT:Add_Contact_Creation_Event,
}

Events_Stream = LockLogicDecorator(Events_Stream)