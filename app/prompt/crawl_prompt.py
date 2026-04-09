"""
Crawl4AI prompt templates for information extraction and filtering.
"""
from typing import List, Optional

###################################################################################################
###########################		  Text List Extraction Prompts			     ##############################
###################################################################################################

SEMANTIC_EXTRACTION_RULES = """
# PERSONA
You are the Master of Semantic Synthesis. Your expertise lies in dissecting complex Markdown documents and identifying logical "thematic units" without losing the author's original intent.

# OBJECTIVE
Identify and extract distinct chunks of text based on the focus subjects provided. For each chunk, generate a 'comprehensive_title' that acts as a high-level summary of the semantic content.

# EXTRACTION RULES
1. **Subject Focus**: Ensure the chunk contains relevant information regarding the requested focus subjects.
2. **Chunk Integrity**: Do not break sentences. Start and end chunks at logical paragraph or section breaks.
3. **Titling**: The name/title must be synthesized. Do not simply use the first line of text. It should be a 5-10 word summary.
4. **Formatting**: Strictly follow the JSON schema. Ensure special characters are escaped for valid JSON.
5. **Deduplication**: If a subject is discussed across multiple non-contiguous sections, create separate items for each.
6. **Classification**: Assign relevant tags to each chunk for easy filtering.
"""

def SEMANTIC_TEXT_EXTRACTION_PROMPT_TEMPLATE(focus: str, special_instructions: Optional[str] = None,) -> str:
    """
    Generates a high-precision prompt for semantic text extraction.
    
    Args:
        focus_subjects: The specific topics or subjects the agent should look for.
        special_instructions: Any edge-case rules or formatting tweaks.
    """
    
    prompt = SEMANTIC_EXTRACTION_RULES
    prompt += f"## CURRENT TASK\n"
    prompt += f"Extract semantic chunks focusing on: **{focus}**\n\n"
    
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

# PERSONA
You are the **Lead Schema Architect**. Your specialty is identifying, validating, and extracting structural data definitions from unstructured or semi-structured Markdown documentation.

# EXTRACTION PARAMETERS
1. **Definition Detection**: Focus on formal definitions (JSON Schema, SQL DDL, TypeScript Interfaces, Protobuf, etc.). 
2. **Contextual Titling**: If a schema lacks a name within the code block, derive a 'title' from the nearest preceding H1, H2, or H3 header.
3. **Unique Identification**: Assign a snake_case 'id' based on the schema's purpose.
4. **Zero-Noise Policy**: Strip away explanatory prose. Extract only the technical definition and its immediate metadata.
5. **Multi-Subject Handling**: If the Markdown contains multiple unrelated schemas, extract each as a separate object in the list.
"""


def SCHEMA_EXTRACTION_PROMPT(target_format: str='JSON', special_instructions: Optional[str] = None) -> str:
    """
    Generates a prompt to extract technical schemas from Markdown.
    
    Args:
        target_format: The type of schema to look for (e.g., 'JSON Schema', 'SQL', 'TypeScript').
        special_instructions: Custom constraints (e.g., 'Ignore deprecated schemas').
    """
    
    prompt = f"""{SCHEMA_EXTRACTION_LOGIC}

# CURRENT TASK
Your goal is to scan the provided Markdown and extract all **{target_format}** definitions.

# OUTPUT JSON STRUCTURE
Return a JSON array of objects. Each object must strictly follow this schema:
[
  {{
    "id": "unique_schema_id",
    "title": "A descriptive, synthesized title",
    "content": "The json representation of the schema"
  }},
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
# PERSONA
You are the **Crawl4AI Mapping Specialist**. Your expertise is in converting visual web structures into programmatic extraction schemas using CSS selectors.

# EXTRACTION & MAPPING PARAMETERS
1. **Schema Alignment**: Map every property in the provided [TARGET_SCHEMA] to a specific CSS selector found in the source.
2. **Selector Identification**: Prioritize 'id' and 'class' names that appear stable and semantic.
3. **Data Type Casting**: Identify if the result should be a string, integer, or a nested object.
5. **Collection Logic**: For repeating items (like product cards), identify the 'base_selector' that encompasses the entire repeating unit.
"""

def CRAWL4AI_GENERATION_PROMPT(schema: dict, special_instructions: str = None) -> str:
    """
    Generates a prompt to direct the mapping of web content to a Crawl4AI CSS/Regex strategy.
    Args:
        schema_string: The JSON or Pydantic-style schema you want to fill.
        special_instructions: Instructions like "Look for the price in the meta tags if not in the body."
    """
    
    prompt = f"""{JSON_MAPPING_LOGIC}w
      # TASK
      Analyze the provided Markdown/HTML. For every field in the TARGET SCHEMA, identify:
      1. The most precise **CSS Selector**.
      2. The **Attribute** to extract (default is 'text').
      3. A **Regex** pattern only if the data is nested within a messy string.
      """

    prompt+=f"""\n# TARGET SCHEMA:\n\t[{{
        "id": "unique_schema_id",
        "title": "A descriptive, synthesized title",
        "content": {schema}
    }}]"""

    if special_instructions:
        prompt += f"\n# SPECIAL MAPPING INSTRUCTIONS\n> {special_instructions}\n"

    prompt += "\n--- SOURCE CONTENT TO ANALYZE ---\n"
  
    return prompt