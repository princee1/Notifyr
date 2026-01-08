from random import randint
import re, nltk, yake, json
from typing import Any, List, Generator
from enum import Enum

# NLTK & Text Processing
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk import FreqDist
from gensim import corpora, models

from llama_index.core.node_parser import SentenceSplitter, SemanticSplitterNodeParser
from llama_index.core.schema import TextNode
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.readers.base import BaseReader
from llama_index.readers.file import (
    PDFReader, DocxReader, MarkdownReader, 
    HTMLTagReader, PptxReader,XMLReader
)

DOCLING_INSTALLED = True
# Docling Integration
try:
    from llama_index.readers.docling import DoclingReader
    from llama_index.node_parser.docling import DoclingNodeParser
except ImportError as e:
    DOCLING_INSTALLED = False
    

from qdrant_client.models import PointStruct
from app.utils.constant import ParseStrategy
from app.utils.tools import Mock, RunAsync

nltk.download(['stopwords', 'punkt', 'wordnet'], quiet=True)
STOP_WORDS = set(stopwords.words('english'))
KW_EXTRACTOR = yake.KeywordExtractor(lan="en", n=1, top=10)

TEXT_READERS: dict[str, type[BaseReader]] = {
    "pdf": PDFReader,
    "docx": DocxReader,
    "md": MarkdownReader,
    "html": HTMLTagReader,
    "pptx": PptxReader,
    "xml":XMLReader
}

class DataLoaderStepIndex(int, Enum):
    CHECK = 1
    PROCESS = 2
    TOKEN_VERIFY = 3
    TOKEN_COST = 4
    CLEANUP = 5
class BaseDataLoader:
    def __init__(self, api_key: str, file_path: str, lang: str, extension: str,category:str):
        self.file_path = file_path
        self.lang = lang
        self.extension = extension
        self.category = category

    async def process(self):
        raise NotImplementedError

    @staticmethod
    def Factory(ext: str) -> 'BaseDataLoader':
        # Docling handles PDF, DOCX, PPTX, HTML, MD, etc.
        if ext.lower() in ["pdf", "docx", "md", "html", "pptx", "txt",'xml']:
            return TextDataLoader
        return None

class TextDataLoader(BaseDataLoader):
    
    class TextDetector:
        def __init__(self, text: str):
            self.text = text
            self.tokens = [t.lower() for t in word_tokenize(text) if t.isalnum()]
            self.clean_tokens = [t for t in self.tokens if t not in STOP_WORDS]
            self.freq_dist = FreqDist(self.clean_tokens)
            self.sentence_count = len(sent_tokenize(text))

        @RunAsync
        def extract_keywords(self) -> List[str]:
            return [kw for kw, _ in KW_EXTRACTOR.extract_keywords(self.text)]

        @RunAsync
        def extract_topics(self, num_topics=3) -> List[str]:
            if len(self.clean_tokens) < 5: return []
            dict_ = corpora.Dictionary([self.clean_tokens])
            corpus = [dict_.doc2bow(self.clean_tokens)]
            lda = models.LdaModel(corpus, num_topics=num_topics, id2word=dict_, passes=10)
            topics = lda.show_topics(formatted=False)
            return [word for _, top in topics for word, prob in top[:2]]

        def density_label(self) -> str:
            count = self.freq_dist.N()
            return "low" if count < 80 else "medium" if count < 160 else "high"

    def __init__(self, api_key: str, file_path: str, lang: str, extension: str,category:str,
                 strategy: ParseStrategy = ParseStrategy.SEMANTIC, use_docling: bool = False):
        super().__init__(api_key, file_path, lang, extension,category)
        self.points = []
        self.tokens = []
        if use_docling and DOCLING_INSTALLED:
            raise TypeError('Docling must be installed to use it')

        self.strategy = strategy
        self.use_docling = use_docling
        return
        self.embed_model = OpenAIEmbedding(api_key=api_key)

        # Parsers
        self.splitter = SentenceSplitter(chunk_size=1000, chunk_overlap=200)
        self.semantic_parser = SemanticSplitterNodeParser(
            buffer_size=3,
            breakpoint_percentile_threshold=95,
            sentence_splitter=self.splitter.split_text,
            embed_model=self.embed_model,
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

        # 2. SPLIT INTO NODES
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
            detector = self.TextDetector(node.text)
            
            rel_ids = []
            for rel in node.relationships.values():
                if isinstance(rel, list): rel_ids.extend([r.node_id for r in rel])
                else: rel_ids.append(rel.node_id)

            if self.use_docling and self.strategy == ParseStrategy.STRUCTURED:
                current_section = node.metadata.get("heading", current_section)
            else:
                new_section = self.extract_section(node.text)
                if new_section: current_section = new_section

            payload = {
                "text": node.text,
                "document_name": self.file_path,
                "document_id": node.ref_doc_id,
                "node_id": node.node_id,
                "source": node.metadata.get("file_name", node.metadata.get('file_path', None)),
                "extension": self.extension,
                "strategy": self.strategy.value,
                "parser": "docling" if self.use_docling else "llama",
                
                "page": node.metadata.get("page_label"),
                "bbox": node.metadata.get("bbox", None),
                
                "chunk_id": f"{node.ref_doc_id}_{i}",
                "chunk_index": i,
                "title": node.metadata.get("title", ""),
                "section": current_section,
                "language": self.lang,
                "content_type": self.detect_type(node.text),

                "document_type":"file",
                "category":self.category,
                
                "token_count": detector.freq_dist.N(),
                "full_token_count": len(detector.tokens),
                "word_count": detector.freq_dist.B(),
                "most_common": detector.freq_dist.most_common(5),
                "sentence_count": detector.sentence_count,
                "keywords": await detector.extract_keywords(),
                "topics": await detector.extract_topics(),
                "density": detector.density_label(),
                "relationship": rel_ids
            }

            self.points.append(PointStruct(
                id=node.node_id,
                vector=node.embedding,
                payload=payload
            ))

    def compute_token(self):
        return randint(2000,30000)

    @classmethod
    def extract_section(cls, text: str) -> str:
        patterns = [
            r"^(#+)\s+(.*)",                      # Markdown
            r"^(?:\d+\.)+\d*\s+(.*)",             # Numbered: 1.1.2
            r"^(Chapter\s+\d+[:\-]?)\s*(.*)",     # Chapters
            r"^[A-Z][A-Z\s]{5,20}$"               # ALL CAPS short lines
        ]
        for p in patterns:
            match = re.search(p, text, re.MULTILINE)
            if match:
                return next((g for g in match.groups() if g), "").strip()
        return None

    @classmethod
    def detect_type(cls, text: str) -> str:
        text_s = text.strip()
        if cls.extract_section(text_s): return "heading"
        if "|" in text_s or re.search(r"{3,}.*{3,}", text_s): return "table"
        if re.search(r"\b(def|class|import|return|void|public)\b", text_s): return "code"
        if any(x in text_s for x in ["∑", "∫", "λ", "δ", "=="]): return "equation"
        return "paragraph"

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
        
