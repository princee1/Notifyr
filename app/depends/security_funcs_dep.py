from typing import Annotated
from fastapi import HTTPException, Header,status,Request
from app.container import Get
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService
from app.utils.globals import CAPABILITIES


def verify_dashboard_token(x_dashboard_token:Annotated[str,Header()]):
    configService:ConfigService = Get(ConfigService)
    securityService:SecurityService = Get(SecurityService)

def verify_dmz_token(x_dmz_token:Annotated[str,Header()]):
    configService:ConfigService = Get(ConfigService)
    securityService:SecurityService = Get(SecurityService)

if CAPABILITIES['twilio']:
    from app.services.ntfr.twilio_service import TwilioService,RequestValidator

    async def verify_twilio_token(request: Request):
        twilioService = Get(TwilioService)
        twilio_signature = request.headers.get("X-Twilio-Signature", None)

        if not twilio_signature:
            raise HTTPException(
                status_code=400, detail='Twilio Signature not available')

        full_url = str(request.url)

        form_data = await request.form()
        params = {key: form_data[key] for key in form_data}

        validator = RequestValidator(twilioService.main.auth_token)
        if not validator.validate(full_url, params, twilio_signature):
            raise HTTPException(
                status_code=403, detail="Invalid Twilio Signature")