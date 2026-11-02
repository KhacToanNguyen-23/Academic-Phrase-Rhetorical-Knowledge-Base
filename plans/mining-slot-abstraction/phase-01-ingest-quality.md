# Phase 01 — Chất lượng ingest

Trạng thái: chờ duyệt. Phải xong trước khi lấy mẫu gold (phase 02).

## Việc

1. **Tách câu** (`modules/corpus/sentence_splitter.py`): không cắt sau chữ viết tắt (`e.g.`, `i.e.`, `et al.`, `Fig.`, `Eq.`, `Tab.`, `Dr.`, `vs.`, `cf.`, `approx.`), số thập phân, chữ cái viết tắt tên (`J. Smith`). Danh sách chữ viết tắt trong `policies/lexicon/abbreviations.yaml`. Giữ đúng `char_start/char_end`.
2. **Nhận diện section** (`modules/corpus/section_detector.py`): ánh xạ tiêu đề → mã section qua `policies/section_headings.yaml` (bỏ số đầu dòng như `1.`, `2.3`, `IV.`; so khớp không phân biệt hoa thường; ví dụ "Materials and Methods", "Experimental Setup" → `METHODS`). Không khớp thì `None`. Mã section lấy theo bảng `sections` đã seed; thêm mã còn thiếu vào seed.
3. **Lọc câu nhiễu** (`modules/mining/stages/sentence_filter.py`, mục 3.1b): loại dòng bảng (`|`), chú thích hình/bảng (`Fig. 3`, `Table 2:` đầu câu), công thức (tỉ lệ ký hiệu toán cao), câu chủ yếu là số, phần References/Acknowledgements (theo section). Ngưỡng nằm trong `policies/mining_filter.yaml`, đánh dấu `TODO(owner)`.
4. **Ingest lại** 4 bài đã import (lệnh CLI `reingest --source slr`), sau đó import thêm bài mới từ SLR.

## Kiểm tra

- Unit test với câu tự viết: mỗi chữ viết tắt, số thập phân, tiêu đề có đánh số, dòng bảng, caption.
- Chạy thử trên 4 bài thật: in **số liệu** (số câu trước/sau, phân bố section, số câu bị lọc theo lý do), không in câu.
