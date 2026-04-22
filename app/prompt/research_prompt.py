from typing import List, Literal

QUERY_EXPANSION_SYSTEM_MESSAGE = "You are a semantic search query expansion specialist. Return responses as valid JSON only, without any markdown formatting, explanations, or text outside the JSON structure. Be precise and concise."

def QUERY_EXPANSION_PROMPT(query:str, num_concepts=6)->str:
    """
    Generates a structured prompt for an LLM to expand a search query 
    into broader or related conceptual categories.
    
    Args:
        query (str): The search term or subject to expand.
        num_concepts (int): How many relative concepts to generate.
        
    Returns:
        str: A formatted prompt ready for an LLM.
    """
    
    prompt_template = f"""
### Role
You are an expert Semantic Search Engineer. Your task is to perform a multi-dimensional query expansion.

### Task
Analyze the following Seed Query and expand it into exactly {num_concepts} distinct concepts. 
These should range from broad "parent" topics to specific "child" niches and lateral "parallel" ideas.

**Seed Query:** "{query}"

### Query Formulation
Use specific, descriptive queries
Include key terms you expect to find
Avoid overly broad queries

### Expansion Constraints:
1. **Quantity:** Provide exactly {num_concepts} unique entries.
2. **Diversity:** Ensure at least one concept is "Broad" (macro-level), one is "Specific" (micro-level), and one is "Relative" (contextually linked).
3. **Logic:** Each expansion must include a brief justification for its relevance.

### Instructions:
- Provide ONLY the JSON array. 
- Do not include any introductory text, explanations, or markdown formatting outside the array.
- Each string should be a concise concept (1-6 words).

### Example Output Format:
["Concept 1", "Concept 2", "Concept 3"]
""".strip()

    return prompt_template


SEARCH_RESULT_SCHEMA_PROMPT:dict[Literal['persona','focus','instruction'],str] ={

    'persona':"You are a search engine result expert",
    'focus':" on finding out how to extract search result of a certain html given, not ads, not recommended just pure search results",
    'instruction':None,
}