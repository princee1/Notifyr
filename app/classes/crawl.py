from dataclasses import dataclass, field
import json
import re
from typing import List, Optional, Tuple, TypedDict, Union, Self,Iterator,Dict,Any
import aiohttp
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, get_args
from itertools import product

from app.classes.chunk import Chunk, ChunkPayload
from app.definition._error import BaseError

JSONLD_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE
)

ValueType = Literal["string", "number", "boolean"]

StringMode = Literal["equals","contains","regex","exists","in_list"]
NumberMode = Literal["gt","gte","lt","lte","eq","bt"]
BoolMode = Literal["equals","exists"]

LogicOperator = Literal["AND","OR"]

MODE:dict[ValueType,list[str]] = {
    'string':get_args(StringMode),
    'boolean':get_args(BoolMode),
    'number':get_args(NumberMode)    
}

class JSONLDFilterRule(BaseModel):

    field: str
    type: ValueType
    compare_mode: Union[NumberMode,BoolMode,StringMode]
    value: Union[str,float,bool,List[str],Tuple[float,float]] | None

    # ---------------------
    # VALIDATE MODE
    # ---------------------
    @field_validator("compare_mode")
    def validate_mode(cls, v, info):

        t = info.data.get("type")

        if t not in MODE:
            raise ValueError("Invalid type")
        
        allowed = MODE[t]

        if v not in allowed:
            raise ValueError(f"{v} not allowed for {t}")

        return v

    # ---------------------
    # NORMALIZATION
    # ---------------------
    @field_validator("value")
    def normalize_value(cls, v):

        if isinstance(v, str):
            return v.lower()
        
        if isinstance(v,List[str]):
            return [x.lower() for x in v]

        return v
    
    @model_validator(mode='after')
    def coerce_value(self:Self)->Self:

        if self.compare_mode == 'equals' and self.type == 'string' and isinstance(self.value,str):
            self.value = [self.value]
        
        return self

    @model_validator(mode='after')
    def validate_value(self: Self) -> Self:
        match self.compare_mode:
            case 'eq' | 'gt' | 'gte' | 'lt' | 'lte':
                if not isinstance(self.value, float):
                    raise ValueError(f"Value for '{self.compare_mode}' must be a float (number), got {type(self.value).__name__}")
            case 'bt':
                if not isinstance(self.value, tuple) or len(self.value) != 2:
                    raise ValueError("Value for 'bt' must be a tuple of two floats (min, max)")
                if not all(isinstance(x, float) for x in self.value):
                    raise ValueError("Both elements in 'bt' tuple must be floats")
            case 'exists':
                self.value = None
            case 'equals' | 'in_list':
                if self.type == 'string':
                    if not isinstance(self.value, list):
                        raise ValueError(f"Value for '{self.compare_mode}' with type 'string' must be a list of strings")
                elif self.type == 'boolean':
                    if not isinstance(self.value, bool):
                        raise ValueError(f"Value for '{self.compare_mode}' with type 'boolean' must be a boolean")
            case 'contains' | 'regex':
                if not isinstance(self.value, str):
                    raise ValueError(f"Value for '{self.compare_mode}' must be a string")
        return self
 
