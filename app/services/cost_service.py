import asyncio
import functools
from pathlib import Path
import traceback
from typing import Any, Callable, Self

from fastapi import Response
from redis import WatchError
from app.classes.cost_definition import CostCredits, CostRules, CreditDeductionFailedError, EmailCostDefinition, FileCostDefinition, InsufficientCreditsError, InvalidPurchaseRequestError, PhoneCostDefinition, SMSCostDefinition, SimpleTaskCostDefinition,Bill
from app.definition._service import BaseService, BuildAbortError, BuildWarningError, Service, ServiceStatus
from app.errors.service_error import BuildFailureError
from app.services.config_service import MODE, ConfigService
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.services.database.redis_service import RedisService
from app.services.file.file_service import FileService
from app.utils.constant import CostConstant, RedisConstant
from app.utils.fileIO import JSONFile
from app.classes.auth_permission import AuthPermission
from app.utils.helper import flatten_dict
from datetime import datetime
from app.utils.globals import  CAPABILITIES

REDIS_CREDIT_KEY_BUILDER= lambda credit_key: f"notifyr/credit:{credit_key}"

CREDIT_TO_CAPABILITIES:dict[CostConstant.Credit,str] = {
    'email':'email',
    'agent':'agentic',
    'object':'object',
    'sms':'twilio',
    'phone':'twilio',
    'document':'agentic',
    'token':'agentic',
    'message':'message',
    'webhook':'webhook',
    'workflow':'workflow',
    'chat':'chat',
    'notification':'notification'
}


