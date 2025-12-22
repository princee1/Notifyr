from app.definition._service import BaseService, Service, ServiceStatus
from app.errors.service_error import BuildOkError
from app.models.properties_model import SettingsModel
from app.services.config_service import ConfigService, MODE
from app.services.vault_service import VaultService
from app.utils.fileIO import JSONFile
from app.utils.constant import SettingDBConstant,DEFAULT_SETTING, VaultConstant

DEV_MODE_SETTING_FILE = './settings_db.json'


SETTING_SERVICE_SYNC_BUILD_STATE = DEFAULT_BUILD_STATE = -1
SETTING_SERVICE_ASYNC_BUILD_STATE = 1
SETTING_SERVICE_DEFAULT_SETTING_BUILD_STATE = 0


@Service()
class SettingService(BaseService):
    
    def __init__(self,configService:ConfigService,vaultService:VaultService):
        super().__init__()
        self.configService = configService
        self.vaultService = vaultService
    
        self.use_settings_file = ConfigService.parseToBool(self.configService.getenv('USE_SETTING_FILE','false'),False)
    
    async def async_verify_dependency(self):
        await super().async_verify_dependency()
        async with self.vaultService.statusLock.reader:
            return self.verify_dependency()
        
    def verify_dependency(self):
        if self.vaultService.service_status != ServiceStatus.AVAILABLE and self.configService.MODE == MODE.PROD_MODE:
            raise BuildOkError
        

    def build(self,build_state:int=SETTING_SERVICE_SYNC_BUILD_STATE):
        if self.configService.MODE == MODE.DEV_MODE and self.use_settings_file:
            self._read_setting_json_file()
        else:
            self._data = DEFAULT_SETTING.copy()
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
            data= self.vaultService.secrets_engine.read(VaultConstant.SETTINGS_SECRETS)
            SettingsModel(**data) # Validate the data
            return data
        except Exception as e:
            return DEFAULT_SETTING.copy()

    def _read_setting_json_file(self):
        self.jsonFile = JSONFile(DEV_MODE_SETTING_FILE)
        if not self.jsonFile.exists or self.jsonFile.data == None:
            self.jsonFile.data = DEFAULT_SETTING.copy()
        
        self._data = self.jsonFile.data

    async def aio_get_settings(self):
        if self.configService.MODE == MODE.DEV_MODE and self.use_settings_file:
            self._read_setting_json_file()
        else:
            self._data = DEFAULT_SETTING.copy()
            self._data = self.vaultService.secrets_engine.read(VaultConstant.SETTINGS_SECRETS)
        
        return self._data

    async def update_setting(self,new_data:dict):
        if self.configService.MODE == MODE.DEV_MODE and self.use_settings_file:
            self._data.update(new_data)
            self.jsonFile.save()
            return 
        
        self.vaultService.secrets_engine.put(VaultConstant.SETTINGS_SECRETS,self.data)

    @property
    def API_EXPIRATION(self):
        return self._data.get(SettingDBConstant.API_EXPIRATION_SETTING,DEFAULT_SETTING[SettingDBConstant.API_EXPIRATION_SETTING])
        

    @property
    def ALL_ACCESS_EXPIRATION(self):
        return self._data.get(SettingDBConstant.ALL_ACCESS_EXPIRATION_SETTING,DEFAULT_SETTING[SettingDBConstant.ALL_ACCESS_EXPIRATION_SETTING])

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
    def CONTACT_TOKEN_EXPIRATION(self):
        return self._data.get(SettingDBConstant.CONTACT_TOKEN_EXPIRATION_SETTING,DEFAULT_SETTING[SettingDBConstant.CONTACT_TOKEN_EXPIRATION_SETTING])

    @property
    def data(self):
        """
        Return a copy of the current settings data."""
        return self._data.copy()
    
