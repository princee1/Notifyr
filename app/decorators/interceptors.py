from sched import scheduler
from typing import Any, Type
from fastapi.responses import JSONResponse
from typing_extensions import Literal
from fastapi import BackgroundTasks, Request, Response,status
from app.container import Get
from app.definition._cost import Cost
from app.definition._utils_decorator import Interceptor, InterceptorDefaultException
from app.depends.class_dep import Broker, KeepAliveQuery
from app.depends.dependencies import get_request_id
from app.depends.res_cache import ResponseCacheInterface
from app.services.cost_service import CostService
from app.services.database_service import MemCachedService, RedisService
from app.services.reactive_service import ReactiveService
from app.utils.helper import APIFilterInject, SkipCode, copy_response

class KeepAliveResponseInterceptor(Interceptor):
    
    def intercept_before(self):
        ...

    def intercept_after(self,result:Any|Response, keepAliveConn:KeepAliveQuery,request:Request):
        keepAliveConn.dispose()


class ResponseCacheInterceptor(Interceptor):

    def __init__(self,mode:Literal['invalid-only','cache'],cacheType:Type[ResponseCacheInterface],hit_status_code=status.HTTP_200_OK,raise_default_exception=True):
        super().__init__(False,False)
        self.mode = mode
        self.cacheType = cacheType
        self.memCachedService = Get(MemCachedService)
        self.hit_status_code = hit_status_code
        self.raise_default_exception = raise_default_exception

    async def intercept_before(self,*args,**kwargs):
        if self.mode != 'cache':
            return
        
        result = await self.cacheType.Get(**kwargs)
        if result == None:
            return
        
        response:Response = kwargs.get('response')
        response.status_code = self.hit_status_code

        if not self.raise_default_exception:
            raise SkipCode(result)
        
        raise InterceptorDefaultException(response=copy_response(JSONResponse(result),response))

    async def intercept_after(self, result:Any,*args,**kwargs):
        backgroundTasks:BackgroundTasks = kwargs.get('backgroundTasks')

        if self.mode == 'cache':
            backgroundTasks.add_task(self.cacheType.Set,result,**kwargs)
        else:
            backgroundTasks.add_task(self.cacheType.Delete,**kwargs)
        

class CostInterceptor(Interceptor):
    
    def __init__(self,singular_static_cost:int|None=None,retry_limit=5):
        super().__init__(False, True)
        self.singular_static_cost = singular_static_cost
        self.redisService = Get(RedisService)
        self.costService = Get(CostService)
        self.reactiveService = Get(ReactiveService)
        self.retry_limit=retry_limit

    
    async def intercept_before(self,*args,**kwargs):
        cost:Cost = kwargs.get('cost')
        cost.register_request_id(await get_request_id(kwargs.get('request')))
        request_cost = self.singular_static_cost if self.singular_static_cost else APIFilterInject(cost.compute_cost)(**kwargs)
        balance_before = await self.costService.deduct_credits(cost.credit_key,request_cost,self.retry_limit)
        cost.register_state(balance_before)

    async def intercept_after(self, result:Any,cost:Cost,broker:Broker):
        await self.costService.refund_credits(cost.credit_key,cost.refund_cost)
        broker.push(...,cost.receipt)
        