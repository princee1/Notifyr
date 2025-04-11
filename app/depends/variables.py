
from typing import Callable
from app.container import GetAttr, GetDependsFunc
from app.depends.dependencies import get_query_params
from app.services.celery_service import TaskService
from app.services.config_service import ConfigService
from app.services.twilio_service import TwilioService


SECURITY_FLAG=GetAttr(ConfigService,'SECURITY_FLAG')

verify_twilio_token: Callable = GetDependsFunc(TwilioService, 'verify_twilio_token')

parse_to_phone_format: Callable = GetDependsFunc(TwilioService, 'parse_to_phone_format')

populate_response_with_request_id: Callable = GetDependsFunc(TaskService,'populate_response_with_request_id')

# ----------------------------------------------                                    ---------------------------------- #

as_async_query:Callable = get_query_params('background','false',True)

runtype_query:Callable=get_query_params('runtype','concurrent',False,checker=lambda v: v in ['parallel','concurrent'])

save_results_query:Callable=get_query_params('save','false',True)

ttl_query:Callable=get_query_params('ttl','60',True)

get_task_results:Callable= get_query_params('get_task_results','true',True)

carrier_info:Callable=get_query_params('carrier_info','true',True,False)

callee_info:Callable=get_query_params('callee_info','false',False,False)