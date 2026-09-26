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

- Tìm kiếm lai FAISS + BM25, chặn câu hỏi ngoài phạm vi kho
- Trích dẫn nguồn chỉ đúng dòng trên trang gốc: tô sáng đoạn được trích ngay trên ảnh trang PDF, kể cả bản scan
- Cập nhật chỉ mục tăng dần (chỉ xử lý tệp thêm, sửa hoặc xóa)
- Đọc PDF, Word (`.docx`, `.doc`), PowerPoint (`.pptx`), Excel/CSV, TXT, Markdown, HTML, EPUB
- OCR PDF scan và ảnh bằng Tesseract
- Phiên âm video/âm thanh offline bằng faster-whisper, đọc phụ đề `.srt`/`.vtt`
- Tệp đính kèm trong cuộc trò chuyện, lịch sử chat, cache ngữ nghĩa
- Tài khoản người dùng và quyền quản trị; tệp người dùng tải lên là tài liệu riêng, chỉ vào kho chung khi chủ tệp đề xuất và quản trị viên duyệt
- Sổ tay bên cạnh cuộc trò chuyện: ghi chú, bảng vẽ, trình đọc PDF, ảnh, Word, Excel, PowerPoint, HTML với công cụ **Khoanh để hỏi**, đánh dấu và tải tài liệu kèm nét đánh dấu
- Dịch hơn 130 ngôn ngữ ngay trong giao diện
- Nói thay vì gõ: nhận giọng nói bằng faster-whisper trên máy chủ, tự nhận ra ngôn ngữ
- Mỗi người tự chọn mô hình trả lời cho câu hỏi của mình
- Đồng bộ thư mục Google Drive
- Chế độ chạy công khai có mật khẩu qua đường hầm Cloudflare, bộ script triển khai lên VPS

## Sơ đồ hệ thống

### Các chức năng

![Các chức năng của Chatbot RAG Giáo dục](so_do_chuc_nang.svg)

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

### Tác tử AI

Mô hình ngôn ngữ chạy cục bộ qua Ollama và chỉ soạn câu trả lời từ các đoạn trích được cấp.

![Tác tử AI trong Chatbot RAG Giáo dục](so_do_tac_tu_ai.svg)

## Tính năng trên giao diện

### Nguồn trích dẫn chỉ đúng chỗ

Mỗi câu trả lời kèm danh sách bằng chứng đã dùng. Với nguồn PDF hoặc ảnh trong kho, giao diện không chỉ ghi số trang mà chỉ đúng các dòng được trích:

- Dưới câu trả lời có ảnh thu nhỏ của trang gốc: **tô vàng** cả đoạn đã đưa cho mô hình, **viền đỏ** câu sát câu hỏi nhất, ảnh tự cuộn tới đoạn đó. Hai bằng chứng cùng một trang thì gộp vào một ảnh (`[2][3] Trang 5`).
- Bấm vào nguồn hoặc ảnh trang thì sổ tay mở tài liệu đúng trang, cuộn tới và tô sáng các dòng ấy. Đoạn trích vắt sang trang kế bên thì tô cả phần ở trang đó.
- Chunk lập chỉ mục từ trước khi có số trang vẫn hiện được trang: máy chủ dò lại chính chữ của đoạn trích trong tệp gốc, nên không phải lập lại chỉ mục.

Cách định vị (`POST /api/doc/dinh-vi`, xem `dinh_vi_doan` trong `trinh_doc_tai_lieu.py`):

