from fastapi import Depends, Response, Request, status
from pydantic import BaseModel
from app.classes.auth_permission import AuthPermission, Role
from app.container import InjectInMethod
from app.decorators.handlers import FastAPIHandler, WebSocketHandler
from app.decorators.permissions import BalancerPermission, JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPRessource, HTTPStatusCode, UseHandler, UseLimiter, UsePermission, UseRoles
from app.depends.dependencies import get_auth_permission
from app.services.task_service import CeleryService, TaskService
from app.services.config_service import ConfigService
from app.services.health_service import HealthService
from app.services.security_service import JWTAuthService, SecurityService
from app.websockets.ping_pong_ws import PingPongWebSocket
from app.definition._service import PROCESS_SERVICE_REPORT

class AppSpec(BaseModel):
    CpuCount: int
    Ram: float
    Weight: float
    Workers: int

class NotifyrInfo(BaseModel):
    Spec: AppSpec
    InstanceId: str
    ParentPid:str
    Capabilities:list[str]


TOKEN_NAME = 'X-PING-PONG-TOKEN'
PING_PONG_PREFIX = 'ping-pong'

@HTTPRessource(prefix=PING_PONG_PREFIX, websockets=[PingPongWebSocket])
class PingPongRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, securityService: SecurityService, jwtAuthService: JWTAuthService, configService: ConfigService,taskService:TaskService,celeryService:CeleryService):
        super().__init__()

        self.healthService = self.get(HealthService)
        self.securityService = securityService
        self.jwtAuthService = jwtAuthService
        self.configService = configService
        self.taskService = taskService
        self.celeryService = celeryService

    #@UseLimiter(limit_value="1/day")
    @UsePermission(BalancerPermission)
    @UseHandler(FastAPIHandler)
    @UseHandler(WebSocketHandler)
    @HTTPStatusCode(status.HTTP_200_OK)
    @BaseHTTPRessource.Get('/permission/{ws_path}/', response_model=NotifyrInfo, response_description='The Spec of the server')
    def issue_ping_permission(self, ws_path: str, request: Request, response: Response):
        self._check_ws_path(ws_path)
        run_id = self.websockets[PingPongWebSocket.__name__].run_id
        token = self.jwtAuthService.encode_ws_token(run_id, ws_path, 3600)
        response.headers.append(TOKEN_NAME, token)
        return self.healthService.notifyr_app_info
    
    @UseRoles([Role.ADMIN])
    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.Get('/')
    def check_health(self, authPermission: AuthPermission = Depends(get_auth_permission)):
        ...

    @UseLimiter(limit_value="5/minutes")
    @UseRoles([Role.ADMIN])
    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.Get('/report')
    def check_report(self, request: Request, authPermission: AuthPermission = Depends(get_auth_permission)):
        return {
            'instance_id':self.configService.INSTANCE_ID,
            'parent_pid':self.configService.PARENT_PID,
            'process_pid':self.configService.PROCESS_PID,
            'report':PROCESS_SERVICE_REPORT
        }


    @UseRoles([Role.ADMIN])
    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.Post('/')
    def set_health_config(self, authPermission: AuthPermission = Depends(get_auth_permission)):
        ...



# TODO add a custom auth key for the connection with the load balancer
