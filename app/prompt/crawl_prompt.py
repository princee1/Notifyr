"""
Crawl4AI prompt templates for information extraction and filtering.
"""
from typing import List, Optional

###################################################################################################
###########################		  Text List Extraction Prompts			     ##############################
###################################################################################################

SEMANTIC_EXTRACTION_RULES = """
# EXTRACTION RULES
1. **Subject Focus**: Ensure the chunk contains relevant information regarding the requested focus subjects.
2. **Chunk Integrity**: Do not break sentences. Start and end chunks at logical paragraph or section breaks.
3. **Titling**: The name/title must be synthesized. Do not simply use the first line of text. It should be a 5-10 word summary.
4. **Formatting**: Strictly follow the JSON schema. Ensure special characters are escaped for valid JSON.
5. **Deduplication**: If a subject is discussed across multiple non-contiguous sections, create separate items for each.
6. **Classification**: Assign relevant tags to each chunk for easy filtering.
"""

def SEMANTIC_TEXT_EXTRACTION_PROMPT_TEMPLATE(
    focus: str,
    persona: str = "Master of Semantic Synthesis",
    special_instructions: Optional[str] = None,
) -> str:
    """
    Generates a high-precision prompt for semantic text extraction.
    
    Args:
        focus: The specific topics or subjects the agent should look for.
        persona: The expert persona extracting the content (e.g., "Security Expert", "Data Analyst").
        special_instructions: Any edge-case rules or formatting tweaks.
    """
    
    prompt = f"# PERSONA\n"
    prompt += f"You are the {persona}. Your expertise lies in dissecting complex Markdown documents and identifying logical \"thematic units\" "
    prompt += f"that are relevant to {focus}. You extract information with precision while preserving the author's original intent.\n\n"
    
    prompt += f"# OBJECTIVE\n"
    prompt += f"Identify and extract distinct chunks of text based on the focus area: **{focus}**. For each chunk, generate a 'comprehensive_title' "
    prompt += f"that acts as a high-level summary of the semantic content from the perspective of a {persona.lower()}.\n\n"
    
    prompt += SEMANTIC_EXTRACTION_RULES
    prompt += f"\n## CURRENT TASK\n"
    prompt += f"As a {persona}, extract semantic chunks from the provided content focusing specifically on: **{focus}**\n"
    prompt += f"Your extraction should highlight aspects most relevant to understanding {focus}.\n\n"
    
    prompt += """## OUTPUT FORMAT
Return a JSON array of objects:
[
  {
    "id": "semantic_chunk_1",
    "title": "Synthesized Comprehensive Title",
    "keywords": ["List", "Of", "Relevant", "Keywords"],
    "section": "The section or heading this chunk belongs to",
    "content_type": "paragraph/heading/table/code",
    "topics": ["List", "Of", "Relevant", "Subheadings"],
    "text": "The extracted markdown content..."
  }
]
"""

    if special_instructions:
        prompt += f"\n## SPECIAL INSTRUCTIONS (PRIORITY)\n"
        prompt += f"> {special_instructions}\n"

    prompt += "\nBegin extraction from the provided Markdown text below:"
    
    return prompt

###################################################################################################
###########################		  Schema Extraction Prompts   ##############################
###################################################################################################

SCHEMA_EXTRACTION_LOGIC = """
# EXTRACTION PARAMETERS
1. **Definition Detection**: Focus on formal definitions (JSON Schema, SQL DDL, TypeScript Interfaces, Protobuf, etc.). 
2. **Contextual Titling**: If a schema lacks a name within the code block, derive a 'title' from the nearest preceding H1, H2, or H3 header.
3. **Unique Identification**: Assign a snake_case 'id' based on the schema's purpose.
4. **Zero-Noise Policy**: Strip away explanatory prose. Extract only the technical definition and its immediate metadata.
5. **Multi-Subject Handling**: If the Markdown contains multiple unrelated schemas, extract each as a separate object in the list.
"""


