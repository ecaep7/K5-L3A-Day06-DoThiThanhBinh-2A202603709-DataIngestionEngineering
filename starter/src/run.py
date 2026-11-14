"""Pipeline Day 06.

    python -m src.run ingest               đọc PDF, chia chunk A và B, tạo vector, lưu vào pgvector
    python -m src.run retrieve --split dev  chạy top-3 cho cả A, B, C trên tập dev, lưu trace
    python -m src.run retrieve --split test chỉ chạy SAU KHI đã chọn chiến lược trên dev

Cấu hình C dùng chung index với B; khác B duy nhất ở điều kiện lọc chapter cho câu có filter.
"""
import argparse
import csv
import hashlib
import json
import os
import statistics
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import DEFAULT_MODEL, SentenceTransformerEmbedder
from .ingestion import load_pdf
from .store import PgVectorStore

STARTER = Path(__file__).resolve().parents[1]
REPO = STARTER.parent
PDF = STARTER / "data" / "pom-ch01-02.pdf"
QUESTIONS = REPO / "benchmark" / "questions.csv"
RESULTS = STARTER / "results"
DOCUMENT_ID = "pom-ch01-02"
SOURCE = "starter/data/pom-ch01-02.pdf"
MIN_CONTENT_PAGES = 30
TOP_K = 3

# Index = cách chia chunk được lưu trong database.
INDEXES = {
    "A": lambda page: fixed_size(page, size=500, overlap=50),
    "B": lambda page: by_paragraph(page, max_size=500),
}
# Chiến lược = index + có lọc metadata hay không.
STRATEGIES = {
    "A": {"index": "A", "use_filter": False},
    "B": {"index": "B", "use_filter": False},
    "C": {"index": "B", "use_filter": True},
}


def setup() -> tuple[SentenceTransformerEmbedder, PgVectorStore]:
    load_dotenv(STARTER / ".env")
    model_name = os.getenv("EMBEDDING_MODEL") or DEFAULT_MODEL
    embedder = SentenceTransformerEmbedder(model_name)
    store = PgVectorStore(os.getenv("DATABASE_URL", ""), embedder.dimensions)
    store.create_schema()
    return embedder, store


def ingest() -> None:
    embedder, store = setup()
    pages = load_pdf(PDF, document_id=DOCUMENT_ID, source=SOURCE)
    content = [p for p in pages if p.metadata["status"] == "ok"]
    skipped = {p.page: p.metadata["status"] for p in pages if p.metadata["status"] != "ok"}
    if len(content) < MIN_CONTENT_PAGES:
        raise SystemExit(f"Chỉ có {len(content)} trang nội dung, cần ít nhất {MIN_CONTENT_PAGES}")

    stats = {"run_at": datetime.now().isoformat(timespec="seconds"), "model": embedder.model_name,
             "dimensions": embedder.dimensions, "max_seq_length": embedder.max_seq_length,
             "pages_total": len(pages), "content_pages": len(content), "skipped_pages": skipped,
             "cost_usd": 0, "indexes": {}}
    for name, split in INDEXES.items():
        started = time.perf_counter()
        chunks = [c for p in content for c in split(p)]
        for c in chunks:
            c.metadata["content_hash"] = hashlib.sha256(c.text.encode("utf-8")).hexdigest()
        saved = store.existing_hashes(name, embedder.model_name)
        changed = [c for c in chunks if saved.get(c.chunk_id) != c.metadata["content_hash"]]

        embed_started = time.perf_counter()
        vectors = embedder.embed_documents([c.text for c in changed])
        embed_seconds = time.perf_counter() - embed_started
        deleted = store.upsert(name, [c.chunk_id for c in chunks], changed, vectors,
                               embedder.model_name, [DOCUMENT_ID])
        rows, distinct = store.count(name)

        lengths = [len(c.text) for c in chunks]
        tokens = embedder.token_counts([c.text for c in chunks])
        stats["indexes"][name] = {
            "chunks": len(chunks), "embedded_this_run": len(changed), "deleted_obsolete": deleted,
            "rows_in_db": rows, "distinct_ids_in_db": distinct, "duplicates": rows - distinct,
            "chars_min": min(lengths), "chars_median": statistics.median(lengths),
            "chars_max": max(lengths), "chars_total": sum(lengths),
            "tokens_median": statistics.median(tokens), "tokens_max": max(tokens),
            "chunks_truncated_by_model": sum(t > embedder.max_seq_length for t in tokens),
            "seconds_embed": round(embed_seconds, 2),
            "seconds_total": round(time.perf_counter() - started, 2),
        }
        s = stats["indexes"][name]
        print(f"Index {name}: {s['chunks']} chunk | tạo vector mới {s['embedded_this_run']} | "
              f"xóa cũ {s['deleted_obsolete']} | trong DB {s['rows_in_db']} dòng, trùng {s['duplicates']} | "
              f"bị model cắt bớt {s['chunks_truncated_by_model']} | {s['seconds_total']} giây")

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "ingest_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(RESULTS / "ingest_log.jsonl", "a", encoding="utf-8") as f:   # giữ lịch sử mọi lần nạp
        f.write(json.dumps(stats, ensure_ascii=False) + "\n")
    print("Đã lưu results/ingest_stats.json và thêm một dòng vào results/ingest_log.jsonl")


def retrieve(split: str) -> None:
    embedder, store = setup()
    with open(QUESTIONS, encoding="utf-8") as f:
        questions = [q for q in csv.DictReader(f) if q["split"] == split]
    if not questions:
        raise SystemExit(f"Không có câu hỏi nào thuộc split '{split}'")

    query_vectors = {q["id"]: embedder.embed_query(q["question"]) for q in questions}
    traces = []
    for strategy, config in STRATEGIES.items():
        for q in questions:
            flt = None
            if config["use_filter"] and q["filter_chapter"]:
                flt = {"chapter": int(q["filter_chapter"])}
            hits = store.search(config["index"], query_vectors[q["id"]], TOP_K, flt)
            traces.append({
                "strategy": strategy, "index": config["index"], "filter": flt,
                "id": q["id"], "split": q["split"], "type": q["type"], "question": q["question"],
                "expected_answer": q["expected_answer"], "gold_source_id": q["gold_source_id"],
                "gold_page": int(q["gold_page"]), "evidence_quote": q["evidence_quote"],
                "alt_gold_page": int(q["alt_gold_page"]) if q["alt_gold_page"] else None,
                "alt_evidence_quote": q["alt_evidence_quote"] or None,
                "hits": [{"rank": i + 1, **{k: (round(v, 4) if k == "score" else v) for k, v in h.items()}}
                         for i, h in enumerate(hits)],
            })
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"traces_{split}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"{len(questions)} câu x {len(STRATEGIES)} chiến lược = {len(traces)} lượt truy xuất "
          f"-> results/{out.name} (model {embedder.model_name})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Day 06 data ingestion pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest")
    r = sub.add_parser("retrieve")
    r.add_argument("--split", choices=["dev", "test"], required=True)
    args = parser.parse_args()
    if args.command == "ingest":
        ingest()
    else:
        retrieve(args.split)


if __name__ == "__main__":
    main()
