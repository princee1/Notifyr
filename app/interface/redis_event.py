import functools
from typing import Callable, Self
from app.definition._interface import Interface, IsInterface
from app.services.database_service import RedisService

@IsInterface
class RedisEventInterface(Interface):
    
    def __init__(self,redisService:RedisService):
        Interface.__init__(self)
        self.redisService = redisService

    async def async_stream_event(self,event_name:str,event:list[dict]|dict):
        
        if not isinstance(event,list):
            event = [event]

        for e in event:
            try:
                await self.redisService.stream_data(event_name, e)
            except Exception as e:
                print('Redis',e) 
            
    def sync_stream_event(self,event_name:str,event:list[dict]|dict):
        if not isinstance(event,list):
            event = [event]

        for e in event:
            try:
                self.redisService.stream_data(event_name, e)
            except Exception as e:
                print('Redis',e) 
    

    redis_event_callback = (async_stream_event,sync_stream_event)
