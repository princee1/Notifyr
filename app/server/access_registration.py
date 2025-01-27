from app.utils.constant import ConfigAppConstant
from app.container import InjectInFunction
from app.services.security_service import SecurityService, JWTAuthService
from app.services.config_service import ConfigService
from app.utils.prettyprint import PrettyPrinter_
from app.services.file_service import FileService
from app.utils.question import SimpleInputHandler, ask_question, NumberInputHandler, ExpandInputHandler, ConfirmInputHandler, CheckboxInputHandler, one_or_more, one_or_more_invalid_message

from app.utils.prettyprint import printJSON, show, PrettyPrinter_
from app.utils.validation import ipv4_validator
from app.definition._ressource import PROTECTED_ROUTES
from app.classes.auth_permission import Role, RoutePermission, PermissionScope
from app.utils.question import ask_question, ConfirmInputHandler, SimpleInputHandler, FileInputHandler,CheckboxInputHandler
from app.utils.fileIO import ConfigFile, FDFlag, JSONFile, exist, inputFilePath, writeContent


API_KEY = "api_key"
AUTH_KEY = "auth_key"


def ress_conf(x): return f"{x}_confirm"


ipv4_addresses = []


def ip_addr_validation(ip_addr: str):
    if ip_addr in ipv4_addresses:
        return False
    return ipv4_validator(ip_addr)


@InjectInFunction
def register_client_services(securityService: SecurityService, jwtAuthService: JWTAuthService, configService: ConfigService):
    PrettyPrinter_.show(1, print_stack=False,)
    jwtAuthService.set_generation_id(True)
    if not configService.config_json_app.exists:
        # TODO not implemented the error
        return
    # BUG this works only for the first app
    current_ressources = configService.config_json_app.data[
        ConfigAppConstant.APPS_KEY][0]['ressources']

    client_number = ask_question([NumberInputHandler(
        "Enter the number of clients you want to register", 1, 'client_number', 1, 1,)])['client_number']  # BUG the max value will be 1 for now
    client_number = int(client_number)
    clients_secrets = {}

    for i in range(client_number):
        PrettyPrinter_.show(0, clear_stack=True)
        PrettyPrinter_.info(f"Registering client {i+1} of {client_number}", saveable=False)
        if i > 0:
            previous_clients = ask_question([ConfirmInputHandler('Do you want to copy the same config as previous clients?', default=False, name='copy_previous'), CheckboxInputHandler(
                'Select the previous clients you want to copy', choices=ipv4_addresses, name='previous_clients', when=lambda x: x['copy_previous'])])
            ...  # TODO implements a copy of the previous client

        bases_questions = [
            SimpleInputHandler("Enter the ip address of the client", default='', name='ip_address',
                               validate=ip_addr_validation, invalid_message="The ip address is already in use or not properly formatted",),
            CheckboxInputHandler("Select the roles of the client", 'roles',Role._member_names_,validate=one_or_more,invalid_message=one_or_more_invalid_message)
        ]
       
        results = ask_question(bases_questions)
        client_ipv4 = results['ip_address']
        roles = results['roles']

        ipv4_addresses.append(client_ipv4)

        custom_route_permission ={}
        if Role.CUSTOM.value in roles:
            custom_route_permission = ask_custom_routes(current_ressources)
            custom_route_permission = parse_access_routes(custom_route_permission, current_ressources)

        access_token = securityService.generate_custom_api_key(client_ipv4)
        auth_token = jwtAuthService.encode_auth_token(custom_route_permission, roles,client_ipv4)
        clients_secrets[client_ipv4] = {API_KEY: access_token, AUTH_KEY: auth_token}
        PrettyPrinter_.success(f"Client {i+1} successfully registered with ip address {client_ipv4}")

    return clients_secrets


def parse_access_routes(access_routes: dict, current_ressources: list[str]):
    result = {}
    for ressource in current_ressources:
        val = access_routes[ressource]
        if val != None:
            result[ressource] = RoutePermission(
                custom_routes=val, scope='custom')
        else:
            result[ressource] = RoutePermission(scope='all')

    return result


def ask_custom_routes(current_ressources:list[str]):

    result ={}
    for ressource in current_ressources:
        ressource_routes = PROTECTED_ROUTES[ressource]
        questions_routes = []
        questions_routes.extend([
            ConfirmInputHandler(f"Do you want to give all access (Y) or custom access (N) to the client for {ressource}", default=True, name=ress_conf(ressource),),
            CheckboxInputHandler(f"Select the routes you want to give access to the client for {ressource}",
                                choices=ressource_routes, name=ressource, instruction='(Press Enter to skip this ressource)', when=lambda result: not result[ress_conf(ressource)]),])
    
        result.update(ask_question(questions_routes))
    
    return result

def prompt_client_registration():

    client_secrets = register_client_services()
    PrettyPrinter_.show(2, clear_stack=True)

    PrettyPrinter_.space_line()
    answers = ask_question([ConfirmInputHandler('Do you want to save the client secrets?', default=False, name='save_secrets'), SimpleInputHandler(
        'Enter the path to save the client secrets', default='secrets.json', name='secrets_path', validate=lambda x: len(x) > 0, invalid_message='Invalid path', when=lambda x: x['save_secrets'])])

    if answers['save_secrets']:
        writeContent(answers['secrets_path'],client_secrets, flag=FDFlag.WRITE)
        if exist(answers['secrets_path']):
            PrettyPrinter_.success(f"Client secrets successfully saved to {answers['secrets_path']}", saveable=False)
            PrettyPrinter_.warning(f'Make sure to keep the file in a secure place or to delete them after loading them in other clients', saveable=False)
        else:
            PrettyPrinter_.error(f"Errors while saving client secrets to {answers['secrets_path']}", saveable=False)
    else:
        PrettyPrinter_.warning('Client secrets not saved... make sure to properly copy and set the clients secrets', saveable=False)
        printJSON(client_secrets)

    PrettyPrinter_.space_line(saveable=False)
    PrettyPrinter_.wait(0.5)
