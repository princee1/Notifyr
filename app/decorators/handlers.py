from asyncio import CancelledError
import asyncio
import traceback
from typing import Callable

import aiohttp
from amqp import AccessRefused
from fastapi.exceptions import ResponseValidationError
import hvac
from minio import S3Error, ServerError
import requests
from app.errors.llm_error import LLMProviderDoesNotExistError
from app.services.worker.arq_service import DataTaskNotFoundError, JobAlreadyExistsError, JobDequeueError, JobDoesNotExistsError, JobStatusNotValidError,ResultNotFound
from app.classes.auth_permission import WSPathNotFoundError
from app.classes.email import EmailInvalidFormatError, NotSameDomainEmailError
from app.classes.stream_data_parser import ContinuousStateError, DataParsingError, SequentialStateError, ValidationDataError
from app.classes.template import SchemaValidationError, SkipTemplateCreationError, TemplateBuildError, TemplateCreationError, TemplateFormatError, TemplateInjectError, TemplateNotFoundError, TemplateValidationError
from app.container import InjectInMethod
from app.definition._error import BaseError, ServerFileError
from app.definition._utils_decorator import Handler, HandlerDefaultException, NextHandlerException
from app.definition._service import MethodServiceNotExistsError, MethodServiceNotImplementedError, ServiceDoesNotExistError, ServiceNotAvailableError, MethodServiceNotAvailableError, ServiceNotImplementedError, ServiceTemporaryNotAvailableError, StateProtocolMalFormattedError
from fastapi import status, HTTPException
from app.classes.celery import CeleryNotAvailableError, CeleryRedisVisibilityTimeoutError, CelerySchedulerOptionError, CeleryTaskNameNotExistsError, CeleryTaskNotFoundError
from celery.exceptions import AlreadyRegistered, MaxRetriesExceededError, BackendStoreError, QueueNotFound, NotRegistered
from app.errors.aps_error import APSJobDoesNotExists
from app.errors.service_error import MiniServiceAlreadyExistsError,MiniServiceDoesNotExistsError,MiniServiceCannotBeIdentifiedError

from app.errors.async_error import KeepAliveTimeoutError, LockNotFoundError, ReactiveSubjectNotFoundError
from app.errors.contact_error import ContactAlreadyExistsError, ContactMissingInfoKeyError, ContactNotExistsError, ContactDoubleOptInAlreadySetError, ContactOptInCodeNotMatchError
from app.errors.properties_error import GlobalKeyAlreadyExistsError, GlobalKeyDoesNotExistsError
from app.errors.security_error import AlreadyBlacklistedClientError, AuthzIdMisMatchError, ClientDoesNotExistError, CouldNotCreateAuthTokenError, CouldNotCreateRefreshTokenError, GroupAlreadyBlacklistedError, GroupIdNotMatchError, SecurityIdentityNotResolvedError, ClientTokenHeaderNotProvidedError
from app.errors.twilio_error import TwilioCallBusyError, TwilioCallFailedError, TwilioCallNoAnswerError, TwilioPhoneNumberParseError
from app.classes.profiles import ProfileModelRequestBodyError, ProfileDoesNotExistsError, ProfileHasNotCapabilitiesError, ProfileModelTypeDoesNotExistsError, ProfileNotAvailableError, ProfileNotSpecifiedError, ProfileTypeNotMatchRequest
from app.services.assets_service import AssetConfusionError, AssetNotFoundError, AssetTypeNotAllowedError, AssetTypeNotFoundError
from twilio.base.exceptions import TwilioRestException

from tortoise.exceptions import OperationalError, DBConnectionError, ValidationError, IntegrityError, DoesNotExist, MultipleObjectsReturned, TransactionManagementError, UnSupportedError, ConfigurationError, ParamsError, BaseORMException
from requests.exceptions import SSLError, Timeout

