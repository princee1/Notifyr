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
    GENERATION_ID_KEY = 'generation_id'
    CREATION_DATE_KEY = 'creation_date'


class HTTPHeaderConstant:
    API_KEY_HEADER = 'X-API-KEY'
    TOKEN_NAME_PARAMETER = 'token_'
    CLIENT_IP_PARAMETER = 'client_ip_'
    ADMIN_KEY_PARAMETER = 'admin_'
    FUNC_NAME_SPECIAL_KEY_PARAMETER = 'func_name'
    CLASS_NAME_SPECIAL_KEY_PARAMETER = 'class_name'

    ADMIN_KEY = 'X-Admin-Key'
