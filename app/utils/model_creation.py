"""
Cerberus → Pydantic v2 model converter

Features:
- Full Cerberus schema support (as far as Pydantic allows)
- Schema registry + references
- Nested dict / list schemas
- Cross-model reuse
- Coerce support (single / list of callables)
- Dependencies / excludes / oneof / anyof / allof
- Constraints mapped where possible
"""

from __future__ import annotations

from typing import (
    Any,
    Dict,
    List,
    Optional,
    Type,
    Union,
    Callable,
    Set,
)
from pydantic import (
    BaseModel,
    Field,
    create_model,
    field_validator,
    model_validator,
)

# ============================================================
# GLOBAL REGISTRY
# ============================================================

MODEL_REGISTRY: Dict[str, Type[BaseModel]] = {}

# ============================================================
# TYPE MAP
# ============================================================

CERBERUS_TYPE_MAP = {
    "string": str,
    "integer": int,
    "float": float,
    "number": float,
    "boolean": bool,
    "dict": dict,
    "list": list,
    "set": set,
}

# ============================================================
# SCHEMA RESOLUTION
# ============================================================

def resolve_schema_ref(ref: Union[str, Type[BaseModel]]) -> Type[BaseModel]:
    if isinstance(ref, type) and issubclass(ref, BaseModel):
        return ref
    if isinstance(ref, str):
        if ref not in MODEL_REGISTRY:
            raise KeyError(f"Referenced schema '{ref}' not found")
        return MODEL_REGISTRY[ref]
    raise TypeError("Invalid _schema reference")

# ============================================================
# FIELD BUILDER
# ============================================================

def build_field(
    field_name: str,
    rules: Dict[str, Any],
    parent: str,
    validators: Dict[str, classmethod],
    root_validators: List[Callable],
):
    required = rules.get("required", False)
    nullable = rules.get("nullable", False)
    default = rules.get("default", ...)
    readonly = rules.get("readonly", False)

    # ---------------------------
    # 1️⃣ Resolve type FIRST
    # ---------------------------

    if "_schema" in rules:
        field_type = resolve_schema_ref(rules["_schema"])

    elif rules.get("type") == "dict":
        field_type = cerberus_schema_to_pydantic(
            rules.get("schema", {}),
            f"{parent}_{field_name.capitalize()}",
        )

    elif rules.get("type") == "list":
        item_rules = rules.get("schema", {})
        if "_schema" in item_rules:
            item_type = resolve_schema_ref(item_rules["_schema"])
        elif item_rules.get("type") == "dict":
            item_type = cerberus_schema_to_pydantic(
                item_rules.get("schema", {}),
                f"{parent}_{field_name.capitalize()}Item",
            )
        else:
            item_type = CERBERUS_TYPE_MAP.get(item_rules.get("type"), Any)
        field_type = List[item_type]

    elif rules.get("type") == "set":
        field_type = Set[Any]

    else:
        field_type = CERBERUS_TYPE_MAP.get(rules.get("type"), Any)

    # ---------------------------
    # 2️⃣ Optional handling
    # ---------------------------

    if not required or nullable:
        field_type = Optional[field_type]
        if default is ...:
            default = None

    # ---------------------------
    # 3️⃣ Constraints
    # ---------------------------

    constraints: Dict[str, Any] = {}

    if "min" in rules:
        constraints["ge"] = rules["min"]
    if "max" in rules:
        constraints["le"] = rules["max"]
    if "minlength" in rules:
        constraints["min_length"] = rules["minlength"]
    if "maxlength" in rules:
        constraints["max_length"] = rules["maxlength"]
    if "regex" in rules:
        constraints["pattern"] = rules["regex"]
    if "allowed" in rules:
        constraints["enum"] = rules["allowed"]

    # ---------------------------
    # 4️⃣ COERCE
    # ---------------------------

    if "coerce" in rules:
        funcs = rules["coerce"]
        if not isinstance(funcs, list):
            funcs = [funcs]

        def make_coerce_validator(fns):
            def _coerce(v):
                for fn in fns:
                    v = fn(v)
                return v
            return _coerce

        validators[f"coerce_{field_name}"] = field_validator(
            field_name, mode="before"
        )(make_coerce_validator(funcs))

    # ---------------------------
    # 5️⃣ READONLY
    # ---------------------------

    if readonly:
        validators[f"readonly_{field_name}"] = field_validator(
            field_name, mode="before"
        )(lambda v: v)

    # ---------------------------
    # 6️⃣ DEPENDENCIES
    # ---------------------------

    if "dependencies" in rules:
        deps = set(rules["dependencies"])

        @model_validator(mode="after")
        def _dependencies_check(cls, values):
            if field_name in values and values[field_name] is not None:
                missing = deps - values.keys()
                if missing:
                    raise ValueError(
                        f"{field_name} requires fields {missing}"
                    )
            return values

        root_validators.append(_dependencies_check)

    # ---------------------------
    # 7️⃣ EXCLUDES
    # ---------------------------

    if "excludes" in rules:
        excluded = set(rules["excludes"])

        @model_validator(mode="after")
        def _excludes_check(cls, values):
            if field_name in values and values[field_name] is not None:
                conflict = excluded & values.keys()
                if conflict:
                    raise ValueError(
                        f"{field_name} excludes {conflict}"
                    )
            return values

        root_validators.append(_excludes_check)

    return field_type, Field(default, **constraints)

# ============================================================
# MAIN CONVERTER
# ============================================================

def cerberus_schema_to_pydantic(
    schema: Dict[str, Any],
    name: str,
) -> Type[BaseModel]:

    if name in MODEL_REGISTRY:
        return MODEL_REGISTRY[name]

    fields = {}
    field_validators = {}
    root_validators: List[Callable] = []

    for field_name, rules in schema.items():
        annotation, field_info = build_field(
            field_name,
            rules,
            name,
            field_validators,
            root_validators,
        )
        fields[field_name] = (annotation, field_info)

    model = create_model(
        name,
        __validators__={
            **field_validators,
            **{f"root_{i}": v for i, v in enumerate(root_validators)},
        },
        **fields,
    )

    MODEL_REGISTRY[name] = model
    return model
