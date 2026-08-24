from dataclasses import dataclass
import re
from typing import Any, Callable, Iterable, Literal

PATH_SEPARATOR = "/"

@dataclass
class APIRoute:
    methods:list[str]
    path_format:Any

@dataclass(frozen=True)
class PathParameter:
    name: str
    converter: str | None = None

    @property
    def operation_name(self) -> str:
        if self.converter:
            return f"{self.name}_{self.converter}"
        return self.name

##############################################################################################################
#############################                                                            #####################
##############################################################################################################


class OperationIDFactory:

    def __call__(self,route:APIRoute )->str:
        ...

    def compute(self,methods:list[str],path:str,func_name:str)->str:
        ...


class SimpleOperationID(OperationIDFactory):

    def __init__(self,
                 prefix: str | None = None,
                 operation_id: str | None = None,
                 *,
                 separator: str = "_",
                 prefix_separator:str = ":",
                 method_separator: str = "_",
                 identifier:Literal['path','func']='func',
                 add_method:bool = True,
                 lower: bool = True,
                 upper: bool = False,
                 callback: Callable[[str, str | None, list[str]], str] | None = None):
        
        self.prefix = prefix
        self.operation_id = operation_id

        self.separator = separator
        self.method_separator = method_separator
        self.prefix_separator = prefix_separator

        self.lower = lower
        self.upper = upper
        self.add_method = add_method

        self.callback = callback
        self.identifier = identifier

    def _normalize_route_name(self, route_name: str) -> str:
        route_name = str(route_name or "").strip(PATH_SEPARATOR)
        if not route_name:
            route_name = "root"

        route_name = route_name.replace(PATH_SEPARATOR, self.separator)
        route_name = route_name.replace(" ", self.separator)

        if self.lower:
            route_name = route_name.lower()
        elif self.upper:
            route_name = route_name.upper()

        return route_name
 
    def _normalize_methods(self, methods: list[str]) -> list[str]:
        if methods is None:
            return []

        if self.lower:
            return [m.lower() for m in methods]
        return methods
    
    def _build_operation_id(self, route_name: str, func_name:str, method_name: list[str]) -> str:
        parts: list[str] = []

        if self.prefix:
            parts.append(str(self.prefix).strip(self.separator))
            parts.append(self.prefix_separator)

        if self.add_method:
            methods = self._normalize_methods(method_name)
            parts.append(self.method_separator.join(methods))

        if self.identifier == 'path':
            route_id = self._normalize_route_name(route_name)
        else:
            route_id = func_name

        parts.append(route_id)
        
        return self.separator.join(part for part in parts if part)

    def compute(self,methods: list[str],route_name: str,func_name:str) -> str:

        if self.operation_id is not None:
            return str(self.operation_id)

        if self.callback is not None:
            return str(self.callback(route_name, self.prefix, methods, self.operation_id))

        return self._build_operation_id(route_name,func_name, methods)

    def __call__(self,route:APIRoute):
        return self.compute(route.methods,route.path_format,None)
    
    def __repr__(self) -> str:
        return f"OperationID(prefix={self.prefix!r}, separator={self.separator!r}, method_separator={self.method_separator!r})"

class MCPOperationID(OperationIDFactory):
    """
    Generate deterministic MCP-friendly operation IDs.

    Example:

        operation_id = MCPOperationID(prefix="email")

        operation_id.generate(
            {"POST"},
            "/email/template/{profile}/{template:path}/",
        )

        -> send_template_email_with_profile_using_template_path
    """

    DEFAULT_ACTION_WORD_MAP = {
        "GET": "get",
        "POST": "send",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
        "HEAD": "head",
        "OPTIONS": "options",
    }

    DEFAULT_PARAMETER_RELATION_MAP = {
        "profile": "with",
        "id": "with",
    }

    _PARAMETER_RE = re.compile(
        r"^\{(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)(?::(?P<converter>[^}]+))?\}$"
    )

    def __init__(self,prefix: str,operation_id:str=None,*,action_word_map: dict[str, str] | None = None,parameter_relation_map: dict[str, str] | None = None,):
        self.operation_id:str=operation_id
        self.prefix = self._normalize_segment(prefix)
        self.action_word_map = {**self.DEFAULT_ACTION_WORD_MAP,**(action_word_map or {}),}
        self.parameter_relation_map = {**self.DEFAULT_PARAMETER_RELATION_MAP,**(parameter_relation_map or {}),}

    def __call__(self, route:APIRoute) -> str:
        return self.generate(route.methods, route.path_format)

    def generate(self,methods: Iterable[str],path: str,) -> str:
        if self.operation_id != None:
            return self.operation_id
        
        method = self._get_method(methods)
        action = self._action_word(method)

        segments = self._parse_path(path)

        # Ignore the configured prefix if it is present in the route.
        static_segments = [
            segment
            for segment in segments
            if isinstance(segment, str) and segment != self.prefix
        ]

        parameters = [
            segment for segment in segments if isinstance(segment, PathParameter)
        ]

        resource_words = self._build_resource_words(static_segments)
        parameter_words = self._build_parameter_words(parameters)

        return "_".join(
            part
            for part in [
                action,
                *resource_words,
                self.prefix,
                *parameter_words,
            ]
            if part
        )

    def _get_method(self, methods: Iterable[str]) -> str:
        methods = sorted(methods)

        if not methods:
            raise ValueError("Route has no HTTP methods")

        return methods[0].upper()

    def _action_word(self, method: str) -> str:
        try:
            return self.action_word_map[method]
        except KeyError:
            raise ValueError(f"No action word configured for HTTP method {method!r}")

    def _parse_path(self,path: str,) -> list[str | PathParameter]:
        path = path.strip(PATH_SEPARATOR)
        if not path:
            return []

        result: list[str | PathParameter] = []

        for segment in path.split(PATH_SEPARATOR):
            match = self._PARAMETER_RE.match(segment)
            if match:
                result.append(PathParameter(name=match.group("name"),converter=match.group("converter"),))
            else:
                result.append(self._normalize_segment(segment))

        return result

    def _build_resource_words(
        self,
        segments: list[str],
    ) -> list[str]:
        if not segments:
            return []

        # Last resource comes first.
        #
        # /email/template
        # -> template
        #
        # /api/email/template
        # -> template/api
        return [
            segments[-1],
            *segments[:-1],
        ]

    def _build_parameter_words(
        self,
        parameters: list[PathParameter],
    ) -> list[str]:
        result: list[str] = []

        for index, parameter in enumerate(parameters):
            relation = self.parameter_relation_map.get(
                parameter.name,
                "with" if index == 0 else "using",
            )

            result.extend(
                [
                    relation,
                    parameter.operation_name,
                ]
            )

        return result

    def compute(self, methods, path, func_name):
        return self.generate(methods,path)

    @staticmethod
    def _normalize_segment(segment: str) -> str:
        segment = re.sub(
            r"([a-z0-9])([A-Z])",
            r"\1_\2",
            segment,
        )
        segment = re.sub(
            r"[^a-zA-Z0-9]+",
            "_",
            segment,
        )
        return segment.strip("_").lower()
