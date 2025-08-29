from app.definition._service import BaseService, Service, ServiceStatus
from app.services.config_service import ConfigService, MODE
from app.services.database_service import JSONServerDBService
from app.utils.fileIO import JSONFile
from app.utils.constant import SettingDBConstant

DEV_MODE_SETTING_FILE = './setting.json'

DEFAULT_SETTING = {
    SettingDBConstant.AUTH_EXPIRATION_SETTING: 3600,
    SettingDBConstant.REFRESH_EXPIRATION_SETTING: 7200,
    SettingDBConstant.CHAT_EXPIRATION_SETTING: 3600,
    SettingDBConstant.ASSET_LANG_SETTING: "en"
}


@Service
class SettingService(BaseService):
    
    def __init__(self,configService:ConfigService,jsonServerService:JSONServerDBService):
        super().__init__()
        self.configService = configService
        self.jsonServerService = jsonServerService
        
    def verify_dependency(self):
        if self.jsonServerService.service_status != ServiceStatus.AVAILABLE and self.configService.MODE != MODE.DEV_MODE:
            self.service_status = ServiceStatus.PARTIALLY_AVAILABLE
            self.method_not_available = {'aio_get_settings'}
            
    def build(self):
        if self.configService.MODE == MODE.DEV_MODE:
            self._read_setting_json_file()
        else:
            self._data = DEFAULT_SETTING
            self._data = self.jsonServerService.get_setting()

    def _read_setting_json_file(self):
        self.jsonFile = JSONFile(DEV_MODE_SETTING_FILE)
        if not self.jsonFile.exists or self.jsonFile.data == None:
            self.jsonFile.data = DEFAULT_SETTING
        else:
            self._data = self.jsonFile.data

    async def aio_get_settings(self):
        if self.configService.MODE == MODE.DEV_MODE:
            self._read_setting_json_file()
        else:
            self._data = DEFAULT_SETTING
            self._data = await self.jsonServerService.aio_get_setting()

    async def update(self,new_data:dict):
        if self.configService.MODE == MODE.DEV_MODE:
            self._data.update(new_data)
            self.jsonFile.save()
            return 
        
        return await self.jsonServerService.save_setting(new_data)

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
    
