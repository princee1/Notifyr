import functools
from typing import Annotated, Any, Callable, Literal, TypedDict
from fastapi import Depends, HTTPException, Header, Query, Response, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.classes.auth_permission import AuthPermission, ContactPermission, Role
from app.classes.stream_data_parser import StreamContinuousDataParser, StreamDataParser, StreamSequentialDataParser
from app.container import Get, GetAttr
from app.errors.async_error import ReactiveSubjectNotFoundError
from app.models.contacts_model import ContactORM, ContentSubscriptionORM
from app.models.link_model import LinkORM
from app.models.security_model import BlacklistORM, ClientORM, GroupClientORM
from app.services.admin_service import AdminService
from app.services.celery_service import OffloadTaskService, RunType, TaskService
from app.services.config_service import ConfigService
from app.services.link_service import LinkService
from app.services.logger_service import LoggerService
from app.services.reactive_service import ReactiveService, ReactiveSubject, ReactiveType,Disposable
from app.services.security_service import JWTAuthService, SecurityService
from app.depends.dependencies import get_auth_permission, get_query_params, get_request_id
from tortoise.exceptions import OperationalError
from .variables import *
from time import perf_counter,time


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


async def get_link(link_id:str,lid:str = Depends(get_query_params('lid','sid',raise_except=True,checker=lambda v: v in ['id','name','sid',]))):
    link =None
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail='Link does not exists with the this lid provided')
    return link


async def get_task(request_id: str = Depends(get_request_id), as_async: bool = Depends(as_async_query), runtype: RunType = Depends(runtype_query), ttl=Query(1, ge=0, le=24*60*60), save=Depends(save_results_query), return_results=Depends(get_task_results)):
    taskService: TaskService = Get(TaskService)
    offload_task: Callable = GetAttr(OffloadTaskService, 'offload_task')
    if offload_task == None:
        raise HTTPException(500, detail='Offload task is not available')
    return taskService._register_tasks(request_id, as_async, runtype, offload_task, ttl, save, return_results)


class ServerScopedParams(TypedDict):
    client_id:str | None = None
    group_id:str|None = None
    contact_id:str|None = None
    session_id:str|None = None
    message_id:str|None = None

class IdsTypeParams(TypedDict):
    cid:str |None = None
    gid:str |None = None
    lid:str |None = None
    ctid:str |None = None

    cid_type :Literal['client','contact']

class LinkArgs:
    server_scoped_params = ["client_id", "group_id", "contact_id", "session_id","message_id","link_id"]
    ids_type = ["cid","gid","lid","ctid",]
    
    def __init__(self, request: Request):
        self.request = request
        self._filter_params()
        self.configService:ConfigService = Get(ConfigService)
        self.linkService:LinkService = Get(LinkService)
    
    def __getitem__(self,params)->str|None:
        return self.request.query_params.get(params,None)

    def _filter_params(self) -> dict:
        scoped_params ={}
        ids_type_params = {}
        self._link_params = {}

        for key,value in self.request.items():

            if key in self.ids_type:
                ids_type_params[key] = value

            elif key in self.server_scoped_params:
                scoped_params[key]=value
            else:
                self._link_params[key] =value

        self.server_scoped:ServerScopedParams = ServerScopedParams(**scoped_params) 
        self.ids_type_params:IdsTypeParams = IdsTypeParams(**ids_type_params)

    @property
    def all_params(self):
        return self.request._query_params.__str__()

    @property
    def raw_link_params(self):
        return "&".join([ f'{key}={value}' for key,value in self._link_params.items()])
    
    def raw_filtered_out_params(self,attr,include=()):
        return "&".join([ f'{key}={value}' for key,value in getattr(self,attr).items() if key in include])
    
    def create_link(self,link:LinkORM,path:str,include_scoped_out=(),include_ids_type=()):
        if link == None:
            url = self.request.url.hostname
        else:
            url = link.link_url
            
        if not url.endswith("/"):
            url+="/"
        
        url+=path
        url+="?"
        url+=self.raw_link_params
        url+=self.raw_filtered_out_params('server_scoped',include_scoped_out)
        url+=self.raw_filtered_out_params('ids_type_params',include_ids_type)
        return url
    


