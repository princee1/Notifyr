import argparse
import json
import sys
import asyncio

from pydantic import Secret, ValidationError

import app.models.orm.security_model as security
from app.services.config_service import ConfigService
from app.services.security_service import AccessVaultConstant
from app.utils.constant import RedisConstant, SetupRootConstant, VaultConstant
from app.utils.fileIO import JSONFile
from app.utils.prettyprint import PrettyPrinter_
from app.utils.toolbox import RunAsync, RunInThreadPool
from app.utils.helper import generateId, slice_dict

SYSTEM_FILE = '/tmp/root-credentials.json'

parser = argparse.ArgumentParser(description="Read and validate JSON from a file or stdin.")
parser.add_argument("-f", "--file",required=False,help="Path to the JSON file. If omitted, JSON is read from stdin.")
parser.add_argument('-s',"--system",required=False,default=SYSTEM_FILE,help='Path to the JSON file we will stored the system credentials')

args = parser.parse_args()

try:
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)
    admin = security.AdminClientModel(**data)
except FileNotFoundError:
    parser.error(f"File not found: {args.file}")
except PermissionError:
    parser.error(f"Permission denied: {args.file}")
except json.JSONDecodeError as e:
    parser.error(f"Invalid JSON")
except ValidationError as e:
    parser.error(f'Validation Error {e.errors(include_input=False,include_url=False)}')

from app.services import VaultService
from app.services import TortoiseConnectionService
from app.services import RedisService

from app.classes.auth_permission import AccessTypeAPIModel, ClientType
from app.services.admin_service import ClientMiniService
from app.services.database.tortoise_service import SECURITY_CREDS
from app.classes.step import LambdaStepRunner, StepCallback

from app.container import InjectInMethod, build_container, Get, InjectInMiniService
PrettyPrinter_.message(f'Building container for the admin creation')
build_container()

ADMIN_INIT_KEY='admin-init'

class InitStepCallback(StepCallback):

    @InjectInMethod()
    def __init__(self,redisService:RedisService):
        self.redisService  = redisService

    async def before_enter(self,key:str):
        return bool(await self.redisService.retrieve(RedisConstant.CONFIG_DB,key))

    async def after_exit(self,key:str):
        await self.redisService.store(RedisConstant.CONFIG_DB,key,int(True),0)

async def main():
    vaultService:VaultService = Get(VaultService)
    redisService:RedisService = Get(RedisService)
    configService:ConfigService = Get(ConfigService)
    tortoiseService:TortoiseConnectionService = Get(TortoiseConnectionService)

    await tortoiseService.init_connection()
    system_file = JSONFile(args.system,None)
    callback = InitStepCallback()

    async with LambdaStepRunner(callback,SetupRootConstant.SYSTEM_ACCESS_KEY) as skip:
        skip()

        system_access = AccessTypeAPIModel(token = f'app:{generateId(75)}',type='System',description='The access of Notifyr System, this is the superuser',
            allowed_ip=[configService.SYSTEM_IP],alias = f'Notifyr System')
        system_access._path = AccessVaultConstant.ACCESS_PATH('system')
        system_file['access'] = system_access.model_dump(mode='json')
        system_file.save()
        await RunInThreadPool(vaultService.secrets_engine.put)(VaultConstant.INTERNAL_API_SECRETS,system_access.model_dump(),system_access._path)

    async with LambdaStepRunner(callback,SetupRootConstant.SYSTEM_LOGIN_KEY) as skip:
        skip()
        
        systemInfo = {'client_email':'system@noreply-notifyr.ca','client_name':'Notifyr System','client_username' :'notifyr_system',
                        'client_description':'Root Super user account that can login and do Admin operation and super user operation','issued_for':configService.SYSTEM_IP}
        systemORM = security.ClientORM(client_type=ClientType.System,max_connection=1,max_refresh=25,can_login=True,**systemInfo)
        system_client = InjectInMiniService(ClientMiniService,client=systemORM,group_id=None,policies=[])
        password = generateId(22)
        encrypted_password,salt = await system_client.encrypt_password(password)

        async with tortoiseService.transaction(SECURITY_CREDS) as ctx:
            await systemORM.save(ctx)
            slice_dict(systemInfo,{'client_username','client_email'},'include')
            system_file['client'] = {'password':password,**systemInfo,}
            system_file.save()
            await system_client.store_password(encrypted_password,salt)
    
    async with LambdaStepRunner(callback,SetupRootConstant.ADMIN_LOGIN_KEY) as skip:
        skip()

        admin_info = admin.model_dump(mode='python',exclude={'password',})
        adminORM = security.ClientORM(client_type=ClientType.Admin,max_connection=1,can_login=True,max_refresh=50,client_description='Admin Account',**admin_info)
        admin_client = InjectInMiniService(ClientMiniService,client=adminORM,group_id=None,policies=[])
        encrypted_password,salt = await admin_client.encrypt_password(admin.password.get_secret_value())

        async with tortoiseService.transaction(SECURITY_CREDS) as ctx:
            await adminORM.save(ctx)
            await admin_client.store_password(encrypted_password,salt)

    async with LambdaStepRunner(callback,SetupRootConstant.ADMIN_ACCESS_KEY) as skip:
        skip()

        admin_access = AccessTypeAPIModel(
            token = f'app:{generateId(75)}',
            type='Admin',description='Admin Access',
            allowed_ip=None if not admin.issued_for else [admin.issued_for],
            alias = f'{admin.client_name}@{admin.client_username}'
        )
        admin_access._path = AccessVaultConstant.ACCESS_PATH('admin')
        await RunInThreadPool(vaultService.secrets_engine.put)(VaultConstant.INTERNAL_API_SECRETS,admin_access.model_dump(),admin_access._path)

    await redisService.close_connections()
    await tortoiseService.close_connections()

    await RunAsync(redisService.revoke_lease)()
    await RunAsync(tortoiseService.revoke_lease)()
    await RunAsync(vaultService.revoke_auth_token)()

    return

if __name__ == '__main__':
    asyncio.run(main())
    