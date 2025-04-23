from app.definition._middleware import MIDDLEWARE
from app.utils.prettyprint import printJSON, show, PrettyPrinter_
from app.definition._ressource import RESSOURCES
from app.utils.question import ListInputHandler, ask_question, SimpleInputHandler, NumberInputHandler, ConfirmInputHandler, CheckboxInputHandler, ExpandInputHandler,exactly_one,one_or_more,one_or_more_invalid_message,instruction
from .application import AppParameter, Application

ressources_key: set = set(RESSOURCES.keys())
middlewares_key = list(MIDDLEWARE.keys())

app_titles = []
available_ports = []

def existing_port(port): return port not in available_ports


def existing_title(title): return title not in app_titles



def createApps() -> dict[str, AppParameter]:
    _results = {}

    apps_counts = ask_question([NumberInputHandler('Enter the number of applications: ',
                               name='apps_counts', default=1, min_allowed=1, max_allowed=1)])['apps_counts']
    show(1)
    PrettyPrinter_.info(f'Creating {apps_counts} applications')
    print()
    for i in range(int(apps_counts)):
        result = ask_question([SimpleInputHandler(f'Enter the title of application {i+1} : ', name='title', default='', validate=existing_title, invalid_message='Title already exists'),
                               SimpleInputHandler(
            f'Enter the summary of application {i+1} : ', name='summary', default=''),
            SimpleInputHandler(
            f'Enter the description of application {i+1} : ', name='description', default=''),
            CheckboxInputHandler(
            f'Select the ressources of application {i+1} that will be used once per application: ', choices=ressources_key, name='ressources', validate=one_or_more, invalid_message=one_or_more_invalid_message, instruction=instruction
        ),
            CheckboxInputHandler(
            f'Select the middlewares of application {i+1} : ', choices=middlewares_key, name='middlewares', validate=one_or_more, invalid_message=one_or_more_invalid_message, instruction=instruction),
            NumberInputHandler(
            f'Enter the port of application {i+1} : ', name='port', default=8080, min_allowed=4000, max_allowed=65535),
            SimpleInputHandler(
            f'Enter the log level of application {i+1} : ', name='log_level', default='debug'),
        ],)
        ressources_key.difference_update(result['ressources'])
        result['port'] = int(result['port'])
        _results[result['title']] = AppParameter.fromJSON(result, RESSOURCES, MIDDLEWARE)
        show(1)

    return _results


def editApps(json_file_app_data: dict[str, dict]) -> dict[str, AppParameter]:
    titles = list(json_file_app_data.keys())
    app_titles.clear()
    app_titles.extend(titles)
    available_ports.clear()
    available_ports.extend([json_file_app_data[title]['port'] for title in titles])

    show(1)
    PrettyPrinter_.info('Editing Applications')
    print()
    selected_title = ask_question([ListInputHandler('Select the application to edit: ', default=titles[0], choices=titles, name='selected_app',
                                  validate=exactly_one, invalid_message='Should be exactly one selection', instruction=instruction)])['selected_app']
    index = titles.index(selected_title)
    title = titles[index]
    show(1, f'Editing {title}')
    print()
    result = ask_question([SimpleInputHandler(f'Enter the title of application {index+1} : ', name='title', default=title, validate=existing_title, invalid_message='Title already exists'),
                           SimpleInputHandler(
        f'Enter the summary of application {index+1} : ', name='summary', default=json_file_app_data[title]['summary']),
        SimpleInputHandler(
        f'Enter the description of application {index+1} : ', name='description', default=json_file_app_data[title]['description']),
        CheckboxInputHandler(
        f'Select the ressources of application {index+1} that will be used once per application: ', choices=ressources_key, name='ressources', validate=one_or_more, invalid_message=one_or_more_invalid_message, instruction=instruction
    ),
        CheckboxInputHandler(
        f'Select the middlewares of application {index+1} : ', choices=middlewares_key, name='middlewares', validate=one_or_more, invalid_message=one_or_more_invalid_message, instruction=instruction),
        NumberInputHandler(
        f'Enter the port of application {index+1} : ', name='port', default=json_file_app_data[title]['port'], min_allowed=4000, max_allowed=65535),
        SimpleInputHandler(
        f'Enter the log level of application {index+1} : ', name='log_level', default=json_file_app_data[title]['log_level']),
    ],)
    result['port'] = int(result['port'])
    json_file_app_data[title] = result
    return {title: AppParameter.fromJSON(data, RESSOURCES, MIDDLEWARE) for title, data in json_file_app_data.items()}


def bootstrap_fastapi_server(app: AppParameter):
    return Application(appParameter=app)