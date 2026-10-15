from fastapi import Depends, Request, Response

from app.classes.auth_permission import AccessAPIInfo,AuthPermission,ClientAccessInfo
from app.definition._ressource import BaseHTTPRessource, HTTPRessource
from app.depends.dependencies import get_access_info, get_auth_permission, get_client_info
from app.services import SystemService
from app.services import RedisService
from app.services import ReactiveService
from app.services.config_service import ConfigService

@HTTPRessource('system')
class SystemRessource(BaseHTTPRessource):
    
    def __init__(self,configService:ConfigService,reactiveService:ReactiveService,redisService:RedisService,systemService:SystemService):
        super().__init__(None,None)
        self.configService = configService
        self.reactiveService = reactiveService
        self.redisService = redisService
        self.systemService = systemService


    async def live_notification(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission),clientInfo:ClientAccessInfo=Depends(get_client_info),accessInfo:AccessAPIInfo=Depends(get_access_info)):
        ...

    async def read_notification(self,):
        ...

    async def delete_notification(self):
        ...

    async def create_note(self):
        ...

    async def delete_note(self):
        ...

    async def read_notes(self):
        ...