from typing import Callable
from app.classes.auth_permission import WSPathNotFoundError
from app.classes.template import TemplateBuildError, TemplateNotFoundError, TemplateValidationError
from app.definition._error import BaseError
from app.definition._utils_decorator import Handler,HandlerDefaultException,NextHandlerException
from app.definition._service import MethodServiceNotExistsError, ServiceNotAvailableError,MethodServiceNotAvailableError, ServiceTemporaryNotAvailableError
from fastapi import status, HTTPException
from app.classes.celery import CelerySchedulerOptionError, CeleryTaskNameNotExistsError,CeleryTaskNotFoundError
from celery.exceptions import AlreadyRegistered,MaxRetriesExceededError,BackendStoreError,QueueNotFound,NotRegistered

from app.errors.contact_error import ContactAlreadyExistsError, ContactNotExistsError,ContactDoubleOptInAlreadySetError,ContactOptInCodeNotMatchError
from app.errors.request_error import IdentifierTypeError
from app.errors.security_error import AlreadyBlacklistedClientError, ClientDoesNotExistError, CouldNotCreateAuthTokenError, CouldNotCreateRefreshTokenError, GroupAlreadyBlacklistedError, GroupIdNotMatchError, SecurityIdentityNotResolvedError
from app.services.assets_service import AssetNotFoundError
from twilio.base.exceptions import TwilioRestException

from tortoise.exceptions import OperationalError,DBConnectionError,ValidationError,IntegrityError,DoesNotExist,MultipleObjectsReturned,TransactionManagementError,UnSupportedError,ConfigurationError,ParamsError,BaseORMException
from requests.exceptions import SSLError,Timeout


class ServiceAvailabilityHandler(Handler):
    
    async def handle(self, function:Callable, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        
        except ServiceNotAvailableError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail='Service not available')
            
        except MethodServiceNotAvailableError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail='Method service not available')

        except MethodServiceNotExistsError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail='Method service does not exists')


        except ServiceTemporaryNotAvailableError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail='Service temporary not available')
                  
        
class TemplateHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except AssetNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='Asset not found')
        
        except TemplateNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='Template not found')
        
        except TemplateBuildError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail='Cannot build template with data specified')

        except TemplateValidationError as e:
            error = e.args[0]
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={
                'details':error,
                'message': 'Validation Error'
            })
        
class WebSocketHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
           return await function(*args, **kwargs)
        
        except WSPathNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={
                'message':'WS Path Not Found'
            })


class CeleryTaskHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
           return await function(*args,**kwargs)
        
        except CeleryTaskNotFoundError as e:
           raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={})

        except CeleryTaskNameNotExistsError as e:
           raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={})

        except CelerySchedulerOptionError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={})
        
        except QueueNotFound as e:
           raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={})
            
        except AlreadyRegistered as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail={})

        except NotRegistered as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={})
            
        except MaxRetriesExceededError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail={})
        
class TwilioHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
    
        except TwilioRestException as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                'message': 'Twilio REST API error',
            })

        except SSLError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={
                'message': 'SSL error',
            })

        except Timeout as e:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail={
                'message': 'Request timed out',
            })
    


class ContactsHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:

            return await function(*args, **kwargs)
        
        except ContactNotExistsError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={'message':'The user specified does not exists',})

        except ContactAlreadyExistsError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={'message':'Error could not create the user because info are already used','detail':e.message})
        
        except ContactDoubleOptInAlreadySetError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={'message':'Error could not create the user because info are already used','detail':e.message})
        
        except ContactOptInCodeNotMatchError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={'message':'Error could not create the user because info are already used','detail':e.message})
    
class TortoiseHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except OperationalError as e:
            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={'message': 'Database execution error', 'detail': mess, })

        except ValidationError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)

            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={'message': 'Validation error', 'detail': mess, })

        except DBConnectionError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={'message': 'Database connection error', 'detail': mess, })

        except IntegrityError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={'message': 'Integrity error', 'detail': mess, })

        except DoesNotExist as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={'message': 'Record not found', 'detail': mess, })

        except MultipleObjectsReturned as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={'message': 'Multiple objects returned', 'detail': mess, })

        except TransactionManagementError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={'message': 'Transaction management error', 'detail': mess, })

        except UnSupportedError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={'message': 'Unsupported operation', 'detail': mess, })

        except ConfigurationError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={'message': 'Configuration error', 'detail': mess, })

        except ParamsError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={'message': 'Parameters error', 'detail': mess, })

        except BaseORMException as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={'message': 'ORM error', 'detail': mess, })


class SecurityClientHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        
        except GroupAlreadyBlacklistedError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                'message': f'Group {e.group_id} is already blacklisted',
                'group_id': e.group_id,
                'group_name': e.group_name
            })

        except CouldNotCreateRefreshTokenError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                'message': 'Could not create refresh token'
            })

        except CouldNotCreateAuthTokenError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                'message': 'Could not create auth token'
            })

        except SecurityIdentityNotResolvedError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                'message': 'Both group and client can\'t be None'
            })

        except GroupIdNotMatchError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                'message': 'Group ID does not match',
                'client_group_id': e.client_group_id,
                'group_id': e.group_id
            })

        except ClientDoesNotExistError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                'message': 'Client does not exist'
            })

        except AlreadyBlacklistedClientError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={
                'message': 'Client is already blacklisted'if not  e.reversed_ else 'Client is not blacklisted yet',
            })

class RequestErrorHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except IdentifierTypeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={
                'message':'Invalid identifier type specified'
            })
            
