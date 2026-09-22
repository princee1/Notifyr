
from typing import Callable, Literal,get_args
from fastapi import Depends, Query, Request, Response
from app.container import GetDependsFunc,Get
from app.services import ConfigService
from app.depends.dependencies import get_query_params
from app.utils.constant import VariableConstant
from app.utils.globals import CAPABILITIES

configService = Get(ConfigService)
mcp_configuration = lambda:configService.MCP_ENABLED

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

# ----------------------------------------------                                    ---------------------------------- #

summary_query:Callable = get_query_params('summary','false',True)

# ----------------------------------------------                                    ---------------------------------- #

wait_timeout_query = Query(0, description="Time in seconds wait for the response", ge=0, le=VariableConstant.MAX_WAIT_TIMEOUT)

wait_timeout_query:Callable[[Request],int|float] = get_query_params('timeout','-1',True,False,checker= _wrap_checker(
        'timeout',
        lambda v: (isinstance(v, (int, float)) and v >= -1 and v <= VariableConstant.MAX_WAIT_TIMEOUT),
        msg=f"timeout must be between -1 and {VariableConstant.MAX_WAIT_TIMEOUT}"
    ))

# ----------------------------------------------                                    ---------------------------------- #

profile_query:Callable[[Request],str] = get_query_params('profile','main',raise_except=True)
# ----------------------------------------------                                    ---------------------------------- #

force_update_query: Callable[[Request],bool]=get_query_params('force','false',True,raise_except=True)

# ----------------------------------------------                                    ---------------------------------- #

DeleteMode = Literal['hard','soft']

delete_mode_query:Callable[[Request],DeleteMode] = get_query_params('mode','soft',False,raise_except=True,checker=_wrap_checker('mode',lambda v: v in get_args(DeleteMode),choices=list(get_args(DeleteMode))))

# ----------------------------------------------                                    ---------------------------------- #

SourceMode = Literal['cache','memory','database']
sources_choices = list(get_args(SourceMode))

source_mode_query:Callable[[Request],SourceMode] = get_query_params('source','memory',False,raise_except=True,checker=_wrap_checker('source',lambda v: v in sources_choices,choices=sources_choices))

# ----------------------------------------------                                    ---------------------------------- #
ScopeMode = Literal['all','single']
scope_choices = list(get_args(ScopeMode))
scope_mode_query:Callable[[Request],ScopeMode] = get_query_params('scope','single',False,raise_except=True,checker=_wrap_checker('scope',lambda v: v in scope_choices,choices=scope_choices))