@Service()
class CostService(BaseService):
    COST_PATH = "/run/secrets/costs.json"
    COST_PATH_OBJ= Path(COST_PATH)
    DICT_SEP='/'

    OVERDRAFT_ALLOWED = 0.15

    def __init__(self,configService:ConfigService,redisService:RedisService,fileService:FileService):
        super().__init__()
        self.configService = configService
        self.redisService = redisService
        self.fileService = fileService
        self.costs_definition={}

    @staticmethod
    def RedisCreditKeyBuilder(func:Callable):

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrapper(self:Self,credit_key:str,*args,**kwargs):
                credit_key = REDIS_CREDIT_KEY_BUILDER(credit_key)
                return await func(self,credit_key,*args,**kwargs)            
        else:
            @functools.wraps(func)
            def wrapper(self:Self,credit_key:str,*args,**kwargs):
                credit_key = REDIS_CREDIT_KEY_BUILDER(credit_key)
                return func(self,credit_key,*args,**kwargs)

        return wrapper
    
    @staticmethod
    def CreditSilentFail(value:Any=None):

        def decorator(function:Callable):

            async def wrapper(self:Self,*args,**kwargs):
                if not self.configService.COST_FLAG:
                    return value
                return await function(self,*args,**kwargs)
            
            return wrapper

        return decorator

    def verify_dependency(self):
        if self.configService.MODE == MODE.PROD_MODE:
            if not self.COST_PATH_OBJ.exists():
                raise BuildFailureError('Cost file does not exist')
        
        if self.redisService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError('Redis Service not available')

    def build(self,build_state=-1):

        storage_uri = None if self.configService.MODE == MODE.DEV_MODE else None # TODO redis url + f'/{RedisConstant.LIMITER_DB}'
        self.GlobalLimiter = Limiter(get_remote_address, storage_uri=storage_uri, headers_enabled=True)

        if self.configService.MODE == MODE.PROD_MODE:
            try:
                self.costs_file= JSONFile(self.COST_PATH)
                self.load_file_into_objects()
                self.verify_cost_file()
                self.init_plan_credits()
                self.service_status = ServiceStatus.AVAILABLE
            except Exception as e:
                print(e)
                raise BuildWarningError(f'Could not mount the cost file so limit will revert too default settings')
        else:
            self.service_status = ServiceStatus.AVAILABLE
    
    ###################################################                        #######################################

    ###################################################                        #######################################

    @RedisCreditKeyBuilder
    async def check_enough_credits(self,credit_key:str,purchase_cost:int):
        current_balance = await self.redisService.redis_limiter.get(credit_key)
        if current_balance == None:
            raise InvalidPurchaseRequestError
        
        current_balance = int(current_balance)

        if current_balance <= 0:
            raise InsufficientCreditsError
        
        if current_balance < purchase_cost:
            raise InsufficientCreditsError

    @CreditSilentFail()
    @RedisCreditKeyBuilder
    async def refund_credits(self,credit_key:str,refund_cost:int):
        if refund_cost > 0:
            await self.redisService.increment(RedisConstant.LIMITER_DB,credit_key,refund_cost)

    @RedisCreditKeyBuilder
    @CreditSilentFail(0)
    async def deduct_credits(self,credit_key:str,purchase_cost:int,retry_limit=5):
        retry=0
        while retry < retry_limit:
            async with self.redisService.redis_limiter.pipeline(transaction=False) as pipe:
                try:
                    await pipe.watch(credit_key)
                    current_balance = await pipe.get(credit_key)
                    current_balance = int(current_balance)
                    
                    if current_balance is None:
                        await pipe.unwatch()
                        raise InvalidPurchaseRequestError

                    if current_balance < purchase_cost and not self.rules.get('credit_overdraft_allowed',False):
                        await pipe.unwatch()
                        raise InsufficientCreditsError
                    
                    new_balance = current_balance - purchase_cost
                    new_balance = int(new_balance)
                    
                    pipe.multi()
                    pipe.set(credit_key, new_balance)

                    await pipe.execute()
                    return current_balance

                except WatchError:
                    retry+=1
                    continue
                finally:
                    await pipe.reset()
        
        raise CreditDeductionFailedError
    
    @RedisCreditKeyBuilder
    async def get_credit_balance(self,credit_key:str):
        credit = await self.redisService.retrieve(RedisConstant.LIMITER_DB,credit_key)
        if credit != None:
            credit = int(credit)
        return credit

    @CreditSilentFail()
    async def push_bill(self,credit:CostConstant.Credit,bill:Bill):
        bill_key = self.bill_key(credit)
        await self.redisService.push(RedisConstant.LIMITER_DB,bill_key,bill)
        return
    
    async def get_all_credits_balance(self):    

        return {k:await self.get_credit_balance(k) for k in self.plan_credits.keys() }

    ###################################################                        #######################################
    
    ###################################################                        #######################################
    @RedisCreditKeyBuilder
    def bill_key(self,credit:CostConstant.Credit):
        now = datetime.now()
        return f'{credit}@bill[{now.year}-{now.month}]'

    @RedisCreditKeyBuilder
    def receipts_key(self,credit:CostConstant.Credit):
        return f'{credit}@receipts'
    
    ###################################################                        #######################################
    
    ###################################################                        #######################################

    def init_plan_credits(self):
        self.plan_credits:CostCredits = {}
        all_credits:dict = self.costs_file.data.get(CostConstant.CREDITS_KEY,{})
        for credit,default in all_credits.items():
            if credit in CREDIT_TO_CAPABILITIES:
                cap = CREDIT_TO_CAPABILITIES[credit]
                if not CAPABILITIES[cap]:
                    continue
            
            self.plan_credits[credit]=default
            

    def load_file_into_objects(self):
        try:
            cost = self.costs_file.data.get(CostConstant.COST_KEY,None)  

            if cost == None:
                raise BuildFailureError('Cost File not found')
            
            definition = flatten_dict(cost,dict_sep=self.DICT_SEP,_key_builder=lambda p:p+self.DICT_SEP,max_level=1)
            for k,v in definition.items():
                base = {}
                if '__copy__' in v:
                    copy_rules = v['__copy__']
                    if isinstance(copy_rules,str):
                        copy_from = copy_rules
                        mode = 'hard'
                    else:
                        mode = copy_rules.get('mode','hard')
                        copy_from = copy_rules.get('from')
                    
                    if copy_from not in self.costs_definition:
                        continue
                    
                    base = {key: value for key, value in v.items() if key.startswith('__')} if mode == 'soft' else self.costs_definition[copy_from].copy()

                base.update(v)
                    
                cost_type,name=k.split(self.DICT_SEP)

                if cost_type == 'task':
                    if name.startswith('email'):
                        v = EmailCostDefinition(**base)
                    elif name.startswith('sms'):
                        v = SMSCostDefinition(**base)
                    elif name.startswith('phone'):
                        v = PhoneCostDefinition(**base)
                    ...
                elif cost_type == 'simple-task':
                    v = SimpleTaskCostDefinition(**base)
                elif cost_type == 'file':
                    v = FileCostDefinition(**base)
                elif cost_type == 'ai':
                    ...
                
                self.costs_definition[name] = v
            
            if self.costs_file.data.get(CostConstant.RULES_KEY,None) == None:
                raise BuildWarningError
            
        except Exception as e:
            traceback.print_exc()

    def verify_cost_file(self):
        if self.system != 'Notifyr Credit System':
            raise BuildFailureError('Cost system not supported')

        if self.currency != 'NOTIFYR-CREDITS':
            raise BuildFailureError('Currency not supported')

    def is_current_credit_overdraft_allowed(self,current_credits:int,credit_key:str):
        return (self.rules.get('auto_block_on_zero_credit', True) or (((-1 * current_credits)  / self.plan_credits[credit_key]) <self.rules.get('overdraft_ratio_allowed',self.OVERDRAFT_ALLOWED) ))

    ###################################################                        #######################################
    
    ###################################################                        #######################################

    @property
    def version(self)->str:
        return self.costs_file.data.get(CostConstant.VERSION_KEY,None)

    @property
    def system(self)->str:
        return self.costs_file.data.get(CostConstant.SYSTEM_KEY,None)

    @property
    def currency(self)->str:
        return self.costs_file.data.get(CostConstant.CURRENCY_KEY,None)
    
    @property
    def product(self)->str:
        return self.costs_file.data.get(CostConstant.PRODUCT_KEY,None)

    @property
    def promotions(self):
        return self.costs_file.data.get(CostConstant.PROMOTIONS_KEY,{})
        
    @property
    def rules(self)->CostRules:
        return self.costs_file.data.get(CostConstant.RULES_KEY,{})