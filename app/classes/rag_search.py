from enum import Enum

class GraphitiSearchConfig(str, Enum):
    PERSONALIZED_MEMORY = "personalized_memory"
    PRECISE_QA = "precise_qa"
    CONVERSATION_REASONING = "conversation_reasoning"
    DEFAULT_SEARCH = "default_search"
    RAG_COVERAGE = "rag_coverage"