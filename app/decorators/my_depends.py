from typing import Callable
from fastapi import Depends, HTTPException, Query,status
from app.classes.auth_permission import AuthPermission, ContactPermission, Role
from app.container import Get, GetDependsAttr
from app.models.contacts_model import ContactORM, ContentSubscriptionORM
from app.services.security_service import JWTAuthService
from app.services.twilio_service import TwilioService
from app.utils.dependencies import get_auth_permission



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



async def verify_admin_token(x_admin_token: Annotated[str, Header()]):
    configService:ConfigService = Get(ConfigService)
    
    if x_admin_token == None or x_admin_token != configService.ADMIN_KEY:
        raise HTTPException(status_code=403, detail="X-Admin-Token header invalid")