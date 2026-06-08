from typing import Any, Dict, Literal, Optional
import aiohttp
import asyncio
from urllib.parse import urlparse
from pydantic import BaseModel, ValidationError
from app.definition._agent import BaseToolArtifact
from app.definition._tool import ExecutionTool, RetryToolError,Tool,RetrievalTool, ToolContextFactory, ToolRuntime, UnexpectedToolError
from app.models.odm.outbound_model import HTTPOutboundModel, OutboundCredentials,Method
from app.prompt import context_prompt
from app.services.config_service import ConfigService
from app.services.custom_service import CustomService
from app.models.tools_model import APIToolModel
from app.services.profile_service import ProfileMiniService
from langchain.messages import HumanMessage,ToolMessage


# Custom API Tool Exceptions
class APIToolError(Exception):
    """Base exception for API Tool errors"""
    pass

class APIToolTimeoutError(APIToolError):
    """Raised when API request times out"""
    def __init__(self,message:str,timeout:int,when:str):
        self.timeout = timeout
        self.when = when
        self.message = message

class APIToolConnectionError(APIToolError):
    """Raised when connection to API fails"""
    pass

class APIToolHTTPStatusError(APIToolError):
    """Raised when API returns an error HTTP status code"""
    def __init__(self, status_code: int, reason: str, url: str):
        super().__init__(f"HTTP {status_code} {reason}: {url}")
        self.status_code = status_code
        self.reason = reason
        self.url = url
        
class APIToolValidationError(APIToolError):
    """Raised when request parameters fail validation"""
    def __init__(self, when:Literal['after','before'],message:str):
        self.when = when
        self.message = message
    pass

class APIArtifact(BaseToolArtifact):
    headers:dict[str,Any]
    cookies:dict[str,Any]
    status:int
    message:str|dict
    method:Method
    url:str