class KeepAliveQuery:

    def __init__(self, response: Response, x_request_id: Annotated[str, Depends(get_request_id)], keep_alive: Annotated[bool, Depends(keep_connection)], timeout: int = Query(0, description="Time in seconds to delay the response", ge=0, le=60*3)):
        self.timeout = timeout
        self.response = response
        self.x_request_id = x_request_id
        self.keep_alive = keep_alive

        self.value = {}
        self.error = None
        self.subscription:dict[str,Disposable] = {}


        self.start_time = perf_counter()
        self.rx_subject = None

        self.reactiveService: ReactiveService = Get(ReactiveService)
        self.loggerService: LoggerService = Get(LoggerService)

        self.subject_list:list[str] = []
        self.parser:StreamContinuousDataParser|StreamSequentialDataParser= None

    def set_stream_parser(self,parser):
        self.parser = parser

    def register_subject(self,subject_id:str,only_subject:bool):
        subscription = self.reactiveService.subscribe(
            subject_id,
            on_next= self.on_next,
            on_completed=self.on_complete,
            on_error=self.on_error
        )
        
        if only_subject:
            self.rx_subject = self.reactiveService[subject_id]
        else:
            self.subject_list.append(subject_id)
        
        self.subscription[subject_id] = subscription


    def create_subject(self, reactiveType: ReactiveType):

        if self.keep_alive:
            rx_subject = self.reactiveService.create_subject(self.x_request_id, reactiveType)
            rx_id = rx_subject.id_

            subscription = self.reactiveService.subscribe(
                rx_id,
                on_next=self.on_next,
                on_error=self.on_error,
                on_completed=self.on_complete
            )
            self.rx_subject = rx_subject
            self.subscription[rx_id] =subscription
            return rx_subject.id_
        else:
            return None

    def on_next(self, v: dict):
        try:
            state = v['state']
            if state in self.parser.state:
                value = {state:v['data']}
                self.value.update(value)

            self.parser.up_state(state)

            self.on_error(None)
        except Exception as e:
            self.on_error(e)

    def on_error(self, e: Exception):
        self.process_time = perf_counter() - self.start_time
        self.error = e
        if self.error !=None:
            setattr(self.error, 'process_time', self.process_time)

    def on_complete(self,):
        self.parser._completed = True

    def register_lock(self,subject_id=None):
        if subject_id == None:
            self.rx_subject.register_lock(self.x_request_id)
        else:
            rx_sub = self.reactiveService._subscriptions.get(subject_id,None)
            if rx_sub != None:
                rx_sub.register_lock(self.x_request_id)
            else:
                raise ReactiveSubjectNotFoundError(subject_id)

    def dispose(self):

        self.process_time = perf_counter() - self.start_time
        
        for rx_sub_id in self.subject_list:
            rx_sub = self.reactiveService._subscriptions.get(rx_sub_id,None)
            if rx_sub==None:
                continue
            rx_sub.dispose_lock(self.x_request_id)
            if rx_sub_id in self.subscription:
                self.subscription[rx_sub_id].dispose()

        if self.rx_subject !=None:
            self.subscription[self.rx_subject.id_].dispose()
            self.reactiveService.delete_subject(self.rx_subject.id_)
            
    async def wait_for(self, result_to_return: Any = None, coerce: str = None,subject_id=None):
        if self.keep_alive:
            if subject_id == None:
                rx_sub = self.rx_subject
            else:
                rx_sub = self.reactiveService._subscriptions.get(subject_id,None)
                if rx_sub != None:
                    rx_sub.register_lock(self.x_request_id)
                else:
                    raise ReactiveSubjectNotFoundError(subject_id)
            current_timeout = self.timeout
            current_time = time()

            while True:
                await rx_sub.wait_for(self.x_request_id,current_timeout, result_to_return)
                if self.error != None:
                    raise self.error
                
                if self.parser.completed:
                    break
                rx_sub.lock_lock(self.x_request_id)

                delta = self._compute_delta(current_timeout, current_time)
                current_time= time()
                current_timeout -=delta 

            key = 'value' if coerce == None else coerce
            return {
                key: self.value,
                'results': result_to_return,
            }
        else:
            return result_to_return

    def _compute_delta(self, current_timeout, current_time):
        delta= time() - current_time

        if delta> current_timeout:
            raise TimeoutError
        return delta

    def __repr__(self):
        subj_id = None if self.rx_subject == None else self.rx_subject.id_
        return f'KeepAliveQuery(timeout={self.timeout}, subject_id={subj_id}, request_id={self.x_request_id})'
    