from random import randint
import re
from typing import Any, List, Generator
from enum import Enum

from llama_index.core.node_parser import SentenceSplitter, SemanticSplitterNodeParser
from llama_index.core.schema import TextNode
from llama_index.core.readers.base import BaseReader
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.readers.file import (
    PDFReader, DocxReader, MarkdownReader, 
    HTMLTagReader, PptxReader,XMLReader
)

from app.classes.text_detector import TextDetector

DOCLING_INSTALLED = True
# Docling Integration
try:
    from llama_index.readers.docling import DoclingReader
    from llama_index.node_parser.docling import DoclingNodeParser
except ImportError as e:
    DOCLING_INSTALLED = False

from app.classes.chunk import ChunkWrapper, ChunkPayload
from app.utils.constant import ParseStrategy
from app.utils.tools import Mock, RunAsync

TEXT_READERS: dict[str, type[BaseReader]] = {
    "pdf": PDFReader,
    "docx": DocxReader,
    "md": MarkdownReader,
    "html": HTMLTagReader,
    "pptx": PptxReader,
    "xml":XMLReader,
    "txt":...,
}

MEDIA_READERS :dict[str,type[BaseReader]] = {

}

TABULAR_READERS :dict[str,type[BaseReader]] = {

}

class FileIngestionStepIndex(int, Enum):
    PROCESS = 1
    TOKEN_COST = 2
    CLEANUP = 3

class BaseDataLoader:
    def __init__(self,embedding_model:BaseEmbedding ,file_path: str, lang: str, extension: str,category:str):
        self.file_path = file_path
        self.lang = lang
        self.extension = extension
        self.category = category
        self.embedding_model = embedding_model

    async def process(self):
        raise NotImplementedError

    @staticmethod
    def Factory(ext: str) -> type['BaseDataLoader']:
        # Docling handles PDF, DOCX, PPTX, HTML, MD, etc.
        ext = ext.lower()
        if ext in TEXT_READERS:
            return TextDataLoader

        if ext in TABULAR_READERS:
            ...
        
        if ext in MEDIA_READERS:
            match ext:
                case '':
                    ...
                case _:
                    raise TypeError('Media Extension not supported')
        
        raise TypeError('File not supported')

class TextDataLoader(BaseDataLoader):
    
    def __init__(self,embedding_model:BaseEmbedding , file_path: str, lang: str, extension: str,category:str,
                 strategy: ParseStrategy = ParseStrategy.SEMANTIC, use_docling: bool = False):
        super().__init__(embedding_model, file_path, lang, extension,category)
        self.chunks = []
        self.tokens = []
        if use_docling and not DOCLING_INSTALLED:
            raise TypeError('Docling must be installed to use it')

        self.strategy = strategy
        self.use_docling = use_docling
        # Parsers
        self.splitter = SentenceSplitter(chunk_size=1000, chunk_overlap=200)
        self.semantic_parser = SemanticSplitterNodeParser(
            buffer_size=3,
            breakpoint_percentile_threshold=95,
            sentence_splitter=self.splitter.split_text,
            embed_model=self.embedding_model,
        )
        self.structured_parser = DoclingNodeParser() if use_docling else None
        
    @Mock()
    async def process(self):
        if self.use_docling:
            export_type = "markdown" if self.strategy == ParseStrategy.SEMANTIC else "json"
            reader = DoclingReader(export_type=export_type)
            documents = await reader.aload_data(self.file_path)
        else:
            reader_cls = TEXT_READERS.get(self.extension)
            documents = await reader_cls().aload_data(self.file_path)

        nodes: List[TextNode] = []
        if self.strategy == ParseStrategy.SEMANTIC:
            nodes = await self.semantic_parser.abuild_semantic_nodes_from_documents(documents)
        elif self.strategy == ParseStrategy.STRUCTURED and self.use_docling:
            nodes = self.structured_parser.get_nodes_from_documents(documents)
        elif self.strategy == ParseStrategy.SPLITTER:
            nodes = self.splitter.get_nodes_from_documents(documents)
        else:
            raise ValueError('Must be a valid parse strategy (semantic,structured,splitter)')
        
        current_section = "General"
        for i, node in enumerate(nodes):
            detector = TextDetector(node.text,extract_topics=True,extract_keyword=True,extract_type=True)
            
            rel_ids = []
            for rel in node.relationships.values():
                if isinstance(rel, list): rel_ids.extend([r.node_id for r in rel])
                else: rel_ids.append(rel.node_id)

            if self.use_docling and self.strategy == ParseStrategy.STRUCTURED:
                current_section = node.metadata.get("heading", current_section)
            else:
                new_section = TextDetector.extract_sections(node.text)
                if new_section: current_section = new_section
            
            stats = await detector.analyze()
            payload = ChunkPayload(**{
                "text": node.text,
                "document_name": self.file_path,
                "document_id": node.ref_doc_id,
                "chunk_id": node.node_id,
                "source": node.metadata.get("file_name", node.metadata.get('file_path', self.file_path)),
                "extension": self.extension,
                "strategy": self.strategy.value,
                "parser": "docling" if self.use_docling else "llama",
                "page": node.metadata.get("page_label",None),
                "bbox": node.metadata.get("bbox", None),
                "index": i+1,
                "title": node.metadata.get("title", node.metadata.get("file_name", node.metadata.get('file_path', self.file_path))),
                "section": current_section,
                "language": self.lang,
                "document_type":"textfile",
                "relationship": rel_ids,
                **stats
            })

            self.chunks.append(ChunkWrapper(
                chunk_id=node.node_id,
                vector=node.embedding,
                payload=payload,
                lang=self.lang
            ))

    def compute_token(self):
        return randint(2000,30000)


class AudioDataLoader(BaseDataLoader):
    ...

class ImageDataLoader(BaseDataLoader):
    ...

class VideoDataLoader(BaseDataLoader):

    def __init__(self, api_key, file_path, lang, doc_type):
        super().__init__(api_key, file_path, lang, doc_type)

    async def process(self,video_path: str, frame_rate: int = 1):
        raise NotImplementedError
        cap = cv2.VideoCapture(video_path)
        frames = []
        timestamps = []
        frame_idx = 0
        fps = int(cap.get(cv2.CAP_PROP_FPS))

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % (fps * frame_rate) == 0:
                frames.append(frame)
                timestamps.append(frame_idx / fps)
            frame_idx += 1
        cap.release()
        for i, frame in enumerate(tqdm(frames, desc="Embedding frames")):
            pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            buf = io.BytesIO()
            pil_image.save(buf, format="JPEG")
            image_bytes = buf.getvalue()

            response = client.embeddings.create(
                model="image-embedding-3-large",
                input=image_bytes
            )
            vector = response.data[0].embedding

            yield vector,{
                    "video": video_path,
                    "timestamp": timestamps[i]
                }

class TabularDataLoader(BaseDataLoader):
    ...      