- **PDF có lớp chữ**: lấy hộp từng chữ bằng `pypdfium2`, đổi sang toạ độ của ảnh trang đang nhìn nên trang xoay 90° vẫn tô đúng chỗ.
- **PDF scan và ảnh**: tìm trang bằng bản OCR đã lưu lúc lập chỉ mục; hộp chữ của trang đó lấy từ Tesseract (đầu ra TSV) ở lần xem đầu tiên, mất vài giây, rồi lưu vào `ocr_cache/<hash>--vie--hop-<trang>.json` nên các lần sau gần như tức thì.
- Chữ OCR sai vài ký tự hay lớp chữ PDF tách từ khác lúc lập chỉ mục vẫn khớp được: hai dãy chữ được gióng bằng `difflib` rồi lấy cụm khớp dày nhất, bỏ các chữ khớp lẻ loi ở chỗ khác.
- Đang có câu trả lời được sinh thì máy chủ không OCR (OCR cùng lúc với mô hình làm câu trả lời chậm đi nhiều lần trên máy chỉ có CPU): ảnh trang hiện trước, phần tô sáng được hỏi lại khi máy rảnh.
- Dải ảnh trang chỉ tự tải cho PDF và ảnh. Nguồn Word/HTML phải chuyển sang PDF bằng LibreOffice trước nên chỉ được định vị khi người dùng bấm vào nguồn.

PDF scan chỉ định vị được khi đã có bản OCR trong `ocr_cache` (thư mục này không nằm trong repository). Chuyển kho sang máy khác thì chép kèm `ocr_cache`, nếu không các PDF scan chỉ còn số trang theo metadata.

### Tài khoản và quyền quản trị

Không bắt buộc đăng nhập: khách vẫn hỏi đáp như thường. Khi đăng nhập, lịch sử chat và sổ tay được lưu trên máy chủ theo tài khoản nên mở ở máy khác vẫn thấy. Chỉ tài khoản quản trị mới được cập nhật chỉ mục, đổi mô hình mặc định, đồng bộ Drive và quản lý kho.

- **Xác minh email**: máy chủ gửi mã 6 số qua thư (`gui_thu.py`, mặc định Gmail với mật khẩu ứng dụng). Mã sống 15 phút, nhập sai 5 lần là huỷ, mỗi giờ chỉ xin được vài mã. Chưa xác minh vẫn dùng bình thường; riêng email trong `RAG_EMAIL_QUAN_TRI` phải xác minh mới thành quản trị viên, nên người lạ đăng ký trước bằng email của quản trị viên không chiếm được quyền. Máy chủ chưa cấu hình gửi thư thì giao diện ẩn nút xác minh và bỏ qua điều kiện này.
- **Thông tin cá nhân**: tự đổi tên hiển thị và ảnh đại diện (ảnh tới 8 MB được cắt vuông, nén còn 256×256). Đổi email phải nhập mật khẩu hiện tại và xác minh lại email mới. Đổi mật khẩu thì các phiên đăng nhập ở máy khác bị đăng xuất.
- **Quản lý tài khoản** (menu tài khoản > Quản lý tài khoản, chỉ quản trị viên): xem mọi tài khoản, lọc tài khoản chưa xác minh hoặc bị khoá, khoá / mở khoá, xoá tài khoản. Xoá tài khoản thì xoá luôn phiên đăng nhập, sổ tay, ảnh, lịch sử trò chuyện và tài liệu riêng của người đó. Không khoá hay xoá được chính mình và quản trị viên khác; muốn thì thu quyền bằng dòng lệnh trước.

Mật khẩu băm bằng scrypt; phiên đăng nhập là chuỗi ngẫu nhiên trong cookie HttpOnly, máy chủ chỉ giữ bản băm nên lộ tệp cơ sở dữ liệu cũng không dùng lại được phiên của ai. Đăng nhập sai 10 lần liên tiếp thì bị khoá tạm 15 phút theo cả địa chỉ IP lẫn email. Nếu không đặt `RAG_EMAIL_QUAN_TRI` thì tài khoản đăng ký đầu tiên là quản trị viên.

Quên mật khẩu, cấp hoặc thu quyền quản trị, xác minh hộ khi chưa cấu hình gửi thư: quản trị viên chạy trên máy chủ.

