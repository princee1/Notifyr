from enum import Enum
from typing_extensions import Literal
import random
########################  ** Dependencies **   ########################################


SECONDS_IN_AN_HOUR = 60*60

class DependencyConstant:
    TYPE_KEY = "type"
    DEP_KEY = "dep"
    PARAM_NAMES_KEY = "param_name"
    DEP_PARAMS_KEY = "dep_params"
    FLAG_BUILD_KEY = "flag_build"

    RESOLVED_FUNC_KEY = "resolved_func"
    RESOLVED_DEPS_KEY = "resolved_deps"
    RESOLVED_PARAMETER_KEY = "parameter"
    RESOLVED_CLASS_KEY= "resolved_class"

    BUILD_ONLY_FUNC_KEY = "build_only_function"
    BUILD_ONLY_PARAMS_KEY = "build_only_params"
    BUILD_ONLY_DEP_KEY = "build_only_dep"
    BUILD_ONLY_FLAG_KEY = "build_only_flag"
    BUILD_ONLY_CLASS_KEY= "build_only_class"

########################  ** ValidationHTML **      ########################################
class ValidationHTMLConstant:
    VALIDATION_ITEM_BALISE = "validation-item"
    VALIDATION_REGISTRY_BALISE = "validation-registry"
    VALIDATION_KEYS_RULES_BALISE = "validation-keysrules"
    VALIDATION_VALUES_RULES_BALISE = "validation-valuesrules"

########################                     ########################################

class ConfigAppConstant:
    META_KEY = 'meta'
    APPS_KEY = 'apps'
    FROM_KEY = 'from'
    RESSOURCE_KEY='ressources'
    GENERATION_ID_KEY = 'generation_id'
    CREATION_DATE_KEY = 'creation_date'
    EXPIRATION_DATE_KEY = 'expiration_date'
    EXPIRATION_TIMESTAMP_KEY = 'expiration_timestamp'


class HTTPHeaderConstant:
    API_KEY_HEADER = 'X-API-KEY'
    ADMIN_KEY = 'X-Admin-Key'
    CONTACT_TOKEN='X-Contact-TOKEN'
    WS_KEY = 'X-WS-Auth-Key'
    REQUEST_ID = 'x-request-id'
    X_PROCESS_TIME="X-Process-Time"
    X_INSTANCE_ID= "X-Instance-Id"
    X_PROCESS_PID = "X-Process-PID"
    X_PARENT_PROCESS_PID="X-Parent-Process-PID"


class CookieConstant:
    JSESSION_ID= 'jsessionid'
    LANG ='lang'

class SpecialKeyParameterConstant:
    TOKEN_NAME_PARAMETER = 'token_'
    CLIENT_IP_PARAMETER = 'client_ip_'
    ADMIN_KEY_PARAMETER = 'admin_'
    FUNC_NAME_SPECIAL_KEY_PARAMETER = 'func_name'
    CLASS_NAME_SPECIAL_KEY_PARAMETER = 'class_name'
    AUTH_PERMISSION_PARAMETER = 'authPermission'
    META_SPECIAL_KEY_PARAMETER = 'func_meta'
    TEMPLATE_SPECIAL_KEY_PARAMETER = 'template'
    SCHEDULER_SPECIAL_KEY_PARAMETER = 'scheduler'
    WS_MESSAGE_SPECIAL_KEY_PARAMETER = 'message'
    WAIT_TIMEOUT_PARAMETER = 'wait_timeout'
    BACKGROUND_PARAMETER = 'background'

class SpecialKeyAttributesConstant:
    CONTACT_SPECIAL_KEY_ATTRIBUTES='_contact'

########################                     ########################################

class EmailHostConstant(Enum):
    GMAIL_RELAY = "GMAIL_RELAY"
    GMAIL_RESTRICTED = 'GMAIL_RESTRICTED'
    GMAIL = "GMAIL"
    OUTLOOK = "OUTLOOK"
    YAHOO = "YAHOO"
    AOL = 'AOL'
    ICLOUD = 'ICLOUD'
    CUSTOM = 'CUSTOM'

########################                     ########################################

