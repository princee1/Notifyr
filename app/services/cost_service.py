from pathlib import Path

from redis import WatchError
from app.classes.cost import CostCredits, CostRules, CreditDeductionFailedError, EmailCostDefinition, InsufficientCreditsError, InvalidPurchaseRequestError, PhoneCostDefinition, SMSCostDefinition, SimpleTaskCostDefinition
from app.definition._service import BaseService, BuildAbortError, BuildWarningError, Service, ServiceStatus
from app.errors.service_error import BuildFailureError
from app.services.config_service import MODE, ConfigService
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.services.database_service import RedisService
from app.services.file_service import FileService
from app.utils.constant import CostConstant, RedisConstant
from app.utils.fileIO import JSONFile
from app.classes.auth_permission import AuthPermission
from app.utils.helper import flatten_dict

@Service()
class CostService(BaseService):
    RATE_LIMITS_PATH = Path("/run/secrets/costs")
    DICT_SEP='/'

    def __init__(self,configService:ConfigService,redisService:RedisService,fileService:FileService):
        super().__init__()
        self.configService = configService
        self.redisService = redisService
        self.fileService = fileService
        self.costs_definition={}
    
    def verify_dependency(self):
        if self.configService.MODE == MODE.PROD_MODE:
            if not self.RATE_LIMITS_PATH.exists():
                self.service_status = ServiceStatus.PARTIALLY_AVAILABLE
        
        if self.redisService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError

    def build(self,build_state=-1):

        storage_uri = None if self.configService.MODE == MODE.DEV_MODE else self.configService.SLOW_API_REDIS_URL
        self.GlobalLimiter = Limiter(get_remote_address, storage_uri=storage_uri, headers_enabled=True)
        
        if self.configService.MODE == MODE.PROD_MODE:
            path = self.RATE_LIMITS_PATH.name
            try:
                self.costs_file={"default":True}
                self.costs_file= JSONFile(path).data
                self.load_file_into_objects()
                self.service_status = ServiceStatus.AVAILABLE
            except:
                raise BuildWarningError(f'Could not mount the cost file so limit will revert too default settings')
        else:
            self.costs_file = {}
            self.service_status = ServiceStatus.AVAILABLE
    
    async def refund_credits(self,credit_key:str,refund_cost:int):
        if refund_cost > 0:
            await self.redisService.increment(RedisConstant.LIMITER_DB,credit_key,refund_cost)

    async def deduct_credits(self,credit_key,purchase_cost:int,retry_limit=5):
        retry=0
        while retry < retry_limit:
            async with self.redisService.redis_limiter.pipeline(transaction=False) as pipe:
                try:
                    await pipe.watch(credit_key)
                    current_balance = await pipe.get(credit_key)

                    if current_balance is None:
                        await pipe.unwatch()
                        raise InvalidPurchaseRequestError

                    if current_balance < purchase_cost:
                        await pipe.unwatch()
                        raise InsufficientCreditsError
                    
                    new_balance = current_balance - purchase_cost

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
    
    async def get_current_credits(self):
        ...

    def load_file_into_objects(self):
        cost = self.costs_file.get(CostConstant.COST_KEY,None)  

        if cost == None:
            raise BuildFailureError
        
        definition = flatten_dict(cost,dict_sep=self.DICT_SEP,_key_builder=lambda p:p+self.DICT_SEP)
         
        for k,v in definition.items():
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
                    
                v = v.update({key: value for key, value in v.items() if key.startswith('__')}) if mode == 'soft' else self.costs_definition[copy_from].copy()

            _,cost_type,name=k.split(self.DICT_SEP)

            if cost_type == 'task':
                if name.startswith('email'):
                    v = EmailCostDefinition(**v)
                elif name.startswith('sms'):
                    v = SMSCostDefinition(**v)
                elif name.startswith('phone'):
                    v = PhoneCostDefinition(**v)
                ...
            elif cost_type == 'simple-task':
                v = SimpleTaskCostDefinition(**v)
            
            self.costs_definition[name] = v
        
        if self.costs_file.get(CostConstant.RULES_KEY,None) == None:
            raise BuildWarningError

    @property
    def version(self)->str:
        return self.costs_file.get(CostConstant.VERSION_KEY,None)

    @property
    def system(self)->str:
        return self.costs_file.get(CostConstant.SYSTEM_KEY,None)

    @property
    def currency(self)->str:
        return self.costs_file.get(CostConstant.CURRENCY_KEY,None)
    
    @property
    def product(self)->str:
        return self.costs_file.get(CostConstant.PRODUCT_KEY,None)

    @property
    def promotions(self):
        return self.costs_file.get(CostConstant.PROMOTIONS_KEY,{})
    
    @property
    def plan_credits(self)->CostCredits:
        return self.costs_file.get(CostConstant.CREDITS_KEY,{})

    @property
    def rules(self)->CostRules:
        self.costs_file.get(CostConstant.RULES_KEY,{})