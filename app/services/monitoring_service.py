from app.definition._service import BaseService, Service
from app.errors.service_error import BuildWarningError
from app.services.config_service import ConfigService
from prometheus_client import Counter, Gauge, Histogram

from app.services.file_service import FileService


@Service()
class MonitoringService(BaseService):
    
    def  __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__()
        self.configService = configService
        self.fileService = fileService
    

    def build(self, build_state = ...):
        try:
            self.connection_count = Gauge('http_connections','Active Connection Count')
            self.request_latency = Histogram("http_request_duration_seconds", "Request duration in seconds")
            self.connection_total = Counter('total_http_connections','Total Request Received')
            self.background_task_count = Gauge('background_task','Active Background Working Task')
            self.route_task_handling_count = Gauge('route_task','Active Task Handled by the Route Handler')
        except:
            raise BuildWarningError  