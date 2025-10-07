from typing import Self
from tortoise import Tortoise, fields, models
from tortoise.contrib.pydantic import pydantic_model_creator
from pydantic import BaseModel, field_validator, model_validator
from app.classes.auth_permission import ClientType, Scope
from app.utils.helper import uuid_v1_mc
from app.utils.validation import ipv4_subnet_validator, ipv4_validator,PasswordValidator


SCHEMA = 'security'


class GroupClientORM(models.Model):
    group_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    group_name = fields.CharField(max_length=80, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        schema = SCHEMA
        table = "groupclient"

    @property
    def to_json(self):
        return {
            "group_id": str(self.group_id),
            "group_name": self.group_name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

class ClientORM(models.Model):
    client_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    client_name = fields.CharField(max_length=200, unique=True, null=True)
    client_scope = fields.CharEnumField(enum_type=Scope, default=Scope.SoloDolo, max_length=25)
    authenticated = fields.BooleanField(default=False)
    password = fields.TextField()
    password_salt = fields.TextField()
    max_connection = fields.IntField(default=1)
    current_connection_count = fields.IntField(default=0)
    can_login = fields.BooleanField(default=False)
    client_type = fields.CharEnumField(enum_type=ClientType, default=ClientType.User, max_length=25)
    issued_for = fields.CharField(max_length=50, null=False, unique=True)
    group = fields.ForeignKeyField("models.GroupClientORM", related_name="group", on_delete=fields.SET_NULL, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        schema = SCHEMA
        table = "client"

    @property
    def to_json(self):
        return {
            "client_id": str(self.client_id),
            "client_name": self.client_name,
            "client_scope": self.client_scope.value,
            "authenticated": self.authenticated,
            "max_connection":self.max_connection,
            "current_connection_count":self.current_connection_count,
            "client_type": self.client_type.value,
            "issued_for": self.issued_for,
            "group_id": str(self.group_id) if self.group else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

class ChallengeORM(models.Model):
    client = fields.OneToOneField("models.ClientORM", pk=True, related_name="challenge", on_delete=fields.CASCADE)
    challenge_auth = fields.TextField(generated=True)
    created_at_auth = fields.DatetimeField(auto_now_add=True)
    expired_at_auth = fields.DatetimeField(null=True)
    challenge_refresh = fields.TextField(generated=True)
    created_at_refresh = fields.DatetimeField(auto_now_add=True)
    expired_at_refresh = fields.DatetimeField(null=True)
    last_authz_id=fields.UUIDField(generated=True)

    class Meta:
        schema = SCHEMA
        table = "challenge"

class BlacklistORM(models.Model):
    blacklist_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    client = fields.ForeignKeyField("models.ClientORM", related_name="blacklist", on_delete=fields.CASCADE, null=True)
    group = fields.ForeignKeyField("models.GroupClientORM", related_name="groupclient", on_delete=fields.CASCADE, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    expired_at = fields.DatetimeField(null=False)

    class Meta:
        schema = SCHEMA
        table = "blacklist"

    @property
    def to_json(self):
        return {
            "blacklist_id": str(self.blacklist_id),
            "client_id": str(self.client_id) if self.client else None,
            "group_id": str(self.group_id) if self.group else None,
            "created_at": self.created_at.isoformat(),
            "expired_at": self.expired_at.isoformat() if self.expired_at else None
        }

class PolicyORM(models.Model):
    policy_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    allowed_profiles = fields.JSONField(default=list)  # TEXT[] as list
    allowed_routes = fields.JSONField(default=dict)    # JSONB as dict
    allowed_assets = fields.JSONField(default=list)    # TEXT[] as list
    roles = fields.JSONField(default=lambda: ["PUBLIC"])  # role[] as list
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        schema = SCHEMA
        table = "policy"
    
    @property
    def to_json(self,):
        return {
            'policy_id':str(self.policy_id),
            'allowed_profiles':self.allowed_profiles,
            'allowed_routes':self.allowed_routes,
            'allowed_assets':self.allowed_assets,
            'roles':self.roles,
            'created_at':self.created_at.isoformat(),
            'updated_at':self.updated_at.isoformat()

        }

class PolicyMappingORM(models.Model):
    mapping_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    policy = fields.ForeignKeyField("models.PolicyORM", related_name="mappings", on_delete=fields.CASCADE)
    client = fields.ForeignKeyField("models.ClientORM", related_name="policy_mappings", on_delete=fields.CASCADE, null=True)
    group = fields.ForeignKeyField("models.GroupClientORM", related_name="policy_mappings", on_delete=fields.CASCADE, null=True)

    class Meta:
        schema = SCHEMA
        table = "policymapping"
        unique_together = [
            ("policy", "client"),
            ("policy", "group"),
        ]
        
    @property
    def to_json(self):
        return {
            'mapping_id':str(self.mapping_id),
            'policy_id':str(self.policy_id),
            'client_id':str(self.client_id) if self.client else None,
            'group_id':str(self.group_id) if self.group else None,
        }

client_password_validator = PasswordValidator(12,60,)

ClientModelBase = pydantic_model_creator(ClientORM, name="ClientORM", exclude=('created_at', 'updated_at','client_id',"authenticated","client_scope","group","password_salt","can_login"))


class GroupModel(BaseModel):
    group_name: str
    policy_ids: list[str] = []

    @field_validator('group_name')
    def parse_name(cls,group_name:str):
        group_name= group_name.strip()
        return group_name
        group_name=group_name.lower()
        return group_name.capitalize()

class ClientModel(ClientModelBase):
    
    client_scope:Scope
    group_id:str | None = None
    policy_ids:list[str] =[]

    @model_validator(mode="after")
    def validate_ip_issuance(self)->Self:
        if self.client_scope == Scope.Organization:
            if not ipv4_subnet_validator(self.issued_for):
                raise ValueError('Invalid ipv4 subnet')
            return self
        if not ipv4_validator(self.issued_for):
            raise ValueError('Invalid ipv4 address')
        return self

    @field_validator('password')
    def check_password(cls,password:str):
        return client_password_validator(password)

class UpdateClientModel(ClientModel):
    client_scope:Scope|None = None
    password:str|None = None
    client_name:str | None = None
    issued_for:str | None = None

    @model_validator(mode="after")
    def validate_ip_issuance(self)->Self:
        if self.client_scope != None and self.issued_for!=None:
            return super().validate_ip_issuance
        return self
    
    @field_validator('password')
    def check_password(cls, password):
        if password!=None:
            return super().check_password(password)
        return password
    
    # @model_validator(mode="after")
    # def final_validate(self) -> Self:
    #     if all([self.client_scope is None, self.password is None, self.client_name is None, self.issued_for is None,self.group_id]):
    #         raise ValueError('At least one field must be provided for update.')
    #     return self


async def raw_revoke_challenges(client:ClientORM):
    query = "SELECT security.raw_revoke_challenges($1::UUID);"
    tortoise_client = Tortoise.get_connection('default')
    return await tortoise_client.execute_query(query, [client.client_id])

async def raw_revoke_auth_token(client:ClientORM):
    query = "SELECT security.raw_revoke_auth_token($1::UUID);"
    tortoise_client = Tortoise.get_connection('default')
    return await tortoise_client.execute_query(query, [client.client_id])