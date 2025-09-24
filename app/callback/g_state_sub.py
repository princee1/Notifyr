import asyncio
import traceback
from typing import Any
from app.container import Get
from app.definition._service import _CLASS_DEPENDENCY, DEFAULT_BUILD_STATE, DEFAULT_DESTROY_STATE, BaseService, ServiceStatus,StateProtocol, VariableProtocol
from app.interface.timers import SchedulerInterface
from app.utils.constant import SubConstant
from app.classes.profiles import ProfileStateProtocol


class ServiceStateScheduler(SchedulerInterface):
    ...


async def Set_Service_Status(message:StateProtocol):
    
    try:
        print("Starting..")
        service:BaseService = Get(_CLASS_DEPENDENCY[message['service']])
        
        async with service.statusLock.writer:

            if message['status'] is not None:
                service.service_status = ServiceStatus(message['status'])
        
            if message['to_destroy']:
                service._destroyer(True,message.get('destroy_state',DEFAULT_DESTROY_STATE))
            
            if message['to_build']:
                build = True
                if not message.get('bypass_async_verify',False):
                    build = await service.async_verify_dependency()
                
                if build:
                    service._builder(True,message.get('build_state',DEFAULT_BUILD_STATE),force_sync_verify=message.get('force_sync_verify',False))

            if 'callback_state_function' in message and message['callback_state_function'] != None:
                callback_state_function = getattr(service,message['callback_state_function'],None)
                if callback_state_function != None and callable(callback_state_function):
                    if asyncio.iscoroutinefunction(callback_state_function):
                        var_ = await callback_state_function()
                    else:
                        var_ = callback_state_function()

                service.report('variable',var_,)

        print("Ending...")
        return
    except Exception as e:
        traceback.print_exc()

async def Set_Service_Variables(message:VariableProtocol):
    try:
        print("Starting..")
        service:BaseService = Get(_CLASS_DEPENDENCY[message['service']])
        async with service.statusLock.writer:

            if message['variables'] is not None:
                for key,value in message['variables'].items():
                    if hasattr(service,key):
                        setattr(service,key,value)
                    
            if message['variables_function'] is not None:

                variables_function = getattr(service,message['variables_function'],None)
                if variables_function != None and callable(variables_function):
                    if asyncio.iscoroutinefunction(variables_function):
                        await variables_function()
                    else:
                        variables_function()
    
        print("Ending...")
        return
    except Exception as e:
        traceback.print_exc()

async def ProfilStatus(message:ProfileStateProtocol):
    ...

async def Schedule_State_Service():
    ...

G_State_Subs = {
    SubConstant.SERVICE_STATUS:Set_Service_Status,
    SubConstant.SERVICE_VARIABLES:Set_Service_Variables,
}