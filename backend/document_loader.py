import uuid
from typing import List, Dict
from langchain_community.document_loaders import PyPDFLoader, DocxLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

class DocumentLoader:
    def __init__(self, chunk_sizes=[2000, 800, 300], overlaps=[200, 100, 50]):
        self.chunk_sizes = chunk_sizes  # L1, L2, L3 大小
        self.overlaps = overlaps

    def load_document(self, file_path: str) -> str:
        if file_path.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
        elif file_path.endswith('.docx'):
            loader = DocxLoader(file_path)
        else:
            raise ValueError("Unsupported file type")
        docs = loader.load()
        return "\n".join([doc.page_content for doc in docs])

    def split_by_level(self, text: str, level: int) -> List[Dict]:
        """按层级分块，返回带元数据的块列表"""
        size = self.chunk_sizes[level-1]
        overlap = self.overlaps[level-1]
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
        )
        chunks = splitter.split_text(text)
        result = []
        for i, chunk in enumerate(chunks):
            result.append({
                "chunk_id": str(uuid.uuid4()),
                "level": level,
                "text": chunk,
                "order": i
            })
        return result

    def process_document(self, file_path: str) -> Dict:
        """三级分块，返回叶子块（L3）和父块（L1/L2）"""
        full_text = self.load_document(file_path)

        # L1 分块
        l1_chunks = self.split_by_level(full_text, level=1)
        parent_chunks = []  # 存储 L1 和 L2
        leaf_chunks = []    # 存储 L3

        for l1 in l1_chunks:
            # 存储 L1 父块
            parent_chunks.append({
                "chunk_id": l1["chunk_id"],
                "level": 1,
                "text": l1["text"],
                "parent_id": None,
                "root_id": l1["chunk_id"]
            })
            # L2 分块
            l2_chunks = self.split_by_level(l1["text"], level=2)
            for l2 in l2_chunks:
                parent_chunks.append({
                    "chunk_id": l2["chunk_id"],
                    "level": 2,
                    "text": l2["text"],
                    "parent_id": l1["chunk_id"],
                    "root_id": l1["chunk_id"]
                })
                # L3 分块
                l3_chunks = self.split_by_level(l2["text"], level=3)
                for l3 in l3_chunks:
                    leaf_chunks.append({
                        "chunk_id": l3["chunk_id"],
                        "level": 3,
                        "text": l3["text"],
                        "parent_id": l2["chunk_id"],
                        "root_id": l1["chunk_id"]
                    })

        return {
            "leaf_chunks": leaf_chunks,
            "parent_chunks": parent_chunks
        }