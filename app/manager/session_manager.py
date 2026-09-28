from fastapi import Cookie, Request, Response
from app.classes.auth_permission import AuthState
from app.container import Get
from app.errors.security_error import ClientAuthenticationFlagError, SecurityIdentityNotResolvedError, TokenExpiredError
from app.models.orm.security_model import ClientORM
from app.services.config_service import ConfigService
from app.services.security_service import JWTAuthService
from app.services.setting_service import SettingService

REFRESH_TOKEN_KEY='refresh_token'
REFRESH_PATH ='/auth/'

class AuthSessionManager:

    def __init__(self,request:Request,response:Response,refresh_token: str | None = Cookie(default=None)):
        self.request = request
        self.response = response

        self.refresh_token = refresh_token or None

        self.settingService = Get(SettingService)
        self.configService = Get(ConfigService)
        self.jwtService = Get(JWTAuthService)

        self.authState:AuthState = None
    
    def update_auth_state(self,authState:AuthState):
        self.authState = authState

    def is_client_authenticated(self,clientORM:ClientORM):
        try:
            refresh = self.verify_refresh_token(False)
            if refresh['status'] != 'expired': # NOTE active or inactive
                raise ClientAuthenticationFlagError(refresh['client_id'],True)
            else:
                if refresh['client_id'] != str(clientORM.client_id):
                    raise ... 
                return refresh['session_id']
        except (ClientAuthenticationFlagError,) as e:
            raise e
        except:
            return None
        

    def verify_refresh_token(self,raise_on_expired:bool=True):
        if self.refresh_token == None:
            raise SecurityIdentityNotResolvedError(None,'refresh_token not found')
        
        return self.jwtService.verify_refresh_permission(self.refresh_token,raise_on_expired)

    def logout(self):
        self.response.delete_cookie(
            key=REFRESH_TOKEN_KEY,
            path=REFRESH_PATH,
            httponly=True,
            secure=self.configService.HTTP_MODE == 'HTTPS',
            samesite='lax',
        )

    def login(self,refresh_token:str):
        self.response.set_cookie(
            key=REFRESH_TOKEN_KEY,
            value=refresh_token,
            httponly=True,
            secure=self.configService.HTTP_MODE == 'HTTPS',
            samesite='lax',
            path=REFRESH_PATH

        )