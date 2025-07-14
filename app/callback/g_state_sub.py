from typing import Any
from app.container import Get
from app.definition._service import _CLASS_DEPENDENCY, BaseService, ServiceStatus,StateProtocol
from app.utils.constant import SubConstant




async def Set_Service_Status(v:StateProtocol):
    
    print("Starting..")
    service:BaseService = Get(_CLASS_DEPENDENCY[v['service']])
    
    async with service.statusLock.writer:
        service.service_status = ServiceStatus(v['status'])
    
    async with service.statusLock.writer:
        if v['to_destroy']:
            service.destroy()
        
        if v['to_build']:
            service.build()

    
    print("Ending...")
    return

G_State_Subs = {
    SubConstant.SERVICE_STATUS:Set_Service_Status
}