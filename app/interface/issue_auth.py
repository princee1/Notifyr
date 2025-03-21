from app.classes.auth_permission import AuthPermission
from app.definition._interface import Interface, IsInterface
from app.models.security_model import ChallengeORM
from app.services.admin_service import AdminService

@IsInterface
class IssueAuthInterface(Interface):

    def __init__(self,adminService:AdminService):
        self.adminService:AdminService =adminService
    
    def _transform_to_auth_model(self, permission: AuthPermission):
        ...

    async def issue_auth(self, client, authPermission):
        challenge = await ChallengeORM.filter(client=client).first()
        auth_model = self._transform_to_auth_model(authPermission)
        auth_token, refresh_token = self.adminService.issue_auth(challenge, client, auth_model)
        return auth_token, refresh_token
