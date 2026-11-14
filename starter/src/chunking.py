"""Hai cách chia chunk trên cùng một text đã chuẩn hóa của từng trang.

A - fixed_size: cửa sổ trượt theo số ký tự, không quan tâm câu hay đoạn.
B - by_paragraph: nhận diện tiêu đề và đoạn văn, gom đoạn đến giới hạn kích thước,
    đoạn quá dài thì cắt ở ranh giới câu.

Cả hai cùng làm trên chuỗi `flat` của trang (các dòng PDF nối lại), nên khác nhau
duy nhất ở chỗ đặt ranh giới chunk. Vị trí char_start/char_end tính trên chuỗi này.
"""
import re

from .models import Chunk, DocumentPage

BODY_LINE_MIN = 90          # dòng thân bài trong sách dài ~98-115 ký tự
TERMINAL = (".", "?", "!", ":", ";", "”", '"', ")")
SENTENCE_END = re.compile(r"(?<=[.?!”])\s+(?=[A-Z“\"(])")


def flatten_lines(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Nối các dòng thành một chuỗi; trả về chuỗi và vị trí (start, end) của từng dòng.

    Dòng kết thúc bằng '-' hoặc '—' (ví dụ 'decision-' + 'making') nối liền không cách.
    """
    flat, spans = "", []
    for line in text.split("\n"):
        if flat and not flat.endswith(("-", "—")):
            flat += " "
        start = len(flat)
        flat += line
        spans.append((start, len(flat)))
    return flat, spans


def is_heading(line: str) -> bool:
    """Dòng ngắn, viết hoa đầu, không kết thúc bằng dấu câu (bỏ số chú thích cuối dòng)."""
    core = re.sub(r"[\d,]+$", "", line).rstrip()
    return (len(line) < BODY_LINE_MIN and bool(core)
            and (core[0].isupper() or core[0].isdigit())
            and not core.endswith(TERMINAL))


def paragraph_spans(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Tìm ranh giới đoạn: tiêu đề gắn vào đoạn ngay sau nó; dòng thân bài ngắn kết thúc đoạn."""
    flat, spans = flatten_lines(text)
    paragraphs, start, end = [], None, None
    pending_heading = None
    for line, (s, e) in zip(text.split("\n"), spans):
        if is_heading(line):
            if start is not None:
                paragraphs.append((start, end))
                start = None
            pending_heading = pending_heading if pending_heading is not None else s
            end = e
            continue
        if start is None:
            start = pending_heading if pending_heading is not None else s
            pending_heading = None
        end = e
        if len(line) < BODY_LINE_MIN:       # dòng cuối của đoạn
            paragraphs.append((start, end))
            start = None
    if start is not None:
        paragraphs.append((start, end))
    elif pending_heading is not None:       # tiêu đề cuối trang, không có thân bài theo sau
        paragraphs.append((pending_heading, end))
    return flat, paragraphs


def _split_long(flat: str, start: int, end: int, max_size: int) -> list[tuple[int, int]]:
    """Cắt một đoạn quá dài ở ranh giới câu; câu dài hơn max_size thì cắt cứng."""
    cuts = [start] + [start + m.end() for m in SENTENCE_END.finditer(flat[start:end])] + [end]
    pieces, piece_start, last = [], start, start
    for cut in cuts[1:]:
        if cut - piece_start > max_size and last > piece_start:
            pieces.append((piece_start, last))
            piece_start = last
        while cut - piece_start > max_size:            # một câu dài hơn giới hạn
            pieces.append((piece_start, piece_start + max_size))
            piece_start += max_size
        last = cut
    if last > piece_start:
        pieces.append((piece_start, last))
    return pieces


def _make_chunk(page: DocumentPage, kind: str, index: int, flat: str,
                start: int, end: int, method: str) -> Chunk:
    text = flat[start:end].strip()
    return Chunk(
        chunk_id=f"{page.document_id}-p{page.page}-{kind}{index:02d}",
        document_id=page.document_id,
        source=page.source,
        page=page.page,
        text=text,
        metadata={"chapter": page.metadata["chapter"],
                  "printed_page": page.metadata["printed_page"],
                  "char_start": start, "char_end": end, "chunking": method},
    )


def fixed_size(page: DocumentPage, size: int = 500, overlap: int = 50) -> list[Chunk]:
    """Cấu hình A: cửa sổ `size` ký tự, mỗi cửa sổ lùi lại `overlap` ký tự so với cửa sổ trước."""
    if overlap >= size:
        raise ValueError("overlap phải nhỏ hơn size")
    flat, _ = flatten_lines(page.text)
    chunks, start = [], 0
    while start < len(flat):
        end = min(start + size, len(flat))
        chunks.append(_make_chunk(page, "f", len(chunks), flat, start, end,
                                  f"fixed_{size}_{overlap}"))
        if end == len(flat):
            break
        start = end - overlap
    return chunks


def by_paragraph(page: DocumentPage, max_size: int = 500) -> list[Chunk]:
    """Cấu hình B: gom các đoạn liền nhau đến tối đa `max_size` ký tự."""
    flat, paragraphs = paragraph_spans(page.text)
    pieces = []
    for s, e in paragraphs:
        pieces.extend(_split_long(flat, s, e, max_size) if e - s > max_size else [(s, e)])
    groups, g_start, g_end = [], None, None
    for s, e in pieces:
        if g_start is not None and e - g_start <= max_size:
            g_end = e
            continue
        if g_start is not None:
            groups.append((g_start, g_end))
        g_start, g_end = s, e
    if g_start is not None:
        groups.append((g_start, g_end))
    return [_make_chunk(page, "p", i, flat, s, e, f"paragraph_max{max_size}")
            for i, (s, e) in enumerate(groups)]


if __name__ == "__main__":
    import csv
    import statistics
    from pathlib import Path

    from .ingestion import load_pdf

    root = Path(__file__).resolve().parents[1]
    pages = load_pdf(root / "data" / "pom-ch01-02.pdf", document_id="pom-ch01-02",
                     source="starter/data/pom-ch01-02.pdf")
    content = [p for p in pages if p.metadata["status"] == "ok"]
    strategies = {"A": lambda p: fixed_size(p, size=500, overlap=50),
                  "B": lambda p: by_paragraph(p, max_size=500)}
    for name, split in strategies.items():
        chunks = [c for p in content for c in split(p)]
        lengths = [len(c.text) for c in chunks]
        out = root / "results" / f"chunks_{name}.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["chunk_id", "page", "chapter", "char_start", "char_end", "chars", "text"])
            for c in chunks:
                writer.writerow([c.chunk_id, c.page, c.metadata["chapter"], c.metadata["char_start"],
                                 c.metadata["char_end"], len(c.text), c.text])
        print(f"{name}: {len(chunks)} chunk | dài ngắn nhất {min(lengths)} | trung vị "
              f"{statistics.median(lengths):.0f} | dài nhất {max(lengths)} | tổng {sum(lengths)} ký tự "
              f"-> results/{out.name}")
