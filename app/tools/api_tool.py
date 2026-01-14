from app.definition._tool import ReAct,Tool,Pipeline
from app.services.mini.outbound.http_outbound_service import HTTPOutboundMiniService
class APIFetchTool(Pipeline):
    
    def __init__(self,httpOutboundService:HTTPOutboundMiniService):
        super().__init__()
        self.outboundService = httpOutboundService
    

class APIControlTool(ReAct):
    
    def __init__(self,httpOutboundService:HTTPOutboundMiniService):
        super().__init__()
        self.outboundService = httpOutboundService

