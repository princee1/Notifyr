from app.utils.globals import APP_MODE,CAPABILITIES


if CAPABILITIES['agent']:
    from app.container import build_container,Get

    build_container()

    from app.callback import Callbacks_Stream,Callbacks_Sub
    from app.services import RedisService
    from app.services import VaultService
    from fastapi import FastAPI,Depends
    from app.routers import Routers


    async def on_startup():
        ...
    
    async def on_shutdown():
        ...

    app = FastAPI(on_shutdown=[on_shutdown],on_startup=[on_startup])

    for r in Routers:
        app.include_router(r)

    
    

else:
    ...