def SCHEMA_EXTRACTION_PROMPT(
    target_format: str = 'JSON',
    persona: str = "Lead Schema Architect",
    focus: Optional[str] = None,
    special_instructions: Optional[str] = None
) -> str:
    """
    Generates a prompt to extract technical schemas from Markdown.
    
    Args:
        target_format: The type of schema to look for (e.g., 'JSON Schema', 'SQL', 'TypeScript').
        persona: The expert persona extracting the schema (e.g., "Data Engineer", "API Designer").
        focus: The specific aspect or domain the schema should focus on (e.g., "user authentication", "product catalog").
        special_instructions: Custom constraints (e.g., 'Ignore deprecated schemas').
    """
    
    focus_context = f" related to {focus}" if focus else ""
    
    prompt = f"# PERSONA\n"
    prompt += f"You are the {persona}. Your specialty is identifying, validating, and extracting structural data definitions "
    prompt += f"from unstructured or semi-structured Markdown documentation{focus_context}. "
    prompt += f"You ensure that all extracted schemas are clean, well-organized, and directly relevant to the domain.\n\n"
    
    prompt += SCHEMA_EXTRACTION_LOGIC
    
    prompt += f"\n# CURRENT TASK\n"
    prompt += f"Your goal is to scan the provided Markdown and extract all **{target_format}** definitions"
    if focus:
        prompt += f" that contribute to understanding or implementing {focus}"
    prompt += ".\n\n"
    
    prompt += """# OUTPUT JSON STRUCTURE
Return a JSON array of objects. Each object must strictly follow this schema:
[
  {
    "id": "unique_schema_id",
    "title": "A descriptive, synthesized title",
    "content": "The json representation of the schema"
  }
]
"""

    if special_instructions:
        prompt += f"\n# USER-DEFINED SPECIAL INSTRUCTIONS\n> {special_instructions}\n"

    prompt += "\n--- SOURCE MARKDOWN START ---\n"
    
    return prompt

###################################################################################################
###########################		  Schema Generation Prompts		     ##############################
###################################################################################################

JSON_MAPPING_LOGIC = """
# EXTRACTION & MAPPING PARAMETERS
1. **Selector Identification**: Prioritize 'id' and 'class' names that appear stable and semantic.
2. **Contextual Extraction**: Apply domain-specific knowledge to identify the most relevant elements for the extraction task.
"""

def CRAWL4AI_GENERATION_PROMPT(
    schema: dict,
    persona: str = "Crawl4AI Mapping Specialist",
    focus: Optional[str] = None,
    special_instructions: Optional[str] = None
) -> str:
    """
    Generates a prompt to direct the mapping of web content to a Crawl4AI CSS/Regex strategy.
    
    Args:
        schema: The JSON or Pydantic-style schema you want to fill.
        persona: The expert persona performing the mapping (e.g., "Frontend Engineer", "Data Extraction Specialist").
        focus: The specific aspect or use-case focus (e.g., "e-commerce product data", "news article content").
        special_instructions: Instructions like "Look for the price in the meta tags if not in the body."
    """
    
    focus_context = f" to support {focus}" if focus else ""
    
    prompt = f"# PERSONA\n"
    prompt += f"You are the {persona}. Your expertise is in converting visual web structures into programmatic extraction schemas using CSS selectors "
    prompt += f"and regular expressions{focus_context}. You understand data relationships and know how to identify stable, semantic selectors "
    prompt += f"that work reliably across similar pages.\n\n"
    
    prompt += JSON_MAPPING_LOGIC

    prompt += f"# TARGET SCHEMA:\n\t[{{\n"
    prompt += f"    \"id\": \"unique_schema_id\",\n"
    prompt += f"    \"title\": \"A descriptive, synthesized title\",\n"
    prompt += f"    \"content\": {schema}\n"
    prompt += f"}}]\n"

    if special_instructions:
        prompt += f"\n# SPECIAL MAPPING INSTRUCTIONS (PRIORITY)\n> {special_instructions}\n"

    prompt += "\n# SOURCE CONTENT TO ANALYZE\n"
    
    return prompt