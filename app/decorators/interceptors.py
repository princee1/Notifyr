from typing import Any, Callable, Type, get_args
from fastapi.responses import JSONResponse
from typing_extensions import Literal
from fastapi import BackgroundTasks, Request, Response,status
from app.classes.cost_definition import CostLessThanZeroError, CostMoreThanZeroError
from app.container import Get, InjectInMethod
from app.definition._cost import Cost, DataCost, SimpleTaskCost,Bill
from app.definition._utils_decorator import Interceptor, InterceptorDefaultException
from app.depends.res_cache import ResponseCacheInterface
from app.manager.broker_manager import Broker
from app.manager.keep_alive_manager import KeepAliveManager
from app.manager.task_manager import TaskManager
from app.services.cost_service import CostService
from app.services.database.memcached_service import MemCachedService

from app.services.database.redis_service import RedisService
from app.services.reactive_service import ReactiveService
from app.utils.constant import CostConstant, RedisConstant
from app.utils.helper import APIFilterInject, SkipCode, copy_response

class RegisterBackgroundTaskInterceptor(Interceptor):

    def intercept_before(self):
        ...

    def intercept_after(self, result:Any,taskManager:TaskManager):
        taskManager.register_backgroundTask()

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

class CacheInterceptor(Interceptor):

    def __init__(self,key_builder:Callable[[Request],str], expires:int,inject_headers=True):
        super().__init__(True, True)
        self.memcachedService = Get(MemCachedService)
        self.key_builder = key_builder
        self.expires = expires
        self.inject_headers = inject_headers

    def intercept_before(self,request:Request,response:Response):
        ...

    def intercept_after(self, result:dict|list):
        ...

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
        response:Response = kwargs.get('response')

        APIFilterInject(cost.register_meta_key)(**kwargs)
        APIFilterInject(cost.compute_cost)(**kwargs)
        bill = cost.generate_bill()
        cost.last_total = bill['total']
        if cost.last_total < 0:
            raise CostLessThanZeroError(cost.last_total)

        await self.costService.deduct_credits(cost.credit_key,bill,self.retry_limit)
        Cost.inject_cost_info(response,bill,cost.credit_key)
        cost.reset_bill()

    async def intercept_after(self, result:Any,cost:SimpleTaskCost,broker:Broker,response:Response,taskManager:TaskManager):
        bill = cost.generate_bill()
        if bill['total'] != 0:
            await self.costService.refund_credits(cost.credit_key,bill)
            Cost.inject_cost_info(response,bill,cost.credit_key,cost.last_total)

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
        cost.init(self.price,self.credit)

        match self.mode:
            case 'purchase':
                APIFilterInject(cost.pre_purchase)(**kwargs)
                bill = cost.generate_bill()
                if cost.last_total < 0:
                    raise CostLessThanZeroError(bill['total'])

                await self.costService.check_enough_credits(self.credit,bill['total'])
                cost.reset_bill() # reset the potential bill
            case 'refund':
                ...

    async def intercept_after(self, result:Any,*args,**kwargs):
        response:Response = kwargs.get('response')
        cost:DataCost = kwargs.get('cost',None)
        if cost.bypass:
            return
        match self.mode:
            case 'purchase':
                APIFilterInject(cost.post_purchase)(result,**kwargs)
                bill = cost.generate_bill()
                if bill['total'] < 0:
                    raise CostLessThanZeroError(cost.last_total)
                await self.costService.deduct_credits(self.credit,bill,self.retry_limit)
            case 'refund':
                APIFilterInject(cost.post_refund)(result,**kwargs)
                bill = cost.generate_bill()
                if bill['total'] > 0:
                    raise CostMoreThanZeroError(bill['total'])
                await self.costService.refund_credits(self.credit,bill)

        Cost.inject_cost_info(response,bill,self.credit)
