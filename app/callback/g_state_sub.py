import traceback
from typing import Any
from app.container import Get
from app.definition._service import _CLASS_DEPENDENCY, BaseService, ServiceStatus,StateProtocol
from app.utils.constant import SubConstant




async def Set_Service_Status(message:StateProtocol):
    
    try:
        print("Starting..")
        service:BaseService = Get(_CLASS_DEPENDENCY[message['service']])
        
        async with service.statusLock.writer:
            service.service_status = ServiceStatus(message['status'])
        
        async with service.statusLock.writer:
            if message['to_destroy']:
                service.destroy()
            
            if message['to_build']:
                service.build()
            
        print("Ending...")
        return
    except Exception as e:
        traceback.print_exc()

G_State_Subs = {
    SubConstant.SERVICE_STATUS:Set_Service_Status
}