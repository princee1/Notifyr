from typing import Any, Dict, Literal, Optional
import aiohttp
import asyncio
from urllib.parse import urlparse
from pydantic import BaseModel, ValidationError
from app.definition._tool import ExecutionTool,Tool,ContextPipelineTool
from app.models.odm.outbound_model import HTTPOutboundModel, OutboundCredentials
from app.services.config_service import ConfigService
from app.services.custom_service import CustomService
from app.models.tools_model import APIToolModel
from app.services.profile_service import ProfileMiniService


# Custom API Tool Exceptions
class APIToolError(Exception):
    """Base exception for API Tool errors"""
    pass

class APIToolTimeoutError(APIToolError):
    """Raised when API request times out"""
    pass

class APIToolConnectionError(APIToolError):
    """Raised when connection to API fails"""
    pass

class APIToolHTTPStatusError(APIToolError):
    """Raised when API returns an error HTTP status code"""
    def __init__(self, status_code: int, reason: str, url: str):
        self.status_code = status_code
        self.reason = reason
        self.url = url
        super().__init__(f"HTTP {status_code} {reason}: {url}")

class APIToolResponseParsingError(APIToolError):
    """Raised when response body cannot be parsed"""
    pass

class APIToolValidationError(APIToolError):
    """Raised when request parameters fail validation"""
    def __init__(self, when:Literal['after','before'],message:str):
        self.when = when
        self.message = message
    pass


class APIBaseTool:
    def __init__(self,configService:ConfigService,customService:CustomService,httpOutboundService:ProfileMiniService[HTTPOutboundModel]):
        self.outboundService = httpOutboundService
        self.configService = configService
        self.customService = customService
        self.client = aiohttp.ClientSession()
        self.models:dict[str,type[BaseModel]]= {}
    
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
  

    async def request(self, method: str, path: Dict[str, Any], query: Dict[str, Any], body: Optional[Dict] = None):
        """Execute API request with comprehensive error handling"""
        
        try:
            if method.upper() not in self.outboundService.model.method:
                raise APIToolValidationError('before',f'Method not valid: {method}')
        
            url = self._config.url.build_url(path, query)
            BodyModel:type[BaseModel] = self.models.get(self._config.body,None)

            headers = {}
            body = BodyModel(**body).model_dump()  if isinstance(body,dict) and BodyModel else None
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
                    
                    return res_body
                else:
                    return response.text()
        except asyncio.TimeoutError:
            raise APIToolTimeoutError(f"Request timeout while accessing {url}")
        except (aiohttp.ClientConnectorError,aiohttp.ClientError,aiohttp.ClientSSLError,aiohttp.ClientConnectionError) as e:
            raise APIToolConnectionError(f"Connection failed to {url}: {str(e)}")
        except (ValidationError,ValueError) as e:
            raise APIToolValidationError('after',f"Invalid parameters: {str(e)}")
        except Exception as e:
            raise APIToolError(f"Unexpected error during API request: {str(e)}")

    @property
    def _config(self)->APIToolModel:
        return self.config
    
    def to_credentials(self)->OutboundCredentials:
        return self.outboundService.credentials.to_plain()

class APIFetchTool(APIBaseTool, ContextPipelineTool):
    
    def __init__(self, configService: ConfigService, httpOutboundService: ProfileMiniService[HTTPOutboundModel], customService: CustomService, config: APIToolModel):
        super().__init__(configService, customService, httpOutboundService)
        ContextPipelineTool.__init__(self, config)
        self.after_init()

    async def __call__(self, body: Optional[Dict[str, Any]] = None, path: Dict[str, Any] = {}, query: Dict[str, Any] = {}) -> Dict[str, Any]:
        async with self.customService.statusLock.reader:
            async with self.outboundService.statusLock.reader:
                return await self.request(method='GET', path=path, query=query, body=body)

    
class APIControlTool(APIBaseTool, ExecutionTool):

    def __init__(self, configService: ConfigService, httpOutboundService: ProfileMiniService[HTTPOutboundModel], customService: CustomService, config: APIToolModel):
        super().__init__(configService, customService, httpOutboundService)
        ExecutionTool.__init__(self, config)
        self.after_init()
  
    async def __call__(self, method:str,body:Optional[Dict[str,Any]]=None,path:Dict[str,Any]={},query:Dict[str,Any]={}) -> Dict[str, Any]:
        async with self.customService.statusLock.reader:
            async with self.outboundService.statusLock.reader:
                return await self.request(method=method, path=path,body=body,query=query)

