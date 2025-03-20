import functools
from typing import Callable
from fastapi import Depends, HTTPException, Query, Request,status
from app.classes.auth_permission import AuthPermission, ContactPermission, Role
from app.container import Get, GetDependsAttr
from app.models.contacts_model import ContactORM, ContentSubscriptionORM
from app.models.security_model import ClientORM, GroupClientORM
from app.services.security_service import JWTAuthService
from app.services.twilio_service import TwilioService
from app.utils.dependencies import get_auth_permission


def AcceptNone(pos,key=None ):

    def depends(func:Callable):

        @functools.warps(func)
        async def wrapper(*args,**kwargs):
            if key !=None:
                param = kwargs[key]
            else:
                param = args[pos]
            
            if param==None:
                return None
            
            return await func(*args,**kwargs)
        return wrapper

    return depends



verify_twilio_token:Callable = GetDependsAttr(TwilioService,'verify_twilio_token')


async def get_contacts(contact_id: str, idtype: str = Query("id"),authPermission:AuthPermission=Depends(get_auth_permission)) -> ContactORM:

    if Role.CONTACTS not in authPermission['roles']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Role not allowed")
        
    match idtype:
        case "id":
            user = await ContactORM.filter(contact_id=contact_id).first()

        case "phone":
            user = await ContactORM.filter(phone=contact_id).first()

        case "email":
            user = await ContactORM.filter(email=contact_id).first()

        case _:
            raise HTTPException(
                400,{"message": "idtype not not properly specified"})

    if user == None:
        raise HTTPException(404, {"detail": "user does not exists"})

    return user

def get_contact_permission(token:str= Query(None))->ContactPermission:

    jwtAuthService:JWTAuthService = Get(JWTAuthService)
    if token == None:
        raise # TODO 
    return jwtAuthService.verify_contact_permission(token)

async def get_subs_content(content_id:str,content_idtype:str = Query('id'),authPermission:AuthPermission=Depends(get_auth_permission))->ContentSubscriptionORM:

    if Role.SUBSCRIPTION not in authPermission['roles']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Role not allowed")
    
    match content_idtype:
        case "id":
            content = await ContentSubscriptionORM.filter(content_id=content_id).first()
        case "name":
            content = await ContentSubscriptionORM.filter(name=content_id).first()
        case _:
            raise HTTPException(
                400,{"message": "idtype not not properly specified"})
    
    if content == None:
        raise HTTPException(404, {"message": "Subscription Content does not exists with those information"})


def cost()->int:
    ...
    
def key_contact_id()->str:
    ...

def key_client_id()->str:
    ...

def key_group_id()->str:
    ...

@AcceptNone(0)
async def get_client(client_id:str,idtype:str=Query('id'),authPermission:AuthPermission=Depends(get_auth_permission))->ClientORM:
    # TODO check if client is a user type and if it is admin says it does not exists
    ...

@AcceptNone(0)
async def get_group(group_id:str,idtype:str=Query('id'),authPermission:AuthPermission=Depends(get_auth_permission))->GroupClientORM:
    ...