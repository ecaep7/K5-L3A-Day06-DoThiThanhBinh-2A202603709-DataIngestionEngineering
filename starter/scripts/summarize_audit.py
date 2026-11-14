"""Tổng hợp nhãn chấm thủ công trong results/audit/ thành results/audit_summary.json.

    python scripts/summarize_audit.py

Chỉ đếm và tính trung bình nhãn người chấm đã điền; không tự sửa hay suy ra nhãn.
Grounding được đặt cạnh Evidence Hit@3 (results/eval_test.csv) để thấy chỗ hai thước đo lệch nhau.
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[1] / "results"
AUDIT = RESULTS / "audit"


def read(name: str) -> list[dict]:
    with open(AUDIT / name, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def score_stats(rows: list[dict], column: str) -> dict:
    scores = [int(r[column]) for r in rows]
    blank = [r for r in rows if r[column].strip() == ""]
    if blank:
        raise SystemExit(f"Còn {len(blank)} dòng chưa chấm ở cột {column}")
    return {"n": len(scores), "mean": round(sum(scores) / len(scores), 2),
            "count_0": scores.count(0), "count_1": scores.count(1), "count_2": scores.count(2)}


def main() -> None:
    summary: dict = {"grader": "Đỗ Thị Thanh Bình (tác giả)", "scale": "0/1/2 theo GUIDE.md"}

    coherence = read("coherence_audit.csv")
    by_strategy = defaultdict(list)
    for r in coherence:
        by_strategy[r["strategy"]].append(r)
    summary["coherence"] = {s: score_stats(rows, "score_0_1_2") for s, rows in sorted(by_strategy.items())}

    metadata = read("metadata_audit.csv")
    meta = {}
    for s in sorted({r["strategy"] for r in metadata}):
        rows = [r for r in metadata if r["strategy"] == s]
        meta[s] = {"chunks": len(rows),
                   "all_three_ok": sum(r["source_ok"] == r["page_ok"] == r["chapter_ok"] == "1" for r in rows)}
    meta["checked_against_pdf_by_hand"] = sum("đối chiếu" in r["note"] for r in metadata)
    meta["relied_on_auto_check"] = sum("auto" in r["note"] for r in metadata)
    summary["metadata"] = meta

    grounding = read("grounding_audit.csv")
    with open(RESULTS / "eval_test.csv", encoding="utf-8") as f:
        hit3 = {(r["strategy"], r["id"]): int(r["hit3"]) for r in csv.DictReader(f)}
    g = {}
    for s in sorted({r["strategy"] for r in grounding}):
        rows = [r for r in grounding if r["strategy"] == s]
        g[s] = score_stats(rows, "grounding_0_1_2")
    g["grounding_vs_hit3"] = dict(Counter(
        f"grounding={r['grounding_0_1_2']}, hit3={hit3[(r['strategy'], r['id'])]}" for r in grounding))
    g["disagreements"] = [
        {"strategy": r["strategy"], "id": r["id"], "grounding": int(r["grounding_0_1_2"]),
         "hit3": hit3[(r["strategy"], r["id"])], "reason": r["reason"]}
        for r in grounding
        if (int(r["grounding_0_1_2"]) == 2) != bool(hit3[(r["strategy"], r["id"])])]
    summary["grounding"] = g

    (RESULTS / "audit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Coherence (10 vị trí):")
    for s, v in summary["coherence"].items():
        print(f"  {s}: trung bình {v['mean']} | 0:{v['count_0']} 1:{v['count_1']} 2:{v['count_2']}")
    print(f"Metadata: " + ", ".join(f"{s} {v['all_three_ok']}/{v['chunks']}" for s, v in meta.items()
                                     if isinstance(v, dict))
          + f" | đối chiếu PDF bằng tay {meta['checked_against_pdf_by_hand']}/{len(metadata)}")
    print("Grounding (5 câu test):")
    for s in ("A", "B", "C"):
        v = g[s]
        print(f"  {s}: trung bình {v['mean']} | 0:{v['count_0']} 1:{v['count_1']} 2:{v['count_2']}")
    print("Chỗ grounding và Hit@3 lệch nhau:")
    for d in g["disagreements"]:
        print(f"  {d['strategy']} {d['id']}: grounding {d['grounding']}, Hit@3 {d['hit3']}")
    print("Đã lưu results/audit_summary.json")


if __name__ == "__main__":
    main()
