from fastapi import Cookie, Request, Response
from app.classes.auth_permission import AuthState
from app.container import Get
from app.errors.security_error import SecurityIdentityNotResolvedError
from app.services.config_service import ConfigService
from app.services.security_service import JWTAuthService
from app.services.setting_service import SettingService

REFRESH_TOKEN_KEY='notifyr_refresh_token'
REFRESH_PATH ='/auth/'

class AuthSessionManager:

    def __init__(self,request:Request,response:Response,refresh_token: str | None = Cookie(default=None)):
        self.request = request
        self.response = response

        self.refresh_token = refresh_token

        self.settingService = Get(SettingService)
        self.configService = Get(ConfigService)
        self.jwtService = Get(JWTAuthService)

        self.authState:AuthState = None
    
    def update_auth_state(self,authState:AuthState):
        self.authState = authState

    def verify_refresh_token(self,raise_on_expired:bool=True):
        if self.refresh_token == None:
            raise SecurityIdentityNotResolvedError(None,'refresh_token not found')
        
        return self.jwtService.verify_refresh_permission(self.refresh_token,raise_on_expired)

    def logout(self):
        self.response.delete_cookie(
            key=REFRESH_TOKEN_KEY,
            path=REFRESH_PATH,
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