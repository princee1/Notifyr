from dataclasses import dataclass
from typing import Dict, Literal
from fastapi import Request
from app.classes.auth_permission import AccessAPIInfo, AuthMechanism, ClientAccessInfo, ClientTypeLiteral
from app.container import Get
from app.depends.dependencies import get_access_info, get_auth_mechanism, get_client_info, get_session_id
from app.services.config_service import ConfigService, WorkerService

configService = Get(ConfigService)
workerService = Get(WorkerService)

@dataclass()
class Bucket:
    bucket:str


KeyFunc = Literal['default','worker','none','ip','subnet','balancer']
SecurityKeyFunc = Literal['group','client','session','access','type','issuer','private']

def constant_cost_func(cost:int):
    def cost_func(request:Request):
        return cost
    
    return cost_func

def client_info_cost_func(cost:Dict[ClientTypeLiteral,int],max_limit:int):
    def cost_func(request:Request):
        clientInfo:ClientAccessInfo = get_client_info(request)
        clientType = clientInfo['client_type']
        unit_cost = cost.get(clientType,1)
        unit_cost = max(1,unit_cost)
        return min(unit_cost,max_limit) 

    return cost_func

def access_info_cost_func(cost:Dict[ClientTypeLiteral,int],max_limit:int):

    def cost_func(request:Request):
        access_type = request.state.accessInfo['type']
        unit_cost = cost.get(access_type,1)
        unit_cost = max(1,unit_cost)
        return min(unit_cost,max_limit)

    return cost_func

def cost_func_by_auth_mechanism(cost:Dict[ClientTypeLiteral,int],max_limit:int):

    access_func = access_info_cost_func(cost,max_limit)
    client_func = client_info_cost_func(cost,max_limit)

    def cost_func(request:Request):
        auth_mechanism = get_auth_mechanism(request)
        if auth_mechanism == 'token':
            return access_func(request)
        else:
            return client_func(request)

    return cost_func

def access_type_token_func(request:Request):
    return request.state.accessInfo['id']

def client_private_key_func(request:Request):
    clientInfo:ClientAccessInfo = get_client_info(request)
    return clientInfo['client_id']

def group_private_key_func(request:Request):
    clientInfo:ClientAccessInfo = get_client_info(request)
    if not (group_id:=clientInfo.get('group_id',None)):
        return client_private_key_func(request)
    return group_id

def session_key_func(request:Request)->str:
    clientInfo:ClientAccessInfo = get_client_info(request)
    return get_session_id(clientInfo)
    return clientInfo['session_id']

def private_key_func(request:Request)->str:
    access_info:AccessAPIInfo = get_access_info(request)
    clientInfo:ClientAccessInfo = get_client_info(request)
    return 'private'

def public_bucket_key_func(bucket:Bucket):
    
    def public_key_func(request:Request):
        return bucket

    return public_key_func

def type_cost_func(auth_mechanism:AuthMechanism):

    if auth_mechanism == 'token':
        def cost_func(request:Request):
            access_info:AccessAPIInfo = get_access_info(request)
            return access_info.get['type']

    elif auth_mechanism == 'userpass':
        def cost_func(request:Request):
            client_info:ClientAccessInfo = get_client_info(request)
            return client_info['client_type']
    
    return cost_func