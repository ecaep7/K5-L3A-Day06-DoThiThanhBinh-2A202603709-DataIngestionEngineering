"""Tạo 3 file mẫu cho phần chấm thủ công (coherence, metadata, grounding) trong results/audit/.

    python scripts/make_audit_sheets.py

File được lưu UTF-8 có BOM để Excel mở đúng dấu. Mở bằng Excel, điền các cột để trống,
rồi lưu lại dưới dạng "CSV UTF-8 (Comma delimited)". Script KHÔNG ghi đè file đã có,
để nhãn đã chấm không bị mất.

Các cột auto_* là kiểm tra bằng máy để hỗ trợ; nhãn chính thức là các cột người chấm điền.
"""
import csv
import json
import sys
from pathlib import Path

STARTER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STARTER))

from src.chunking import by_paragraph, fixed_size, flatten_lines  # noqa: E402
from src.ingestion import chapter_of, load_pdf  # noqa: E402

RESULTS = STARTER / "results"
AUDIT = RESULTS / "audit"
COHERENCE_PAGES = 10   # 10 trang nội dung đầu tiên theo số trang; vị trí = điểm giữa text của trang


def write(name: str, header: list[str], rows: list[list]) -> None:
    path = AUDIT / name
    if path.exists():
        print(f"Bỏ qua {name}: file đã có (không ghi đè nhãn đã chấm)")
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"Đã tạo results/audit/{name} ({len(rows)} dòng cần chấm)")


def coherence(pages) -> None:
    rows = []
    for n, page in enumerate(pages[:COHERENCE_PAGES], start=1):
        flat, _ = flatten_lines(page.text)
        offset = len(flat) // 2
        context = flat[max(0, offset - 120): offset + 120]
        for strategy, chunks in (("A", fixed_size(page, 500, 50)), ("B (= C)", by_paragraph(page, 500))):
            chunk = next(c for c in chunks if c.metadata["char_start"] <= offset < c.metadata["char_end"])
            rows.append([f"pos{n:02d}", page.page, offset, strategy, chunk.chunk_id, context, chunk.text, "", ""])
    write("coherence_audit.csv",
          ["position_id", "page", "char_offset", "strategy", "chunk_id", "text_around_position",
           "chunk_text", "score_0_1_2", "reason"], rows)


def metadata_and_grounding(pages) -> None:
    flat_by_page = {p.page: flatten_lines(p.text)[0] for p in pages}
    traces = [json.loads(line) for line in open(RESULTS / "traces_test.jsonl", encoding="utf-8")]
    meta_rows, ground_rows = [], []
    for t in traces:
        for h in t["hits"]:
            meta_rows.append([
                t["strategy"], t["id"], h["rank"], h["chunk_id"], h["source"], h["page"], h["chapter"],
                h["printed_page"], json.dumps(t["filter"]) if t["filter"] else "",
                h["text"] in flat_by_page.get(h["page"], ""), h["chapter"] == chapter_of(h["page"]),
                h["text"][:200], "", "", "", ""])
        top3 = "\n\n".join(f"[{h['rank']}] trang {h['page']} | {h['chunk_id']}\n{h['text']}" for h in t["hits"])
        ground_rows.append([t["strategy"], t["id"], t["type"], t["question"], t["expected_answer"],
                            t["gold_page"], t["evidence_quote"], top3, "", ""])
    write("metadata_audit.csv",
          ["strategy", "id", "rank", "chunk_id", "source", "page", "chapter", "printed_page", "filter_applied",
           "auto_text_found_on_page", "auto_chapter_matches_page", "text_preview",
           "source_ok", "page_ok", "chapter_ok", "note"], meta_rows)
    write("grounding_audit.csv",
          ["strategy", "id", "type", "question", "expected_answer", "gold_page", "evidence_quote",
           "top3_chunks", "grounding_0_1_2", "reason"], ground_rows)


if __name__ == "__main__":
    AUDIT.mkdir(parents=True, exist_ok=True)
    pdf_pages = load_pdf(STARTER / "data" / "pom-ch01-02.pdf", "pom-ch01-02", "starter/data/pom-ch01-02.pdf")
    content = sorted((p for p in pdf_pages if p.metadata["status"] == "ok"), key=lambda p: p.page)
    coherence(content)
    metadata_and_grounding(content)
