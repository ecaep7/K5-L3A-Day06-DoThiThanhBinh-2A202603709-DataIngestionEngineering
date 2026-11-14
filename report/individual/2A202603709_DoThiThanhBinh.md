# Báo cáo cá nhân — Day 6

**Đỗ Thị Thanh Bình · 2A202603709 · L3A**

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:**
  - **Nguồn:** sách *Principles of Management* của OpenStax (©2026 Rice University), giấy phép CC BY-NC-SA 4.0, tải ngày 2026-11-13. Bài dùng chương 1 "Managing and Performing" và chương 2 "Managerial Decision-Making", trang PDF 21–63 của sách gốc, tổng cộng 43 trang vật lý.
  - **Cách tính trang:** đánh số theo trang PDF của sách gốc (bằng số in trên trang cộng 14). Một trang được tính khi còn ít nhất 200 ký tự sau chuẩn hóa và có nội dung. Theo quy tắc này, trang 30 bị loại vì chỉ có 2 câu Concept Check (183 ký tự), trang 34 bị loại vì trống. Kết quả là **41 trang nội dung, 130.301 ký tự**. Số ký tự từng trang nằm trong [pages.csv](../../starter/results/pages.csv), quy tắc đầy đủ nằm trong [manifest](../../data/manifest.csv).
  - **Vì sao không nộp PDF:** giấy phép yêu cầu mỗi trang chia sẻ lại phải giữ dòng "Access for free at openstax.org", nhưng trong bản PDF dòng này chỉ có ở trang chẵn. Vì vậy repo chỉ nộp script [extract_chapters.py](../../starter/scripts/extract_chapters.py) cùng hướng dẫn tải lại trong [README](../../README.md).

- **Chuẩn hóa, lỗi và giới hạn:**
  - **Đọc và làm sạch:** dùng pypdf đọc từng trang, chuẩn hóa Unicode NFKC, gộp khoảng trắng trong từng dòng, bỏ ba loại dòng lặp lại ở đầu/chân trang (dòng ghi nguồn OpenStax, tiêu đề chương trên trang chẵn, tiêu đề mục trên trang lẻ). Chỗ xuống dòng được giữ lại cho bước chia theo đoạn.
  - **Ghi lỗi:** mỗi trang được gán trạng thái `ok`, `empty` hoặc `extract_error`. Không trang nào gặp lỗi đọc. Hai trang rỗng được ghi lại chứ không bị bỏ qua im lặng.
  - **Kiểm tra:** sau khi làm sạch, cả 20 đoạn bằng chứng của benchmark vẫn tìm thấy nguyên văn đúng trang.
  - **Giới hạn:**
    - Chú thích ảnh ("Exhibit…") và nhãn khung bên lề vẫn lẫn vào text.
    - Số chú thích dính vào cuối câu, ví dụ "system.4".
    - Các trang câu hỏi ôn tập cuối chương vẫn được giữ trong corpus.
    - Chunk được chia trong phạm vi từng trang, nên đoạn văn vắt qua hai trang bị cắt đôi. Ví dụ chunk `p28-p00` chỉ còn nửa câu nối tiếp từ trang 27.

- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:**
  - **Model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` chạy local bằng sentence-transformers 6.3.0 (torch 2.15.0) trên CPU máy cá nhân Windows. Vector có **384 chiều** và được chuẩn hóa độ dài 1. Model chỉ đọc tối đa 128 token mỗi đoạn. Câu hỏi và chunk dùng chung model, không thêm prefix.
  - **Vector store:** PostgreSQL 16.16 với pgvector 0.8.7, chạy trong Docker. Metric là khoảng cách cosine (`<=>`), tìm chính xác, không dùng index xấp xỉ.
  - **Lệnh chạy:** `python -m src.run ingest`, `python -m src.run retrieve --split dev|test` và `python -m src.evaluation --split dev|test`. Danh sách đầy đủ nằm trong [README](../../README.md).
  - **Chi phí API:** 0 USD, vì không gọi API nào.

- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:**
  - **Metadata mỗi chunk:** `chunk_id` ổn định (dạng `pom-ch01-02-p23-p02`), `document_id`, `source`, `page`, `printed_page` và vị trí `char_start`/`char_end` trong text của trang.
  - **Trường lọc bổ sung:** `chapter`. Giá trị được tra theo mốc trang mở đầu chương lấy từ PDF gốc (chương 1 là trang 21–34, chương 2 là trang 35–63), không suy đoán từ nội dung.
  - **Lý do chọn:** hai chương có nhiều chủ đề giao nhau (nhà quản lý, quyết định, thời gian, các mối quan hệ). Khi người dùng nêu rõ đang hỏi về chương nào, lọc theo chương có thể loại bớt đoạn đúng chủ đề nhưng sai phạm vi.

## Cấu hình và benchmark

- **A / B / C (tham số cụ thể, khác biệt duy nhất B–C):**
  - **A — `fixed_size`:** cửa sổ 500 ký tự, chồng 50 ký tự, không quan tâm câu hay chữ. Tạo ra 307 chunk.
  - **B — `by_paragraph`:** nhận diện tiêu đề và đoạn văn theo độ dài dòng (dòng thân bài trong sách dài khoảng 98–115 ký tự). Tiêu đề được gắn vào đoạn ngay sau nó. Các đoạn được gom lại đến tối đa 500 ký tự, đoạn dài hơn thì cắt ở cuối câu. Tạo ra 356 chunk.
  - **Vì sao cả A và B đều dùng mức 500 ký tự:** model chỉ đọc 128 token, nên tăng kích thước cho B sẽ khiến B bị cắt bớt nhiều hơn. Khi giữ cùng mức 500, A và B chỉ khác nhau ở cách đặt ranh giới. Hai cách cùng chạy trên một chuỗi text đã chuẩn hóa của mỗi trang.
  - **C:** dùng chung index với B, cùng model, cùng corpus. Khác biệt duy nhất là câu SQL có thêm `AND chapter = <filter_chapter>` cho các câu hỏi có nêu chương. Câu không có filter thì C chạy y hệt B.
  - Chi tiết và giả thuyết: [experiment_log.csv](../../artifacts/experiment_log.csv).

- **≥20 câu: phân chia ≥15 dev / ≥5 test, câu metadata filter và cách kiểm chứng evidence:**
  - **Bộ câu hỏi:** 20 câu bằng tiếng Anh, cùng ngôn ngữ với sách. 8 câu từ chương 1, 12 câu từ chương 2. Phân loại: direct 6, paraphrase 5, condition 5, filter 4.
  - **Chia dev/test:** chia trước khi chạy, test là các câu có số thứ tự chia hết cho 4 (q04, q08, q12, q16, q20). Có 4 câu filter: q07 và q18 thuộc dev, q08 và q20 thuộc test, mỗi chương có 2 câu.
  - **Kiểm chứng bằng chứng:** mỗi câu có trang gold và đoạn bằng chứng trích nguyên văn. Có 7 câu kèm bằng chứng thay thế ở mục Key Terms trang 59. Một script kiểm tra mọi đoạn bằng chứng nằm nguyên văn đúng trang ghi trong benchmark, và kiểm tra `filter_chapter` khớp với chương của trang gold.
  - **Nguy cơ rò rỉ:** 3 câu test nằm cùng trang với một câu dev, dù hỏi đoạn khác. Câu hỏi được soạn với hỗ trợ của Claude, tác giả đọc lại và đối chiếu trước khi chạy. Xem [questions.csv](../../benchmark/questions.csv) và [benchmark/README.md](../../benchmark/README.md).

- **Tiêu chí chọn chiến lược đã chốt trước khi xem test:** chọn trên dev theo thứ tự ưu tiên:
  1. Evidence Hit@3 cao nhất.
  2. Nếu hòa thì xét Hit@1.
  3. Nếu vẫn hòa thì xét coherence trung bình.
  4. Nếu vẫn hòa thì cấu hình nào ít chunk và chạy nhanh hơn thắng.

  Trên dev, B và C hòa ở cả bốn bậc vì dùng chung index. C được chọn sau khi xem dev với một lý do **bổ sung, không có trong danh sách chốt trước**: C bảo đảm kết quả nằm đúng phạm vi chương khi người dùng nêu chương. Quyết định này được ghi lại trước khi chạy test.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 8/15 | 10/15 | 307 | nạp 8,94 s (tạo vector 8,58 s) | 0 USD |
| B | dev | 11/15 | 13/15 | 356 | nạp 12,08 s (tạo vector 11,64 s) | 0 USD |
| C | dev | 11/15 | 13/15 | 356 (chung với B) | dùng lại index B | 0 USD |
| A | test | 3/5 | 3/5 | 307 | như trên | 0 USD |
| B | test | 3/5 | 4/5 | 356 | như trên | 0 USD |
| C | test | **4/5** | **4/5** | 356 | như trên | 0 USD |

Chạy nạp lần hai: tạo vector mới 0, dòng trùng 0, A vẫn 307 dòng và B vẫn 356 dòng ([ingest_log.jsonl](../../starter/results/ingest_log.jsonl)). Số chunk dài hơn 128 token, tức bị model cắt bớt: A 8/307 (dài nhất 172 token, trung vị 109), B 6/356 (dài nhất 149, trung vị 86,5).

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 0,1 (n=10; 9 chunk điểm 0, 1 chunk điểm 1) | 15/15 | không lọc: top-3 đúng chương ở 3/4 câu filter (dev 2/2, test 1/2) | 1/0/4, trung bình 1,6 |
| B | 1,9 (n=10; 1 chunk điểm 1, 9 chunk điểm 2) | 15/15 | không lọc: 3/4 (dev 2/2, test 1/2) | 0/1/4, trung bình 1,8 |
| C | 1,9 (chung chunk với B) | 15/15 | **4/4** (dev 2/2, test 2/2) | 0/1/4, trung bình 1,8 |

**Đường dẫn trace, nhãn thủ công và cách chọn mẫu:**
- **Trace top-3:** [traces_dev.jsonl](../../starter/results/traces_dev.jsonl) và [traces_test.jsonl](../../starter/results/traces_test.jsonl). Kết quả chấm tự động: `eval_*.csv`, `summary_*.json`.
- **Nhãn thủ công:** nằm trong [audit/](../../starter/results/audit/), tổng hợp tại [audit_summary.json](../../starter/results/audit_summary.json). Người chấm là tác giả, dùng thang 0/1/2 theo GUIDE.
- **Coherence:** 10 vị trí cố định, mỗi vị trí là điểm giữa text của 10 trang nội dung đầu tiên. Mỗi vị trí chấm chunk A và chunk B chứa nó. C dùng chung chunk với B.
- **Metadata:** 45 chunk, gồm top-3 của 5 câu test cho cả 3 cấu hình. 10/45 dòng được đối chiếu tận mắt với PDF gốc, 35 dòng còn lại dựa vào kiểm tra tự động (text của chunk có trên đúng trang đó, và chương khớp với mốc trang).
- **Grounding:** 5 câu test × 3 cấu hình. Câu hỏi đặt ra khi chấm: chỉ đọc 3 chunk thì có trả lời được và chỉ ra trang không.

## Phân tích và kết luận

- **So sánh A–B và B–C; 2 ví dụ sai có ID câu và nguồn:**
  - **A–B:** đổi cách chia giúp Hit@3 trên dev tăng từ 10 lên 13/15 và Hit@1 tăng từ 8 lên 11/15. Coherence tăng từ 0,1 lên 1,9.
    - **Cơ chế:** ở 4 câu A trượt trên dev (q14, q17, q18, q19), A vẫn tìm đúng trang gold nhưng không chunk nào chứa trọn đoạn bằng chứng. Ví dụ q17 (trang 46): bằng chứng bị chia giữa `p46-f00` và `p46-f01`, cả hai đều lọt top-3 nhưng không chunk nào đủ. B sửa được q17, q18 và q19.
    - **Thước đo Hit@3 quá chặt:** ở câu A q20 trên test, chunk `p57-f01` chứa cả đoạn bằng chứng chỉ thiếu **dấu chấm cuối câu**. Người chấm cho grounding 2 nhưng máy chấm Hit@3 bằng 0, vì phép khớp chuỗi đòi nguyên văn. Như vậy Hit@3 có phần đánh giá thấp A. Dù vậy, coherence 0,1 cho thấy chunk của A thực sự khó đọc: 9 trên 10 vị trí bị cắt giữa chữ.
  - **B–C:** trên dev hai cấu hình giống hệt nhau, vì ở q07 và q18, B dù không lọc vẫn trả về đúng chương. Trên test, câu **q08** (gold trang 23, chương 1) cho thấy tác dụng của filter: B xếp hạng 1 là `p46-p03` (chương 2, nói về relationship conflict), vì trùng ý "relationship". C lọc `chapter = 1` nên loại được chunk đó, và chunk đúng `p23-p02` lên hạng 1. Nhờ vậy Hit@1 trên test tăng từ 3 lên 4/5, và tỷ lệ đúng phạm vi chương tăng từ 1/2 lên 2/2. Tuy nhiên kết luận này chỉ dựa trên 4 câu filter, trong đó 1 câu tạo ra khác biệt.
  - **Ví dụ sai 1 — q10 (dev, cả 3 cấu hình trượt, gold trang 37):** câu hỏi "vì sao chờ quá lâu cũng hại như quyết quá nhanh". Cả ba cấu hình trả về trang 40 (Reactive/Reflective Decision-Making, điểm cosine 0,647 và 0,615) và trang 60 (tóm tắt). Model bắt được các từ chủ đề "quick", "decision", nhưng không bắt được cấu trúc đánh đổi giữa nhanh và chậm của câu hỏi. Loại câu condition yếu nhất trên dev: A đúng 1/3, B đúng 2/3.
  - **Ví dụ sai 2 — q16 (test, cả 3 cấu hình trượt, gold trang 44):** câu hỏi diễn đạt lại "escalation of commitment" bằng cụm "keep backing a bad choice even as the results keep getting worse". Không cấu hình nào lấy được câu định nghĩa ở trang 44 hay mục Key Terms ở trang 59. B và C trả về hai chunk trang 54 nói chuyện khác, và ở hạng 3 là `p44-p03` mô tả đúng hành vi "stay the course" nhưng không có tên thuật ngữ. Tác giả chấm câu này grounding 1. Đây là giới hạn của model khi câu hỏi và sách dùng cách diễn đạt khác hẳn nhau.
  - **Lỗi chung khác — q14 (dev):** cả ba cấu hình đều về đúng trang 42, nhưng trang này có nhiều đoạn cùng nói về heuristics. Chunk chứa bằng chứng `p42-p00` thua hai đoạn khác cùng trang.

- **Chiến lược chọn, đánh đổi, điều kiện áp dụng:**
  - **Chọn C.** Lý do là chất lượng chunk của B và khả năng giữ đúng phạm vi khi người dùng nêu chương. Với câu hỏi không có phạm vi, C hoạt động y như B.
  - **Đánh đổi so với A:**
    - B tạo nhiều chunk hơn (356 so với 307) và tạo vector chậm hơn khoảng 36% (11,6 s so với 8,6 s).
    - Tổng số ký tự lưu trữ ít hơn (129.971 so với 143.500) vì B không có phần chồng lấn.
    - Cách nhận diện đoạn dựa vào độ dài dòng của bố cục OpenStax, nên khó dùng lại cho tài liệu khác. Cách này cũng sinh chunk rác như `p47-p05` chỉ có chữ "CONCEPT CHECK" (13 ký tự).
  - **Điều kiện áp dụng filter:** chỉ nên lọc khi phạm vi chương được cung cấp đáng tin cậy, ví dụ người dùng đang đọc chương nào. Lọc sai chương sẽ loại mất bằng chứng đúng, nên khi không chắc thì không lọc.

- **Hạn chế của dữ liệu, nhãn, test nhỏ, đo thời gian/chi phí:**
  - **Dữ liệu:** chỉ một cuốn sách, hai chương, một ngôn ngữ, một bố cục PDF.
  - **Benchmark:** do chính người dựng pipeline soạn (có AI hỗ trợ), nên có thể nghiêng về cách diễn đạt của sách.
  - **Tập test:** chỉ có 5 câu, nên mỗi câu chiếm 20%. Chỉ có 4 câu filter, nên kết luận B–C còn yếu.
  - **Nhãn thủ công:** chỉ một người chấm. Cả 10 vị trí coherence đều thuộc chương 1. Metadata chỉ đối chiếu tận mắt 10/45 dòng.
  - **Thước đo Hit:** dùng khớp chuỗi tuyệt đối, nên lệch một dấu câu cũng bị tính trượt.
  - **Thời gian:** chỉ đo thời gian nạp, một lần, trên một máy. Không đo độ trễ khi truy vấn.
  - **Chi phí:** 0 USD chưa tính phần cứng.
  - **Model:** chỉ đọc 128 token, nên 2–3% chunk bị cắt bớt khi tạo vector.

- **Nếu làm lại hoặc mở rộng, cải tiến gì?**
  - **Chia chunk:** cho chunk nối qua ranh giới trang, bỏ chú thích ảnh và nhãn khung bên lề trước khi chia.
  - **Model:** thử model đọc được 512 token để dùng chunk lớn hơn.
  - **Tìm kiếm kết hợp:** kết hợp tìm theo từ khóa (BM25) với tìm theo vector để bắt được thuật ngữ như ở q16.
  - **Metadata:** thêm trường `section` lấy từ tiêu đề đánh số (1.1, 2.4…).
  - **Đánh giá:**
    - Mở rộng test lên ít nhất 20 câu, với nhiều câu filter hơn.
    - Thêm người chấm thứ hai.
    - So khớp bằng chứng cho phép sai khác dấu câu.
    - Đo độ trễ truy vấn.
  - **Thí nghiệm phụ:** thử hỏi bằng tiếng Việt trên cùng corpus để đo khả năng tìm kiếm khác ngôn ngữ của model đa ngữ.

**Sử dụng AI:** Claude (Anthropic) hỗ trợ giải thích, viết code pipeline, soạn bộ câu hỏi và soạn bản nháp báo cáo này. Tác giả đã chạy toàn bộ pipeline trên máy cá nhân, đối chiếu kết quả, tự chấm toàn bộ nhãn thủ công và đọc duyệt báo cáo.
