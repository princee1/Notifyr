from dataclasses import dataclass
from typing import Any, Callable, Iterable
from app.definition._interface import Interface, IsInterface
from app.interface.timers import CronParams, DateParams, IntervalParams, SchedulerInterface

class EmailInterface:
    def __init__(self,email_address):
        self.email_address = email_address

class EmailSendInterface(Interface,EmailInterface):

    def __init__(self,email_address:str,disposition_notification_to=None,return_receipt_to=None):
        EmailInterface.__init__(self,email_address)
        self.disposition_notification_to = disposition_notification_to
        self.return_receipt_to = return_receipt_to

    def sendTemplateEmail(self, data, meta, images,contact_id=None,email_profile:str=None):
        ...

    def sendCustomEmail(self, content, meta, images, attachment,contact_id=None,email_profile:str=None):
        ...

    def reply_to_an_email(self, content, meta, images, attachment, reply_to, references, contact_ids:list[str]=None):
       ...

    def verify_same_domain_email(self, email: str):
       ...

@dataclass
class Jobs:
    job_name:str
    func: str
    args: Iterable
    kwargs: dict
    trigger:Any

@IsInterface
class EmailReadInterface(SchedulerInterface,EmailInterface):

    JOBS_META ={}

    @classmethod
    def register_job(cls,job_name: str, trigger, args:tuple, kwargs:dict):

        def wrapper(func: Callable):
            func_name = func.__qualname__
            classname =func_name.split('.')[0]
            job_name_prime = f'{job_name} - {func_name}' if job_name else func_name
            params = {
                'job_name': job_name_prime,
                'func': func.__name__,
                'args': args,
                'kwargs': kwargs,
                'trigger':trigger
            }
            job = Jobs(**params)

            if classname not in cls.JOBS_META:
                cls.JOBS_META[classname] = []
            
            cls.JOBS_META.append(job)

            return func
        return wrapper
    
    def __init__(self,email_address:str, misfire_grace_time = None):
        SchedulerInterface.__init__(self,misfire_grace_time)
        EmailInterface.__init__(self,email_address)
        self._schedule_jobs()
    
    def _schedule_jobs(self,id=None):
        jobs:list[Jobs] = EmailReadInterface.JOBS_META.get(self.__class__.__name__,[])
        for j in jobs:
            func = getattr(self,j.func,None)
            if func == None:
                continue
                
            self._schedule(func,j.args,j.kwargs,j.trigger,id,j.job_name)


setattr(EmailReadInterface,'JOBS_META',{})