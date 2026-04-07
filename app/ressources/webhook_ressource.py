from fastapi import Depends, Response

from app.classes.auth_permission import AuthPermission
from app.container import InjectInMethod
from app.definition._ressource import BaseHTTPRessource, HTTPRessource
from app.depends.dependencies import get_auth_permission
from app.services.config_service import ConfigService
from app.services.workflow_service import WorkflowService


@HTTPRessource('webhook')
class WebhookIncomingRessource(BaseHTTPRessource):
    
    @InjectInMethod()
    def __init__(self,configService:ConfigService,workflowService:WorkflowService,):
        self.configService = configService
        self.workflowService = workflowService
    

    @BaseHTTPRessource.Post('{profile}')
    async def process_events(self,profile:str,request:Response,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...