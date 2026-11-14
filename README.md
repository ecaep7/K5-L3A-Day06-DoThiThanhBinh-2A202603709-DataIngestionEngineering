# Day 06 · Data Ingestion Engineering — Đỗ Thị Thanh Bình (2A202603709)

Bài lab cá nhân: biến 2 chương sách *Principles of Management* (OpenStax) thành kho truy xuất theo nghĩa, rồi so sánh 3 cấu hình chia chunk và lọc metadata trên bộ 20 câu hỏi có bằng chứng.

- **Corpus:** chương 1–2, trang PDF 21–63 của sách gốc; 41 trang nội dung, 130.301 ký tự sau chuẩn hóa ([manifest](data/manifest.csv)).
- **Embedding:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, chạy local, 384 chiều, chi phí 0.
- **Vector store:** PostgreSQL 16 + pgvector 0.8.7 (Docker), khoảng cách cosine, tìm chính xác.
- **Ba cấu hình:** A cắt cố định 500 ký tự / chồng 50 · B theo đoạn văn, tối đa 500 ký tự · C = B + lọc `chapter`. Chi tiết và giả thuyết: [artifacts/experiment_log.csv](artifacts/experiment_log.csv).
- **Benchmark:** 15 dev / 5 test, chia và chốt tiêu chí chọn trước khi chạy ([benchmark/](benchmark/README.md)).

| Cấu hình | Dev Hit@1 | Dev Hit@3 | Test Hit@1 | Test Hit@3 |
|---|---|---|---|---|
| A | 8/15 | 10/15 | 3/5 | 3/5 |
| B | 11/15 | 13/15 | 3/5 | 4/5 |
| **C (chọn)** | 11/15 | 13/15 | 4/5 | 4/5 |

Phân tích đầy đủ: [report/individual/2A202603709_DoThiThanhBinh.md](report/individual/2A202603709_DoThiThanhBinh.md).

## Cấu trúc repo

```text
data/manifest.csv                 nguồn, giấy phép, trang, quy tắc tính trang, số ký tự
benchmark/questions.csv           20 câu hỏi, split, trang gold, đoạn bằng chứng nguyên văn
benchmark/README.md               quy tắc chia dev/test, tiêu chí chọn, lựa chọn C
artifacts/experiment_log.csv      cấu hình A/B/C, giả thuyết, Hit@1/Hit@3 dev
starter/src/                      code pipeline
  ingestion.py                    đọc PDF, chuẩn hóa, bỏ dòng đầu/chân trang, gắn trang/chương
  chunking.py                     A: fixed_size · B: by_paragraph
  embeddings.py                   model Sentence Transformers (local)
  store.py                        pgvector: schema, upsert theo ID ổn định, tìm kiếm + lọc
  run.py                          ingest / retrieve
  evaluation.py                   Hit@1, Evidence Hit@3, tuân thủ phạm vi chương
starter/scripts/
  extract_chapters.py             cắt chương 1–2 từ PDF gốc
  make_audit_sheets.py            tạo mẫu chấm thủ công
  summarize_audit.py              tổng hợp nhãn chấm thủ công
starter/results/                  kết quả (đề bài để ở results/, repo này để ở starter/results/)
  pages.csv                       số ký tự và trạng thái từng trang
  chunks_A.csv, chunks_B.csv      toàn bộ chunk của hai cách chia
  ingest_stats.json, ingest_log.jsonl   thống kê và lịch sử các lần nạp
  traces_dev.jsonl, traces_test.jsonl   trace top-3 của từng câu, từng cấu hình
  eval_*.csv, summary_*.json      chấm tự động
  audit/*.csv, audit_summary.json nhãn chấm thủ công (coherence, metadata, grounding)
report/individual/                báo cáo cá nhân
```

## Cài đặt

Cần Docker Desktop, Python 3.11–3.14. Các lệnh dưới chạy trong thư mục `starter/` (Windows PowerShell; macOS/Linux dùng `source .venv/bin/activate` và `cp`).

```powershell
cd starter
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py          # mong đợi: Setup OK
```

Lần chạy đầu sẽ tải model MiniLM (~470 MB) từ Hugging Face.

## Lấy lại dữ liệu

File PDF **không có trong repo** (xem mục Giấy phép). Để tạo lại:

1. Tải PDF tại <https://openstax.org/details/books/principles-management> (bản ©2026 Rice University).
2. Lưu thành `starter/data/principles-of-management.pdf`.
3. Chạy `python scripts/extract_chapters.py` → tạo `starter/data/pom-ch01-02.pdf` (43 trang, trang PDF 21–63 của sách gốc).

Mọi số trang trong manifest, benchmark và trace là **số trang PDF của sách gốc** (= số in trên trang + 14).

## Chạy pipeline

```powershell
python -m src.ingestion                    # kiểm tra đọc PDF -> results/pages.csv
python -m src.chunking                     # xem hai cách chia -> results/chunks_A.csv, chunks_B.csv
python -m src.run ingest                   # tạo vector, lưu pgvector (chạy lần 2 để kiểm tra không nhân đôi)
python -m src.run retrieve --split dev
python -m src.evaluation --split dev
python -m src.run retrieve --split test    # chỉ chạy sau khi đã chọn cấu hình trên dev
python -m src.evaluation --split test
python scripts/make_audit_sheets.py        # tạo mẫu chấm thủ công (không ghi đè nhãn đã có)
python scripts/summarize_audit.py
```

Kiểm tra trực tiếp trong database:

```powershell
docker exec day6_student_starter-postgres-1 psql -U day6 -d day6_lab -c "SELECT strategy, count(*), count(DISTINCT chunk_id) FROM chunks GROUP BY strategy;"
```

## Giấy phép và ghi nguồn

Nội dung sách: *Principles of Management*, OpenStax, ©2026 Rice University, giấy phép [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Access for free at openstax.org.

- File PDF không được commit vì khi chia sẻ lại một phần, mỗi trang phải giữ dòng ghi nguồn, mà trong bản PDF dòng này chỉ có ở trang chẵn.
- Các đoạn trích từ sách nằm trong `benchmark/questions.csv`, `starter/results/chunks_*.csv`, `traces_*.jsonl` và `audit/*.csv` được dùng cho mục đích học tập phi thương mại, ghi nguồn như trên và chia sẻ theo cùng giấy phép CC BY-NC-SA 4.0.

## Sử dụng AI

Claude (Anthropic) hỗ trợ giải thích, viết code pipeline và soạn bộ câu hỏi. Tác giả đã chạy toàn bộ pipeline trên máy cá nhân, kiểm tra kết quả, đọc lại bộ câu hỏi (mọi đoạn bằng chứng được kiểm tự động là nằm nguyên văn đúng trang) và **tự chấm toàn bộ nhãn thủ công** trong `starter/results/audit/`.

## Hướng dẫn gốc của lab

[GUIDE.md](GUIDE.md) · [BENCHMARK.md](BENCHMARK.md) · [RUBRIC.md](RUBRIC.md) · [RULES.md](RULES.md) · [SUBMISSION.md](SUBMISSION.md) · [CHECKPOINTS.md](CHECKPOINTS.md)
