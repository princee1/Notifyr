from fastapi import Depends, Response,Request,status
from pydantic import BaseModel
from app.classes.auth_permission import AuthPermission, Role
from app.container import InjectInMethod
from app.decorators.handlers import WebSocketHandler
from app.decorators.permissions import BalancerPermission, JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource,HTTPRessource, HTTPStatusCode, UseHandler, UseLimiter, UsePermission, UseRoles
from app.depends.dependencies import get_auth_permission
from app.services.config_service import ConfigService
from app.services.health_service import HealthService
from app.services.security_service import JWTAuthService, SecurityService
from app.websockets.ping_pong_ws import PingPongWebSocket

class AppSpec(BaseModel):
    cpu_count:int
    ram:int
    weight:float
    process_count:int

class NotifyInfo(BaseModel):
    spec:AppSpec
    

TOKEN_NAME= 'X-PING-PONG-TOKEN'

@HTTPRessource(websockets=[PingPongWebSocket])
class PingPongRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,healthService:HealthService,securityService:SecurityService,jwtAuthService:JWTAuthService,configService:ConfigService):
        super().__init__()
        self.healthService = healthService
        self.securityService= securityService
        self.jwtAuthService = jwtAuthService
        self.configService = configService

    #@UseLimiter()
    @UsePermission(BalancerPermission)
    @UseHandler(WebSocketHandler)
    @HTTPStatusCode(status.HTTP_101_SWITCHING_PROTOCOLS)
    @BaseHTTPRessource.Get('/permission/{ws_path}/',response_model=AppSpec,response_description='The Spec of the server')
    def issue_ping_permission(self,ws_path:str,request:Request,response:Response):
        self._check_ws_path(ws_path)
        run_id = self.websockets[PingPongWebSocket.__name__].run_id
        token = self.jwtAuthService.encode_ws_token(run_id,ws_path,3600)
        response.headers.append(TOKEN_NAME,token)
        return {
            'cpu_count':4,
            'ram':4096,
            'weight':1,
            'process_count':8,
        }


        

    @UseRoles([Role.ADMIN])
    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.Get('/')
    def check_health(self,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...
    
    @UseRoles([Role.ADMIN])
    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.Post('/')
    def set_health_config(self,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...



# TODO add a custom auth key for the connection with the load balancer 