class StreamConstant:
    StreamLiteral = Literal['email-event','twilio','links-event','links-session','email-tracking','contact-event']

    EMAIL_EVENT_STREAM ='email-event'
    TWILIO_REACTIVE ='twilio-reactive'
    LINKS_EVENT_STREAM ='links-event'
    LINKS_SESSION_STREAM ='links-session'
    EMAIL_TRACKING ='email-tracking'
    CONTACT_EVENT = 'contact-event'
    TWILIO_TRACKING_SMS ='twilio-tracking-sms'
    TWILIO_TRACKING_CALL ='twilio-tracking-call'
    TWILIO_EVENT_STREAM_SMS = 'twilio-event-sms'
    TWILIO_EVENT_STREAM_CALL = 'twilio-event-call'
    CONTACT_SUBS_EVENT = 'contact-subs-event'
    CONTACT_CREATION_EVENT= 'contact-creation-event'
    CELERY_RETRY_MECHANISM='retry-mechanism'
    PROFILE_ERROR_STREAM='profile-error-stream'
    S3_EVENT_STREAM='s3_object_events'


class SubConstant:
    SERVICE_STATUS = 'service-status'
    SERVICE_VARIABLES = 'service-variables'
    PROCESS_TERMINATE = 'process-terminate' 
    MINI_SERVICE_STATUS = 'mini-service-status'

    _SUB_CALLBACK = {SERVICE_STATUS,MINI_SERVICE_STATUS,SERVICE_VARIABLES,PROCESS_TERMINATE}

class ServerParamsConstant(Enum):
    SESSION_ID = 'session-id'


########################                     ########################################

class EmailHeadersConstant(str,Enum):

    X_EMAIL_ID = 'X-EMAIL-ID'
    MESSAGE_ID = 'MESSAGE-ID'
    CONTACT_ID = 'X_CONTACT_ID'


class LinkConstant(str,Enum):
    PIXEL = 'pixel'


class VariableConstant:
    WAIT_TIMEOUT = 'wait'
    MAX_WAIT_TIMEOUT = 60*3


class RunModeConstant(Enum):
    SERVER = "server"
    REGISTER = "register"

class HTMLTemplateConstant:
    _tracking_url = '_tracking_url'
    _signature = '_signature'

    values= {_tracking_url,_signature}


########################                     ########################################
class MongooseDBConstant:
    AGENT_COLLECTION = 'agent'
    PROFILE_COLLECTION = 'profile'
    CHAT_COLLECTION = 'chat'
    WORKFLOW_COLLECTION ='workflow'

    DATABASE_NAME = 'notifyr'


    def __init__(self):
        self.available_collection = []

        for x in dir(self.__class__):
            if x.endswith('_COLLECTION'):
                x = getattr(self.__class__,x)
                self.available_collection.append(x)
            
########################                     ########################################

class SettingDBConstant:
    BASE_JSON_DB='settings'
    HEALTH_JSON_DB='health'
    
    AUTH_EXPIRATION_SETTING='AUTH_EXPIRATION'
    REFRESH_EXPIRATION_SETTING='REFRESH_EXPIRATION'
    CHAT_EXPIRATION_SETTING='CHAT_EXPIRATION'
    ASSET_LANG_SETTING='ASSET_LANG'
    CONTACT_TOKEN_EXPIRATION_SETTING='CONTACT_TOKEN_EXPIRATION'
    API_EXPIRATION_SETTING='API_EXPIRATION'
    ALL_ACCESS_EXPIRATION_SETTING='ALL_ACCESS_EXPIRATION_SETTING'

    #_available_db_key=[AUTH_EXPIRATION_SETTING,REFRESH_EXPIRATION_SETTING,CHAT_EXPIRATION_SETTING,ASSET_LANG_SETTING,CONTACT_TOKEN_EXPIRATION_SETTING]

    def __init__(self):

        self.available_setting_key = []
        self.available_db_key = []

        for x in dir(self.__class__):
            if x.endswith('_SETTING'):
                self.available_setting_key.append(x)
            
            elif x.endswith('_DB'):
                self.available_db_key.append(x)


