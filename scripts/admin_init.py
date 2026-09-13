import argparse
import json
import sys
import asyncio

from pydantic import ValidationError

import app.models.orm.security_model as security
from app.utils.constant import RedisConstant
from app.utils.prettyprint import PrettyPrinter_
from app.utils.toolbox import RunAsync

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

from app.classes.auth_permission import ClientType
from app.services.admin_service import ClientMiniService
from app.services.database.tortoise_service import SECURITY_CREDS

from app.container import build_container, Get, BuildMiniService
PrettyPrinter_.message(f'Building container for the admin creation')
build_container()

ADMIN_INIT_KEY='admin-init'

async def main():
    vaultService:VaultService = Get(VaultService)
    redisService:RedisService = Get(RedisService)
    tortoiseService:TortoiseConnectionService = Get(TortoiseConnectionService)

    setup = await redisService.retrieve(RedisConstant.CONFIG_DB,ADMIN_INIT_KEY)
    if bool(setup):
        await redisService.close_connections()
        print('alloap')
        return 

    await tortoiseService.init_connection()

    admin_info = admin.model_dump(mode='python',exclude={'password',})
    clientORM = security.ClientORM(client_type=ClientType.Admin,client_description='Admin Account',**admin_info)

    client = BuildMiniService(ClientMiniService,client=clientORM) 
    encrypted_password,salt =await client.encrypt_password(admin.password.get_secret_value())

    async with tortoiseService.transaction(SECURITY_CREDS) as ctx:
        await clientORM.save(ctx)
        await client.store_password(encrypted_password)
        await client.create_auth_signature()

    await redisService.store(RedisConstant.CONFIG_DB,ADMIN_INIT_KEY,True)

    await redisService.close_connections()
    await tortoiseService.close_connections()

    await RunAsync(redisService.revoke_lease)()
    await RunAsync(tortoiseService.revoke_lease)()
    await RunAsync(vaultService.revoke_auth_token)()

    return

if __name__ == '__name__':
    asyncio.run(main())
    