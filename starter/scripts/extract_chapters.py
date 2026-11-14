"""Cắt chương 1–2 (trang PDF 21–63) từ sách gốc thành file nhỏ để nộp kèm repo."""
from pathlib import Path
from pypdf import PdfReader, PdfWriter

DATA = Path(__file__).resolve().parents[1] / "data"
SOURCE = DATA / "principles-of-management.pdf"
OUTPUT = DATA / "pom-ch01-02.pdf"
FIRST_PAGE, LAST_PAGE = 21, 63  # số trang theo trình xem PDF; trang 64 trống nên bỏ

reader = PdfReader(SOURCE)
writer = PdfWriter()
for number in range(FIRST_PAGE, LAST_PAGE + 1):
    writer.add_page(reader.pages[number - 1])  # pypdf đếm trang từ 0, nên phải trừ 1
writer.write(OUTPUT)
print(f"Đã ghi {LAST_PAGE - FIRST_PAGE + 1} trang vào {OUTPUT.name}")