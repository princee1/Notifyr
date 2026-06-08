from app.classes.chunk import ChunkContext
from app.classes.nodes import KGraphFacts

def _esc(value: str) -> str:
        if value is None:
            return ""
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

def VECTOR_RAG_TEMPLATE(chunks:list[ChunkContext])->str:
    """
    Generate a RAG context template from vector chunks.

    Each chunk is rendered as a `<chunk>` element with a nested
    `<content>` and a `<source>` containing `<title>` and `<document>`.
    Values are XML-escaped to prevent markup injection.
    """
    contexts = []
    for chunk in chunks:
        contexts.append(
            (
                f'<chunk id="{_esc(chunk["chunk_id"]) }">'
                f'<content>{_esc(chunk["text"])}</content>'
                f'<source id="{_esc(chunk["source"]) }">'
                f'<title>{_esc(chunk["title"])}</title>'
                f'<document>{_esc(chunk["document_name"])}</document>'
                f'</source>'
                f'</chunk>'
            )
        )
    return f"<context>{'\n'.join(contexts)}</context>"

def GRAPH_RAG_TEMPLATE(facts: list[KGraphFacts]) -> str:
    """
    Generate a RAG context template from knowledge graph facts.
    
    Each fact is structured as:
    `<triplet>
        <source>...</source>
        <fact>...</fact>
        <target>...</target>
    </triplet>
    <sources>
        <source id="...">...</source>
        ...
    </sources>`
    """
    contexts = []
    for fact in facts:
        # Build sources XML elements
        sources_xml = "".join(
            f'<source id="{source.id}">'
            f'<document>{source.document_name}</document>'
            f'<title>{source.title}</title>'
            f'</source>'
            for source in fact['source']
        )
        # Build complete triplet with sources
        triplet = (
            f'<triplet>'
            f'<source>{fact["source_summary"]}</source>'
            f'<fact>{fact["fact"]}</fact>'
            f'<target>{fact["target_summary"]}</target>'
            f'</triplet>'
            f'<sources>{sources_xml}</sources>'
        )
        contexts.append(triplet)
    
    return f"<context>{''.join(contexts)}</context>"

def REST_API_TEMPLATE(content:dict|str,status_code:int,method:str):
    return f"<response method={method} status={status_code}> {content} </response>"

def ERROR_TEMPLATE(content:str|dict,retry:str|None=None,instruction:str=None)->str:
    return f"<error> <content>{content}</content> {f'<retry>{retry}</retry>' if retry else ''} {f'<instruction>{instruction}</instruction>' if instruction else ''} </error>"
