# Benchmark — Principles of Management (OpenStax), Ch.1–2

File `questions.csv`: 20 câu hỏi, 15 dev / 5 test. Bản xem và sửa ở Claude Sheet "Day06 Benchmark".

## Cột
- `id`, `split` (dev/test), `type` (direct / paraphrase / condition / filter)
- `filter_chapter`: chỉ có ở câu loại `filter`; giá trị lọc theo metadata `chapter`, coi như ngữ cảnh người dùng cung cấp **trước khi truy xuất** (câu hỏi nêu rõ chương). Câu không có giá trị này thì cấu hình C chạy không lọc.
- `gold_source_id`, `gold_page`: số trang PDF của **sách gốc** (21–63), không phải số in trên trang.
- `evidence_quote`: trích nguyên văn từ trang `gold_page`.
- `alt_gold_page`, `alt_evidence_quote`: bằng chứng hợp lệ thứ hai (thường là mục Key Terms trang 59); top-k chứa một trong hai đều tính là hit.

## Phân bố
- Chương 1: 8 câu (trang 21–33); chương 2: 12 câu (trang 35–63).
- Loại: direct 6, paraphrase 5, condition 5, filter 4 (2 lọc chương 1, 2 lọc chương 2).

## Quy tắc chia dev/test (chốt trước khi chạy bất kỳ thử nghiệm nào)
Test = mọi câu có số thứ tự chia hết cho 4: q04, q08, q12, q16, q20. Còn lại là dev.
Test có 2 câu filter (q08, q20), có cả hai chương và ba loại câu.

Nguy cơ rò rỉ: q08, q12, q16 (test) nằm cùng trang với một câu dev (q02, q11, q18) nhưng hỏi đoạn khác; ghi ở cột `notes`.

## Cách soạn và kiểm chứng
- Câu hỏi soạn với hỗ trợ của AI (Claude), từ text trích bằng pypdf của file `starter/data/pom-ch01-02.pdf`.
- Mọi `evidence_quote` và `alt_evidence_quote` được kiểm tự động: sau khi gộp khoảng trắng, đoạn trích phải nằm nguyên văn trong text của đúng trang ghi ở `gold_page` / `alt_gold_page`. Cả 20 câu đều đạt.
- Giá trị `filter_chapter` được kiểm khớp với chương của `gold_page` (chương 1 = trang 21–34, chương 2 = trang 35–63).
- Học viên đọc lại từng câu, đối chiếu với PDF trước khi chạy thử nghiệm.

## Tiêu chí chọn chiến lược (chốt trước khi chạy, trước khi xem kết quả test)
Chọn trên tập **dev**, theo thứ tự ưu tiên:
1. Evidence Hit@3 cao nhất.
2. Nếu bằng nhau: Hit@1 cao hơn.
3. Nếu vẫn bằng nhau: điểm chunk coherence trung bình cao hơn.
4. Nếu vẫn bằng nhau: ít chunk hơn và thời gian ingest ngắn hơn.

Sau khi chọn, chạy tập **test một lần** cho cả ba cấu hình và báo cáo nguyên kết quả; không chỉnh pipeline theo kết quả test.
