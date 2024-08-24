from .constant import ValidationHTMLConstant
from .helper import parse_value
from bs4 import Tag
from enum import Enum
from typing import Any, Literal
from utils.prettyprint import printJSON


class CSSLevel(Enum):
    SAME = ","
    CHILDREN = " "
    DIRECT_CHILDREN = ">"


class SchemaBuilder:
    pass


class HtmlSchemaBuilder (SchemaBuilder):
    CurrentHashRegistry = {}
    HashSchemaRegistry = {}

    def __init__(self, root) -> None:
        self.root: Tag = root
        # next_children = self.css_selectorBuilder(CSSLevel.SAME, [ValidationHTMLConstant.VALIDATION_ITEM_BALISE,
        #                                          ValidationHTMLConstant.VALIDATION_VALUES_RULES_BALISE, ValidationHTMLConstant.VALIDATION_KEYS_RULES_BALISE])
        self.schema: dict[str, dict] = self.find(self.root)
        printJSON(self.schema)

    def find(self, validation_item: Tag, css_selector: str | None = None, next_children_css_selector=None):
        schema: dict[str, dict | str] = {}
        # next_children_css_selector = css_selector if next_children_css_selector is None else next_children_css_selector
        for validator in validation_item.find_all(ValidationHTMLConstant.VALIDATION_ITEM_BALISE, recursive=False):
            v: Tag = validator
            has_noSuccessor = len(v.find_all(
                ValidationHTMLConstant.VALIDATION_ITEM_BALISE, recursive=False)) == 0
            if not v.attrs.__contains__("type"):
                # TODO find the error element
                raise TypeError
            if not v.attrs.__contains__("id") and v.name == ValidationHTMLConstant.VALIDATION_ITEM_BALISE:
                # TODO find the error element
                raise NameError
            key = v.attrs["id"]
            # TODO validates arguments
            schema[key] = self.parse(v.attrs)

            is_struct = v.attrs['type'] in ["list", "dict"]
            if has_noSuccessor:
                if not is_struct:
                    raise TypeError

                if schema[key].__contains__("schema"):
                    default_schema_registry = schema[key]["schema"]
                    if type(default_schema_registry) == str and default_schema_registry in HtmlSchemaBuilder.HashSchemaRegistry.keys():
                        schema[key]["schema"] = HtmlSchemaBuilder.HashSchemaRegistry[default_schema_registry]
                continue

            if not is_struct:
                raise TypeError
            successor_schema = self.find(v)
            next_key = "schema"  # NOTE might add valuerules
            schema[key][next_key] = successor_schema
        return schema

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
