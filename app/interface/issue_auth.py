from dataclasses import dataclass
from app.classes.auth_permission import AuthPermission, Role, Scope
from app.definition._interface import Interface, IsInterface
from app.models.security_model import ChallengeORM, ClientORM, raw_revoke_challenges
from app.services.admin_service import AdminService


@IsInterface
class IssueAuthInterface(Interface):
    @dataclass
    class AuthModel:
        scope:Scope
        roles:list[str|Role]
        allowed_routes:list
        allowed_assets:list

    def __init__(self,adminService:AdminService):
        self.adminService:AdminService =adminService
    
    def _transform_to_auth_model(self, permission: AuthPermission):
        permission['roles']=[r.value for r in permission['roles']]
        return IssueAuthInterface.AuthModel(permission['scope'],permission['roles'],permission['allowed_routes'],permission['allowed_assets'])

    async def issue_auth(self, client, authPermission):
        challenge = await ChallengeORM.filter(client=client).first()
        auth_model = self._transform_to_auth_model(authPermission)

        auth_token, refresh_token = self.adminService.issue_auth(challenge, client, auth_model)
        return auth_token, refresh_token

    async def _revoke_client(self, client:ClientORM):
        await raw_revoke_challenges(client)
        client.authenticated = False
        await client.save()