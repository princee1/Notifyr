from sched import scheduler
from typing import Any, Type
from fastapi.responses import JSONResponse
from typing_extensions import Literal
from fastapi import BackgroundTasks, Request, Response,status
from app.container import Get
from app.definition._cost import Cost, CreditDeductionFailedError, InsufficientCreditsError, InvalidPurchaseRequestError
from app.definition._utils_decorator import Interceptor, InterceptorDefaultException
from app.depends.class_dep import Broker, KeepAliveQuery
from app.depends.dependencies import get_request_id
from app.depends.res_cache import ResponseCacheInterface
from app.services.cost_service import CostService
from app.services.database_service import MemCachedService, RedisService
from app.services.reactive_service import ReactiveService
from app.utils.constant import RedisConstant
from app.utils.helper import APIFilterInject, SkipCode, copy_response
from app.depends.class_dep import TrackerInterface
from redis.exceptions import WatchError

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

    async def deduct_credits(self,cost_key,purchase_cost:int):
        retry=0
        while retry < self.retry_limit:
            async with self.redisService.redis_limiter.pipeline(transaction=False) as pipe:
                try:
                    await pipe.watch(cost_key)
                    current_balance = await pipe.get(cost_key)

                    if current_balance is None:
                        await pipe.unwatch()
                        raise InvalidPurchaseRequestError

                    if current_balance < purchase_cost:
                        await pipe.unwatch()
                        raise InsufficientCreditsError
                    
                    new_balance = current_balance - purchase_cost

                    pipe.multi()
                    pipe.set(cost_key, new_balance)

                    await pipe.execute()
                    return current_balance

                except WatchError:
                    retry+=1
                    continue
                finally:
                    await pipe.reset()
        
        raise CreditDeductionFailedError
    
    async def intercept_before(self,*args,**kwargs):
        cost:Cost = kwargs.get('cost')
        cost.register_request_id(await get_request_id(kwargs.get('request')))
        request_cost = self.singular_static_cost if self.singular_static_cost else APIFilterInject(cost.compute_cost)(**kwargs)
        balance_before = await self.deduct_credits(cost.cost_key,request_cost)
        cost.register_state(balance_before)

    async def intercept_after(self, result:Any,cost:Cost,broker:Broker):
        if cost.refund_cost > 0:
            await self.redisService.increment(RedisConstant.LIMITER_DB,cost.cost_key,cost.refund_cost)
        broker.push(...,cost.receipt)
        