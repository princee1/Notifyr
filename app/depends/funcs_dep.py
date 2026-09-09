import functools
from typing import Annotated, Callable
from fastapi import Depends, HTTPException, Header, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.classes.auth_permission import AuthPermission, ClientType, ContactPermission, PolicyModel, Role, filter_asset_permission
from app.container import Get
from app.definition._error import ServerFileError
from app.models.orm.contacts_model import ContactORM, ContentSubscriptionORM
from app.models.orm.link_model import LinkORM
from app.models.orm.security_model import BlacklistModel, ClientORM, GroupClientORM, PolicyMappingORM
from app.services.config_service import ConfigService
from app.services.security_service import JWTAuthService, SecurityService
from app.depends.dependencies import get_auth_permission, get_query_params, get_request_id, wrapper_auth_permission

from app.services.vault_service import VaultService
from app.utils.toolbox import RunInThreadPool
from .variables import *


def AcceptNone(key):

    def depends(func: Callable):

        @functools.wraps(func)
        async def wrapper(**kwargs):
            if key not in kwargs:
                # TODO Raise Warning
                return None
            param = kwargs[key]
            if isinstance(param, str):
                if not param:
                    return None
            else:
                if param == None:
                    return None

            return await func(**kwargs)
        return wrapper

    return depends


def ByPassAdminRole(bypass=False, skip=False):

    def depends(func: Callable):

        @functools.wraps(func)
        async def wrapper(**kwargs):
            if not skip:  # NOTE no need for the authPermission
                authPermission: AuthPermission = kwargs['authPermission']

                # NOTE need to have the authPermission
                if Role.ADMIN not in authPermission['roles'] and not bypass:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")

            return await func(**kwargs)
        return wrapper
    return depends


async def fetch_group(group:str) -> GroupClientORM:
    group = await GroupClientORM.filter(group_id=group).first()
    if group == None:
        raise GroupDoesNotExistError(group)

    return group


def GetClient(bypass: bool = False, accept_admin: bool = False, skip: bool = False, raise_: bool = True):
    @ByPassAdminRole(bypass, skip=skip)
    @AcceptNone(key='client_id')
    async def _get_client(client_id: str | None = None, cid: str = None, authPermission: AuthPermission = None) -> ClientORM:
        if cid == 'id':
            client = await ClientORM.filter(client_id=client_id).first()
        elif cid == 'name':
            client = await ClientORM.filter(client_name=client_id).first()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CID type")

        if client is None:
            if raise_:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Client does not exist")
            else:
                return None

        if client.client_type == 'Admin' and not accept_admin:
            if raise_:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Client does not exist")
            else:
                return None

        return client

    return _get_client


def Get_Contact(skip_permission:bool,raise_file:bool):

    async def get_contacts(contact_id: str, idtype: str = Query("id"), authPermission: AuthPermission = Depends(wrapper_auth_permission)) -> ContactORM:

        if not skip_permission:
            if authPermission == None:
                if Get(ConfigService).SECURITY_FLAG:
                    raise HTTPException(status_code=401, detail="Unauthorized")

            else:
                if Role.CONTACTS not in authPermission['roles']:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Role not allowed")

        match idtype:
            case "id":
                user = await ContactORM.filter(contact_id=contact_id).first()

            case "phone":
                user = await ContactORM.filter(phone=contact_id).first()

            case "email":
                user = await ContactORM.filter(email=contact_id).first()

            case _:
                if raise_file:
                    raise ServerFileError('app/static/error-400-page/index.html',status.HTTP_400_BAD_REQUEST)
                else:
                    raise HTTPException(400, {"message": "idtype not not properly specified"})

        if user == None:
            if not raise_file:
                raise HTTPException(404, {"detail": "user does not exists"})
            else:
                raise ServerFileError('app/static/error-404-page/index.html',status.HTTP_404_NOT_FOUND)


        return user

    return get_contacts


def get_contact_permission(token: str = Query(None)) -> ContactPermission:

    jwtAuthService: JWTAuthService = Get(JWTAuthService)
    if token == None:
        raise  # TODO
    return jwtAuthService.verify_contact_permission(token)


async def get_subs_content(content_id: str, content_idtype: str = Query('id'), authPermission: AuthPermission = Depends(get_auth_permission)) -> ContentSubscriptionORM:

    if Role.SUBSCRIPTION not in authPermission['roles']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Role not allowed")

    match content_idtype:
        case "id":
            content = await ContentSubscriptionORM.filter(content_id=content_id).first()
        case "name":
            content = await ContentSubscriptionORM.filter(name=content_id).first()
        case _:
            raise HTTPException(
                400, {"message": "idtype not not properly specified"})

    if content == None:
        raise HTTPException(
            404, {"message": "Subscription Content does not exists with those information"})


async def get_client_by_password(credentials: Annotated[HTTPBasicCredentials, Depends(HTTPBasic())], cid: str = Depends(get_query_params('cid', 'id'))):
    security: SecurityService = Get(SecurityService)
    configService: ConfigService = Get(ConfigService)
    key = configService.getenv('CLIENT_PASSWORD_HASH_KEY', 'test')
    error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid username or password",
        headers={"WWW-Authenticate": "Basic"},
    )

    return
    if not client.can_login:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Cant authenticate right now... get your token from the admin!'
        )

    await client.save()

    return client


def GetLink(raise_file_error:bool,raise_err:bool=True):

    async def get_link(link_id:str,lid:str = Depends(get_query_params('lid','sid',raise_except=True,checker=lambda v: v in ['id','name','sid',]))):

        match lid:
            case 'id':
                link = await LinkORM.filter(link_id=link_id).first()

            case 'name':
                link = await LinkORM.filter(link_name=link_id).first()

            case 'sid':
                link = await LinkORM.filter(link_short_id=link_id).first()

            case _:
                link = None

        if link == None:
            if raise_file_error:
                raise ServerFileError('app/static/error-404-page/index.html',status.HTTP_404_NOT_FOUND)
            else:
                if raise_err:
                    raise HTTPException(status.HTTP_404_NOT_FOUND,"links not found")
                else:
                    return None

        return link

    return get_link

@RunInThreadPool
def fetch_policy(policy:str):
    vaultService = Get(VaultService) 
    params = vaultService.security_engine.read('policies',policy)
    policy_obj = PolicyModel(**params)
    policy_obj._policy_id = policy
    return policy_obj

def get_template(template:str):
    return template

def get_profile(profile:str):
    return profile

def get_agent(agent:str):
    return agent

def get_policy(policy:str):
    return policy

def get_group(group:str):
    return group

def get_client(client:str):
    return client

def get_blacklist(blacklist:BlacklistModel):
    return blacklist
