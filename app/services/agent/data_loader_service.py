from app.definition._service import BaseService, Service
from app.services.agent.llm_provider_service import LLMProviderService
from app.services.config_service import ConfigService
from openai import OpenAI
from llama_index.core.node_parser import SimpleNodeParser,SentenceSplitter
from llama_index.readers.file import CSVReader,PDFReader, ImageReader, VideoAudioReader,XMLReader,MarkdownReader
from app.services.file.file_service import FileService
import cv2
from PIL import Image
import io
from openai import OpenAI
from tqdm import tqdm


EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_SIZE = 512
OPENAI_API_KEY = "YOUR_OPENAI_KEY"
client = OpenAI(api_key=OPENAI_API_KEY)


@Service()
class DataLoaderService(BaseService):
    
    def __init__(self,configService:ConfigService,llmProviderService:LLMProviderService,fileService:FileService):
        super().__init__()
        self.configService = configService
        self.llmProviderService = llmProviderService
        self.fileService = fileService

    def build(self, build_state=...):
        self.splitter = SentenceSplitter(chunk_size=1000,chunk_overlap=200)

    def _load_and_chunk_pdf(self,path:str):
        docs = PDFReader().load_data(file=path)
        texts = [d.text for d in docs if getattr(d,"text",None)]
        chunks = []
        for t in texts:
            chunks.extend(self.splitter.split_text(t))
        return chunks

    def embed_texts(texts:list[str])-> list[list[float]]:

        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts
        )
        return [item.embedding for item in response.data]


    def process_pdf(self):
        ...
    

    def process_video_frames(self,video_path: str, frame_rate: int = 1):
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
        