DEFAULT_SETTING = {
    SettingDBConstant.AUTH_EXPIRATION_SETTING: SECONDS_IN_AN_HOUR * 10,
    SettingDBConstant.REFRESH_EXPIRATION_SETTING: SECONDS_IN_AN_HOUR * 24 * 1,
    SettingDBConstant.CHAT_EXPIRATION_SETTING: SECONDS_IN_AN_HOUR,
    SettingDBConstant.ASSET_LANG_SETTING: "en",
    SettingDBConstant.CONTACT_TOKEN_EXPIRATION_SETTING:360000000,
    SettingDBConstant.API_EXPIRATION_SETTING: 360000000,
    SettingDBConstant.ALL_ACCESS_EXPIRATION_SETTING: 36000000000,
}


########################                     ########################################

class VaultConstant:

    SECRET_ID_FILE= 'secret-id.txt' 
    ROLE_ID_FILE = 'role_id.txt' # in the secrets shared by the vault
    SUPERCRONIC_SEED_TIME_FILE = 'seed-time.txt'
    

    
    @staticmethod
    def VAULT_SECRET_DIR(file:str)->str:
        return f'../../vault/secrets/{file}'

    @staticmethod
    def VAULT_SHARED_DIR(file:str)->str:
        return f'../../vault/shared/{file}'


    NotifyrSecretType = Literal['tokens','profiles','messages','generation-id']
    TOKENS_SECRETS = 'tokens'
    PROFILES_SECRETS = 'profiles'
    MESSAGES_SECRETS = 'messages'
    GENERATION_ID = 'generation-id'


    NotifyrTransitKeyType = Literal['profiles-key','messages-key','chat-key','s3-rest-key']
    SECRETS_MESSAGE_KEY = 'messages-key'
    PROFILES_KEY = 'profiles-key'
    CHAT_KEY='chat-key'
    S3_REST_KEY='s3-rest-key'

    NotifyrDynamicSecretsRole= Literal['postgres','mongo']
    MONGO_ROLE='mongo'
    POSTGRES_ROLE='postgres'

    NotifyrMinioRole = Literal['static-minio','sts-minio']


    NOTIFYR_SECRETS_MOUNT_POINT = 'notifyr-secrets'
    NOTIFYR_TRANSIT_MOUNT_POINT = 'notifyr-transit'
    NOTIFYR_DB_MOUNT_POINT = 'notifyr-database'
    NOTIFYR_GENERATION_MOUNT_POINT ='notifyr-generation'
    NOTIFYR_MINIO_MOUNT_POINT = 'notifyr-minio-s3'


    @staticmethod
    def KV_ENGINE_BASE_PATH(sub_mount:NotifyrSecretType='',path:str=''):
        if sub_mount == '':
            return path+'/'
        return f'{sub_mount}/{path}'

    @staticmethod
    def DATABASE_ENGINE_BASE_PATH(sub_mount:NotifyrTransitKeyType,path:str=''):
        return f'{sub_mount}/{path}'
    


class VaultTTLSyncConstant:
    SECRET_ID_ROTATION = SECONDS_IN_AN_HOUR*24
    TRANSIT_ROTATION = SECONDS_IN_AN_HOUR*24

    SECRET_ID_TTL= SECONDS_IN_AN_HOUR*24*3
    
    VAULT_TOKEN_TTL=SECONDS_IN_AN_HOUR*24
    VAULT_TOKEN_MAX_TTL=SECONDS_IN_AN_HOUR*28

    POSTGRES_AUTH_TTL=SECONDS_IN_AN_HOUR*12
    POSTGRES_MAX_TTL=SECONDS_IN_AN_HOUR*16

    MONGODB_AUTH_TTL=SECONDS_IN_AN_HOUR*12
    MONGODB_MAX_TTL=SECONDS_IN_AN_HOUR*16

    MINIO_TTL=SECONDS_IN_AN_HOUR*12
    MINIO_MAX_TTL= SECONDS_IN_AN_HOUR *16

    


class MinioConstant:
    STORAGE_METHOD = 'mount(same FS)','s3 object storage(source of truth)'
    ASSETS_BUCKET = 'assets'
    STATIC_TEMPLATE = 'static'
    ENCRYPTED_KEY = 'encrypted'
    MINIO_EVENT='s3_object_events'


class RedisConstant:

    EVENT_DB=0
    CELERY_DB=2
    LIMITER_DB=1
    CACHE_DB=3