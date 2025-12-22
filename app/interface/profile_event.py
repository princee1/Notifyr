import asyncio
import functools
from typing import Callable, Self
from app.classes.profiles import ProfileModelException
from app.definition._interface import Interface, IsInterface
from app.services.database.redis_service import RedisService

@IsInterface
class ProfileEventInterface(Interface):
    
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
    
    @staticmethod
    def EventWrapper(func: Callable):

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            self: Self = args[0]
            try:
                result = await func(*args,**kwargs)
                await self.async_stream_event(*result[1], **result[2])
                result = result[0]
                return result
            except ProfileModelException as e:
                await self.async_stream_event(e.topic,e.error)
                return e.error
            
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            self: Self = args[0]
            try:
                result = func(*args,**kwargs)
                self.sync_stream_event(*result[1], **result[2])
                result = result[0]
                return result
            except ProfileModelException as e:
                self.sync_stream_event(e.topic,e.error)
                return e.error
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    redis_event_callback = (async_stream_event,sync_stream_event)
