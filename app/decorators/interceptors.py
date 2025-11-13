from sched import scheduler
from typing import Any, Type
from fastapi.responses import JSONResponse
from typing_extensions import Literal
from fastapi import BackgroundTasks, Request, Response,status
from app.container import Get
from app.definition._cost import Cost, DataCost, SimpleTaskCost
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
        

class TaskCostInterceptor(Interceptor):
    
    def __init__(self,singular_static_cost:int|None=None,retry_limit=20):
        super().__init__(False, True)
        self.redisService = Get(RedisService)
        self.costService = Get(CostService)
        self.reactiveService = Get(ReactiveService)

        self.retry_limit=retry_limit
        self.singular_static_cost = singular_static_cost


    async def intercept_before(self,*args,**kwargs):
        cost:SimpleTaskCost = kwargs.get('cost')
        APIFilterInject(cost.register_meta_key)(**kwargs)
        APIFilterInject(cost.compute_cost)(**kwargs)
        balance_before = await self.costService.deduct_credits(cost.credit_key,cost.purchase_cost,self.retry_limit)
        cost.register_state(balance_before)

    async def intercept_after(self, result:Any,cost:SimpleTaskCost,broker:Broker,response:Response):
        await self.costService.refund_credits(cost.credit_key,cost.refund_cost)
        receipt = cost.receipt
        print(receipt)
        broker.push(...,...)
        

class DataCostInterceptor(Interceptor):
    
    def __init__(self,credit:str,mode:Literal['refund','purchase']='purchase',price=1,retry_limit=20):
        super().__init__(False, False)

        self.mode = mode
        self.credit=credit
        self.price = price

        self.retry_limit = retry_limit
        self.costService = Get(CostService)

    async def intercept_before(self,*args,**kwargs):
        match self.mode:
            case 'purchase':
                cost:DataCost = kwargs.get('cost',None)
                cost.credit_key = self.credit
                if cost!=None:
                    APIFilterInject(cost.pre_purchase)(**kwargs)
                price = self.price if cost == None else cost.purchase_cost
                await self.costService.check_enough_credits(self.credit,price)
                if cost!=None:
                    cost.reset_bill()
            case 'refund':
                ...      
            case _:
                ...
            
    async def intercept_after(self, result:Any,*args,**kwargs):
        response:Response = kwargs.get('response')
        request:Request = kwargs.get('request')
        broker:Broker = kwargs.get('broker')
        cost:DataCost = kwargs.get('cost',None)
        match self.mode:
            case 'purchase':
                if cost!=None:
                    APIFilterInject(cost.post_purchase)(result,**kwargs)
                price = self.price if cost == None else cost.purchase_cost
                await self.costService.deduct_credits(self.credit,price,self.retry_limit)

            case 'refund':
                cost.credit_key = self.credit
                if cost!=None:
                    APIFilterInject(cost.refund)(result,**kwargs)
                price = self.price if cost == None else cost.refund_cost
                if price > 0:
                    await self.costService.refund_credits(self.credit,cost.refund_cost)
            case _:
               ...

        #TODO push receipt