class JSONLDFilterGroup(BaseModel):

    operator: LogicOperator
    rules: List[Union[JSONLDFilterRule, "JSONLDFilterGroup"]]

    @staticmethod
    def get_nested(data: dict, path: str):

        value = data

        for k in path.split("."):
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None

        return value

    def evaluate_rule(self, rule: JSONLDFilterRule, data: dict):

        value = self.get_nested(data, rule.field)

        # -----------------
        # STRING
        # -----------------

        if rule.type == "string":

            if value is None:
                return False

            value = str(value).lower()

            if rule.compare_mode == "exists":
                return value is not None

            if rule.compare_mode == "equals":
                return value in self.value

            if rule.compare_mode == "contains":
                return rule.value in value

            if rule.compare_mode == "regex":
                return bool(re.search(rule.value, value))

            if rule.compare_mode == "in_list":
                return value in rule.value

        # -----------------
        # NUMBER
        # -----------------

        if rule.type == "number":

            try:
                num = float(value)
            except:
                return False

            if rule.compare_mode == "gt":
                return num > rule.value

            if rule.compare_mode == "gte":
                return num >= rule.value

            if rule.compare_mode == "lt":
                return num < rule.value

            if rule.compare_mode == "lte":
                return num <= rule.value

            if rule.compare_mode == "eq":
                return num == rule.value

            if rule.compare_mode == "bt":
                return rule.value[0] <= num <= rule.value[1]

        # -----------------
        # BOOLEAN
        # -----------------

        if rule.type == "boolean":

            if rule.compare_mode == "exists":
                return value is not None

            if rule.compare_mode == "equals":
                return bool(value) == rule.value

        return False

    def _match(self, data: dict):
        try:
            results = []
            for rule in self.rules:

                if isinstance(rule, JSONLDFilterRule):
                    results.append(self.evaluate_rule(rule, data))
                else:
                    results.append(rule.match(data))

            if self.operator == "AND":
                return all(results)

            if self.operator == "OR":
                return any(results)

            return False
        except:
            return False


    def match(self,jsonld:list[dict]):
        matches = []
        for jsld in jsonld[:5]:
            m = self._match(jsld)
            matches.append(m)
        
        return any(matches)
    

# ---------------------------
# URL generator
# ---------------------------

class URLParam(BaseModel):
    values: Union[List[str|int|bool], Tuple[int, int, int]]  # List or range tuple (start, step, end)

    @field_validator('values',mode='after')
    def validate_range_or_list(cls, v):
        if isinstance(v, tuple):
            if len(v) != 3:
                raise ValueError("Range tuple must be (start, step, end)")
            if v[1] == 0:
                raise ValueError("Step cannot be 0")
        elif not isinstance(v, list):
            raise ValueError("Must be a list or a range tuple")
        return v

class URLConfigModel(BaseModel):
    base_url: str
    path_params: Dict[str, URLParam] = {}
    query_params: Dict[str, URLParam] = {}

    @field_validator('path_params', mode='after')
    def filter_invalid_path_params(cls, v, values):
        """
        Remove path params that are not in the base URL placeholders.
        """
        base_url = values.get('base_url', '')
        valid_keys = re.findall(r"\{\{(.*?)\}\}", base_url)
        return {k: val for k, val in v.items() if k in valid_keys}

def extract_jsonld(html: str):
    """Extract and flatten JSON-LD objects from HTML."""

    results = []
    matches = JSONLD_PATTERN.findall(html)

    for match in matches:
        try:
            data = json.loads(match.strip())
        except:
            continue

        # Expand @graph
        if isinstance(data, dict) and "@graph" in data:
            results.extend(data["@graph"])
        elif isinstance(data, list):
            results.extend(data)
        else:
            results.append(data)

    return results

async def fetch_jsonld(session: aiohttp.ClientSession, url: str):
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
        html = await resp.text()

    jsonld = extract_jsonld(html)
    return jsonld
    
def generate_urls(config: URLConfigModel) -> Iterator[str]:
    def process_values(val):
        if isinstance(val, tuple):
            start, step, end = val
            return list(range(start, end + 1, step))
        elif isinstance(val, list):
            return val
        else:
            return [val]

    # Process path and query parameters
    path_values = {k: process_values(v.values) for k, v in config.path_params.items()}
    query_values = {k: process_values(v.values) for k, v in config.query_params.items() if v.values}

    path_keys = list(path_values.keys())
    query_keys = list(query_values.keys())

    path_combinations = product(*path_values.values()) if path_values else [()]
    query_combinations = product(*query_values.values()) if query_values else [()]

    for p_combo in path_combinations:
        url = config.base_url
        # Fill path parameters
        for key, val in zip(path_keys, p_combo):
            url = url.replace(f"{{{{{key}}}}}", str(val))

        # Fill query parameters
        for q_combo in query_combinations:
            if query_keys:
                query_string = "&".join(f"{k}={v}" for k, v in zip(query_keys, q_combo))
                full_url = f"{url}?{query_string}"
            else:
                full_url = url
            yield full_url

