from typing import Any, Type, get_args
from fastapi.responses import JSONResponse
from typing_extensions import Literal
from fastapi import BackgroundTasks, Request, Response,status
from app.container import Get
from app.definition._cost import DataCost, SimpleTaskCost,Bill
from app.definition._utils_decorator import Interceptor, InterceptorDefaultException
from app.depends.res_cache import ResponseCacheInterface
from app.manager.broker_manager import Broker
from app.manager.keep_alive_manager import KeepAliveManager
from app.services.cost_service import CostService
from app.services.database_service import MemCachedService, RedisService
from app.services.reactive_service import ReactiveService
from app.utils.constant import CostConstant, RedisConstant
from app.utils.helper import APIFilterInject, SkipCode, copy_response

class KeepAliveResponseInterceptor(Interceptor):
    
    def intercept_before(self):
        ...

    def intercept_after(self,result:Any|Response, keepAliveConn:KeepAliveManager,request:Request):
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
            raise SkipCode(result,True)
        
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
        bill = cost.generate_bill()
        self.costService.inject_cost_info(response,bill)
        broker.push(RedisConstant.LIMITER_DB,self.costService.bill_key(cost.credit_key),bill)
        
        

class DataCostInterceptor(Interceptor):

    Mode = Literal['refund','purchase']

    def __init__(self,credit:str,mode:Mode='purchase',price=1,retry_limit=20):
        super().__init__(False, False)
        
        if mode not in get_args(self.Mode):
            raise ValueError('Invalid DataCostInterceptor Mode')
        
        self.mode = mode
        self.credit=credit
        self.price = price

        self.retry_limit = retry_limit
        self.costService = Get(CostService)
        self.redisService = Get(RedisService)

    async def intercept_before(self,*args,**kwargs):
        cost:DataCost = kwargs.get('cost',None)
        cost.init(self.price,self.credit,kwargs.get('func_meta',{}).get('cost_definition_name',None))

        match self.mode:
            case 'purchase':
                APIFilterInject(cost.pre_purchase)(**kwargs)
                await self.costService.check_enough_credits(self.credit, cost.purchase_cost)
                cost.reset_bill()
            case 'refund':
                ...      
            
    async def intercept_after(self, result:Any,*args,**kwargs):
        response:Response = kwargs.get('response')
        broker:Broker = kwargs.get('broker')
        cost:DataCost = kwargs.get('cost',None)
        match self.mode:
            case 'purchase':
                APIFilterInject(cost.post_purchase)(result,**kwargs)
                balance_before = await self.costService.deduct_credits(self.credit,cost.purchase_cost,self.retry_limit)
            case 'refund':
                balance_before = await self.costService.get_credit_balance(self.credit)
                APIFilterInject(cost.post_refund)(result,**kwargs)
                await self.costService.refund_credits(self.credit,cost.refund_cost)

        cost.balance_before = balance_before
        bill = cost.generate_bill()
        self.costService.inject_cost_info(response,bill)
        broker.push(RedisConstant.LIMITER_DB,self.costService.bill_key(self.credit),bill)
