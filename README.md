# Chatbot RAG Giáo dục

**Trường Đại học Sư phạm Thành phố Hồ Chí Minh**
**Khoa Công nghệ thông tin**

Học viên thực hiện:

1. Tăng Ngọc Phụng - KHMT836027
2. Hoàng Châu Ngọc Phương - KHMT836028
3. Lê Thị Mai Len - KHMT836015

Giảng viên hướng dẫn: TS. Nguyễn Minh Hải

**Bản chạy trực tuyến:** <https://chatbot.148-113-237-209.sslip.io/>

---

Ứng dụng hỏi đáp tài liệu giáo dục chạy cục bộ bằng FastAPI, Ollama, FAISS và giao diện web tiếng Việt. Hệ thống hỗ trợ:

- Tìm kiếm lai FAISS + BM25, trích dẫn nguồn kèm vị trí trong tài liệu, chặn câu hỏi ngoài phạm vi kho
- Cập nhật chỉ mục tăng dần (chỉ xử lý tệp thêm, sửa hoặc xóa)
- Đọc PDF, Word (`.docx`, `.doc`), PowerPoint (`.pptx`), Excel/CSV, TXT, Markdown, HTML, EPUB
- OCR PDF scan và ảnh bằng Tesseract
- Phiên âm video/âm thanh offline bằng faster-whisper, đọc phụ đề `.srt`/`.vtt`
- Tệp đính kèm trong cuộc trò chuyện, lịch sử chat, cache ngữ nghĩa
- Đồng bộ thư mục Google Drive
- Chế độ chạy công khai có mật khẩu qua đường hầm Cloudflare, bộ script triển khai lên VPS

## Sơ đồ hệ thống

### Pipeline tổng thể

Hai luồng tách biệt về thời gian: luồng ngoại tuyến biến tài liệu thô thành chỉ mục, luồng trực tuyến chỉ đọc chỉ mục đó để trả lời.

![Pipeline toàn hệ thống](so_do_pipeline_tong_the.svg)

### Kiến trúc mô hình

`bge-m3` nhúng cả tài liệu lẫn câu hỏi; truy hồi lai FAISS + BM25 hợp nhất bằng RRF rồi xếp hạng lại; `qwen3.5:4b` sinh câu trả lời chỉ từ 4 đoạn bằng chứng và được hậu kiểm trích dẫn, số liệu.

![Kiến trúc mô hình RAG](so_do_kien_truc_mo_hinh.svg)

### Các tầng xử lý

Năm tầng từ người dùng, giao diện, điều phối, xử lý chuyên biệt đến lõi AI và nền tảng tri thức.

![Kiến trúc hệ thống tổng thể](so_do_kien_truc_tang.svg)

### Nạp và cập nhật kho tri thức

![Nạp và cập nhật kho tri thức](so_do_nap_kho_tri_thuc.svg)

### Hỏi đáp trực tuyến

![Hỏi đáp trực tuyến](so_do_hoi_dap_truc_tuyen.svg)

## Yêu cầu

- Windows 10/11 và Python 3.11
- [Ollama](https://ollama.com/) đang chạy
- Model embedding `bge-m3`
- Một model hội thoại, mặc định `qwen3.5:4b` (đổi bằng biến môi trường `RAG_LLM_MODEL` hoặc chọn trên giao diện)
- Tesseract OCR (kèm dữ liệu tiếng Việt `vie`) nếu cần đọc PDF scan hoặc ảnh
- Microsoft Word hoặc LibreOffice nếu cần đọc tệp `.doc` đời cũ

## Cài đặt

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull bge-m3
ollama pull qwen3.5:4b
```

Đặt tài liệu vào thư mục (có thể đổi bằng biến `RAG_DATA_PATH`):

```text
ollama-rag-desktop/data_giao_duc
```

Tạo chỉ mục lần đầu:

```powershell
.\.venv\Scripts\python.exe main.py
```

Khởi động giao diện:

```powershell
.\start_ui.bat
```

`start_ui.bat` cố định cổng `8010` và tự mở trình duyệt tại `http://127.0.0.1:8010`. Nếu chạy trực tiếp `run_ui.py` mà không đặt `RAG_PORT`, ứng dụng chọn cổng trống đầu tiên từ `8000` đến `8020`.

## Cập nhật tài liệu

Sau khi thêm, sửa hoặc xóa tài liệu trong kho, có thể cập nhật chỉ mục từ giao diện hoặc chạy:

```powershell
.\.venv\Scripts\python.exe capnhat_tailieu_moi.py
```

Kết quả OCR, phiên âm và sổ ghi chép giúp lần chạy tiếp theo tiếp tục mà không xử lý lại toàn bộ kho.

## Đo chất lượng hệ thống

Bộ câu hỏi chuẩn nằm ở `bo_cau_hoi_benchmark.json` (127 câu, trong đó 97 câu có nhãn nguồn đúng và 30 câu cố tình ngoài phạm vi kho).

```powershell
.\.venv\Scripts\python.exe benchmark_chatbot.py --ir
```

Chế độ `--ir` đo chất lượng **xếp hạng** của khối truy hồi bằng bộ chỉ số IR/QA kinh điển — MRR, Hit@K, Recall@K, nDCG@K, MAP (công thức nằm trong `chi_so_ir.py`). Không gọi LLM nên chạy vài phút, kết quả ghi ra `ket_qua_chi_so_ir.json` và bảng markdown `bang_chi_so_ir.md`.

Hai chế độ còn lại: `--nhanh` đo truy hồi kèm cổng chặn lạc đề, `--bo` gọi đủ LLM để đo thêm trích dẫn và số liệu (chậm, khoảng 150 giây/câu trên CPU).

Kiểm thử tự động nằm trong thư mục `tests`:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest
```

## Cấu hình Google Drive

Sao chép `khoa_api.mau.bat` thành `khoa_api.bat`, sau đó điền khóa API của riêng bạn. `start_ui.bat` tự nạp tệp này nếu có. `khoa_api.bat` đã được loại khỏi Git để tránh công khai khóa.

## Chạy công khai

Sao chép `mat_khau.mau.bat` thành `mat_khau.bat`, đặt tài khoản và mật khẩu, rồi chạy:

```powershell
.\chay_cong_khai.bat
```

Ứng dụng bật lớp bảo vệ truy cập (từ chối chạy nếu thiếu mật khẩu) và mở đường hầm Cloudflare, in ra địa chỉ dạng `https://....trycloudflare.com`. Cần cài sẵn `cloudflared`. Hướng dẫn triển khai lên VPS nằm trong [trien_khai_vps/HUONG_DAN.md](trien_khai_vps/HUONG_DAN.md).

## Dữ liệu không nằm trong repository

Repository chỉ chứa mã nguồn. Tài liệu gốc, chỉ mục FAISS, cache OCR, bản phiên âm, lịch sử chat, khóa API, mật khẩu và cấu hình riêng của máy không được commit vì có thể chứa dữ liệu riêng tư hoặc tệp dung lượng lớn.

Xem thêm [hướng dẫn chạy giao diện](HUONG_DAN_CHAY_GIAO_DIEN.md) (bảng biến môi trường, API) và [tài liệu bàn giao](HUONG_DAN_BAN_GIAO_UI.md).
