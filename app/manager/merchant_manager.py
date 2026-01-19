import asyncio
import functools
from typing import Any, Callable, Literal
from fastapi import BackgroundTasks, Depends, Request, Response
from app.classes.auth_permission import AuthPermission
from app.container import Get
from app.definition._cost import Cost, DataCost, SimpleTaskCost
from app.depends.dependencies import get_auth_permission
from app.services.cost_service import CostService
from app.services.database.mongoose_service import MongooseService

class Merchant:

    def __init__(self,request:Request,response:Response,backgroundTasks:BackgroundTasks,authPermission:AuthPermission=Depends(get_auth_permission)):
        self.request = request
        self.response =response
        self.authPermission = authPermission
        self.backgroundTasks = backgroundTasks

        self.to_rollback = False
        self.to_post_payment = False
        self.costService = Get(CostService)
        self.mongooseService = Get(MongooseService)
        self.index = 0
    
    def inject_cost(self,cost:Cost|SimpleTaskCost|DataCost,factor:Literal[-1,1]):
        self.cost = cost
        self.factor = factor
    
    def activate_rollback(self):
        self.to_rollback = True

    def activate_post_payment(self):
        self.to_post_payment=True

    def payment(self,function:Callable,*args,**kwargs):
        async def wrapper():
            try:
                await function(*args,**kwargs)
            except:
                ...
            
        self.backgroundTasks.add_task(wrapper,*args,**kwargs)
        self._set_indexes()
        
    def safe_payment(self,rollbackFunc:Callable[[],None],items:Any|tuple[Any,...],function:Callable,*args,**kwargs):
        if self.cost == None:
            raise AttributeError('Cost not found in the request')

        @functools.wraps(function)
        async def wrapper(*a,**k):
            
            try:
                p = await function(*a,**k)
                if self.to_post_payment:
                    try:
                        self.cost.reset_bill()
                        self.cost.post_payment(p)
                        await self._refund()
                    except:
                        return
            except Exception as e:
                try:
                    if self.to_rollback:
                        await rollbackFunc()
                except:
                    ...
                
                print('Error in safe payment',e.__class__,e)

                self.cost.reset_bill()
                if isinstance(self.cost,DataCost):
                    self.cost.post_refund(items)
                else:
                    self.cost.refund(*items)
                    
                await self._refund()
                
        self.backgroundTasks.add_task(wrapper,*args,**kwargs)
        self._set_indexes()
  
    def wait(self,seconds:int|float):
        self.backgroundTasks.add_task(asyncio.sleep(seconds))

    async def _refund(self):
        bill = self.cost.generate_bill()
        bill['total']*=self.factor
        if self.factor == 1:
            bill['refund_type'] = 'Cancelling a purchase'
        else:
            bill['refund_type'] = 'Cancelling a reimbursement'
        await self.costService.refund_credits(self.cost.credit_key,bill)
    
    def _set_indexes(self,):
        self.cost.indexes[self.index] = len(self.backgroundTasks.tasks) -1
        self.index +=1
