
from typing import Callable,get_args
from fastapi import Query, Request, Response
from app.classes.auth_permission import PolicyUpdateMode
from app.classes.celery import AlgorithmType, InspectMode,RunType
from app.classes.env_selector import StrategyType
from app.container import GetAttr, GetDependsFunc
from app.depends.dependencies import get_query_params
from app.classes.broker import SubjectType
from app.classes.email import MimeType
from app.utils.constant import VariableConstant
from app.utils.globals import CAPABILITIES


# Helper: predicate -> validator that returns None when OK, or an error message including valid choices
def _wrap_checker(name: str, predicate: Callable[[object], bool], choices: list | None = None, msg: str | None = None) -> Callable[[object], str | None]:
    def _checker(value):
        try:
            ok = predicate(value)
        except Exception:
            ok = False
        if ok:
            return None
        if choices:
            choices_list = ", ".join(map(str, choices))
            return msg or f"Invalid value for {name!s}: {value!r}. Valid choices: {choices_list}"
        return msg or f"Invalid value for {name!s}: {value!r}"
    return _checker

if CAPABILITIES['twilio']:
    from app.services.twilio_service import TwilioService
    verify_twilio_token: Callable = GetDependsFunc(TwilioService, 'verify_twilio_token')

# ----------------------------------------------                                    ---------------------------------- #

summary_query:Callable = get_query_params('summary','false',True)

# ----------------------------------------------                                    ---------------------------------- #

background_query:Callable = get_query_params('background','true',True)

fallback_query:Callable = get_query_params('fallback','true',True)

split_query: Callable = get_query_params('split','false',True)

runtype_query:Callable=get_query_params('runtype','sequential',False,checker=_wrap_checker('runtype', lambda v: v in get_args(RunType), choices=list(get_args(RunType))))

save_results_query:Callable=get_query_params('save','false',True,raise_except=True)

get_task_results:Callable= get_query_params('get_task_results','true',True)

retry_query:Callable= get_query_params('retry','false',True)

algorithm_query:Callable = get_query_params('algorithm','route',True,checker=_wrap_checker('algorithm', lambda v: v in get_args(AlgorithmType), choices=list(get_args(AlgorithmType))))

strategy_query:Callable = get_query_params('strategy','softmax',True,checker=_wrap_checker('strategy', lambda v: v in get_args(StrategyType), choices=list(get_args(StrategyType))))

wait_timeout_query = Query(0, description="Time in seconds wait for the response", ge=0, le=VariableConstant.MAX_WAIT_TIMEOUT)

wait_timeout_query:Callable[[Request],int|float] = get_query_params('timeout','-1',True,False,checker= _wrap_checker(
        'timeout',
        lambda v: (isinstance(v, (int, float)) and v >= -1 and v <= VariableConstant.MAX_WAIT_TIMEOUT),
        msg=f"timeout must be between -1 and {VariableConstant.MAX_WAIT_TIMEOUT}"
    ))

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

track:Callable[[Request],bool] = get_query_params('track','false',True,raise_except=True)

profile_query:Callable[[Request],str] = get_query_params('profile','main',raise_except=True)
# ----------------------------------------------                                    ---------------------------------- #

verify_url:Callable[[Request],bool] = get_query_params('verify_strategy',None,False,raise_except=True,checker=_wrap_checker('verify_strategy', lambda v: v in ['domain','well-known'], choices=['domain','well-known']))

email_verifier:Callable[[Request],bool] = get_query_params('email_verifier',None,False,raise_except=True,checker=_wrap_checker('email_verifier', lambda v: v in ['smtp','reacherhq'], choices=['smtp','reacherhq']))

# ----------------------------------------------                                    ---------------------------------- #

subject_id_params:Callable[[Request],str] = get_query_params('subject_id',None)

sid_type_params:Callable[[Request],str] = get_query_params("sid_type","plain",checker=_wrap_checker('sid_type', lambda v: v in get_args(SubjectType), choices=list(get_args(SubjectType))))

mime_type_query:Callable[[Request],str] = get_query_params('mime','both',raise_except=True,checker=_wrap_checker('mime', lambda v: v in get_args(MimeType), choices=list(get_args(MimeType))))

#signature_query:Callable[[Request],str] = get_query_params("sign",None,False)
# ----------------------------------------------                                    ---------------------------------- #

global_var_key:tuple[Callable[[Request],str],Callable[[Request],str]] = get_query_params('key',None,True),get_query_params('key',None,True,raise_except=True)

force_update_query: Callable[[Request],bool]=get_query_params('force','false',True,raise_except=True)

# ----------------------------------------------                                    ---------------------------------- #

policy_update_mode_query:Callable[[Request],str] = get_query_params('mode','merge',False,raise_except=True,checker=_wrap_checker('mode', lambda v: v in get_args(PolicyUpdateMode), choices=list(get_args(PolicyUpdateMode))))

# ----------------------------------------------                                    ---------------------------------- #

celery_inspect_mode_query:Callable[[Request],str] = get_query_params('mode','stats',False,raise_except=True,checker=_wrap_checker('mode',lambda m:m in get_args(InspectMode),choices=list(get_args(InspectMode))))