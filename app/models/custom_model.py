from typing import ClassVar, Dict, List, Literal, Self, Type

from pydantic import ConfigDict, field_validator, model_validator
from app.classes.mongo import BaseDocument
from app.utils.constant import MongooseDBConstant
from app.utils.helper import subset_model
from app.utils.validation import Validator


class CustomModel(BaseDocument):
    schema: Dict
    model_type: Literal['Entity', 'Edge'] = 'Entity'
    edge_map: List[List[str]] = []

    _collection: ClassVar[str] = MongooseDBConstant.CUSTOM_MODEL_COLLECTION
    _unique_indexes: ClassVar[List[str]] = ['schema']

    @field_validator('alias')
    def alias_no_validation(cls, alias):
        if alias == 'Entity':
            raise ValueError('Alias cant have the "Entity" name ')
        if ' ' in alias:
            raise ValueError("Alias cannot contain spaces")
        return alias

    @field_validator('schema')
    def schema_validation(cls, schema):
        if not schema:
            raise ValueError("Schema cannot be empty")
        Validator(schema)
        return schema
    
    @model_validator(mode='after')
    def edge_map_pairs(self:Self)->Self:
        if self.model_type == 'Entity':
            return self
        
        for edge in self.edge_map:
            if not isinstance(edge, list) or len(edge) != 2:
                raise ValueError("Each edge in edge_map must be a list of exactly two elements")
        return self

        


UpdateCustomModelFactory:Type[CustomModel] = subset_model(CustomModel,f'Update{CustomModel.__name__}',__config__=ConfigDict(extra="forbid"),exclude=('model_type'))


class UpdateCustomModel(UpdateCustomModelFactory):
    ...