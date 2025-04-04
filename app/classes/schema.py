from ..utils.constant import ValidationHTMLConstant
from ..utils.helper import parse_value, parseToDataStruct,key_builder,default_flattenReducer
from bs4 import Tag
from enum import Enum
from typing import Any, Literal
from ..utils.prettyprint import printJSON


class CSSLevel(Enum):
    SAME = ","
    CHILDREN = " "
    DIRECT_CHILDREN = ">"


class SchemaBuilder:
    pass


coerce = {

}

transform = {

}


class MLSchemaBuilder (SchemaBuilder):
    CurrentHashRegistry = {}
    HashSchemaRegistry = {}

    def __init__(self, root) -> None:
        self.root: Tag = root
        # next_children = self.css_selectorBuilder(CSSLevel.SAME, [ValidationHTMLConstant.VALIDATION_ITEM_BALISE,
        #                                          ValidationHTMLConstant.VALIDATION_VALUES_RULES_BALISE, ValidationHTMLConstant.VALIDATION_KEYS_RULES_BALISE])
        self.transform: dict[str,str] = {}
        self.schema: dict[str, dict] = self.find(self.root)
       

    def find(self, validation_item: Tag, parent_key="",css_selector: str | None = None, next_children_css_selector=None):
        schema: dict[str, dict | str] = {}
        # next_children_css_selector = css_selector if next_children_css_selector is None else next_children_css_selector
        for validator in validation_item.find_all(ValidationHTMLConstant.VALIDATION_ITEM_BALISE, recursive=False):
            v: Tag = validator
            has_noSuccessor = len(v.find_all(ValidationHTMLConstant.VALIDATION_ITEM_BALISE, recursive=False)) == 0
            
            if not v.attrs.__contains__("type"):
                # TODO find the error element
                raise TypeError("Specify the type of the value")
            if not v.attrs.__contains__("id") and v.name == ValidationHTMLConstant.VALIDATION_ITEM_BALISE:
                # TODO find the error element
                raise NameError("Specify the id of the value")
            key = v.attrs["id"]
            # TODO validates arguments
            schema[key] = self.parse(v.attrs)

            if 'coerce' in schema:
                try:
                    value = schema["coerce"]
                    value = self._parse_to_direct_values(value,coerce)

                    schema['coerce'] = value
                except:
                    del schema['coerce']

            is_struct = v.attrs['type'] in ["list", "dict"]

            if has_noSuccessor:
                if is_struct:
                    raise TypeError("Specify the type of the children of the structure")

                if schema[key].__contains__("schema"):
                    default_schema_registry = schema[key]["schema"]
                    if type(default_schema_registry) == str and default_schema_registry in MLSchemaBuilder.HashSchemaRegistry.keys():
                        schema[key]["schema"] = MLSchemaBuilder.HashSchemaRegistry[default_schema_registry]
                
                if 'transform' in schema:
                    value = schema['transform']
                    value = self._parse_to_direct_values(value,transform)
                    abs_key = key if parent_key == '' else default_flattenReducer(key_builder(parent_key),key)
                    self.transform[abs_key] = value
                
                continue

            if not is_struct:
                type_ = v.attrs["type"]
                # TODO: find the one element that was supposed to be a dict or a list and that has children
                raise TypeError(f"{key} cannot have defined children because it is not a struct: Type: {type_}")

            if 'transform' in schema:
                raise TypeError('Transform cant be in a schema')     
                   
            successor_schema = self.find(v,key)
            next_key = "schema"  # NOTE might add valuerules
            schema[key][next_key] = successor_schema
        return schema

    def _parse_to_direct_values(self, value,data):
        if type(value,dict):
            raise ValueError
        elif type(value,(list,tuple)):
            value = [data[v] for v in value]
        else:
            value = data[value]
        return value

    def parse(self, attrs: dict[str, Any]):
        schema: dict[str, Any] = {}
        for key, val in attrs.items():
            if key == "id":
                continue
            parsed_value = parse_value(val)
            schema[key] = parsed_value
        return schema

    def css_selectorBuilder(self, level: CSSLevel, css_elements: list[str]):
        """
        The function `sameLevel_css_selectorBuilder` takes a list of CSS elments and joins them
        together with a CSSLevel value.

        :param css_element: A list of HTML that you want to combine into a single CSS selector
        :type css_select: list[str]

        :param level: A level that will define how we select the values

        :return: returns a single string that is the result of joining all the HTML element in the level decided.
        """
        return level.value.join(css_elements)
