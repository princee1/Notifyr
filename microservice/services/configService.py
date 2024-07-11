import os
from dotenv import load_dotenv
from enum import Enum


class MODE(Enum):
    DEV_MODE = 'dev'
    PROD_MODE = 'prod'
    TEST_MODE = 'test'


class ConfigService():
    pass
