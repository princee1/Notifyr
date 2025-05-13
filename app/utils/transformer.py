from typing import Callable
from humanize import naturaltime, naturaldelta
from pytimeparse.timeparse import timeparse



def split_by(split=" ")->Callable[[str],str]:
    def _split_by(value):
        return split.join(iter(value))
    return _split_by

def natural_time(value:str):
    value=float(value)
    return naturaltime(value,future=True)


def parse_time(value: str) -> int:
    parsed_time = timeparse(value)
    if parsed_time is None:
        raise ValueError(f"Unable to parse time from value: {value}")
    return parsed_time

coerce = {

}

transform={
    'naturaltime':natural_time
}

transform.update({'split_by_'+key:split_by(key)  for key in [" ",".","-","#"] })

def none_to_empty_str(val:dict):
    for key,values in val.items():
        if values == None:
            val[key] = ''
        if isinstance(values,(dict)):
            none_to_empty_str(values)

def empty_str_to_none(val:dict):
    for key,values in val.items():
        if values == '':
            val[key] = None
        if isinstance(values,(dict)):
            empty_str_to_none(values)
        