# ---------------------------
# Example usage
# ---------------------------
# config = URLConfig(
#     base_url="https://example.com/{{t}}/{{category}}/{{sub}}",
#     path_params={
#         "t": URLParam(values=["v", "d"]),
#         "category": URLParam(values=["shoes", "shirts"]),
#         "sub": URLParam(values=["summer", "winter"]),
#         "invalid": URLParam(values=[1, 2])  # filtered out automatically
#     },
#     query_params={
#         "page": URLParam(values=(1, 1, 2)),
#         "size": URLParam(values=[10, 20]),
#         "optional": URLParam(values=[])  # won't appear in URL
#     }
# )

# # Lazy iteration
# for url in generate_urls(config):
#     print(url)


###################################################################################################
###########################		  URL with Description Model			     ##############################
###################################################################################################
@dataclass
class URLDescription:
	"""URL with associated metadata from jsonld or html head."""
	url: str
	title: Optional[str] = None
	description: Optional[str] = None
	image: Optional[str] = None

###################################################################################################
###########################		  Token Usage Tracking Model		     ##############################
###################################################################################################


class CrawlTokenUsage(TypedDict):
    """Token usage report for cost tracking."""
    input_tokens: int
    output_tokens: int
    step: Optional[str] = None

class CrawlTokenUsageReport(TypedDict):
    model:str
    provider:str
    provider_id:str
    tokens:List[CrawlTokenUsage]

###################################################################################################
###########################		  Error Definitions					     ##############################
###################################################################################################

class CrawlNotSucceededError(BaseError):
	def __init__(self, url: str):
		super().__init__(url)
		self.url = url

class Crawl4AIModeConfigMissingError(BaseError):
	def __init__(self, config: str):
		super().__init__(config)
		self.config = config

class SchemaGenerationError(BaseError):
	def __init__(self, schema_name: str, reason: str):
		super().__init__(f"Schema '{schema_name}': {reason}")
		self.schema_name = schema_name

class UrlDescriptionNotFoundError(BaseError):
    def __init__(self, url:str,reason):
        super().__init__()
        self.url = url
        self.reason = reason

class NoURLToCrawlError(BaseError):
    ...

class SchemaHTMLExampleNotFoundError(BaseError):
    def __init__(self,schema_name,schema_url,reason):
        super().__init__()
        self.schema_name =schema_name
        self.schema_url = schema_url
        self.reason = reason
class SchemaHasNoContentError(BaseError):
    def __init__(self,schema_name,schema_url,reason):
        super().__init__()
        self.schema_name =schema_name
        self.schema_url = schema_url
        self.reason = reason

class SchemaFetchError(BaseError):
    def __init__(self,schema_name,schema_url,reason):
        super().__init__()
        self.schema_name =schema_name
        self.schema_url = schema_url
        self.reason = reason

class NoInputHtmlSchemaError(BaseError):
    def __init__(self, schema_name,schema_urls):
        super().__init__()
        self.schema_name = schema_name
        self.schema_urls = schema_urls

class SchemaCouldNotBeGeneratedError(BaseError):
    def __init__(self, schema_name,schema_url,strategy):
        super().__init__()
        self.schema_name = schema_name
        self.schema_url = schema_url
        self.strategy = strategy

class BadSchemaGenerationStrategyError(BaseError):
    def __init__(self, strategy):
        super().__init__()
        self.strategy = strategy

class CrawlError(TypedDict):
    name:str
    url: str
    message: str
	
###################################################################################################
###########################		  Type Definitions					     ##############################
###################################################################################################

class CrawlText(BaseModel):
    text:str
    title:str
    id:str
    topics:List[str]
    keywords:List[str]
    section: str
    content_type: str

class CrawlTextModel(BaseModel):
	texts:List[CrawlText]


@dataclass
class CrawlResultMetadata:
    url: str
    title: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None
    success: bool = False
    result: Optional[dict] = None
    error: Optional[str] = None
    extracted_content: list[Any] = None
    markdown_content: Optional[str] = None
    chunks: List[Chunk] = field(default_factory=list)

class CrawlDocumentSize(TypedDict):
    size:int
    url:str
    description:str

class CrawlState(TypedDict):
    deep_crawl:Dict
    cancelled:bool



class DigestURLState(TypedDict):
    ...

DigestState  = Dict[str, DigestURLState]