import traceback
from tortoise.models import Model
from tortoise.transactions import in_transaction
from app.depends.lock import LockLogicDecorator
from app.models.email_model import EmailTrackingORM
from app.models.twilio_model import CallTrackingORM, SMSTrackingORM
from app.utils.constant import StreamConstant
from app.utils.transformer import empty_str_to_none


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
            print(e.__class__,e)
            traceback.print_exc()
            invalid_entries.add(ids)
    
    try:
        await orm.bulk_create(objs)
        return list(valid_entries.union(invalid_entries))
    except Exception as e:
        print(e.__class__,e)
        traceback.print_exc()
        return list(invalid_entries)

async def Add_Email_Tracking(entries:list[str,dict]):
    print(f'Treating: {len(entries)} entries for Email Tracking Stream')
    async with in_transaction():
        return await simple_bulk_creates(entries,EmailTrackingORM)


async def Add_Twilio_Tracking_Call(entries: list[tuple[str, dict]]):
    print(f'Treating: {len(entries)} entries for Twilio Tracking Call Stream')
    #print(entries)
    async with in_transaction():
        return await simple_bulk_creates(entries, CallTrackingORM)

async def Add_Twilio_Tracking_Sms(entries: list[tuple[str, dict]]):
    print(f'Treating: {len(entries)} entries for Twilio Tracking SMS Stream')
    async with in_transaction():
        return await simple_bulk_creates(entries, SMSTrackingORM)


Tracking_Stream = {
    StreamConstant.EMAIL_TRACKING:Add_Email_Tracking,
    StreamConstant.TWILIO_TRACKING_CALL:Add_Twilio_Tracking_Call,
    StreamConstant.TWILIO_TRACKING_SMS:Add_Twilio_Tracking_Sms,

}

LockLogicDecorator(Tracking_Stream)