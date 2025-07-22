from enum import Enum
from typing_extensions import Literal
########################  ** Dependencies **   ########################################

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
    AS_ASYNC_PARAMETER = 'as_async'

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


class SubConstant:
    SERVICE_STATUS = 'service-status'

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
    FILE = "file"
    CREATE = "create"
    EDIT = "edit"
    REGISTER = "register"