import re, nltk, yake
from typing import Any, List, Generator
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk import FreqDist
from gensim import corpora, models
from llama_index.core.node_parser import SentenceSplitter, SemanticSplitterNodeParser
from llama_index.embeddings.openai import OpenAIEmbedding
from qdrant_client.models import PointStruct
from llama_index.core.schema import TextNode
from llama_index.readers.file.docs.base import BaseReader
from llama_index.readers.file import CSVReader,PDFReader, ImageReader, VideoAudioReader,MarkdownReader,DocxReader,HTMLTagReader,PptxReader

from app.utils.tools import RunAsync



# Pre-load resources
nltk.download(['stopwords', 'punkt', 'wordnet'], quiet=True)
STOP_WORDS = set(stopwords.words('english'))
KW_EXTRACTOR = yake.KeywordExtractor(lan="en", n=1, top=10)


class BaseDataLoader:

    def __init__(self, api_key: str,file_path:str,lang:str,doc_type:str):
        self.file_path = file_path
        self.lang = lang
        self.doc_type = doc_type

    async def process(self):
        ...


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
            # Fast LDA implementation for small chunks
            dict_ = corpora.Dictionary([self.clean_tokens])
            corpus = [dict_.doc2bow(self.clean_tokens)]
            lda = models.LdaModel(corpus, num_topics=num_topics, id2word=dict_, passes=10)
            topics = lda.show_topics(formatted=False)
            return [word for _, top in topics for word, prob in top[:2]]

        def density_label(self) -> str:
            count = self.freq_dist.N()
            return "low" if count < 80 else "medium" if count < 160 else "high"

    readers:dict[str,type[BaseReader]] = {
        "pdf": PDFReader,
        "docx": DocxReader,
        "md": MarkdownReader,
        "html": HTMLTagReader,
        "pptx":PptxReader,
    }

    def __init__(self, api_key: str,file_path:str,lang:str,doc_type:str):
        super().__init__(api_key,file_path,lang,doc_type)
        self.embed_model = OpenAIEmbedding(api_key=api_key)
        self.splitter = SentenceSplitter(chunk_size=1000, chunk_overlap=200)
        self.semantic_parser = SemanticSplitterNodeParser(
            buffer_size=3,
            breakpoint_percentile_threshold=95,
            sentence_splitter=self.splitter.split_text,
            embed_model=self.embed_model,
        )
    
    async def process(self):
        reader = self.readers[self.doc_type]
        documents = await reader().aload_data(self.file_path)
        nodes:list[TextNode] = await self.semantic_parser.abuild_semantic_nodes_from_documents(documents)
        
        current_section = "General"
        
        for i, node in enumerate(nodes):
            detector = self.TextDetector(node.text)
            
            # Efficiently parse relationships
            rel_ids = []
            for rel in node.relationships.values():
                if isinstance(rel, list): rel_ids.extend([r.node_id for r in rel])
                else: rel_ids.append(rel.node_id)

            # Section tracking
            new_section = self.extract_section(node.text)
            if new_section: current_section = new_section

            payload = {
                "text": node.text,
                "document_id": node.ref_doc_id,
                "node_id": node.node_id,
                "source": node.metadata.get("file_name",node.metadata.get('file_path',None)),
                "document_type": self.doc_type,
                "page": node.metadata.get("page_label"),
                "chunk_id": f"{node.ref_doc_id}_{i}",
                "chunk_index": i,
                "title":node.metadata.get("title",""),
                "section": current_section,
                "language": self.lang,
                "content_type": self.detect_type(node.text),
                "token_count": detector.freq_dist.N(),
                "full_token_count": len(detector.tokens),
                "word_count": detector.freq_dist.B(),
                "sentence_count": detector.sentence_count,
                "keywords": await detector.extract_keywords(),
                "topics": await detector.extract_topics(),
                "density": detector.density_label(),
                "relationship": rel_ids
            }

            yield PointStruct(
                id=i,
                vector=node.embedding,
                payload=payload
            )
    
    @classmethod
    def extract_section(cls,text: str) -> str:
        # Matches: # Header, ## Header, 1.1 Header, or "Chapter 1: Header"
        patterns = [
            r"^(#+)\s+(.*)",                          # Markdown
            r"^(?:\d+\.)+\d*\s+(.*)",                # Numbered: 1.1.2
            r"^(Chapter\s+\d+[:\-]?)\s*(.*)",        # Chapters
            r"^[A-Z][A-Z\s]{5,20}$"                  # ALL CAPS short lines
        ]
        for p in patterns:
            match = re.search(p, text, re.MULTILINE)
            if match:
                return next((g for g in match.groups() if g), "").strip()
        return None

    @classmethod
    def detect_type(cls,text: str) -> str:
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
        
