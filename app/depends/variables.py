
from typing import Callable,get_args

from fastapi import Request
from app.container import GetAttr, GetDependsFunc
from app.depends.dependencies import get_query_params
from app.services.celery_service import TaskService
from app.services.config_service import ConfigService
from app.services.twilio_service import TwilioService

from app.classes.broker import SubjectType


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

track_email:Callable[[Request],bool] = get_query_params('track','false',True)

# ----------------------------------------------                                    ---------------------------------- #

verify_url:Callable[[Request],bool] = get_query_params('verify_strategy',None,False,raise_except=True,checker=lambda v: v in ['domain','well-known'])

email_verifier:Callable[[Request],bool] = get_query_params('email_verifier',None,False,raise_except=True,checker=lambda v:v in ['smtp','reacherhq'])

# ----------------------------------------------                                    ---------------------------------- #

subject_id_params:Callable[[Request],bool] = get_query_params("subject_id",None,)

sid_type_params:Callable[[Request],str] = get_query_params("sid_type","plain",checker=lambda v:v in get_args(SubjectType))