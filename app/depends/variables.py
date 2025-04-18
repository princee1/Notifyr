
from typing import Callable

from fastapi import Request
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

get_task_results:Callable= get_query_params('get_task_results','true',True)

# ----------------------------------------------                                    ---------------------------------- #

carrier_info:Callable[[Request],bool]=get_query_params('carrier_info','true',True)

callee_info:Callable[[Request],bool]=get_query_params('callee_info','false',True)

add_ons:Callable[[Request],bool]=get_query_params('add_ons','false',True)

# ----------------------------------------------                                    ---------------------------------- #

verify_otp:Callable[[Request],bool]=get_query_params('verify_otp','false',True)
"""
    Allow twilio to Verify the user input
"""

keep_connection:Callable[[Request],bool]=get_query_params('keep_connection','false',True)