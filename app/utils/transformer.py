from typing import Callable
from humanize import naturaltime, naturaldelta



def split_by(split=" ")->Callable[[str],str]:
    def _split_by(value):
        return split.join(iter(value))
    return _split_by

def natural_time(value:str):
    value=float(value)
    return naturaltime(value,future=True)

coerce = {

}

transform={
    'naturaltime':natural_time
}

transform.update({'split_by_'+key:split_by(key)  for key in [" ",".","-","#"] })