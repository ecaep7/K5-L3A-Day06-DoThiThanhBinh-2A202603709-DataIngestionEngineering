"""Đọc PDF và chuẩn hóa text, giữ liên kết từng trang về nguồn."""
import csv
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage

FIRST_PAGE = 21
# Trang mở đầu mỗi chương, lấy từ trang tiêu đề chương trong PDF gốc.
CHAPTER_RANGES = {1: (21, 34), 2: (35, 63)}
# Trang còn ít hơn số ký tự này sau khi làm sạch thì coi là trang rỗng.
MIN_CONTENT_CHARS = 200

# Dòng đầu/chân trang lặp lại, không phải nội dung sách.
BOILERPLATE = [
    re.compile(r"^Access for free at openstax\.org$"),  # dòng ghi nguồn (trang chẵn)
    re.compile(r"^\d+ \d+ • .+$"),                      # trang chẵn: "8 1 • Managing and Performing"
    re.compile(r"^[\d.]+ • .+ \d+$"),                    # trang lẻ: "1.2 • The Roles Managers Play 9"
]


def chapter_of(page: int) -> int | None:
    for chapter, (start, end) in CHAPTER_RANGES.items():
        if start <= page <= end:
            return chapter
    return None


def normalize_text(text: str) -> str:
    """Chuẩn hóa Unicode, gộp khoảng trắng trong từng dòng, bỏ dòng đầu/chân trang.

    Giữ nguyên ngắt dòng vì bước chia chunk theo đoạn cần đến chúng.
    """
    text = unicodedata.normalize("NFKC", text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line or any(p.match(line) for p in BOILERPLATE):
            continue
        lines.append(line)
    return "\n".join(lines)


def load_pdf(path: Path, document_id: str, source: str,
             first_page: int = FIRST_PAGE) -> list[DocumentPage]:
    """Đọc từng trang vật lý, gắn số trang theo sách gốc, chương và trạng thái."""
    reader = PdfReader(path)
    pages = []
    for index, pdf_page in enumerate(reader.pages):
        page = index + first_page
        status = "ok"
        try:
            text = normalize_text(pdf_page.extract_text() or "")
        except Exception as error:  # ghi lỗi chứ không bỏ qua im lặng
            text, status = "", f"extract_error: {error}"
        if status == "ok" and len(text) < MIN_CONTENT_CHARS:
            status = "empty"
        pages.append(DocumentPage(
            document_id=document_id,
            source=source,
            page=page,
            text=text,
            metadata={"chapter": chapter_of(page), "printed_page": page - 14, "status": status},
        ))
    return pages


def write_page_report(pages: list[DocumentPage], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["page", "printed_page", "chapter", "chars", "status", "first_line"])
        for p in pages:
            first_line = p.text.split("\n", 1)[0][:80]
            writer.writerow([p.page, p.metadata["printed_page"], p.metadata["chapter"],
                             len(p.text), p.metadata["status"], first_line])


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    pdf = root / "data" / "pom-ch01-02.pdf"
    pages = load_pdf(pdf, document_id="pom-ch01-02", source="starter/data/pom-ch01-02.pdf")
    write_page_report(pages, root / "results" / "pages.csv")
    for p in pages:
        if p.metadata["status"] != "ok":
            print(f"Trang {p.page}: {p.metadata['status']} ({len(p.text)} ký tự)")
    ok = [p for p in pages if p.metadata["status"] == "ok"]
    print(f"Đã đọc {len(pages)} trang; {len(ok)} trang có nội dung; "
          f"tổng {sum(len(p.text) for p in ok)} ký tự. Báo cáo: results/pages.csv")
