from typing import List, Literal, overload
import math
from aiohttp_retry import dataclass
from pydantic import BaseModel


# Custom Exceptions
class EmbeddingException(Exception):
    """Base exception for embedding operations"""
    pass


class EmptyVectorError(EmbeddingException):
    """Raised when attempting to operate on an empty vector"""
    def __init__(self, context: str = "vector"):
        self.context = context
        super().__init__(f"Cannot perform operation on empty {context}")


class VectorDimensionMismatchError(EmbeddingException):
    """Raised when vectors have mismatched dimensions"""
    def __init__(self, dim1: int, dim2: int):
        self.dim1 = dim1
        self.dim2 = dim2
        super().__init__(
            f"Vector dimension mismatch: vector1 has {dim1} dimensions, "
            f"vector2 has {dim2} dimensions"
        )


class ZeroMagnitudeError(EmbeddingException):
    """Raised when a vector has zero magnitude"""
    def __init__(self, which: str = "one or both vectors"):
        self.which = which
        super().__init__(
            f"Cannot calculate cosine similarity: {which} have zero magnitude"
        )


class InvalidExportModeError(EmbeddingException):
    """Raised when an invalid export mode is specified"""
    def __init__(self, mode: str):
        self.mode = mode
        super().__init__(
            f"Invalid export mode '{mode}'. Must be 'json' or 'model'"
        )


class EmbeddingModel(BaseModel):
    vector_id:str
    vector:List[float]
    norm:float

@dataclass
class EmbeddingUsage:
    prompt_tokens:int
    total_tokens: int
    model:str
    provider:str

    @property
    def embed_tokens(self) -> int:
        return self.total_tokens - self.prompt_tokens

class EmbeddingWrapper:

    @overload
    def __init__(self,vector_id:str,vector:List[float],norm:float=None,threshold:float=0.7):
        ...
    
    @overload
    def __init__(self,embedding_model:dict|EmbeddingModel,threshold:float=0.7 ):
        ...

    def __init__(self,*args,threshold:float=0.7):
        self.threshold = threshold
        if len(args) == 1:
            e:dict|EmbeddingModel = args[0]
            if isinstance(e,dict):
                self.vector = e['vector']
                self._norm = e.get('norm',None)
                self.vector_id = e['vector_id']
            else:
                self.vector_id = e.vector_id
                self.vector = e.vector
                self._norm = e.norm
        else:            
            self.vector_id = args[0]
            self.vector = args[1]
            self._norm = args[2]
        
        if self._norm is None:
            self._norm = EmbeddingWrapper.norm(self)
        
    @staticmethod
    def cosine(e1:'EmbeddingWrapper',e2:'EmbeddingWrapper') -> float:
        """Calculate cosine similarity between two embeddings.
        
        Returns:
            float: Cosine similarity value between -1 and 1.
            
        Raises:
            EmptyVectorError: If either vector is empty.
            VectorDimensionMismatchError: If vectors have different dimensions.
            ZeroMagnitudeError: If one or both vectors have zero magnitude.
        """
        if not e1.vector or not e2.vector:
            raise EmptyVectorError("similarity input")
        
        if len(e1.vector) != len(e2.vector):
            raise VectorDimensionMismatchError(len(e1.vector), len(e2.vector))
        
        # Calculate dot product: sum(a_i * b_i)
        dot_product = sum(a * b for a, b in zip(e1.vector, e2.vector))
        
        # Check for zero norms
        if e1._norm == 0 or e2._norm == 0:
            raise ZeroMagnitudeError()
        
        return dot_product / (e1._norm * e2._norm)
    
    @staticmethod
    def norm(e:'EmbeddingWrapper') -> float:
        """Calculate L2 norm (Euclidean norm) of a vector.
        
        Returns:
            float: The L2 norm (magnitude) of the vector.
            
        Raises:
            EmptyVectorError: If vector is empty.
        """
        if not e.vector:
            raise EmptyVectorError("norm input")
        
        # ||v|| = sqrt(sum(v_i^2))
        sum_of_squares = sum(x ** 2 for x in e.vector)
        result = math.sqrt(sum_of_squares)
        e._norm = result
        return result

    def __eq__(self, other):
        return EmbeddingWrapper.cosine(self,other) >= self.threshold
    
    def export(self,mode:Literal['json','model']):
        e = EmbeddingModel(norm=self._norm,vector=self.vector,vector_id=self.vector_id)
        match mode:
            case 'json':
                return e.model_dump()
            case 'model':
                return e
            case _:
                raise InvalidExportModeError(mode)