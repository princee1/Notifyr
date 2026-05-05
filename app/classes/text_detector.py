
# NLTK & Text Processing
from typing import Any, List

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk import FreqDist
from gensim import corpora, models
import nltk, yake,re
from app.utils.tools import RunAsync

nltk.download(['stopwords', 'punkt', 'wordnet'], quiet=True)
STOP_WORDS = set(stopwords.words('english'))
KW_EXTRACTOR = yake.KeywordExtractor(lan="en", n=1, top=10)


class TextDetector:
    def __init__(self, text: str,extract_topic=False,extract_keyword=False,extract_section=False,extract_type=False):
        self.text = text
        self.tokens = [t.lower() for t in word_tokenize(text) if t.isalnum()]
        self.clean_tokens = [t for t in self.tokens if t not in STOP_WORDS]
        self.freq_dist = FreqDist(self.clean_tokens)
        self.sentence_count = len(sent_tokenize(text))
        self.extract_topic = extract_topic
        self.extract_keyword = extract_keyword
        self.extract_section = extract_section
        self.extract_type = extract_type

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
    
    @classmethod
    def extract_sections(cls, text: str) -> str:
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
        if cls.extract_sections(text_s): return "heading"
        if "|" in text_s or re.search(r"{3,}.*{3,}", text_s): return "table"
        if re.search(r"\b(def|class|import|return|void|public)\b", text_s): return "code"
        if any(x in text_s for x in ["∑", "∫", "λ", "δ", "=="]): return "equation"
        return "paragraph"

    async def analyze(self) -> dict[str, Any]:

        stats = {
            "token_count": self.freq_dist.N(),
            "full_token_count": len(self.tokens),
            "word_count": self.freq_dist.B(),
            "most_common": self.freq_dist.most_common(5),
            "sentence_count": self.sentence_count,
            "density": self.density_label(),
        }
        if self.extract_keyword:
            stats["keywords"] = await self.extract_keywords()
        if self.extract_topic:
            stats["topics"] = await self.extract_topics()
        if self.extract_section:
            stats["section"] = self.extract_sections(self.text)
        if self.extract_type:
            stats["content_type"] = self.detect_type(self.text)
        
        return stats

