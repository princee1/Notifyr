from app.definition._service import BaseService, Service, ServiceStatus
from app.models.properties_model import SettingsModel
from app.services.config_service import ConfigService, MODE
from app.services.database_service import JSONServerDBService
from app.utils.fileIO import JSONFile
from app.utils.constant import SettingDBConstant,DEFAULT_SETTING

DEV_MODE_SETTING_FILE = './setting_db.json'


SETTING_SERVICE_SYNC_BUILD_STATE = DEFAULT_BUILD_STATE = -1
SETTING_SERVICE_ASYNC_BUILD_STATE = 1
SETTING_SERVICE_DEFAULT_SETTING_BUILD_STATE = 0


@Service
class SettingService(BaseService):
    
    def __init__(self,configService:ConfigService,jsonServerService:JSONServerDBService):
        super().__init__()
        self.configService = configService
        self.jsonServerService = jsonServerService

        self.use_settings_file = ConfigService.parseToBool(self.configService.getenv('USE_SETTING_FILE','no'))
    
    async def async_verify_dependency(self):
        await super().async_verify_dependency()
        async with self.jsonServerService.statusLock.reader:
            return self.verify_dependency()
        
    def verify_dependency(self):
        if self.jsonServerService.service_status != ServiceStatus.AVAILABLE and self.configService.MODE == MODE.PROD_MODE:
            self.service_status = ServiceStatus.PARTIALLY_AVAILABLE
            self.method_not_available = {'aio_get_settings'}
        else:
            self.service_status = ServiceStatus.AVAILABLE

    def build(self,build_state:int=SETTING_SERVICE_SYNC_BUILD_STATE):
        if self.configService.MODE == MODE.DEV_MODE and self.use_settings_file:
            self._read_setting_json_file()
        else:
            self._data = DEFAULT_SETTING
            match build_state:
                case -1: # SYNC_BUILD_STATE
                    self._data = self.get_setting()
                
                case 0:
                    ... # Keep the default setting

                case 1: # ASYNC_BUILD_STATE: calling the aio_get_settings later is required
                    ...
                case _:
                    self._data = self.get_setting()

    def get_setting(self):
        try:
            data= self.jsonServerService.get_setting()
            SettingsModel(**data) # Validate the data
            return data
        except Exception as e:
            return DEFAULT_SETTING

    def _read_setting_json_file(self):
        self.jsonFile = JSONFile(DEV_MODE_SETTING_FILE)
        if not self.jsonFile.exists or self.jsonFile.data == None:
            self.jsonFile.data = DEFAULT_SETTING
        
        self._data = self.jsonFile.data[SettingDBConstant.BASE_JSON_DB]

    async def aio_get_settings(self):
        if self.configService.MODE == MODE.DEV_MODE:
            self._read_setting_json_file()
        else:
            self._data = DEFAULT_SETTING
            self._data = await self.jsonServerService.aio_get_setting()
        
        return self._data

    async def update_setting(self,new_data:dict):
        if self.configService.MODE == MODE.DEV_MODE and self.use_settings_file:
            self._data.update(new_data)
            self.jsonFile.save()
            return 
        
        return await self.jsonServerService.save_settings(new_data)

    @property
    def AUTH_EXPIRATION(self):
        return self._data.get(SettingDBConstant.AUTH_EXPIRATION_SETTING,DEFAULT_SETTING[SettingDBConstant.AUTH_EXPIRATION_SETTING])

    @property
    def REFRESH_EXPIRATION(self):
        return self._data.get(SettingDBConstant.REFRESH_EXPIRATION_SETTING,DEFAULT_SETTING[SettingDBConstant.REFRESH_EXPIRATION_SETTING])

    @property
    def CHAT_EXPIRATION(self):
        return self._data.get(SettingDBConstant.CHAT_EXPIRATION_SETTING,DEFAULT_SETTING[SettingDBConstant.CHAT_EXPIRATION_SETTING])

    @property
    def ASSET_LANG(self):
        return self._data.get(SettingDBConstant.ASSET_LANG_SETTING,DEFAULT_SETTING[SettingDBConstant.ASSET_LANG_SETTING])

    @property
    def data(self):
        """
        Return a copy of the current settings data."""
        return self._data.copy()
    
