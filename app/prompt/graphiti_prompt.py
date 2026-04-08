"""
graphiti_prompts.py

Prompt templates for Graphiti-oriented knowledge graph ingestion.
These prompts are descriptive framing prompts (not task instructions)
designed to improve entity extraction, relationship quality, and
personalized memory for conversation- and document-based RAG.
"""

# ============================================================
# Conversation-level prompts
# ============================================================

CONVERSATION_DESCRIPTION_PROMPT = lambda reason, contact_id, title: f"""
This episode represents a conversational interaction between a customer and an automated assistant.

Conversation title: {title}
Customer identifier: {contact_id}

The primary reason for this conversation is:
{reason}

The content may include multiple conversational turns, clarifications,
follow-up questions, and responses over the course of a single session.
Focus on information that reflects the customer's intent, stated needs,
preferences, issues, constraints, decisions, and outcomes.

The automated assistant is a system participant and should not be modeled
as a person or customer entity. Prioritize information attributable to
the customer or to factual events, actions, or resolutions discussed.
"""


CONVERSATION_EXTRACTION_PROMPT = lambda subject: f"""
The following content concerns the subject: {subject}.

When interpreting this conversation, prioritize extraction of:
- Entities representing customers, organizations, products, services,
  documents, accounts, orders, or issues
- Relationships indicating actions taken, requests made, problems
  encountered, escalations, or resolutions
- Temporal or causal connections (what led to what, what changed, and
  what remains unresolved)
- Explicit preferences, constraints, commitments, or stated goals
  expressed by the customer

Avoid extracting procedural assistant instructions, generic greetings,
or conversational filler. Focus on durable knowledge that would be useful
for future personalization, reasoning, or question answering.
"""


# ============================================================
# Document chunk prompts
# ============================================================

CHUNK_DESCRIPTION_PROMPT = lambda document_name, subject, title, topics, keywords, most_commons, lang: f"""
This episode represents a chunk of text extracted from a document source.

Document name: {document_name}
Document title or heading: {title}
Primary subject: {subject}
Language: {lang}

Associated topics:
{", ".join(topics)}

Relevant keywords:
{", ".join(keywords)}

Frequently occurring terms or phrases:
{", ".join(most_commons)}

The content should be interpreted as informational or descriptive text
originating from a static document. Focus on extracting factual concepts,
definitions, rules, policies, structured knowledge, and relationships
between entities or sections.

Do not infer conversational intent, personal opinions, or user-specific
context unless explicitly stated within the document text itself.
"""


###################################################################################################
###########################		  Knowledge Graph Extraction Prompts		     ##############################
###################################################################################################
KG_EXTRACTION_RULES = """
# PERSONA
You are the **Knowledge Graph Architect**. You specialize in ontologies and relationship mapping, transforming prose into rigid, interconnected structures.

# EXTRACTION PARAMETERS
1. **Entity Identification**: Identify all entities belonging to the provided [ENTITY_TYPES].
2. **Relationship Mapping**: Connect entities using only the [RELATIONSHIP_TYPES] provided. Every relationship must have a source, a target, and a type.
3. **Canonical ID Generation**: Create unique, slug-style IDs (e.g., 'machine-learning-model') based on the entity's core meaning to ensure cross-document consistency.
4. **Relationship Attributes**: If the text describes *how* or *why* a relationship exists, include it in a 'description' field for that edge.
5. **Title Synthesis**: For every cluster of related entities, provide a 'graph_segment_title' that describes the thematic link.
"""

from typing import List, Optional

def KG_EXTRACTION_PROMPT(
    entities: List[str], 
    relationships: List[str], 
    special_instructions: Optional[str] = None
) -> str:
    """
    Generates a prompt to transform Markdown into a structured Knowledge Graph.
    
    Args:
        entities: List of allowed entity names (e.g., ['Project', 'Stakeholder']).
        relationships: List of allowed relationship types (e.g., ['MANAGES', 'PART_OF']).
        special_instructions: Specific logic for edge cases or metadata.
    """
    
    entity_list = ", ".join(entities)
    rel_list = ", ".join(relationships)
    
    prompt = f"""{KG_EXTRACTION_RULES}

# SCHEMA CONFIGURATION
- **ALLOWED ENTITY TYPES**: [{entity_list}]
- **ALLOWED RELATIONSHIP TYPES**: [{rel_list}]

# OUTPUT JSON FORMAT
Return a JSON object representing the graph segment:
{{
  "graph_id": "unique_segment_id",
  "title": "Comprehensive Title of this Knowledge Cluster",
  "nodes": [
    {{ "id": "entity_id", "label": "Entity Name", "type": "ENTITY_TYPE" }}
  ],
  "edges": [
    {{ "source": "entity_id_1", "target": "entity_id_2", "type": "RELATIONSHIP_TYPE", "description": "context" }}
  ]
}}
"""

    if special_instructions:
        prompt += f"\n# SPECIAL EXTRACTION INSTRUCTIONS\n> {special_instructions}\n"

    prompt += "\n--- BEGIN MARKDOWN SOURCE ---\n"
    
    return prompt