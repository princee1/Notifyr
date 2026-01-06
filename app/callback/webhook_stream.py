from typing import Any, TypedDict
from app.errors.service_error import MiniServiceDoesNotExistsError
from app.services.mini.webhook.db_webhook_service import DBPayload, DBWebhookInterface, WebhookBulkUploadError
from app.services.ntfr.webhook_service import WebhookService
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

class WebhookEntries(TypedDict):
    ids: list[str]
    vals: list[DBPayload]

async def DB_Webhook_Stream(entries:list[tuple[str,DBPayload]]):

    redisService = Get(RedisService)
    webhookService:WebhookService  = Get(WebhookService)
    valid_entries = set()
    invalid_entries = set()
    payloads:dict[str,WebhookEntries] = {}

    print(entries)
    for ids,val in entries:
        mini_service_id = val['mini_service_id']
        if mini_service_id not in payloads:
            payloads[mini_service_id] = WebhookEntries(ids=[],vals=[])
        payloads[mini_service_id]['ids'].append(ids)
        payloads[mini_service_id]['vals'].append(val['data'])

    async with webhookService.statusLock.reader:
        for mini_service_id, webhook_entries in payloads.items():
            try:
                vals = webhook_entries['vals']
                ids = webhook_entries['ids']
                miniService:DBWebhookInterface = webhookService.MiniServiceStore.get(mini_service_id)
                await miniService.bulk(vals)
                valid_entries.update(ids)
            except MiniServiceDoesNotExistsError as e:
                invalid_entries.update(ids)
                continue
            except WebhookBulkUploadError as e:
                invalid_entries.update(ids)
                continue
        
    return valid_entries


Webhook_Stream = {
    StreamConstant.S3_EVENT_STREAM: S3_Event_Stream,
    StreamConstant.DB_WEBHOOK_STREAM: DB_Webhook_Stream,
}