from app.services.logger_service import LoggerService
from pydantic import BaseModel, ValidationError as PydanticValidationError
from app.errors.db_error import DocumentDoesNotExistsError, DocumentExistsUniqueConstraintError, DocumentPrimaryKeyConflictError,MemCacheNoValidKeysDefinedError, MemCachedTypeValueError
from app.utils.fileIO import ExtensionNotAllowedError, MultipleExtensionError
from aiomcache.exceptions import ClientException, ValidationException 
from pymemcache import MemcacheClientError,MemcacheServerError,MemcacheUnexpectedCloseError
from app.errors.upload_error import (
    MaxFileLimitError,
    FileTooLargeError,
    TotalFilesSizeExceededError,
    DuplicateFileNameError,
    InvalidExtensionError,
)


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
            print(e)
            traceback.print_exc()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={
                'message':'Could not be able to properly display the value'
            })

        except SchemaValidationError as e:
            error = e.args[0]
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                'error': error,
                'message': 'Validation Error'
            })
        except SkipTemplateCreationError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,detail='Couldnt create a template')


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

        except CeleryRedisVisibilityTimeoutError as e:
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
        
        except CeleryNotAvailableError as e:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED
            )

        except QueueNotFound as e:
            print(e)
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


        except AccessRefused:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,details='Could not connect to the broker'
            )

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

class ValueErrorHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except ValueError as e:
            mess = e.args[0] if e else ''
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=mess)


class MotorErrorHandler(Handler):
    
    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args,**kwargs)

        except DocumentDoesNotExistsError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Document with id {e.id} does not exists'
            )

        except DocumentPrimaryKeyConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": f'Document with "{e.pk_field}: {e.pk_value}" already exists',
                    "model": str(e.model)
                }
            )

        except DocumentExistsUniqueConstraintError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message":f"The document with the values entered {'already exists' if e.exists  else 'does not exists'}"
                }
            )


class AsyncIOHandler(Handler):

    @InjectInMethod()
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
    
        except ProfileModelRequestBodyError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,detail=e.message)
        
        except ProfileTypeNotMatchRequest as e:
            if e.motor_fallback:
                raise DocumentDoesNotExistsError(e.profile)
            
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
class PydanticHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await super().handle(function, *args, **kwargs)
        except PydanticValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors(include_url=False,include_context=False))
        
class VaultHandler(Handler):
    
    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args,**kwargs)
        except hvac.exceptions.InvalidRequest as e:
            raise HTTPException(500,)

        except hvac.exceptions.Forbidden as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        except hvac.exceptions.Unauthorized as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

        except requests.exceptions.ReadTimeout:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT,detail="Vault server did not respond in time")


class MiniServiceHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except MiniServiceAlreadyExistsError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="MiniService already exists"
            )
        except MiniServiceDoesNotExistsError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MiniService does not exist"
            )
        except MiniServiceCannotBeIdentifiedError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
               detail="MiniService cannot be identified"
            )

class S3Handler(Handler):

    error_codes_to_http_codes= {
        'NoSuchKey':status.HTTP_404_NOT_FOUND
    }

    async def handle(self, function:Callable, *args, **kwargs):
        try:
            return await function(*args,**kwargs)
        except S3Error as e:

            raise HTTPException(
                status_code=self.error_codes_to_http_codes.get(e.code,status.HTTP_500_INTERNAL_SERVER_ERROR),
                detail={
                    'message':'S3 Service error occurred',
                    'error_code':e.code,
                    'error_message':e.message,
                    'request_id':e.request_id,
                    'resource':e.resource,
                    'object_name':e.object_name
                }
            )
    
        except ServerError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f'Failed to build S3 Service due to server error: {str(e)}'
            )

class FileNamingHandler(Handler):

    async def handle(self,function: Callable, *args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except AssetTypeNotAllowedError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Asset type not allowed for upload."
            )

        except AssetTypeNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset type not found."
            )

        except MultipleExtensionError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Multiple file extensions detected; only one is allowed."
            )

        except ExtensionNotAllowedError as e :
            print(e.args)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The file extension is not allowed for this asset type." if not e.args else e.args[0]
            )
        except AssetConfusionError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"XML asset filenames must start with either of those values '{e.asset_confusion}'. Received: '{e.filename}'"
            )

import redis
from fastapi import HTTPException, status

class RedisHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except redis.exceptions.AuthenticationError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Redis authentication failed"
            )

        except redis.exceptions.AuthorizationError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Redis authorization failed"
            )

        except redis.exceptions.ConnectionError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis service unavailable"
            )

        except redis.exceptions.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Redis request timed out"
            )

        except redis.exceptions.BusyLoadingError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis is loading data"
            )

        except redis.exceptions.ReadOnlyError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis is in read-only mode"
            )

        except redis.exceptions.OutOfMemoryError:
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                detail="Redis out of memory"
            )

        except redis.exceptions.ClusterDownError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis cluster is down"
            )

        except (redis.exceptions.AskError, redis.exceptions.MovedError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis cluster redirection error"
            )

        except redis.exceptions.NoScriptError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Redis Lua script not found"
            )

        except redis.exceptions.DataError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid data sent to Redis"
            )

        except redis.exceptions.ResponseError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        except redis.exceptions.LockError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Redis lock error"
            )