```powershell
.\.venv\Scripts\python.exe tai_khoan.py dat-lai-mat-khau email@truong.edu.vn
.\.venv\Scripts\python.exe tai_khoan.py quan-tri email@truong.edu.vn         # thêm --bo để thu quyền
.\.venv\Scripts\python.exe tai_khoan.py xac-minh email@truong.edu.vn
.\.venv\Scripts\python.exe tai_khoan.py danh-sach
```

Cấu hình gửi thư bằng Gmail: bật xác minh 2 bước cho hộp thư gửi đi, tạo mật khẩu ứng dụng ở <https://myaccount.google.com/apppasswords>, rồi đặt `RAG_SMTP_TAI_KHOAN` và `RAG_SMTP_MAT_KHAU` trong `khoa_api.bat` (xem `khoa_api.mau.bat`). Dịch vụ khác thì đặt thêm `RAG_SMTP_MAY_CHU`, `RAG_SMTP_CONG` (465 là SSL, 587 là STARTTLS) và `RAG_SMTP_NGUOI_GUI`.

### Quản lý kho tài liệu

Hộp thoại **Kho tài liệu** có các thẻ: kho chung (ai cũng xem), **Của tôi** (khi đăng nhập), **Chờ duyệt** và **Thùng rác** (chỉ quản trị viên).

- **Tài liệu riêng**: tệp người dùng đính kèm trong chat hoặc tải lên bằng nút `+` là tài liệu riêng, nằm trong thẻ **Của tôi** và chỉ chủ tệp thấy — kể cả quản trị viên cũng không xem được tài liệu riêng của người khác. Tài liệu riêng hỏi đáp được ngay (nút **Hỏi**) và mở được trong sổ tay, không cần đợi lập chỉ mục. Mỗi tài khoản giữ tối đa 100 tài liệu riêng; tệp khách đính kèm không cần đăng nhập thì giữ 30 ngày.
- **Đề xuất vào kho chung**: tài liệu riêng không tự vào kho chung. Chủ tệp bấm **Đề xuất** thì tệp vào hàng chờ, ghi rõ ai đề xuất; thẻ **Của tôi** hiện trạng thái (chờ duyệt, đã vào kho chung, kho chung đã có, không được duyệt). Quản trị viên đề xuất tệp của mình (**Đưa vào kho chung**) hoặc tải lên bằng nút `+` thì tệp vào thẳng kho chung, có ghi tên người đưa vào.
- **Duyệt**: quản trị viên duyệt hoặc từ chối trong thẻ **Chờ duyệt**. Tệp đề xuất dạng HTML/SVG được mở kèm CSP `sandbox` nên script trong tệp không chạy được với phiên đăng nhập của quản trị viên.
- **Thùng rác**: tệp bị từ chối và tài liệu bị gỡ khỏi kho chung đều chuyển vào đây. Khôi phục tài liệu đã gỡ thì nó về lại kho; khôi phục tệp bị từ chối thì nó về lại hàng chờ duyệt.

Tệp mới vào kho chung (duyệt, tải lên, đồng bộ Drive) được lập chỉ mục khi máy rảnh. Lượt cập nhật khoá câu hỏi trên cả kho vài phút, nên máy có người dùng ban ngày (như VPS) đặt `RAG_TU_NAP_CHI_MUC=0`: tệp vẫn vào kho ngay nhưng chờ lượt cập nhật ban đêm hoặc tới khi quản trị viên tự bấm cập nhật. Trong lúc cập nhật, câu hỏi về cả kho vẫn trả lời bằng chỉ mục cũ đang nằm trong RAM.

### Sổ tay của cuộc trò chuyện

Mỗi cuộc trò chuyện có một cuốn sổ riêng nằm bên cạnh (phím tắt `Ctrl + /`); khi đăng nhập, sổ được lưu trên máy chủ theo tài khoản.

