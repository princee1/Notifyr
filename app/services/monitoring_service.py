import functools
from typing import Callable, Self
from app.definition._service import BaseService, Service, ServiceStatus
from app.errors.service_error import BuildSkipError, BuildWarningError
from app.services.config_service import ConfigService,MODE
from app.utils.constant import MonitorConstant


@Service()
class MonitoringService(BaseService):
    
    def  __init__(self,configService:ConfigService):
        super().__init__()
        self.configService = configService

    def verify_dependency(self):
        if self.configService.MODE not in [MODE.MONITOR_MODE,MODE.TEST_MODE]:
            raise BuildSkipError
    

    def build(self, build_state = ...):
        from prometheus_client import Counter, Gauge, Histogram

        try:
            self.connection_count = Gauge('http_connections','Active Connection Count')
            self.request_latency = Histogram("http_request_duration_seconds", "Request duration in seconds")
            self.connection_total = Counter('total_http_connections','Total Request Received')
            self.background_task_count = Gauge('background_task','Active Background Working Task')
            self.route_task_count = Gauge('route_task','Active Task Handled by the Route Handler')

            self.monitors={
                'connection_count': self.connection_count,
                'connection_total': self.connection_total,
                'background_task_count': self.background_task_count,
                'route_task_count': self.route_task_count,
                'request_latency':self.request_latency,
                MonitorConstant.REQUEST_LATENCY:self.request_latency,
                MonitorConstant.ROUTE_TASK_COUNT: self.route_task_count,
                MonitorConstant.CONNECTION_TOTAL: self.connection_total,
                MonitorConstant.BACKGROUND_TASK_COUNT: self.background_task_count,
                MonitorConstant.CONNECTION_COUNT: self.connection_count,
            }
        except:
            raise BuildWarningError  

    @staticmethod
    def MonitorDecorator(func:Callable):

        @functools.wraps(func)
        def wrapper(self:Self,key:str|int,*args,**kwargs):
            if self.service_status != ServiceStatus.AVAILABLE:
                return

            if key not in self.monitors:
                raise KeyError
            monitor = self.monitors[key]
            try:
                return func(monitor,*args,**kwargs)
            except AttributeError:
                return        
        return wrapper
    
    @MonitorDecorator
    def gauge_inc(self,gauge,amount=1):    
        return gauge.inc(amount)
    
    @MonitorDecorator
    def gauge_dec(self,gauge,amount=1):
        return gauge.dec(amount)
    
    @MonitorDecorator
    def counter_inc(self,counter):
        return counter.inc()
    
    @MonitorDecorator
    def  histogram_observe(self,histogram,time):
        histogram.observe(time)