from fastapi import Response,Request,status
from app.classes.auth_permission import Role
from app.container import InjectInMethod
from app.decorators.handlers import WebSocketHandler
from app.decorators.permissions import BalancerPermission, JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource,HTTPRessource, HTTPStatusCode, UseHandler, UseLimiter, UsePermission, UseRoles
from app.services.health_service import HealthService
from app.services.security_service import JWTAuthService, SecurityService
from app.websockets.ping_pong_ws import PingPongWebSocket


@HTTPRessource(websockets=[PingPongWebSocket])
class PingPongRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,healthService:HealthService,securityService:SecurityService,jwtAuthService:JWTAuthService):
        super().__init__()
        self.healthService = healthService
        self.securityService= securityService
        self.jwtAuthService = jwtAuthService

    #@UseLimiter()
    @UsePermission(BalancerPermission)
    @UseHandler(WebSocketHandler)
    @HTTPStatusCode(status.HTTP_101_SWITCHING_PROTOCOLS)
    @BaseHTTPRessource.Get('/permission/{ws_path}/')
    def issue_ping_permission(self,ws_path:str,request:Request,response:Response,):
        self._check_ws_path(ws_path)
        run_id = self.websockets[PingPongWebSocket.__name__].run_id
        token = self.jwtAuthService.encode_ws_token(run_id,ws_path,3600)

    @UseRoles([Role.ADMIN])
    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.Get('/')
    def check_health(self,):
        ...
    
    @UseRoles([Role.ADMIN])
    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.Post('/')
    def set_health_config(self,):
        ...



# TODO add a custom auth key for the connection with the load balancer 