- **Ghi chú**: gõ tự do với chữ đậm, tô vàng, tiêu đề, danh sách và ô "việc cần ôn"; chép nhanh câu trả lời vào sổ. Bôi đen một đoạn trong cuộc trò chuyện thì hiện thanh **Ghi vào sổ**, **Dịch**, **Hỏi về đoạn này**.
- **Bảng vẽ**: vẽ tay sơ đồ, công thức bằng bút, bút tô sáng và tẩy, chọn màu và cỡ nét, có hoàn tác.
- **Tài liệu**: đọc PDF, ảnh chụp trang sách, Word (`.docx`, `.doc`, `.odt`, `.rtf`), Excel/CSV (`.xlsx`, `.xls`, `.ods`, `.csv`, `.tsv`), PowerPoint (`.pptx`, `.ppt`, `.odp`) và HTML. Mở bằng **Mở tài liệu hoặc ảnh** (tệp trên máy được đính kèm vào cuộc trò chuyện, nên câu hỏi sau đó trả lời theo đúng tệp này), **Mở từ Kho tài liệu**, hoặc bấm một nguồn dưới câu trả lời (xem [Nguồn trích dẫn chỉ đúng chỗ](#nguồn-trích-dẫn-chỉ-đúng-chỗ)).
  - **Khoanh để hỏi**: kéo một khung chữ nhật (như Snipping Tool) quanh đoạn chưa hiểu; máy chủ đọc đúng chữ trong khung (lớp chữ của PDF, hoặc OCR ở 300 DPI nếu là bản scan) để bấm **Giải thích**, **Hỏi câu khác** hay **Ghi vào sổ**.
  - **Bút**, **tô sáng** và **tẩy** để đánh dấu ngay trên trang; nét vẽ lưu cùng sổ, mở lại tài liệu vẫn còn.
  - Trang được render ở máy chủ bằng `pypdfium2` thay vì nhúng trình xem PDF vào trình duyệt, vì phần lớn PDF trong kho là bản scan không có lớp chữ để chọn.

Word, Excel, PowerPoint và HTML được LibreOffice chuyển một lần sang PDF (`chuyen_pdf.py`) rồi đi đúng con đường của PDF: xem trang, khoanh để hỏi, đánh dấu, tải về. Bản PDF được nhớ trong `ban_pdf_tam/` (giữ 300 bản dùng gần nhất, đổi bằng `RAG_SO_BAN_PDF_TOI_DA`) nên mở lại không phải chuyển lại. Vì tệp người dùng tải lên có thể trỏ tới địa chỉ nội bộ của máy chủ, trên Linux LibreOffice chạy trong vùng mạng cô lập (`unshare -rn`), còn HTML được gỡ script, iframe và mọi đường dẫn ra ngoài trước khi chuyển. Máy chủ chưa cài LibreOffice thì sổ tay báo rõ lý do, PDF và ảnh vẫn đọc bình thường.

Sổ tay tải về được dạng Word (ghi chú, ảnh vùng khoanh và bảng vẽ), bản in PDF hoặc ảnh bảng vẽ. Tài liệu đang đọc tải về được thành PDF kèm mọi nét bút, tô sáng và vùng khoanh: nét được vẽ thành đường véc-tơ ngay trên trang PDF gốc nên chữ của tài liệu vẫn chọn và tìm được; ảnh chụp thì thành PDF một trang.

### Dịch đa ngôn ngữ

Khung dịch hai cột (mở từ nút **Dịch** dưới câu trả lời hoặc khi bôi đen một đoạn) như Google Translate cho 133 ngôn ngữ: mỗi chiều hiện ba ngôn ngữ dùng gần đây, nút mũi tên mở bảng tìm theo tên tiếng Việt, tên bản địa hoặc mã (`Pháp`, `français`, `fr`). Có thể đọc to văn bản, sao chép, ghi bản dịch vào sổ tay, dịch câu trả lời ngay dưới câu trả lời và dịch đoạn vừa bôi đen.

- Có `RAG_GOOGLE_TRANSLATE_KEY` thì dịch bằng Google Cloud Translation (văn bản được gửi sang Google, giao diện có ghi chú).
- Không có key thì dịch bằng mô hình nhỏ trên máy (mặc định `qwen2.5:3b-instruct`), đi qua tiếng Anh làm trung gian với các cặp không có tiếng Anh. Chất lượng chỉ để tham khảo; với ngôn ngữ mô hình chưa thạo (ngoài khoảng 19 ngôn ngữ phổ biến), giao diện báo trước bản dịch có thể sai nhiều.

### Nói thay vì gõ

Nút **Nói** trong khung hỏi ghi âm câu hỏi (tự dừng sau 60 giây, `Esc` để huỷ). Máy chủ chuyển giọng nói thành chữ bằng faster-whisper (cùng mô hình dùng để phiên âm video) và tự nhận ra người dùng nói tiếng gì, rồi chèn chữ vào ô câu hỏi để xem lại trước khi gửi. Âm thanh không rời máy chủ. Trình duyệt chỉ cho dùng micro khi trang mở qua `https` hoặc `localhost`.

### Chọn mô hình trả lời

Mỗi người chọn mô hình trả lời cho câu hỏi của mình trong menu mô hình mà không làm đổi mô hình mặc định của máy chủ; tên lạ hoặc bị chặn thì máy chủ tự quay về mô hình mặc định. `RAG_MO_HINH_CHO_PHEP` giới hạn danh sách được chọn, ví dụ chặn mô hình lớn trên máy ít RAM.

## Yêu cầu

- Windows 10/11 và Python 3.11
- [Ollama](https://ollama.com/) đang chạy
- Model embedding `bge-m3`
- Một model hội thoại, mặc định `qwen3.5:4b` (đổi bằng biến môi trường `RAG_LLM_MODEL` hoặc chọn trên giao diện)
- Tesseract OCR (kèm dữ liệu tiếng Việt `vie`) nếu cần đọc PDF scan hoặc ảnh
- Microsoft Word hoặc LibreOffice nếu cần đọc tệp `.doc` đời cũ; LibreOffice (`soffice`) để sổ tay mở được Word, Excel, PowerPoint và HTML
- Tuỳ chọn: model `qwen2.5:3b-instruct` để dịch khi không có khóa Google Cloud Translation. Model faster-whisper `small` (khoảng 480 MB) tự tải ở lần phiên âm hoặc nhận giọng nói đầu tiên.

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

## Cấu hình Google Drive và khóa bí mật

Sao chép `khoa_api.mau.bat` thành `khoa_api.bat` rồi điền khóa của riêng bạn: `RAG_DRIVE_API_KEY` cho Google Drive và, nếu muốn bật xác minh email, `RAG_SMTP_TAI_KHOAN` / `RAG_SMTP_MAT_KHAU` (xem [Tài khoản và quyền quản trị](#tài-khoản-và-quyền-quản-trị)). `start_ui.bat` tự nạp tệp này nếu có. `khoa_api.bat` đã được loại khỏi Git để tránh công khai khóa.

Máy chủ tự đồng bộ thư mục Drive dùng chung mỗi 15 phút (`RAG_DRIVE_AUTO_SYNC_PHUT`, `0` để tắt; đổi thư mục bằng `RAG_DRIVE_FOLDER_ID`), tải tệp mới hoặc đã sửa về kho rồi cập nhật chỉ mục:

- **Có `RAG_DRIVE_API_KEY`**: liệt kê cả cây thư mục qua Drive API, so mã băm để chỉ tải phần thay đổi; Google Docs, Sheets, Slides được xuất sang `.docx`, `.xlsx`, `.pptx`.
- **Không có khóa**: tải theo danh sách cố định trong `drive_manifest.json` qua liên kết chia sẻ công khai, nên tệp mới thêm trên Drive chỉ được nhận sau khi xuất lại danh sách này.
- Tệp bị xóa trên Drive được chuyển khỏi kho vào `tep_go_khoi_drive/` chứ không xóa hẳn. Một lượt đồng bộ định gỡ nhiều hơn 20 tệp (`RAG_DRIVE_GO_TOI_DA`) hoặc 10% số tệp đã đồng bộ, tùy số nào lớn hơn, thì dừng lại, không gỡ tệp nào, vì nhiều khả năng danh sách Drive bị thiếu chứ không phải bị xóa thật.

Chạy tay: `.\.venv\Scripts\python.exe drive_sync.py` (thêm `--thu` để chỉ xem trước).

## Biến cấu hình cho các tính năng mới

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `RAG_KHOA_QUAN_TRI` | `1` | `0` tắt khóa quản trị (máy cá nhân một người dùng) |
| `RAG_EMAIL_QUAN_TRI` | trống | Email quản trị viên, phân cách bằng dấu phẩy; trống thì tài khoản đầu tiên là quản trị |
| `RAG_SMTP_TAI_KHOAN` | trống | Hộp thư gửi mã xác minh email; trống thì tắt xác minh email |
| `RAG_SMTP_MAT_KHAU` | trống | Mật khẩu ứng dụng của hộp thư đó |
| `RAG_SMTP_MAY_CHU`, `RAG_SMTP_CONG` | `smtp.gmail.com`, `465` | Máy chủ thư khi không dùng Gmail |
| `RAG_TU_NAP_CHI_MUC` | `1` | `0` để tệp mới vào kho chờ lượt cập nhật ban đêm thay vì cập nhật chỉ mục ngay khi máy rảnh |
| `RAG_SO_TAI_LIEU_RIENG_TOI_DA` | `100` | Số tài liệu riêng tối đa của mỗi tài khoản |
| `RAG_MO_HINH_CHO_PHEP` | trống | Các mô hình người dùng được tự chọn; trống là mọi mô hình |
| `RAG_GOOGLE_TRANSLATE_KEY` | trống | Khóa Google Cloud Translation; trống thì dịch bằng mô hình trên máy |
| `RAG_MO_HINH_DICH` | `qwen2.5:3b-instruct` | Mô hình dịch trên máy (không có thì dùng mô hình trả lời) |
| `RAG_WHISPER_MODEL` | `small` | Mô hình faster-whisper cho phiên âm và nhận giọng nói |
| `RAG_WHISPER_BEAM_GIONG_NOI` | `5` | Beam size khi nhận giọng nói |

## Chạy công khai

Sao chép `mat_khau.mau.bat` thành `mat_khau.bat`, đặt tài khoản và mật khẩu, rồi chạy:

```powershell
.\chay_cong_khai.bat
```

Ứng dụng bật lớp bảo vệ truy cập (từ chối chạy nếu thiếu mật khẩu) và mở đường hầm Cloudflare, in ra địa chỉ dạng `https://....trycloudflare.com`. Cần cài sẵn `cloudflared`. Hướng dẫn triển khai lên VPS nằm trong [trien_khai_vps/HUONG_DAN.md](trien_khai_vps/HUONG_DAN.md).

## Dữ liệu không nằm trong repository

Repository chỉ chứa mã nguồn. Những thứ sau không được commit vì có thể chứa dữ liệu riêng tư hoặc tệp dung lượng lớn: tài liệu gốc, chỉ mục FAISS và các bản sao lưu của nó, cache OCR (`ocr_cache/`), bản phiên âm, lịch sử chat, cơ sở dữ liệu tài khoản, sổ tay và hàng chờ duyệt (`*.db`), tệp đính kèm và tài liệu riêng của người dùng (`tep_dinh_kem/`), tệp chờ duyệt và thùng rác của kho (`kho_cho_duyet/`, `thung_rac_kho/`), tệp gỡ khỏi Drive (`tep_go_khoi_drive/`), bản PDF chuyển từ Word/HTML (`ban_pdf_tam/`), khóa API, mật khẩu và cấu hình riêng của máy.

Xem thêm [hướng dẫn chạy giao diện](HUONG_DAN_CHAY_GIAO_DIEN.md) (bảng biến môi trường, API) và [tài liệu bàn giao](HUONG_DAN_BAN_GIAO_UI.md).
