from app.container import Get
from app.definition._service import __CLASS_DEPENDENCY
from app.utils.constant import SubConstant


def Set_Service_Status():
    ...

Callback_Subs = {
    SubConstant.SERVICE_STATUS:Set_Service_Status
}