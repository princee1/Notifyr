from typing import Annotated
from fastapi import HTTPException, Header,status
from app.container import Get
from app.services.admin_service import AdminService
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService


async def verify_admin_token(x_admin_token: Annotated[str, Header()]):
    configService: ConfigService = Get(ConfigService)

    if x_admin_token == None or x_admin_token != configService.ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Admin-Token header invalid")


async def verify_admin_signature(x_admin_signature: Annotated[str, Header()]):
    adminService: AdminService = Get(AdminService)
    securityService: SecurityService = Get(SecurityService)
    configService: ConfigService = Get(ConfigService)

    if x_admin_signature == None:
        ...

    if securityService.verify_admin_signature():
        ...


def verify_dashboard_token(x_dashboard_token:Annotated[str,Header()]):
    ...

def verify_dmz_token(x_dmz_token:Annotated[str,Header()]):
    ...

def verify_api_key(x_api_key:Annotated[str,Header()]):
    ...