class APIBaseTool:
    def __init__(self,configService:ConfigService,customService:CustomService,httpOutboundService:ProfileMiniService[HTTPOutboundModel]):
        self.outboundService = httpOutboundService
        self.configService = configService
        self.customService = customService
        self.client = aiohttp.ClientSession()
        self.models:dict[str,type[BaseModel]]= {}

        self.metadata = {}
    
    def after_init(self):
        """Initialize models and validate URL is allowed"""
        schemas = []
        if self._config.body:
            schemas.append(self._config.body)
        if self._config.res:
            schemas.append(self._config.res)
        
        self.models = self.customService.to_schemas(schemas)

        credentials = self.to_credentials()
        allowed_url = credentials.get('url')
        base_url = self._config.url.base_url
        
        # Validate that base_url matches allowed_url
        if not allowed_url:
            raise APIToolValidationError('before',"No allowed URL configured in credentials")
        
        # Parse both URLs to compare scheme and netloc (domain)
        allowed_parsed = urlparse(allowed_url)
        base_parsed = urlparse(base_url)
        
        allowed_origin = f"{allowed_parsed.scheme}://{allowed_parsed.netloc}"
        base_origin = f"{base_parsed.scheme}://{base_parsed.netloc}"
        
        if allowed_origin != base_origin:
            raise APIToolValidationError('before',
                f"Base URL origin '{base_origin}' does not match allowed origin '{allowed_origin}'. "
                f"Tool can only send requests to {allowed_origin}"
            )
  
    async def request(self,tool_call_id:str, method: Method, path: Dict[str, Any], query: Dict[str, Any], body: Optional[Dict] = None):
        """Execute API request with comprehensive error handling"""
        
        try:
            async with ToolContextFactory() as factory:
                if method.upper() not in self.outboundService.model.method:
                    raise APIToolValidationError('before',f'Method not valid: {method}')
            
                url = self._config.url.build_url(path, query)
                BodyModel:type[BaseModel] = self.models.get(self._config.body,None)

                headers = {}
                body = BodyModel(**body).model_dump() if isinstance(body,dict) and BodyModel else None
                credentials = self.to_credentials()

                headers.update(self.outboundService.model.headers)
                headers.update(credentials.get('secret_headers',{}))
                query.update(self.outboundService.model.params or {})
                query.update(credentials.get('secret_params',{}))

                auth = credentials.get('auth',None)
                _auth = aiohttp.BasicAuth(auth['username'],auth['password']) if auth else None 
            
                async with self.client.request(method, url,params =query, headers=headers,auth=_auth,json=body) as response:
                    if response.status >= 400:
                        raise APIToolHTTPStatusError(status_code=response.status,reason=response.reason or 'Unknown Error',url=url)

                    if self._config.res_format == 'json':
                        res_body = await response.json()
                        ResModel:type[BaseModel] = self.models.get(self._config.body,None)
                        if isinstance(res_body,dict) and ResModel:
                            res_body = ResModel.model_construct(**res_body).model_dump()
                        body = res_body
                    else:
                        body = response.text()

                    prompt_context = context_prompt.REST_API_TEMPLATE(body,response.status,response.method)
                    artifact = self.to_artifact(response)
                    factory.update(artifact)     
                
        except APIToolValidationError as e:
            prompt_context  = context_prompt.ERROR_TEMPLATE(e.message,'Retry with the valid data',)
            
        except APIToolHTTPStatusError as e:
            artifact = self.to_artifact(response)
            factory.update(artifact)  
            text = response.text()

            if e.status_code == 429:
                prompt_context =  context_prompt.REST_API_TEMPLATE(text,response.status,response.method)
                raise RetryToolError(factory.as_artifact(),prompt_context,{**self.metadata},tool_call_id)
        
            prompt_context = context_prompt.ERROR_TEMPLATE(f'Text: {text} Status: {e.status_code} Reason: {e.reason}','Depending on the status code, the content and the reason you can try again with updated value')

        except (asyncio.TimeoutError,aiohttp.ConnectionTimeoutError,aiohttp.ServerTimeoutError) as e:
            error = APIToolTimeoutError(e)
            factory.recreate_error(error)
            prompt_context = context_prompt.ERROR_TEMPLATE(error.message,)
            raise RetryToolError(factory.as_artifact(),prompt_context,{**self.metadata},tool_call_id)

        except (aiohttp.ClientConnectorError,aiohttp.ClientError,aiohttp.ClientSSLError,aiohttp.ClientConnectionError) as e:
            error = APIToolConnectionError(e)
            factory.recreate_error(error)
            prompt_context = context_prompt.ERROR_TEMPLATE(error.message)
            raise RetryToolError(factory.as_artifact(),prompt_context,{**self.metadata},tool_call_id)
        
        except ValidationError as e:
            prompt_context = context_prompt.ERROR_TEMPLATE(e.json(),instruction='The request body did not meet what we expected')

        except Exception as e:
            prompt_context = context_prompt.ERROR_TEMPLATE(str(e))
            error = {'args':str(e.args),'type':e.__class__.__name__,'__mode__':'exception'}
            factory.update(error,'error')
            raise UnexpectedToolError(prompt_context,factory.as_artifact(),{**self.metadata},tool_call_id)
    
        return ToolMessage(
            prompt_context,
            artifact = factory.as_artifact(),
            status=factory.status,
            tool_call_id=tool_call_id,
			additional_kwargs={**factory.as_option(),**self.metadata}
            )

    def to_artifact(self,response:aiohttp.ClientResponse)->APIArtifact:
        hashes = set()
        computed_req = f"URL()"
        hashes.add(computed_req)
        return {'cookies':response.cookies,'headers':response.headers,'method':response.method,
                'status':response.status,'url':response.url,'hashes':hashes,'message':response.reason
                }

    @property
    def _config(self)->APIToolModel:
        return self.config
    
    def to_credentials(self)->OutboundCredentials:
        return self.outboundService.credentials.to_plain()

class APIFetchTool(APIBaseTool, RetrievalTool):
    
    def __init__(self, configService: ConfigService, httpOutboundService: ProfileMiniService[HTTPOutboundModel], customService: CustomService, config: APIToolModel):
        super().__init__(configService, customService, httpOutboundService)
        RetrievalTool.__init__(self, config)
        self.after_init()

    async def __call__(self,runtime:ToolRuntime, body: Optional[Dict[str, Any]] = None, path: Dict[str, Any] = {}, query: Dict[str, Any] = {}) -> Dict[str, Any]:
        async with self.customService.statusLock.reader:
            async with self.outboundService.statusLock.reader:
                return await self.request(runtime.tool_call_id,method='GET', path=path, query=query, body=body)
            
    @classmethod
    def to_metadata(cls):
	    return super().to_metadata('HTTP FETCH')
  
class APIControlTool(APIBaseTool, ExecutionTool):

    def __init__(self, configService: ConfigService, httpOutboundService: ProfileMiniService[HTTPOutboundModel], customService: CustomService, config: APIToolModel):
        super().__init__(configService, customService, httpOutboundService)
        ExecutionTool.__init__(self, config)
        self.after_init()
  
    async def __call__(self,runtime:ToolRuntime,method:Method,body:Optional[Dict[str,Any]]=None,path:Dict[str,Any]={},query:Dict[str,Any]={}) -> Dict[str, Any]:
        async with self.customService.statusLock.reader:
            async with self.outboundService.statusLock.reader:
                return await self.request(runtime.tool_call_id,method=method, path=path,body=body,query=query)

    @classmethod
    def to_metadata(cls):
	    return super().to_metadata('HTTP CONTROL')

