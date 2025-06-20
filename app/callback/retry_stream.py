from app.services.task_service import CeleryService
from app.utils.constant import StreamConstant
from app.utils.helper import unflattened_dict
from app.classes.celery import TaskHeaviness
from app.container import Get, InjectInFunction
from app.utils.transformer import empty_str_to_none


async def Retry_Mechanism(entries:list[tuple[str,dict]]):
    print(f'Treating: {len(entries)} entries for Retry Mechanism Stream')

    valid_entries = set()
    invalid_entries = set()

    celeryService = Get(CeleryService)

    for ids, val in entries:
        empty_str_to_none(val)
        val = unflattened_dict(val)
        val['celery_task']['heaviness'] = TaskHeaviness(val['celery_task']['heaviness'])
        print(val)
        try:
            celeryService.trigger_task_from_task(**val)
            valid_entries.add(ids)
        except Exception as e:
            invalid_entries.add(ids)

    return list(valid_entries.union(invalid_entries))


Retry_Stream ={
    StreamConstant.CELERY_RETRY_MECHANISM:Retry_Mechanism

}