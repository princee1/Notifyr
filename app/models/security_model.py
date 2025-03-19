from tortoise import fields, models
from tortoise.contrib.pydantic import pydantic_model_creator
import uuid
from pydantic import BaseModel, field_validator

from app.classes.auth_permission import Scope

SCHEMA = 'security'


class GroupClientORM(models.Model):
    group_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    group_name = fields.CharField(max_length=80, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        schema = SCHEMA
        table = "groupclient"

class ClientORM(models.Model):
    client_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    client_name = fields.CharField(max_length=120, unique=True, null=True)
    client_scope = fields.CharEnumField(enum_type=Scope, default=Scope.SoloDolo)
    group_id = fields.ForeignKeyField("models.GroupClientORM", related_name="group", on_delete=fields.SET_NULL, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        schema = SCHEMA
        table = "client"

class ChallengeORM(models.Model):
    client_id = fields.OneToOneField("models.ClientORM", pk=True, related_name="client", on_delete=fields.CASCADE)
    challenge_auth = fields.TextField(unique=True)
    created_at_auth = fields.DatetimeField(auto_now_add=True)
    expired_at_auth = fields.DatetimeField(null=True)
    challenge_refresh = fields.TextField(unique=True)
    created_at_refresh = fields.DatetimeField(auto_now_add=True)
    expired_at_refresh = fields.DatetimeField(null=True)

    class Meta:
        schema = SCHEMA
        table = "challenge"

class BlacklistORM(models.Model):
    blacklist_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    client_id = fields.ForeignKeyField("models.ClientORM", related_name="client", on_delete=fields.CASCADE, null=True)
    group_id = fields.ForeignKeyField("models.GroupClientORM", related_name="groupclient", on_delete=fields.CASCADE, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    expired_at = fields.DatetimeField(null=True)

    class Meta:
        schema = SCHEMA
        table = "blacklist"


class GroupModel(BaseModel):
    group_name: str

    @field_validator('group_name')
    def parse_name(cls,group_name:str):
        group_name= group_name.strip()
        group_name=group_name.lower()
        # TODO add regex remove extra space
        return group_name.capitalize()
    

ClientModelBase = pydantic_model_creator(ClientORM, name="ClientORM", exclude=('created_at', 'updated_at','client_id'))

class ClientModel(ClientModelBase):
    ...
