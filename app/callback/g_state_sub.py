from typing import Any
from app.container import Get
from app.definition._service import __CLASS_DEPENDENCY
from app.utils.constant import SubConstant


async def Set_Service_Status(v:Any):
    print(v)
    return

G_State_Subs = {
    SubConstant.SERVICE_STATUS:Set_Service_Status
}