class MemCachedHandler(Handler):

    async def handle(self,function:Callable,*args,**kwargs):

        try:
            return await function(*args,**kwargs)
        
        except MemCachedTypeValueError as e:
            ...
        
        except MemCacheNoValidKeysDefinedError as e:
            ...
        
        except MemcacheClientError as e:
            ...
        
        except MemcacheServerError as e:
            ...
        
        except MemcacheUnexpectedCloseError as e:
            ...
        
        except ValidationException as e:
            ...
        
        except ClientException as e:
            ...
    
from app.classes.cost_definition import (
    CostException,
    CostLessThanZeroError,
    CostMoreThanZeroError,
    CreditNotInPlanError,
    PaymentFailedError,
    InsufficientCreditsError,
    InvalidPurchaseRequestError,
    CreditDeductionFailedError,
    CurrencyNotSupportedError,
    ProductNotFoundError,
)

class CostHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except PaymentFailedError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={'message': 'Payment gateway failure', 'error': str(e)}
            )

        except InsufficientCreditsError as e:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    'message': 'Insufficient credits to complete the purchase',
                    'credit':e.credit,
                    'current_balance':e.current_balance,
                    'purchase_cost':e.purchase_cost
                    }
            )

        except InvalidPurchaseRequestError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={'message': 'Invalid purchase request', 'error': str(e)}
            )

        except CreditDeductionFailedError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={'message': 'Credit deduction failed', 'error': str(e)}
            )

        except CurrencyNotSupportedError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={'message': 'Currency not supported', 'error': str(e)}
            )

        except ProductNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={'message': 'Product not found', 'error': str(e)}
            )
    
        except CostLessThanZeroError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f'Trying to deduct credit but losing money instead {e.total}'
            )

        except CostMoreThanZeroError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f'Trying to give credit but taking money instead: {e.total}'
            )
    
        except CreditNotInPlanError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={'message':'Credit does not appear in the plan','error':str(e)}
            )

        except CostException as e:
            # generic cost-related errors fallback
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={'message': 'Cost processing error', 'error': str(e)}
            )

class CeleryControlHandler(Handler):
    ...


class ArqHandler(Handler):
    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except ResultNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Result not found", "reason":str(e)}
            )
        except JobDoesNotExistsError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"job_id": e.job_id, "reason": e.reason}
            )
        except DataTaskNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"job_id": e.job_id, "reason": e.reason}
            )

        except JobAlreadyExistsError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"job_id": e.job_id, "reason": e.reason}
            )

        except JobStatusNotValidError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={'job_id':e.job_id,'status':e.status}
            )

        except JobDequeueError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={'job_id':e.job_id}
            )

class APSSchedulerHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        
        try:
            return await function(*args,**kwargs)

        except APSJobDoesNotExists as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=''
            )
            

class UploadFileHandler(Handler):

    async def handle(self, function: Callable, *args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except MaxFileLimitError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        except DuplicateFileNameError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        except InvalidExtensionError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        except FileTooLargeError as e:
            # 413 Payload Too Large
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))

        except TotalFilesSizeExceededError as e:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))


class FileHandler(Handler):
    
    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except PermissionError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: You do not have access to this file. {str(e)}"
            )
        except IsADirectoryError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid path: The specified path is a directory, not a file. {str(e)}"
            )
        except FileNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resource not found: {str(e)}"
            )
        except OSError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An internal server error occurred while processing the file."
            )
        

class ProxyRestGatewayHandler(Handler):


    async def handle(self, function, *args, **kwargs):
        try:
            return await super().handle(function, *args, **kwargs)

        except aiohttp.ClientPayloadError as e:
            body = e.args[0]
            status = e.args[1]


class AgenticHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await super().handle(function, *args, **kwargs)
        except LLMProviderDoesNotExistError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'LLM provider with id {e.provider} does not exist'
            )