from app.utils.constant import StreamConstant, SubConstant
import asyncio
from typing import Dict, TypedDict

MS_1000 = 1000
class CallbacksConfig(TypedDict):
    sub:bool
    count:int|None = None
    block:int|None=None
    wait:int|None=None
    stream:bool
    channel_tasks:asyncio.Task | None = None
    stream_tasks: asyncio.Task | None = None

CALLBACKS_CONFIG:Dict[str,CallbacksConfig] = {
    StreamConstant.LINKS_EVENT_STREAM:CallbacksConfig(**{
        'sub':True,
        'count':MS_1000*4,
        'block':MS_1000*5,
        'stream':True
    }),
    StreamConstant.EMAIL_EVENT_STREAM:CallbacksConfig(**{
        'sub':True,
        'count':MS_1000,
        'block':MS_1000*15,
        'wait':70,
        'stream':True
    }),
    StreamConstant.TWILIO_REACTIVE:CallbacksConfig(**{
        'sub':True,
        'stream':False}),
    
    StreamConstant.EMAIL_TRACKING:CallbacksConfig(**{
        'sub':False,
        'stream':True,
        'block':MS_1000*2,
        'wait':5,
    }),

    StreamConstant.TWILIO_TRACKING_CALL:CallbacksConfig(
        sub=False,
        stream=True,
        wait=5,
        block=MS_1000*5
    ),
    StreamConstant.TWILIO_TRACKING_SMS:CallbacksConfig(
        sub=False,
        stream=True,
        wait=5,
        block=MS_1000*5
    ),
    StreamConstant.TWILIO_EVENT_STREAM_CALL:CallbacksConfig(
        sub=True,
        stream=True,
        wait=45,
        block=MS_1000*15,
        count=MS_1000*5,

    ),
    StreamConstant.TWILIO_EVENT_STREAM_SMS:CallbacksConfig(
        sub=True,
        stream=True,
        wait=45,
        block=MS_1000*15,
        count=500,
    ),
    StreamConstant.CONTACT_CREATION_EVENT:CallbacksConfig(
        sub=False,
        stream=True,
        wait = 60*60*6,
        block=MS_1000*10,
        count=1000
    ),
    StreamConstant.CONTACT_SUBS_EVENT:CallbacksConfig(
        sub=False,
        stream=True,
        wait = 60*60*4,
        block=MS_1000*20,
        count=10000
    ),
    StreamConstant.CELERY_RETRY_MECHANISM:CallbacksConfig(
        sub=False,
        stream=True,
        wait=10,
        block=10,
        count=1000,
    ),

    SubConstant.SERVICE_STATUS:CallbacksConfig(
        sub=True,
        stream=False
    ),
    SubConstant.MINI_SERVICE_STATUS:CallbacksConfig(
        sub=True,
        stream=False,
    ),
    StreamConstant.S3_EVENT_STREAM:CallbacksConfig(
        sub=False,
        stream=True,
        count=100,
        block=MS_1000*10,
        wait=60*2
    )
}