from typing import Annotated
from fastapi import HTTPException, Header,status
from app.container import Get
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService


def verify_dashboard_token(x_dashboard_token:Annotated[str,Header()]):
    configService:ConfigService = Get(ConfigService)
    securityService:SecurityService = Get(SecurityService)

def verify_dmz_token(x_dmz_token:Annotated[str,Header()]):
    configService:ConfigService = Get(ConfigService)
    securityService:SecurityService = Get(SecurityService)
