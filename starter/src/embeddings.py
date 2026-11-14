"""Embedding model thật, chạy local bằng Sentence Transformers (không cần API key)."""
from typing import Protocol

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class SentenceTransformerEmbedder:
    """Câu hỏi và chunk đi qua cùng một model, cùng cách xử lý (model này không dùng prefix).

    Vector được chuẩn hóa độ dài 1, nên cosine similarity = tích vô hướng.
    Nếu không tải được model thì báo lỗi luôn, không có vector giả thay thế.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, batch_size: int = 32) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.batch_size = batch_size
        self.model = SentenceTransformer(model_name)
        # sentence-transformers >= 6 đổi tên hàm; giữ tương thích cả hai phiên bản.
        get_dim = getattr(self.model, "get_embedding_dimension", None) or self.model.get_sentence_embedding_dimension
        self.dimensions = get_dim()
        self.max_seq_length = self.model.max_seq_length

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, batch_size=self.batch_size,
                                    normalize_embeddings=True, convert_to_numpy=True)
        return vectors.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts) if texts else []

    def embed_query(self, question: str) -> list[float]:
        return self._encode([question])[0]

    def token_counts(self, texts: list[str]) -> list[int]:
        """Số token mỗi text (kể cả token đặc biệt), để biết chunk nào bị model cắt bớt."""
        # Chỉ đếm, không cắt; verbose=False để tokenizer không cảnh báo chuỗi dài hơn 128.
        return [len(ids) for ids in self.model.tokenizer(texts, verbose=False)["input_ids"]]
