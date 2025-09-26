from asyncio import CancelledError
import asyncio
from typing import Callable

from fastapi.exceptions import ResponseValidationError
from h11 import LocalProtocolError
import hvac
from app.classes.auth_permission import WSPathNotFoundError
from app.classes.email import EmailInvalidFormatError, NotSameDomainEmailError
from app.classes.stream_data_parser import ContinuousStateError, DataParsingError, SequentialStateError, ValidationDataError
from app.classes.template import SchemaValidationError, TemplateBuildError, TemplateCreationError, TemplateFormatError, TemplateInjectError, TemplateNotFoundError, TemplateValidationError
from app.container import InjectInMethod
from app.definition._error import BaseError, ServerFileError
from app.definition._utils_decorator import Handler, HandlerDefaultException, NextHandlerException
from app.definition._service import MethodServiceNotExistsError, MethodServiceNotImplementedError, ServiceDoesNotExistError, ServiceNotAvailableError, MethodServiceNotAvailableError, ServiceNotImplementedError, ServiceTemporaryNotAvailableError, StateProtocolMalFormattedError
from fastapi import status, HTTPException
from app.classes.celery import CelerySchedulerOptionError, CeleryTaskNameNotExistsError, CeleryTaskNotFoundError
from celery.exceptions import AlreadyRegistered, MaxRetriesExceededError, BackendStoreError, QueueNotFound, NotRegistered

from app.errors.async_error import KeepAliveTimeoutError, LockNotFoundError, ReactiveSubjectNotFoundError
from app.errors.contact_error import ContactAlreadyExistsError, ContactMissingInfoKeyError, ContactNotExistsError, ContactDoubleOptInAlreadySetError, ContactOptInCodeNotMatchError
from app.errors.properties_error import GlobalKeyAlreadyExistsError, GlobalKeyDoesNotExistsError
from app.errors.request_error import IdentifierTypeError
from app.errors.security_error import AlreadyBlacklistedClientError, AuthzIdMisMatchError, ClientDoesNotExistError, CouldNotCreateAuthTokenError, CouldNotCreateRefreshTokenError, GroupAlreadyBlacklistedError, GroupIdNotMatchError, SecurityIdentityNotResolvedError, ClientTokenHeaderNotProvidedError
from app.errors.twilio_error import TwilioCallBusyError, TwilioCallFailedError, TwilioCallNoAnswerError, TwilioPhoneNumberParseError
from app.classes.profiles import ProfileCreationModelError, ProfileDoesNotExistsError, ProfileHasNotCapabilitiesError, ProfileModelTypeDoesNotExistsError, ProfileNotAvailableError, ProfileNotSpecifiedError
from app.services.assets_service import AssetNotFoundError
from twilio.base.exceptions import TwilioRestException

from tortoise.exceptions import OperationalError, DBConnectionError, ValidationError, IntegrityError, DoesNotExist, MultipleObjectsReturned, TransactionManagementError, UnSupportedError, ConfigurationError, ParamsError, BaseORMException
from requests.exceptions import SSLError, Timeout

from app.services.logger_service import LoggerService
from pydantic import BaseModel, ValidationError as PydanticValidationError


class ServiceAvailabilityHandler(Handler):

    async def handle(self, function: Callable, *args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except ServiceNotAvailableError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Service not available')

        except MethodServiceNotAvailableError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Method service not available')

        except MethodServiceNotExistsError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail='Method service does not exists')

        except ServiceTemporaryNotAvailableError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail={
                                    'service':e.service,
                                    'message':'Service temporary not available'
                                })
        
        except ServiceNotImplementedError as e:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED,detail='Service not implemented')

        except MethodServiceNotImplementedError as e:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED,detail='Method Service not implemented')
            
        except StateProtocolMalFormattedError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail='State Protocol MalFormatted')

        except ServiceDoesNotExistError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail='Service does not exists')
            

class TemplateHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except AssetNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail='Asset not found')

        except TemplateNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail='Template not found')

        except TemplateInjectError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Error in the template'
            )

        except TemplateBuildError as e:
            detail = e.args[0] if e.args and len(e.args)>=1 else 'Cannot build template with data specified'
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail={'detail': detail,
                                'message': 'Template build error'})

        except TemplateValidationError as e:
            error = e.args[0]
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={
                'error': error,
                'message': 'Validation Error'
            })
    
        except TemplateFormatError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={
                'message': 'Template format is invalid',
                'error': e.args[0]
            })

        except TemplateCreationError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                'message': 'Failed to create template',
                'error': e.args[0]
            })
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={
                'message':'Could not be able to properly display the value'
            })

        except SchemaValidationError as e:
            error = e.args[0]
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                'error': error,
                'message': 'Validation Error'
            })


class WebSocketHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except WSPathNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                'message': 'WS Path Not Found'
            })


class CeleryTaskHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except CeleryTaskNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail={})

        except CeleryTaskNameNotExistsError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail={})

        except CelerySchedulerOptionError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail={})

        except QueueNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail={})

        except AlreadyRegistered as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail={})

        except NotRegistered as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail={})

        except MaxRetriesExceededError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={})


class TwilioHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except TwilioPhoneNumberParseError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                'message': 'Twilio phone number parse error',
                'detail': str(e)
            })
        
        except TwilioCallBusyError as e:
            ...
            
        except TwilioCallNoAnswerError as e:
            ...
        
        except TwilioCallFailedError as e:
            ...

        except TwilioRestException as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                'message': 'Twilio REST API error',
            })

        except SSLError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
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

        except ContactNotExistsError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                                'message': f'The user: {e.id} specified does not exists', 'ids':[e.id]})

        except ContactAlreadyExistsError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                                'message': 'Error could not create the user because info are already used', 'detail': e.message})

        except ContactDoubleOptInAlreadySetError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                                'message': 'Contact Double opt in is already set',})

        except ContactOptInCodeNotMatchError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                                'message': 'Contact Opt in code does not match',})


        except ContactMissingInfoKeyError as e:
            raise  HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={'message':f'Contact missing {e.info_key} info key'})


class TortoiseHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except OperationalError as e:
            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                                'message': 'Database execution error', 'detail': mess, })

        except ValidationError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)

            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                                'message': 'Validation error', 'detail': mess, })

        except DBConnectionError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                                'message': 'Database connection error', 'detail': mess, })

        except IntegrityError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
                                'message': 'Integrity error', 'detail': mess, })

        except DoesNotExist as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                                'message': 'Record not found', 'detail': mess, })

        except MultipleObjectsReturned as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                                'message': 'Multiple objects returned', 'detail': mess, })

        except TransactionManagementError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                                'message': 'Transaction management error', 'detail': mess, })

        except UnSupportedError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                                'message': 'Unsupported operation', 'detail': mess, })

        except ConfigurationError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                                'message': 'Configuration error', 'detail': mess, })

        except ParamsError as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                                'message': 'Parameters error', 'detail': mess, })

        except BaseORMException as e:
            print(e.__class__)

            mess = e.args[0]
            mess = str(mess)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                                'message': 'ORM error', 'detail': mess, })


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
                'message': 'Client is already blacklisted'if not e.reversed_ else 'Client is not blacklisted yet',
            })

        except ClientTokenHeaderNotProvidedError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                'message': 'Client token header not provided',
            })

        except AuthzIdMisMatchError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={
                'message': 'Authorization ID mismatch',
            })


class RequestErrorHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except IdentifierTypeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                'message': 'Invalid identifier type specified'
            })


class ValueErrorHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except ValueError as e:
            mess = e.args[0] if e else ''
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=mess)


class MotorErrorHandler(Handler):
    ...


class AsyncIOHandler(Handler):

    @InjectInMethod
    def __init__(self, loggerService: LoggerService):
        super().__init__()
        self.loggerService = loggerService
        self.prettyPrinter = self.loggerService.prettyPrinter

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        
        except asyncio.CancelledError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                'message': 'A Task was Cancelled',
            })

        except LockNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                'message': 'Could not wait for the data input',
            })
        except TimeoutError as e:
            result = e.args[0] if len(e.args) >0 else None

            raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail={
                'message': 'Timeout error',
                'result':result
            })
        except asyncio.TimeoutError as e:
            result = e.args[0] if len(e.args) >0 else None
            raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail={
                'message': 'Request timed out',
                'result':result
            })
        
        except KeepAliveTimeoutError as e:
            result = e.args[0] 
            raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail={
                'message': 'Request timed out',
                'result':result
            })
    
class ReactiveHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except ReactiveSubjectNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={
                'message':'subject id not found'
            })


class StreamDataParserHandler(Handler):
    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except SequentialStateError as e:
            raise HTTPException(
                status_code=409,
                detail=f"Sequential state error during data stream: {str(e)}"
            )

        except ContinuousStateError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Continuous state error during data stream: {str(e)}"
            )

        except DataParsingError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error parsing stream data: {str(e)}"
            )

        except ValidationDataError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Validation error in stream data: {str(e)}"
            )
        
class EmailRelatedHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        
        try:
            await super().handle(function, *args, **kwargs)
        except NotSameDomainEmailError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,)

        except EmailInvalidFormatError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,)


class ORMCacheHandler(Handler):
    
    async def handle(self, function, *args, **kwargs):
        return await function(*args,**kwargs)


async def handle_http_exception(function, *args, **kwargs):
    
    try:
        return await function(*args,**kwargs)
    except HTTPException as e:
        if e.status_code == status.HTTP_404_NOT_FOUND:
            raise ServerFileError('app/static/error-404-page/index.html',e.status_code)
        if e.status_code >= 400 and e.status_code< 500:
            raise ServerFileError('app/static/error-400-page/index.html',e.status_code)

        raise ServerFileError('app/static/error-500-page/index.html',e.status_code)
    


class FastAPIHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args,**kwargs)

        except ResponseValidationError as e :
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail={"message":"Error while sending the response","error":e.errors()})

        except LocalProtocolError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=e.error_status_hint)



class GlobalVarHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args,**kwargs)
        except GlobalKeyAlreadyExistsError as e:
            raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,detail=f"Key '{e.key}' already exists")
            
        
        except GlobalKeyDoesNotExistsError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=f"Key '{e.key}' does not exists or it is not a JSON")
            

class ProfileHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await super().handle(function, *args, **kwargs)
        
        except PydanticValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors(include_url=False,include_context=False))
        
        except ProfileModelTypeDoesNotExistsError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,)
    
        except ProfileNotAvailableError as e:
            raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE)
        
        except ProfileHasNotCapabilitiesError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

        except ProfileDoesNotExistsError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
        except ProfileNotSpecifiedError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    
        except ProfileCreationModelError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,detail='Profile model body cannot be parsed into JSON')
        
    

class VaultHandler(Handler):
    
    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args,**kwargs)
        except hvac.exceptions.InvalidRequest as e:
            raise HTTPException(500,)