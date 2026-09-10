from typing import Any, Literal, Optional, Self
from tortoise import Tortoise, fields, models
from tortoise.contrib.pydantic import pydantic_model_creator
from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator
from app.classes.auth_permission import API_TOKEN_CLIENT_TYPE_SET, AuthType, ClientType, Scope
from app.utils.helper import generateId, subset_model, uuid_v1_mc
from app.utils.validation import ipv4_subnet_validator, ipv4_validator,PasswordValidator
from tortoise.contrib.postgres.fields import ArrayField

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
    client_name = fields.CharField(max_length=50, unique=True, null=True)
    client_email = fields.CharField(max_length=200,unique=True,null=False)
    client_username = fields.CharField(max_length=30, unique=True, null=False)
    client_description = fields.TextField()
    client_scope = fields.CharEnumField(enum_type=Scope, default=Scope.SoloDolo, max_length=25)
    client_type = fields.CharEnumField(enum_type=ClientType, default=ClientType.User, max_length=25)
    authenticated = fields.BooleanField(default=False) #NOTE Whether the client has been authenticated or not
    issued_for = fields.CharField(max_length=50, null=False, unique=True)
    group = fields.ForeignKeyField("security.GroupClientORM", related_name="group", on_delete=fields.SET_NULL, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    class Meta:
        schema = SCHEMA
        table = "client"

    @property
    def auth_type(self):
        return AuthType.API_TOKEN if self.client_type in API_TOKEN_CLIENT_TYPE_SET else AuthType.ACCESS_TOKEN

    @property
    def to_json(self):
        return {
            "client_id": str(self.client_id),
            "client_name": self.client_name,
            "client_username": self.client_username,
            "client_description": self.client_description,
            "client_scope": self.client_scope.value,
            "authenticated": self.authenticated,
            "client_type": self.client_type.value,
            "issued_for": self.issued_for,
            "group_id": str(self.group_id) if self.group else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

class PolicyMappingORM(models.Model):
    mapping_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    policy_id = fields.CharField(max_length=30, unique=True, null=False)
    client = fields.ForeignKeyField("security.ClientORM", related_name="policy_mappings", on_delete=fields.CASCADE, null=True)
    group = fields.ForeignKeyField("security.GroupClientORM", related_name="policy_mappings", on_delete=fields.CASCADE, null=True)

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

ClientModelBase = pydantic_model_creator(ClientORM, name="ClientORM", exclude=('created_at', 'updated_at','client_id',"authenticated","client_scope","group","client_username",))


def validate_ip(issued_for:str,scope:Scope):
    if scope == Scope.Organization:
        if not ipv4_subnet_validator(issued_for):
            raise ValueError('Invalid ipv4 subnet')
        return
    elif scope == Scope.SoloDolo:
        if not ipv4_validator(issued_for):
            raise ValueError('Invalid ipv4 address')
    else:
        if issued_for !=None:
            raise ValueError('Issued For must be Null')
    return

class GroupModel(BaseModel):
    group_name: str
    policies: list[str] = []

    @field_validator('group_name')
    def parse_name(cls,group_name:str):
        group_name= group_name.strip()
        return group_name
        group_name=group_name.lower()
        return group_name.capitalize()

class AdminClientModel(BaseModel):
    client_username:str = Field(min_length=12,max_length=30)
    issued_for:Optional[str] = Field(None,min_length=15,max_length=15)
    client_name:str = Field(min_length=10,max_length=70)
    client_scope:Scope = Field(Scope.Free)
    password:str

    @field_validator('password')
    def check_password(cls,p):
        return client_password_validator(p)

    @model_validator(mode="after")
    def validate_ip_issuance(self)->Self:
        validate_ip(self.issued_for,self.client_scope)
        return self

        
class ClientModel(ClientModelBase):
    password:Optional[str] = None
    client_scope:Scope = Field(Scope.SoloDolo)
    group:str | None = Field(None)
    client_description:str = Field(default=None,max_length=500)
    policies:list[str] = Field(default_factory=list,max_length=30)

    _client_id:str = PrivateAttr(default_factory=uuid_v1_mc)

    @model_validator(mode="after")
    def validate_ip_issuance(self)->Self:
        validate_ip(self.issued_for,self.client_scope)
        return self

    @field_validator('policies')
    def normalize_policies(self,val):
        return list(set(val))

    @model_validator(mode='after')
    def check_password(self):
        if self.client_type in API_TOKEN_CLIENT_TYPE_SET:
            raise ValueError(f'This client_type {self.client_type} is a passwordless type of authentication')
        return client_password_validator(self.password)
    
    @field_validator('client_type')
    def validate_client_type(cls,clientType:AuthType):
        if clientType == ClientType.Admin:
            raise ValueError('Cannot create an Admin client')
        return clientType
    
    @field_validator('client_description')
    def validate_description(cls,description:str)->str:
        return description.strip()


UpdateClientModelBase = subset_model(ClientModel,'UpdateClientModelBase',include={'client_name','issued_for','client_email','client_description','client_scope','password','policies'})
class UpdateClientModel(UpdateClientModelBase):

    remove_group:bool = Field(default=False)
    
    @model_validator(mode="after")
    def validate_ip_issuance(self)->Self:
        if self.client_scope != None and self.issued_for!=None:
            return super().validate_ip_issuance()
        
        return self

    @model_validator(mode="after")
    def validate_group_modification(self):
        if self.remove_group and self.group:
            raise ValueError('We cant remove the group if the group is set to be modified')
        return self
    
    @field_validator('password')
    def check_password(cls, password):
        if password!=None:
            return super().check_password(password)
        return password

    @field_validator('client_description')
    def validate_description(cls,description:str|None)->str|None:
        if description!=None:
            return super().validate_description(description)
        return description

    @field_validator('client_type')
    def validate_client_type(cls,x:Any):
        return x

    @model_validator('policies')
    def normalize_policies(cls,val):
        if val!=None:
            return super().normalize_policies(val)
        return val
    
    # @model_validator(mode="after")
    # def final_validate(self) -> Self:
    #     if all([self.client_scope is None, self.password is None, self.client_name is None, self.issued_for is None,self.group_id]):
    #         raise ValueError('At least one field must be provided for update.')
    #     return self

class BlacklistModel(BaseModel):
    mode:Literal['group','client','token']
    identity:str  = Field(min_length=1,max_length=500)
    time:float = Field(3600,le=36000,ge=3600)
    force:bool = Field(False)

class UnRevokeGenerationIDModel(BaseModel):
        version:int|None = None
        destroy:bool = False
        delete:bool = False
        version_to_delete:list[int] = []
