"""Lưu và tìm vector bằng PostgreSQL + pgvector."""
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .models import Chunk

# Chỉ các cột này được dùng làm điều kiện lọc; giá trị luôn truyền qua tham số SQL.
FILTERABLE = {"chapter", "page", "document_id"}


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if not database_url:
            raise ValueError("Thiếu DATABASE_URL (xem starter/.env)")
        if dimensions <= 0:
            raise ValueError("Số chiều vector không hợp lệ")
        self.database_url = database_url
        self.dimensions = dimensions

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, connect_timeout=5)

    def create_schema(self) -> None:
        """Một bảng cho mọi chiến lược; khóa chính (strategy, chunk_id) chống nhân đôi."""
        with self._connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    strategy      text    NOT NULL,
                    chunk_id      text    NOT NULL,
                    document_id   text    NOT NULL,
                    source        text    NOT NULL,
                    page          integer NOT NULL,
                    chapter       integer,
                    printed_page  integer,
                    char_start    integer,
                    char_end      integer,
                    text          text    NOT NULL,
                    content_hash  text    NOT NULL,
                    model         text    NOT NULL,
                    embedding     vector({self.dimensions}) NOT NULL,
                    PRIMARY KEY (strategy, chunk_id)
                )""")
            row = conn.execute("""
                SELECT format_type(atttypid, atttypmod) FROM pg_attribute
                WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'""").fetchone()
            if row[0] != f"vector({self.dimensions})":
                raise ValueError(f"Bảng chunks đang có cột {row[0]}, model cần vector({self.dimensions})")

    def existing_hashes(self, strategy: str, model: str) -> dict[str, str]:
        """chunk_id -> content_hash của các chunk đã lưu bằng đúng model này."""
        with self._connect() as conn:
            rows = conn.execute("SELECT chunk_id, content_hash FROM chunks WHERE strategy = %s AND model = %s",
                                (strategy, model)).fetchall()
        return dict(rows)

    def upsert(self, strategy: str, current_ids: list[str], changed: list[Chunk],
               vectors: list[list[float]], model: str, document_ids: list[str]) -> int:
        """Ghi chunk mới hoặc đã đổi theo ID ổn định, rồi xóa chunk cũ không còn trong lần nạp này.

        current_ids: ID của toàn bộ chunk hiện tại; changed/vectors: chỉ những chunk cần (ghi lại) vector.
        Trả về số chunk cũ đã xóa.
        """
        if len(changed) != len(vectors):
            raise ValueError("Số chunk và số vector không khớp")
        if any(len(v) != self.dimensions for v in vectors):
            raise ValueError(f"Có vector không đủ {self.dimensions} chiều")
        with self._connect() as conn:
            with conn.cursor() as cur:
                for chunk, vector in zip(changed, vectors):
                    m = chunk.metadata
                    cur.execute("""
                        INSERT INTO chunks (strategy, chunk_id, document_id, source, page, chapter,
                                            printed_page, char_start, char_end, text, content_hash,
                                            model, embedding)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)
                        ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                            document_id = EXCLUDED.document_id, source = EXCLUDED.source,
                            page = EXCLUDED.page, chapter = EXCLUDED.chapter,
                            printed_page = EXCLUDED.printed_page, char_start = EXCLUDED.char_start,
                            char_end = EXCLUDED.char_end, text = EXCLUDED.text,
                            content_hash = EXCLUDED.content_hash, model = EXCLUDED.model,
                            embedding = EXCLUDED.embedding""",
                        (strategy, chunk.chunk_id, chunk.document_id, chunk.source, chunk.page,
                         m.get("chapter"), m.get("printed_page"), m.get("char_start"), m.get("char_end"),
                         chunk.text, m["content_hash"], model, _vector_literal(vector)))
                # Chunk của các tài liệu vừa nạp nhưng không còn trong lần nạp này -> xóa.
                cur.execute("""
                    DELETE FROM chunks
                    WHERE strategy = %s AND document_id = ANY(%s) AND NOT (chunk_id = ANY(%s))""",
                    (strategy, document_ids, current_ids))
                return cur.rowcount

    def count(self, strategy: str) -> tuple[int, int]:
        """(tổng số dòng, số chunk_id khác nhau) - hai số bằng nhau nghĩa là không nhân đôi."""
        with self._connect() as conn:
            return conn.execute("SELECT count(*), count(DISTINCT chunk_id) FROM chunks WHERE strategy = %s",
                                (strategy,)).fetchone()

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Lọc metadata trong SQL rồi xếp theo khoảng cách cosine (tìm chính xác, không dùng index xấp xỉ)."""
        if len(query_vector) != self.dimensions:
            raise ValueError("Vector câu hỏi sai số chiều")
        where, params = ["strategy = %s"], [strategy]
        for key, value in (filters or {}).items():
            if key not in FILTERABLE:
                raise ValueError(f"Không cho phép lọc theo '{key}'")
            where.append(f"{key} = %s")
            params.append(value)
        qv = _vector_literal(query_vector)
        sql = f"""
            SELECT chunk_id, document_id, source, page, chapter, printed_page, char_start, char_end,
                   text, 1 - (embedding <=> %s::vector) AS score
            FROM chunks WHERE {' AND '.join(where)}
            ORDER BY embedding <=> %s::vector
            LIMIT %s"""
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, [qv, *params, qv, top_k])
                return cur.fetchall()
