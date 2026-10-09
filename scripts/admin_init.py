import argparse
import json
import sys
import asyncio

from pydantic import Secret, ValidationError

import app.models.orm.security_model as security
from app.services.config_service import ConfigService
from app.services.security_service import AccessVaultConstant, JWTAuthService, SecurityService
from app.utils.constant import RedisConstant, VaultConstant
from app.utils.prettyprint import PrettyPrinter_
from app.utils.toolbox import RunAsync, RunInThreadPool
from app.utils.helper import generateId

parser = argparse.ArgumentParser(description="Read and validate JSON from a file or stdin.")
parser.add_argument("-f", "--file",required=False,help="Path to the JSON file. If omitted, JSON is read from stdin.")

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
from app.services import FileService

from app.classes.auth_permission import AccessTypeAPIModel, ClientType
from app.services.admin_service import ClientMiniService
from app.services.database.tortoise_service import SECURITY_CREDS
from app.classes.step import LambdaStepRunner, Step

from app.container import build_container, Get, InjectInMiniService
PrettyPrinter_.message(f'Building container for the admin creation')
build_container()

ADMIN_INIT_KEY='admin-init'



async def main():
    configService:ConfigService = Get(ConfigService)
    vaultService:VaultService = Get(VaultService)
    redisService:RedisService = Get(RedisService)
    configService:ConfigService = Get(ConfigService)
    jwtService:JWTAuthService = Get(JWTAuthService)
    fileService:FileService = Get(FileService)
    securityService:SecurityService = Get(SecurityService)
    redisService:RedisService = Get(RedisService)

    tortoiseService:TortoiseConnectionService = Get(TortoiseConnectionService)

    setup = await redisService.retrieve(RedisConstant.CONFIG_DB,ADMIN_INIT_KEY)
    if bool(setup):
        await redisService.close_connections()
        await RunAsync(redisService.revoke_lease)()
        await RunAsync(vaultService.revoke_auth_token)()
        return 

    ## TODO create the admin /system access and the system client
    await tortoiseService.init_connection()

    async with LambdaStepRunner() as skip:
        system_access = AccessTypeAPIModel(token = f'app:{generateId(75)}',type='System',description='The access of Notifyr System, this is the superuser',
            allowed_ip=['{COMES FROM ENV}'],alias = f'Notifyr System')
        system_access._path = AccessVaultConstant.ACCESS_PATH('system')
        await RunInThreadPool(vaultService.security_engine.put(VaultConstant.INTERNAL_API_SECRETS,system_access.model_dump(),system_access._path))

    async with LambdaStepRunner() as skip:
        systemInfo = {'client_email':'system@noreply-notifyr.ca','client_name':'Notifyr System','client_username' :'notifyr_system',
                        'client_description':'Root Super user account that can login and do Admin operation and super user operation','issued_for':'{COMES FROM ENV}'}
        systemORM = security.ClientORM(client_type=ClientType.Admin,max_connection=1,can_login=True,**systemInfo)
        system_client = InjectInMiniService(ClientMiniService,client=systemORM,policies=[])
        password = generateId(22)
        encrypted_password,salt = await system_client.encrypt_password(password)

        async with tortoiseService.transaction(SECURITY_CREDS) as ctx:
            await systemORM.save(ctx)
            # store the info
            await system_client.store_password(encrypted_password,salt)
    
    async with LambdaStepRunner() as skip:
        skip()

        admin_info = admin.model_dump(mode='python',exclude={'password',})
        adminORM = security.ClientORM(client_type=ClientType.Admin,max_connection=1,can_login=True,client_description='Admin Account',**admin_info)
        admin_client = InjectInMiniService(ClientMiniService,client=adminORM,policies=[])
        encrypted_password,salt = await admin_client.encrypt_password(admin.password.get_secret_value())

        async with tortoiseService.transaction(SECURITY_CREDS) as ctx:
            await adminORM.save(ctx)
            await admin_client.store_password(encrypted_password,salt)

    async with LambdaStepRunner() as skip:
        skip()

        admin_access = AccessTypeAPIModel(
            token = f'app:{generateId(75)}',
            type='Admin',description='Admin Access',
            allowed_ip=None if not admin.issued_for else [admin.issued_for],
            alias = f'{admin.client_name}@{admin.client_username}'
        )
        admin_access._path = AccessVaultConstant.ACCESS_PATH('admin')
        await RunInThreadPool(vaultService.security_engine.put(VaultConstant.INTERNAL_API_SECRETS,admin_access.model_dump(),admin_access._path))

    await redisService.store(RedisConstant.CONFIG_DB,ADMIN_INIT_KEY,1,0)

    await redisService.close_connections()
    await tortoiseService.close_connections()

    await RunAsync(redisService.revoke_lease)()
    await RunAsync(tortoiseService.revoke_lease)()
    await RunAsync(vaultService.revoke_auth_token)()

    return

if __name__ == '__main__':
    asyncio.run(main())
    