from typing import Any, overload
from app.classes.celery import CeleryTaskNotFoundError,SCHEDULER_RULES
from app.classes.celery import  CeleryTask, SchedulerModel

from app.definition._service import Service, ServiceClass, ServiceStatus
from .config_service import ConfigService
from app.utils.helper import generateId
from app.task import TASK_REGISTRY,celery_app,compute_name, AsyncResult
from redbeat  import RedBeatSchedulerEntry
from app.utils.helper import generateId
import datetime as dt

@ServiceClass
class CeleryService(Service):

    def __init__(self,configService:ConfigService):
        Service.__init__(self)
        self.configService = configService
        self._task_registry = TASK_REGISTRY

    def trigger_task_from_scheduler(self,scheduler:SchedulerModel,*args,**kwargs):
        celery_task = scheduler.model_dump(mode='python',exclude={'content'})
        celery_task: CeleryTask = CeleryTask(args=args,kwargs=kwargs,**celery_task)
        return self._trigger_task(celery_task,scheduler.schedule_name)


    def trigger_task_from_task(self,celery_task:CeleryTask,schedule_name:str= None):
        return self._trigger_task(celery_task,schedule_name)

    def _trigger_task(self,celery_task:CeleryTask,schedule_name:str=None):
        schedule_id = schedule_name if schedule_name is not None else generateId(25)
        c_type = celery_task['task_type']
        t_name = celery_task['task_name']
        now = dt.datetime.now()
        result = {
            'message': f'[{now}] - Task [{t_name}] received successfully'
        }
        
        if c_type == 'now':
            task_result = TASK_REGISTRY[t_name].delay(*celery_task['args'],**celery_task['kwargs'])
            result.update({'task_id':task_result.id,'type':'task'})
            return result

        options = celery_task['task_option']
        if c_type == 'once':
            task_result = TASK_REGISTRY[t_name].apply_async(**options,args=celery_task['args'],kwargs=celery_task['kwargs'])
            result.update({'task_id':task_result.id,'type':'task'})
            return task_result.id

        schedule = SCHEDULER_RULES[c_type]
        schedule = schedule(**options)
        entry = RedBeatSchedulerEntry(schedule_id,t_name,schedule,args=celery_task['args'],kwargs=celery_task['kwargs'])
        entry.save()
        result.update({'task_id':schedule_id,'type':'schedule'})
        return result
        
    def cancel_task(self,task_id,force=False):
        result = AsyncResult(task_id, app=celery_app)

        if result.state in ["PENDING", "RECEIVED"]:
            result.revoke(terminate=False)

        elif result.state in ["STARTED"]:
            if force:
                result.revoke(terminate=True, signal="SIGTERM")

    def delete_schedule(self,schedule_id:str):
        try:
            schedule_id = f'redbeat:{schedule_id}'
            entry = RedBeatSchedulerEntry.from_key(schedule_id,app=celery_app)
            entry.delete()
        except KeyError:
            raise CeleryTaskNotFoundError

    def seek_schedule(self,schedule_id:str):
        try:
            schedule_id = f'redbeat:{schedule_id}'
            entry = RedBeatSchedulerEntry.from_key(schedule_id,app=celery_app)
            return {
                'total_run_count':entry.total_run_count,
                'due_at':entry.due_at,
                'schedule':entry.schedule,
                'last_run_at':entry.last_run_at
            }
        except KeyError:
            raise CeleryTaskNotFoundError

    def seek_result(self, task_id: str):
        try:
            result = AsyncResult(task_id, app=celery_app)
            response = {
                'task_id': result.id,
                'status': result.status,
                'result': result.result,
                'traceback': result.traceback,
                'date_done': result.date_done,
                'successful': result.successful()
            }
            return response
        except KeyError:
            raise CeleryTaskNotFoundError
    
    def build(self):
        response = celery_app.control.ping()
        if len(response) == 0:
            self.service_status = ServiceStatus.NOT_AVAILABLE
        else:
            self.service_status  = ServiceStatus.AVAILABLE

