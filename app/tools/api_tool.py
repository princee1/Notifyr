from app.definition._tool import ReAct,Tool,Pipeline
from app.services.config_service import ConfigService
from app.services.mini.outbound.http_outbound_service import HTTPOutboundMiniService
class APIFetchTool(Pipeline):
    
    def __init__(self,configService:ConfigService,httpOutboundService:HTTPOutboundMiniService):
        super().__init__()
        self.outboundService = httpOutboundService
        self.configService = configService
    
    async def __call__(self,):
        ...


class APIControlTool(ReAct):
    
    def __init__(self,configService:ConfigService,httpOutboundService:HTTPOutboundMiniService):
        super().__init__()
        self.outboundService = httpOutboundService
        self.configService = configService

    async def __call__(self,):
        ...

