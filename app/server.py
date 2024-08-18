from container import CONTAINER
from app.services.config import ConfigService
import multiprocessing
import threading


class Manager(): pass

class App(): 
    def __init__(self):
        self.configService: ConfigService = CONTAINER.get(ConfigService)
    pass

class Server(): pass