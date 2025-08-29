import asyncio
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
                service._destroyer(True)
            
            if message['to_build']:
                if 'build_function' in message and message['build_function'] != None:
                    build_function = getattr(service,message['build_function'],None)
                    if build_function != None and callable(build_function):
                        if asyncio.iscoroutinefunction(build_function):
                            await build_function()
                        else:
                            build_function()
                else:
                    service._builder(True)
            
        print("Ending...")
        return
    except Exception as e:
        traceback.print_exc()

async def Set_Service_Variables(message:dict):
    ...


G_State_Subs = {
    SubConstant.SERVICE_STATUS:Set_Service_Status
}