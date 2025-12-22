from app.container import Get, build_container
from app.services import *
from app.utils.globals import APP_MODE, ApplicationMode,CAPABILITIES
from app.utils.prettyprint import PrettyPrinter_

if  APP_MODE in [ApplicationMode.beat, ApplicationMode.worker]: 
    PrettyPrinter_.message(f'Building container for the celery {APP_MODE.value}')
    build_container()

