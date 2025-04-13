import functools
from typing import Annotated, Any, Callable
from fastapi import Depends, HTTPException, Header, Query, Response, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.classes.auth_permission import AuthPermission, ContactPermission, Role
from app.container import Get, GetAttr
from app.models.contacts_model import ContactORM, ContentSubscriptionORM
from app.models.security_model import BlacklistORM, ClientORM, GroupClientORM
from app.services.admin_service import AdminService
from app.services.celery_service import OffloadTaskService, RunType, TaskService
from app.services.config_service import ConfigService
from app.services.reactive_service import ReactiveService, ReactiveType
from app.services.security_service import JWTAuthService, SecurityService
from app.depends.dependencies import get_auth_permission, get_query_params, get_request_id
from tortoise.exceptions import OperationalError
from .variables import *
from time import perf_counter


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


@ByPassAdminRole()
@AcceptNone('group_id')
async def _get_group(group_id: str = None, gid: str = None, authPermission: AuthPermission = None) -> GroupClientORM:
    if gid == 'id':
        group = await GroupClientORM.filter(group_id=group_id).first()

    elif gid == 'name':
        group = await GroupClientORM.filter(group_name=group_id).first()

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid GID type")

    if group == None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group does not exist")

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


async def get_contacts(contact_id: str, idtype: str = Query("id"), authPermission: AuthPermission = Depends(get_auth_permission)) -> ContactORM:

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
            raise HTTPException(
                400, {"message": "idtype not not properly specified"})

    if user == None:
        raise HTTPException(404, {"detail": "user does not exists"})

    return user


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


def cost() -> int:
    ...


def key_contact_id() -> str:
    ...


def key_client_id() -> str:
    ...


def key_group_id() -> str:
    ...


async def verify_admin_token(x_admin_token: Annotated[str, Header()]):
    configService: ConfigService = Get(ConfigService)

    if x_admin_token == None or x_admin_token != configService.ADMIN_KEY:
        raise HTTPException(
            status_code=403, detail="X-Admin-Token header invalid")


async def verify_admin_signature(x_admin_signature: Annotated[str, Header()]):
    adminService: AdminService = Get(AdminService)
    securityService: SecurityService = Get(SecurityService)
    configService: ConfigService = Get(ConfigService)

    if x_admin_signature == None:
        ...

    if securityService.verify_admin_signature():
        ...


async def get_client(client_id: str = Depends(get_query_params('client_id')), cid: str = Depends(get_query_params('cid', 'id')), authPermission: AuthPermission = Depends(get_auth_permission)):
    try:
        return await GetClient()(client_id=client_id, cid=cid, authPermission=authPermission)
    except OperationalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.args[0])
        )


async def get_group(group_id: str = Query(''), gid: str = Query('id'), authPermission: AuthPermission = Depends(get_auth_permission)):
    try:
        return await _get_group(group_id=group_id, gid=gid, authPermission=authPermission)
    except OperationalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.args[0])
        )


async def get_client_by_password(credentials: Annotated[HTTPBasicCredentials, Depends(HTTPBasic())], cid: str = Depends(get_query_params('cid', 'id'))):
    security: SecurityService = Get(SecurityService)
    configService: ConfigService = Get(ConfigService)
    key = configService.getenv('CLIENT_PASSWORD_HASH_KEY', 'test')
    error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid username or password",
        headers={"WWW-Authenticate": "Basic"},
    )

    try:
        client: ClientORM = await GetClient(skip=True, raise_=False)(client_id=credentials.username, cid=cid, authPermission=None)
    except OperationalError:
        raise error

    if client == None:
        raise error
    stored_hash, stored_salt = client.password, client.password_salt

    if not security.verify_password(stored_hash, stored_salt, credentials.password, key):
        error

    if not client.can_login:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Cant authenticate right now... get your token from the admin!'
        )

    await client.save()

    return client


@ByPassAdminRole()
@AcceptNone('blacklist_id')
async def _get_blacklist(blacklist_id: str = None):
    blacklist = await BlacklistORM.filter(blacklist_id=blacklist_id).first()
    if blacklist == None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail='Blacklist does not exists')
    return blacklist


async def get_blacklist(blacklist_id: str = Depends(get_query_params('blacklist_id', None))):
    return await _get_blacklist(blacklist_id=blacklist_id)


async def get_task(request_id: str = Depends(get_request_id), as_async: bool = Depends(as_async_query), runtype: RunType = Depends(runtype_query), ttl=Query(1, ge=0, le=24*60*60), save=Depends(save_results_query), return_results=Depends(get_task_results)):
    taskService: TaskService = Get(TaskService)
    offload_task: Callable = GetAttr(OffloadTaskService, 'offload_task')
    if offload_task == None:
        raise HTTPException(500, detail='Offload task is not available')
    return taskService._register_tasks(request_id, as_async, runtype, offload_task, ttl, save, return_results)


class KeepAliveQuery:

    def __init__(self, response: Response, x_request_id: Annotated[str, Depends(get_request_id)], keep_alive: Annotated[bool, Depends(keep_connection)], timeout: int = Query(5, description="Time in seconds to delay the response", ge=5, le=60*3)):
        self.timeout = timeout
        self.response = response
        self.x_request_id = x_request_id
        self.keep_alive = keep_alive

        self.value = None
        self.error = None
        self.subscription = None
        self.start_time = perf_counter()

        self.reactiveService: ReactiveService = Get(ReactiveService)

    def create_subject(self, reactiveType: ReactiveType):

        if self.keep_alive:
            rx_subject = self.reactiveService.create_subject(self.x_request_id, reactiveType)
            rx_id = rx_subject.id_

            self.subscription = self.reactiveService.subscribe(
                rx_id,
                on_next=self.on_next,
                on_error=self.on_error,
            )
            self.rx_subject = rx_subject
            return rx_subject.id_
        else:
            return None

    def on_next(self, v: Any):
        self.value = v

    def on_error(self, e: Exception):
        self.process_time = perf_counter() - self.start_time
        self.error = e
        setattr(self.error, 'process_time', self.process_time)

    def register_lock(self):
        self.rx_subject.register_lock(self.x_request_id)

    def dispose(self):

        if self.subscription:
            self.subscription.dispose()
            self.subscription = None
        
        self.process_time = perf_counter() - self.start_time
        self.rx_subject.dispose_lock(self.x_request_id)

    async def wait_for(self, result_to_return: Any = None, coerce: str = None):
        if self.keep_alive:
            await self.rx_subject.wait_for(self.x_request_id,self.timeout, result_to_return)
            if self.error != None:
                raise self.error
            key = 'value' if coerce == None else coerce
            return {
                key: self.value,
                'results': result_to_return,
            }
        else:
            return result_to_return
