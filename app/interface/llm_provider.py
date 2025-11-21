from app.definition._interface import Interface
from typing import Any, Dict, List
from pyparsing import Optional
from app.definition._interface import Interface


class LLMProvider(Interface):
    """
    Minimal unified interface for LLM provider metadata & key verification.
    Concrete providers must try to implement each method, but may return None
    for unavailable fields.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    def verify_api_key(self) -> bool:
        """Return True if api key is valid (by calling a safe endpoint)."""
        raise NotImplementedError

    def list_models(self) -> List[Dict[str, Any]]:
        """Return a list of models (each a small dict with id & metadata)."""
        raise NotImplementedError

    def get_model_metadata(self, model_id: str) -> Dict[str, Any]:
        """Return metadata for the model (as returned by provider)."""
        raise NotImplementedError

    def get_embedding_dimension(self, model_id: str) -> Optional[int]:
        """Return embedding vector dimension if available, else None."""
        raise NotImplementedError

    def get_token_limits(self, model_id: str) -> Dict[str, Optional[int]]:
        """
        Return token limits, e.g. {
            "context_length": int or None,
            "input_limit": int or None,
            "output_limit": int or None
        }
        """
        raise NotImplementedError

    def supports_finetuning(self, model_id: str) -> Optional[bool]:
        """Return True/False/None if unknown."""
        raise NotImplementedError
