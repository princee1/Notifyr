from app.utils.globals import APP_MODE,CAPABILITIES

if CAPABILITIES['agent']:
    from app.container import build_container,Get

    build_container()

    from app.callback import Callbacks_Stream,Callbacks_Sub
    from app.services.database.redis_service import RedisService
    from fastapi import FastAPI,Depends
    import app.routers

else:
    ...


