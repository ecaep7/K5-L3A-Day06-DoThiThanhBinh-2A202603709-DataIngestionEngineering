"""Chấm truy xuất tự động từ trace: Hit@1, Evidence Hit@3, tuân thủ filter.

    python -m src.evaluation --split dev

Định nghĩa (theo GUIDE.md): một chunk là "hit" khi nó thuộc đúng nguồn + trang gold và chứa ĐỦ
đoạn evidence_quote (hoặc thuộc alt_gold_page và chứa đủ alt_evidence_quote).
So khớp sau khi chuẩn hóa Unicode và khoảng trắng; không suy ra nhãn coherence/grounding từ đây.
"""
import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

RESULTS = Path(__file__).resolve().parents[1] / "results"
QUESTIONS = Path(__file__).resolve().parents[2] / "benchmark" / "questions.csv"


def canon(text: str) -> str:
    """Chuẩn hóa để so khớp: NFKC, gộp khoảng trắng, bỏ dấu cách sau '-' hoặc '—' do xuống dòng."""
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text))
    return re.sub(r"(?<=[-—]) ", "", text).strip()


def _gold_pairs(q: dict[str, Any]) -> list[tuple[int, str]]:
    pairs = [(q["gold_page"], q["evidence_quote"])]
    if q.get("alt_gold_page") and q.get("alt_evidence_quote"):
        pairs.append((q["alt_gold_page"], q["alt_evidence_quote"]))
    return pairs


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Chấm một lượt truy xuất. Trả về hit@1, hit@3, hạng của hit đầu tiên và các cờ lỗi."""
    pairs = _gold_pairs(question)
    ranks = []
    for h in hits:
        is_hit = any(h["document_id"] == question["gold_source_id"] and h["page"] == page
                     and canon(ev) in canon(h["text"]) for page, ev in pairs)
        ranks.append(is_hit)
    gold_pages = {p for p, _ in pairs}
    page_only = [h["page"] in gold_pages for h in hits]
    # Evidence bị tách: không chunk nào chứa đủ, nhưng ghép các chunk cùng trang gold trong top-3 thì đủ.
    split = False
    if not any(ranks):
        for page, ev in pairs:
            same = sorted((h for h in hits if h["page"] == page), key=lambda h: h["char_start"])
            if len(same) > 1 and canon(ev) in canon(" ".join(h["text"] for h in same)):
                split = True
    # Phạm vi người hỏi yêu cầu (filter_chapter), xét cho MỌI chiến lược, kể cả khi A/B không áp dụng lọc.
    requested = question.get("requested_filter")
    return {
        "hit1": ranks[0] if ranks else False,
        "hit3": any(ranks),
        "first_hit_rank": ranks.index(True) + 1 if any(ranks) else None,
        "gold_page_in_top3_without_full_evidence": (not any(ranks)) and any(page_only),
        "evidence_split_across_chunks": split,
        "filter_respected": None if not requested else all(h.get(k) == v for h in hits for k, v in requested.items()),
        "top_pages": [h["page"] for h in hits],
        "top_chunk_ids": [h["chunk_id"] for h in hits],
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Gộp Hit@1 và Evidence Hit@3 theo chiến lược (và theo loại câu), giữ dạng n/N."""
    out: dict[str, Any] = {}
    groups: dict[str, list] = defaultdict(list)
    for t in traces:
        groups[t["strategy"]].append(t)
    for strategy, rows in sorted(groups.items()):
        n = len(rows)
        filtered = [r for r in rows if r.get("requested_filter")]
        by_type: dict[str, list] = defaultdict(list)
        for r in rows:
            by_type[r["type"]].append(r)
        out[strategy] = {
            "N": n,
            "hit1": sum(r["eval"]["hit1"] for r in rows),
            "hit3": sum(r["eval"]["hit3"] for r in rows),
            "filter_questions": len(filtered),
            "filter_respected": sum(r["eval"]["filter_respected"] for r in filtered) if filtered else None,
            "by_type": {k: f"{sum(r['eval']['hit3'] for r in v)}/{len(v)}" for k, v in sorted(by_type.items())},
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    split = parser.parse_args().split
    traces = [json.loads(line) for line in open(RESULTS / f"traces_{split}.jsonl", encoding="utf-8")]
    with open(QUESTIONS, encoding="utf-8") as f:
        requested = {q["id"]: {"chapter": int(q["filter_chapter"])} for q in csv.DictReader(f) if q["filter_chapter"]}
    for t in traces:
        t["requested_filter"] = requested.get(t["id"])
        t["eval"] = evaluate_query(t, t["hits"])

    with open(RESULTS / f"eval_{split}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "id", "type", "filter_applied", "gold_page", "alt_gold_page", "hit1", "hit3",
                    "first_hit_rank", "top_pages", "gold_page_in_top3_without_full_evidence",
                    "evidence_split_across_chunks", "filter_respected", "top_chunk_ids"])
        for t in traces:
            e = t["eval"]
            w.writerow([t["strategy"], t["id"], t["type"], json.dumps(t["filter"]) if t["filter"] else "",
                        t["gold_page"], t["alt_gold_page"] or "", int(e["hit1"]), int(e["hit3"]),
                        e["first_hit_rank"] or "", " ".join(map(str, e["top_pages"])),
                        int(e["gold_page_in_top3_without_full_evidence"]),
                        int(e["evidence_split_across_chunks"]),
                        "" if e["filter_respected"] is None else int(e["filter_respected"]),
                        " ".join(e["top_chunk_ids"])])
    summary = summarize(traces)
    (RESULTS / f"summary_{split}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                                   encoding="utf-8")
    print(f"Tập {split}:")
    for s, v in summary.items():
        flt = "N/A" if v["filter_respected"] is None else f"{v['filter_respected']}/{v['filter_questions']}"
        print(f"  {s}: Hit@1 {v['hit1']}/{v['N']} | Evidence Hit@3 {v['hit3']}/{v['N']} | "
              f"top-3 đúng phạm vi chương yêu cầu {flt} | Hit@3 theo loại {v['by_type']}")
    print(f"Chi tiết từng câu: results/eval_{split}.csv; tổng hợp: results/summary_{split}.json")


if __name__ == "__main__":
    main()
