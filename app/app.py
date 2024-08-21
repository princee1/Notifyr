from container import CONTAINER
from services.config import ConfigService
import multiprocessing
import threading

class Manager(): pass

class App(): 
    def __init__(self):
        self.configService: ConfigService = CONTAINER.get(ConfigService)
    pass
