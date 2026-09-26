# Hướng dẫn chạy giao diện Chatbot RAG Giáo dục

## Chạy nhanh trên Windows

1. Mở Ollama và bảo đảm đã có hai model:

   ```powershell
   ollama pull bge-m3
   ollama pull qwen3.5:4b
   ```

   Muốn câu trả lời chắc tay hơn thì tải thêm bậc 9B rồi chọn ở nút model
   trên giao diện. Nặng khoảng 6.6 GB, cần máy từ 12 GB RAM trở lên:

   ```powershell
   ollama pull qwen3.5:9b
   ```

2. Nhấp đúp `start_ui.bat`.

3. Trình duyệt tự mở tại `http://127.0.0.1:8010`. `start_ui.bat` cố định cổng
   8010; nếu cổng này bận thì ứng dụng báo lỗi rõ ràng thay vì âm thầm nhảy sang
   cổng khác. Chạy thẳng `run_ui.py` mà không đặt `RAG_PORT` thì ứng dụng chọn
   cổng trống đầu tiên từ 8000 đến 8020.

4. Lần đầu mở, bấm **Đăng ký** để tạo tài khoản. Nếu không đặt `RAG_EMAIL_QUAN_TRI`
   thì tài khoản đầu tiên là quản trị viên (xem [Tài khoản và quyền quản trị](#tài-khoản-và-quyền-quản-trị)).
   Khách không đăng nhập vẫn hỏi đáp được.

Nếu chưa có `.venv`, tạo môi trường và cài thư viện một lần:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Cấu hình tùy chọn

Thiết lập biến môi trường trước khi chạy nếu cấu hình máy khác mặc định:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `RAG_LLM_MODEL` | `qwen3.5:4b` | Model tạo câu trả lời và suy luận |
| `RAG_EMBEDDING_MODEL` | `bge-m3` | Model embedding, phải khớp model dùng để build index |
| `RAG_REASONING` | `0` | Đặt `1` để bật suy luận sâu; trên máy chỉ có CPU sẽ chậm hơn nhiều |
| `RAG_CONTEXT_LENGTH` | `4096` | Cửa sổ ngữ cảnh dùng cho một câu hỏi; chạy được trên GPU thì nới lên `8192` |
| `RAG_MAX_OUTPUT_TOKENS` | `420` | Độ dài tối đa của câu trả lời |
| `RAG_MAX_OUTPUT_TOKENS_TOM_TAT` | `700` | Hạn mức riêng cho bản tóm tắt tệp đính kèm |
| `RAG_SO_BANG_CHUNG` | `4` | Số đoạn tài liệu đưa vào prompt mỗi câu hỏi |
| `RAG_KY_TU_MOI_BANG_CHUNG` | `900` | Cắt bớt mỗi đoạn còn bấy nhiêu ký tự; `0` = không cắt |
| `RAG_SO_DOAN_TOM_TAT` | `6` | Số đoạn trích để tóm tắt một tệp |
| `RAG_KY_TU_TOM_TAT` | `5000` | Ngân sách ký tự tài liệu khi tóm tắt |
| `RAG_KEEP_ALIVE` | `2h` | Giữ model trong RAM bao lâu sau câu hỏi cuối |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Địa chỉ Ollama |
| `RAG_INDEX_PATH` | `faiss_index_data_giao_duc` trong dự án | Đường dẫn FAISS index |
| `RAG_DATA_PATH` | `ollama-rag-desktop/data_giao_duc` | Kho tài liệu giáo dục dùng để build/cập nhật index |
| `RAG_HOST` | `127.0.0.1` | IP lắng nghe của web server |
| `RAG_PORT` | `8010` khi chạy `start_ui.bat` | Cổng web server; để trống thì chọn cổng trống từ 8000 |
| `RAG_OPEN_BROWSER` | `1` | Đặt `0` nếu không muốn tự mở trình duyệt |
| `RAG_DRIVE_API_KEY` | *(trống)* | API key Google Drive; có key thì hệ thống tự phát hiện file mới trên Drive |
| `RAG_DRIVE_FOLDER_ID` | thư mục đề án | ID thư mục Drive dùng chung |
| `RAG_DRIVE_AUTO_SYNC_PHUT` | `15` | Chu kỳ tự kiểm tra Drive; đặt `0` để tắt |
| `RAG_DRIVE_MAX_MB` | `2048` | Bỏ qua file lớn hơn ngưỡng này khi đồng bộ |
| `RAG_DRIVE_GO_TOI_DA` | `20` | Một lượt đồng bộ định gỡ nhiều tệp hơn mức này (hoặc hơn 10% số tệp đã đồng bộ, tùy số nào lớn hơn) thì dừng, không gỡ tệp nào |
| `RAG_THU_MUC_NONG` | *(trống)* | Thư mục "nóng" (vd thư mục Google Drive for Desktop): tệp thả vào được tự chép vào kho và lập chỉ mục |
| `RAG_LUU_TEP_DINH_KEM` | `1` | Đặt `0` để không tự chép tệp từ thư mục nóng vào kho; nút **Đề xuất** của tài liệu riêng vẫn dùng được |
| `RAG_THU_MUC_TEP_DINH_KEM_TRONG_KHO` | `tai_lieu_dinh_kem` | Thư mục con trong kho chứa tài liệu được đề xuất vào kho, chỉ dùng khi `RAG_KHO_PHANG=0` |
| `RAG_CHO_NAP_TEP_GIAY` | `90` | Đợi bao lâu sau câu hỏi cuối mới nạp tệp mới vào chỉ mục |
| `RAG_TU_NAP_CHI_MUC` | `1` | `0` = không tự cập nhật chỉ mục khi kho có tệp mới (duyệt tệp, tải lên, Drive); tệp chờ lượt cập nhật ban đêm. Đặt `0` trên VPS |
| `RAG_SO_TEP_DINH_KEM_TOI_DA` | `200` | Số tệp đính kèm của khách (chưa đăng nhập) máy chủ giữ, mọi khách cộng lại |
| `RAG_NGAY_GIU_TEP_DINH_KEM` | `30` | Tệp đính kèm của khách được giữ (và hỏi được) bao nhiêu ngày |
| `RAG_SO_TAI_LIEU_RIENG_TOI_DA` | `100` | Số tài liệu riêng tối đa của mỗi tài khoản; tài liệu riêng giữ tới khi chủ xoá |
| `RAG_GIOI_HAN_TEP_MB` | `40` | Dung lượng tối đa một tệp tải lên |
| `RAG_WHISPER_MODEL` | `small` | Model phiên âm video: tiny/base/small/medium/large-v3 |
| `RAG_TRANSCRIBE_ON_INDEX` | `1` | Đặt `0` nếu chỉ nạp video đã phiên âm sẵn |
| `RAG_TU_CHOI_KHI_LAC_DE` | `1` | Tự trả lời "không tìm thấy" khi truy hồi lạc đề |
| `RAG_OCR_ON_INDEX` | `1` | Đặt `0` nếu chỉ nạp PDF đã OCR sẵn |
| `RAG_OCR_DPI` | `300` | Độ phân giải render trang PDF trước khi OCR |
| `RAG_OCR_LUONG` | số lõi − 2 | Số trang OCR song song |
| `RAG_TESSERACT_PATH` | tự dò | Đường dẫn `tesseract.exe` nếu cài chỗ khác |
| `RAG_KHOA_QUAN_TRI` | `1` | Đặt `0` để tắt khóa quản trị (máy cá nhân chỉ một người dùng) |
| `RAG_EMAIL_QUAN_TRI` | *(trống)* | Email quản trị viên, phân cách bằng dấu phẩy; trống thì tài khoản đầu tiên là quản trị. Khi đã cấu hình gửi thư, email này phải xác minh mới có quyền quản trị |
| `RAG_SMTP_TAI_KHOAN` | *(trống)* | Hộp thư gửi mã xác minh email; trống thì giao diện ẩn nút xác minh |
| `RAG_SMTP_MAT_KHAU` | *(trống)* | Mật khẩu ứng dụng của hộp thư đó (Gmail: <https://myaccount.google.com/apppasswords>) |
| `RAG_SMTP_MAY_CHU` / `RAG_SMTP_CONG` / `RAG_SMTP_NGUOI_GUI` | `smtp.gmail.com` / `465` / như tài khoản | Máy chủ thư khi không dùng Gmail; cổng 465 là SSL, 587 là STARTTLS |
| `RAG_TAI_KHOAN_DB` | `tai_khoan.db` trong dự án | Cơ sở dữ liệu tài khoản, phiên đăng nhập và sổ tay |
| `RAG_LICH_SU_DB` | trong dự án | Cơ sở dữ liệu lịch sử hội thoại |
| `RAG_KHO_TAI_LEN_DB` | `kho_tai_len.db` trong dự án | Sổ ghi tệp gửi lên kho, hàng chờ duyệt và thùng rác |
| `RAG_THU_MUC_BAN_PDF` | `ban_pdf_tam` trong dự án | Nơi nhớ bản PDF do LibreOffice chuyển từ Word, Excel, PowerPoint, HTML |
| `RAG_SO_BAN_PDF_TOI_DA` | `300` | Số bản PDF chuyển đổi được giữ (bản dùng gần nhất) |
| `RAG_MO_HINH_CHO_PHEP` | *(trống)* | Các mô hình người dùng được tự chọn, phân cách bằng dấu phẩy; trống là mọi mô hình |
| `RAG_GOOGLE_TRANSLATE_KEY` | *(trống)* | Khóa Google Cloud Translation; trống thì dịch bằng mô hình trên máy |
| `RAG_MO_HINH_DICH` | `qwen2.5:3b-instruct` | Mô hình dịch trên máy; máy không có thì dùng mô hình trả lời |
| `RAG_WHISPER_BEAM_GIONG_NOI` | `5` | Beam size khi nhận giọng nói ở nút **Nói** |

### Nếu câu trả lời quá lâu

Máy chỉ có CPU xử lý prompt khoảng 26 token/giây và sinh chữ khoảng 6 token/giây,
nên thời gian chờ tỉ lệ thẳng với độ dài prompt + độ dài câu trả lời. Theo thứ tự
hiệu quả:

1. Giảm `RAG_SO_BANG_CHUNG` (4 → 3) và `RAG_KY_TU_MOI_BANG_CHUNG` (900 → 700):
   mỗi đoạn bỏ đi tiết kiệm khoảng 15 giây chờ.
2. Giảm `RAG_MAX_OUTPUT_TOKENS` (420 → 300): câu trả lời ngắn hơn, nhanh hơn
   khoảng 20 giây.
3. Đổi sang model nhỏ hơn ngay trên giao diện (`qwen2.5:3b-instruct`,
   `llama3.2:3b`): nhanh gần gấp đôi, đổi lại chất lượng trích dẫn giảm - nên
   chạy `benchmark_chatbot.py` để đối chiếu trước khi dùng lâu dài.
4. Chỉ khi thật cần chi tiết mới đặt `RAG_REASONING=1`; suy luận ẩn làm chậm
   gấp nhiều lần trên CPU.

Ví dụ PowerShell:

```powershell
$env:RAG_LLM_MODEL = "qwen3.5:4b"
$env:RAG_PORT = "8080"
.venv\Scripts\python.exe run_ui.py
```

## API

Các endpoint đánh dấu **[QT]** chỉ tài khoản quản trị gọi được (khi `RAG_KHOA_QUAN_TRI=1`). Tài liệu OpenAPI tương tác: `GET /api/docs`.

Hỏi đáp và kho tri thức:

- `GET /api/status`: trạng thái model và kho tri thức.
- `GET /api/documents`: danh sách tài liệu và tình trạng lập chỉ mục.
- `GET /api/bo-loc`: các lựa chọn phạm vi (môn, cấp học...) kèm số tài liệu.
- `GET /api/goi-y?so_luong=6`: mẻ câu hỏi gợi ý cho màn hình chào.
- `POST /api/chat/stream`: nhận câu hỏi và trả NDJSON streaming.
- `POST /api/chat/dung`: dừng câu trả lời đang sinh dở.
- `GET /api/source?name=...`: mở tệp nguồn đã được kiểm tra trong kho dữ liệu.
- `POST /api/reinitialize`: thử kết nối lại sau khi mở Ollama.
- `GET /api/models`: danh sách model Ollama người dùng được chọn.
- `POST /api/index/update` **[QT]**: cập nhật tăng dần chỉ mục sau khi thêm, sửa hoặc xóa tài liệu.
- `POST /api/drive/sync` **[QT]**: kéo tài liệu mới từ Google Drive rồi tự cập nhật chỉ mục.
- `POST /api/model` **[QT]**: đổi model mặc định của máy chủ.
- `GET /api/thong-ke` **[QT]**, `DELETE /api/cache` **[QT]**: thống kê câu hỏi, xóa cache ngữ nghĩa.

Tài khoản, lịch sử và sổ tay:

- `GET /api/tai-khoan/toi`, `POST /api/tai-khoan/dang-ky`, `/dang-nhap`, `/dang-xuat`, `/doi-mat-khau` (đăng xuất các máy khác, giữ máy đang dùng).
- `POST /api/tai-khoan/thong-tin`: đổi tên hiển thị và/hoặc email `{ten, email, mat_khau}`; đổi email cần mật khẩu hiện tại và phải xác minh lại.
- `POST /api/tai-khoan/gui-ma-xac-minh`, `POST /api/tai-khoan/xac-minh`: gửi mã 6 số qua thư và nhập mã (mã sống 15 phút, sai 5 lần là huỷ).
- `PUT|DELETE /api/tai-khoan/anh-dai-dien` (byte ảnh trong body, tiêu đề `X-RAG-Action: avatar`), `GET /api/tai-khoan/anh-dai-dien/{nguoi_dung_id}`.
- `GET /api/hoi-thoai`, `GET|DELETE /api/hoi-thoai/{id}`, `DELETE /api/hoi-thoai`: lịch sử hội thoại.
- `GET|PUT|DELETE /api/so-tay/{hoi_thoai_id}`: sổ tay của một cuộc trò chuyện (cần đăng nhập).

Tệp đính kèm, trình đọc tài liệu và quản lý kho:

- `POST /api/tep?ten=...`: tải tệp đính kèm (byte thô trong body, tiêu đề `X-RAG-Action: upload-file`); tệp là tài liệu riêng của người tải lên. `GET /api/tep` chỉ trả tệp của chính người hỏi (kể cả quản trị viên); `GET|DELETE /api/tep/{id}`, `GET /api/tep/{id}/noi-dung` (tệp HTML/SVG trả kèm CSP `sandbox`).
- `POST /api/tep/{id}/de-xuat` (tiêu đề `X-RAG-Action: de-xuat-kho`): chủ tài liệu riêng đề xuất vào kho chung; quản trị viên thì vào thẳng kho, người khác vào hàng chờ duyệt.
- `POST /api/kho/tep?ten=...` (tiêu đề `X-RAG-Action: upload-library`): nút `+` trong Kho tài liệu. Quản trị viên: vào thẳng kho chung rồi hẹn lập chỉ mục; người đã đăng nhập: lưu thành tài liệu riêng; khách: 401.
- `GET /api/doc/thong-tin`, `GET /api/doc/trang`: số trang và ảnh từng trang (theo `tep` hoặc `nguon`). PDF và ảnh đọc thẳng; Word, Excel, PowerPoint, HTML được LibreOffice chuyển sang PDF trước (có nhớ).
- `POST /api/doc/vung`: chữ nằm trong vùng khoanh `{so, x0, y0, x1, y1}` (toạ độ 0..1 theo trang).
- `POST /api/doc/dinh-vi`: `{nguon|tep, doan, trong_tam, trang}` → `{trang, danh_dau: {số trang: {vung, chinh}}}` - trang và các hình chữ nhật (toạ độ 0..1) của đoạn bằng chứng trên trang gốc, để tô sáng nguồn trích dẫn. Trang scan chưa có hộp chữ mà máy đang sinh câu trả lời thì trả thêm `cho_ocr: true` (hỏi lại sau).
- `POST /api/doc/tai-ve`: `{nguon|tep, ten, net}` → PDF của tài liệu kèm các nét bút, tô sáng, khoanh của sổ tay.
- `GET /api/quan-ly/tai-len`, `GET /api/quan-ly/tai-len/{ma}/tep`, `POST /api/quan-ly/tai-len/{ma}/duyet|tu-choi`, `POST /api/quan-ly/kho/go`, `GET /api/quan-ly/thung-rac`, `POST /api/quan-ly/thung-rac/{ma}/khoi-phuc`: hàng chờ duyệt, gỡ và khôi phục tài liệu (quản trị).
- `GET /api/quan-ly/tai-khoan`, `POST /api/quan-ly/tai-khoan/{ma}/khoa` (`{khoa: true|false}`, tiêu đề `X-RAG-Action: khoa-tai-khoan`), `DELETE /api/quan-ly/tai-khoan/{ma}` (tiêu đề `X-RAG-Action: xoa-tai-khoan`): quản lý tài khoản (quản trị).

Dịch và giọng nói:

- `GET /api/dich/cau-hinh`: công cụ dịch đang dùng (`google` hay `cuc_bo`) và danh sách 133 ngôn ngữ.
- `POST /api/dich`: `{van_ban, nguon, dich_sang}` (`nguon` = `tu_dong` để tự nhận diện), trả NDJSON.
- `POST /api/giong-noi`: byte ghi âm trong body (tiêu đề `X-RAG-Action: voice-input`), trả `{van_ban, ngon_ngu, ten_ngon_ngu, do_tin_cay}`.

Payload cho endpoint chat (chỉ `question` là bắt buộc):

```json
{
  "question": "Còn giảng viên thì sao?",
  "history": [
    {"role": "user", "content": "Quy định đối với sinh viên là gì?"},
    {"role": "assistant", "content": "Các quy định gồm..."}
  ],
  "hoi_thoai_id": "mã hội thoại đang tiếp tục",
  "tep_ids": ["mã tệp đính kèm"],
  "pham_vi": {},
  "doan_trich": {"van_ban": "đoạn vừa khoanh", "ten": "tên tệp", "trang": 1},
  "model": "qwen3.5:9b"
}
```

Ứng dụng thiết kế cho một lượt sinh câu trả lời tại một thời điểm vì Ollama chạy CPU. Câu hỏi đến sau sẽ chờ lượt hiện tại kết thúc. Lịch sử hội thoại lưu phía máy chủ trong SQLite: đã đăng nhập thì theo tài khoản (mở máy khác vẫn thấy), còn khách thì theo mã ngẫu nhiên của trình duyệt. Tối đa sáu tin nhắn gần nhất được gửi kèm câu hỏi để hiểu câu hỏi nối tiếp, và không được thêm vào kho tài liệu.

Trong giao diện, câu trả lời hỗ trợ tiêu đề, danh sách, chữ đậm, mã ngắn và liên kết trích dẫn. Với nguồn PDF hoặc ảnh, dưới câu trả lời có ảnh thu nhỏ của trang gốc: các dòng được trích tô vàng, câu sát câu hỏi nhất viền đỏ. Nhấp vào nguồn hoặc ảnh trang để mở tài liệu trong trình đọc của sổ tay, đúng trang và cuộn tới đúng dòng đó (`Ctrl` + bấm để mở tài liệu gốc ở tab mới). Chunk lập chỉ mục từ trước khi lưu số trang vẫn hiện được trang, vì máy chủ dò lại chính chữ của đoạn trích trong tệp gốc. Nếu chủ động dừng giữa chừng, phần nội dung đã nhận vẫn được lưu vào lịch sử.

Dưới bốn thẻ chủ đề ở màn hình chào có hàng **Gợi ý khác từ kho tài liệu**: câu hỏi dựng theo tên văn bản đang có trong kho, bấm **Đổi gợi ý** để lấy mẻ khác. Cuối mỗi câu trả lời có hàng **Hỏi tiếp** dựng từ chính nguồn vừa trích - văn bản đã bị thay thế hay còn là dự thảo thì gợi ý hỏi ngay về chỗ đó, nguồn trích theo Điều thì gợi ý đọc sâu vào Điều đó. Khác với bốn thẻ chủ đề (chỉ điền vào khung hỏi để sửa lại), gợi ý dạng chip đã là câu hỏi trọn vẹn nên bấm là gửi luôn. Cả hai hàng gợi ý đều dựng bằng dữ liệu có sẵn, không gọi thêm model nên không làm chậm câu trả lời.

Nút **Kho tài liệu** mở danh sách nguồn, cho phép tìm theo tên hoặc thư mục và hiển thị trạng thái đã lập chỉ mục, cần OCR, tệp trùng hoặc chờ cập nhật.

Khi kho tài liệu thay đổi, thẻ trạng thái sẽ hiện nút **Cập nhật kho tri thức** (chỉ quản trị viên thấy). Quá trình chạy nền: chỉ mục mới được dựng trên đĩa, còn câu hỏi trong lúc đó vẫn được trả lời bằng chỉ mục cũ đang nằm trong RAM (chỉ thiếu các tệp đang nạp); riêng lúc máy chủ vừa khởi động và đang nạp chỉ mục thì phải đợi. Không đóng cửa sổ chạy ứng dụng cho tới khi trạng thái trở lại **Sẵn sàng**.

Chỉ chạy **một** máy chủ trên một kho tài liệu: máy chủ tự đồng bộ Drive và tự lập chỉ mục khi rảnh, nên hai bản chạy song song (ví dụ thêm một bản thử ở cổng khác) có thể cùng ghi vào chỉ mục.

Để đo một model bằng toàn bộ pipeline truy hồi, sinh câu trả lời và kiểm tra số trích dẫn:

```powershell
.venv\Scripts\python.exe benchmark_chatbot.py "Câu hỏi cần kiểm tra"
```

Chạy cả bộ 127 câu hỏi chuẩn trong `bo_cau_hoi_benchmark.json` (97 câu có nhãn nguồn đúng, 30 câu cố tình ngoài phạm vi kho; chấm điểm truy hồi đúng nguồn, trích dẫn hợp lệ, số liệu có căn cứ và từ chối đúng chỗ), kết quả ghi ra `ket_qua_benchmark.json`. Chạy nhanh chỉ phần truy hồi bằng `--nhanh`, đo MRR/Hit@K bằng `--ir` (xem README):

```powershell
.venv\Scripts\python.exe benchmark_chatbot.py --bo
```

## Chọn mô hình trả lời

Bấm vào tên model ở góc trên bên phải để mở danh sách. Menu hiện các model Ollama người dùng được chọn, kèm số tham số và dung lượng; model đang dùng có dấu tích.

**Mỗi người tự chọn mô hình cho câu hỏi của mình.** Lựa chọn chỉ áp dụng cho trình duyệt đang dùng (lưu trong `localStorage`) và được gửi kèm từng câu hỏi; máy chủ không đổi mô hình mặc định cho người khác. Chọn lại đúng mô hình mặc định thì bỏ lựa chọn riêng, để khi quản trị viên đổi mặc định thì mình theo luôn. Mô hình đã chọn bị gỡ khỏi máy hoặc bị chặn thì máy chủ tự quay về mô hình mặc định, không báo lỗi. Lịch sử ghi đúng mô hình đã trả lời từng câu.

Quản trị viên thấy thêm nút **Đặt … làm mặc định cho mọi người** trong menu. Đổi mặc định **không phải nạp lại chỉ mục**: vector đã embed bằng `bge-m3`, chỉ chuỗi sinh câu trả lời được dựng lại nên chuyển gần như tức thì. Lựa chọn mặc định được ghi vào `cai_dat.json` để lần mở sau vẫn giữ nguyên.

Vài điểm cần biết:

- Model nhúng (`bge-m3`, `nomic-embed-text`) bị lọc khỏi danh sách vì chúng chỉ sinh vector, không trò chuyện được.
- `RAG_MO_HINH_CHO_PHEP` giới hạn các model người dùng được tự chọn. Trên máy ít RAM nên chặn model lớn: chỉ một người chọn `qwen3.5:9b` là cả máy chủ có thể hết bộ nhớ.
- Không đổi được mặc định giữa lúc đang trả lời dở; hệ thống báo chờ câu hiện tại xong.
- Đặt biến `RAG_LLM_MODEL` sẽ ép cứng model mặc định và bỏ qua lựa chọn đã lưu.
- Thêm model mới bằng `ollama pull <tên model>`, menu tự thấy ở lần mở sau.

## Tài khoản và quyền quản trị

Không bắt buộc đăng nhập: khách vẫn hỏi đáp như thường. Đăng nhập thì lịch sử và sổ tay nằm trên máy chủ theo tài khoản, mở máy khác vẫn thấy. Chỉ tài khoản quản trị mới được làm các thao tác đụng tới cả hệ thống: cập nhật chỉ mục, đổi mô hình mặc định, đồng bộ Drive, xem thống kê, duyệt và gỡ tài liệu, quản lý tài khoản.

- Mật khẩu băm bằng scrypt; phiên đăng nhập là chuỗi ngẫu nhiên 256 bit trong cookie HttpOnly `rag_phien`, máy chủ chỉ giữ bản băm SHA-256 của nó. Đăng nhập sai 10 lần liên tiếp thì bị khoá tạm 15 phút theo cả IP lẫn email.
- Quản trị viên là các email trong `RAG_EMAIL_QUAN_TRI`; để trống thì tài khoản đăng ký đầu tiên là quản trị.
- Máy cá nhân chỉ một người dùng có thể tắt khóa quản trị bằng `RAG_KHOA_QUAN_TRI=0`.

Trong menu tài khoản (bấm vào tên ở góc trên):

- **Xác minh email**: máy chủ gửi mã 6 số qua thư, mã sống 15 phút, nhập sai 5 lần là huỷ, mỗi giờ xin được tối đa 5 mã. Chưa xác minh vẫn dùng bình thường; riêng email trong `RAG_EMAIL_QUAN_TRI` phải xác minh mới thành quản trị viên, nên người lạ đăng ký trước bằng email của quản trị viên không chiếm được quyền. Máy chủ chưa cấu hình gửi thư thì nút này ẩn và điều kiện trên được bỏ qua.
- **Thông tin cá nhân**: đổi tên hiển thị, ảnh đại diện (ảnh tới 8 MB được cắt vuông, nén còn 256×256), email (phải nhập mật khẩu hiện tại và xác minh lại email mới) và mật khẩu (các máy khác bị đăng xuất).
- **Quản lý tài khoản** (chỉ quản trị viên): xem mọi tài khoản, lọc chưa xác minh hoặc bị khoá, khoá / mở khoá, xoá tài khoản. Xoá tài khoản thì xoá luôn phiên đăng nhập, sổ tay, ảnh, lịch sử trò chuyện và tài liệu riêng của người đó. Không khoá hay xoá được chính mình và quản trị viên khác.

Cấu hình gửi thư bằng Gmail: bật xác minh 2 bước cho hộp thư gửi đi, tạo **Mật khẩu ứng dụng** ở <https://myaccount.google.com/apppasswords>, rồi đặt trong `khoa_api.bat`:

```bat
set "RAG_SMTP_TAI_KHOAN=hopthu@gmail.com"
set "RAG_SMTP_MAT_KHAU=abcd efgh ijkl mnop"
```

Quên mật khẩu, cấp hoặc thu quyền quản trị, xác minh hộ: quản trị viên dùng dòng lệnh trên máy chủ.

```powershell
.venv\Scripts\python.exe tai_khoan.py dat-lai-mat-khau email@truong.edu.vn
.venv\Scripts\python.exe tai_khoan.py quan-tri email@truong.edu.vn         # thêm --bo để thu quyền
.venv\Scripts\python.exe tai_khoan.py xac-minh email@truong.edu.vn
.venv\Scripts\python.exe tai_khoan.py danh-sach
```

## Quản lý kho tài liệu

Hộp thoại **Kho tài liệu** có các thẻ: kho chung (ai cũng xem), **Của tôi** (khi đăng nhập), **Chờ duyệt** và **Thùng rác** (chỉ quản trị viên).

- **Tài liệu riêng**: tệp đính kèm trong chat và tệp người dùng tải lên bằng nút `+` là tài liệu riêng, nằm trong thẻ **Của tôi** và chỉ chủ tệp thấy - kể cả quản trị viên cũng không xem được tài liệu riêng của người khác. Tài liệu riêng hỏi đáp được ngay (nút **Hỏi**, chỉ tìm trong tệp đó) và mở được trong sổ tay, không cần đợi lập chỉ mục. Mỗi tài khoản giữ tối đa 100 tài liệu riêng tới khi tự xoá; tệp khách đính kèm khi chưa đăng nhập thì giữ 30 ngày.
- **Đề xuất vào kho chung**: chủ tệp bấm **Đề xuất** thì tệp vào hàng chờ, ghi rõ ai đề xuất; thẻ **Của tôi** hiện trạng thái (chờ duyệt, đã vào kho chung, kho chung đã có, không được duyệt). Quản trị viên bấm **Đưa vào kho chung** trên tệp của mình, hoặc tải lên bằng nút `+`, thì tệp vào thẳng kho, có ghi tên người đưa vào.
- **Duyệt**: quản trị viên xem tệp, **duyệt** hoặc **từ chối** trong thẻ **Chờ duyệt**. Tệp HTML/SVG được mở kèm CSP `sandbox` nên script trong tệp không chạy được với phiên đăng nhập của quản trị viên.
- **Thùng rác**: tệp bị từ chối và tài liệu bị gỡ khỏi kho đều chuyển vào đây. Khôi phục tài liệu đã gỡ thì nó về lại kho (chỉ mục cập nhật ở lần kế tiếp); khôi phục tệp bị từ chối thì nó về lại hàng chờ duyệt.

Tệp mới vào kho chung được lập chỉ mục sau khi máy rảnh `RAG_CHO_NAP_TEP_GIAY` giây. Máy có người dùng ban ngày (như VPS) nên đặt `RAG_TU_NAP_CHI_MUC=0`: tệp vẫn vào kho ngay nhưng chờ lượt cập nhật ban đêm hoặc tới khi quản trị viên tự bấm cập nhật.

Sổ ghi (ai gửi, lúc nào, ai duyệt) nằm trong `kho_tai_len.db`, tách khỏi sổ ghi chép chỉ mục.

## Sổ tay của cuộc trò chuyện

Nút **Sổ tay** (hoặc `Ctrl + /`) mở một cuốn sổ riêng cho cuộc trò chuyện đang mở, gồm ba thẻ:

- **Ghi chú**: gõ tự do với chữ đậm, tô vàng, tiêu đề, danh sách và ô "việc cần ôn"; chép nhanh câu trả lời, đoạn đã bôi đen, bản dịch.
- **Bảng vẽ**: vẽ tay sơ đồ, công thức bằng bút, tô sáng, tẩy; chọn màu, cỡ nét, có hoàn tác.
- **Tài liệu**: đọc PDF, ảnh chụp trang sách, Word (`.docx`, `.doc`, `.odt`, `.rtf`), Excel/CSV (`.xlsx`, `.xls`, `.ods`, `.csv`, `.tsv`), PowerPoint (`.pptx`, `.ppt`, `.odp`) và HTML ngay bên cạnh khung chat. Mở bằng **Mở tài liệu hoặc ảnh** (tệp trên máy, được đính kèm vào cuộc trò chuyện), **Mở từ Kho tài liệu**, nút **Đọc** trên tệp đính kèm, hoặc bấm vào một nguồn trích dẫn (mở đúng trang, cuộn tới và tô sáng các dòng được trích; `Ctrl` + bấm để mở tab mới). Trang được render ở máy chủ bằng `pypdfium2`, nên đọc được cả PDF scan không có lớp chữ.

**Khoanh để hỏi**: chọn công cụ này rồi nhấn chuột ở một góc và kéo sang góc đối diện để vẽ khung chữ nhật (như Snipping Tool) quanh đoạn chưa hiểu. Máy chủ đọc đúng chữ trong khung: dùng lớp chữ của PDF nếu có, không thì render lại vùng đó ở 300 DPI rồi OCR bằng Tesseract. Hộp nhỏ hiện ngay dưới khung, cho sửa lại chữ rồi chọn **Giải thích**, **Hỏi câu khác** (điền sẵn "Về đoạn … (trang …)" vào khung hỏi để gõ nốt câu hỏi) hoặc **Ghi vào sổ** (kèm ảnh vùng khoanh). Đoạn khoanh được gửi kèm câu hỏi và trở thành bằng chứng số 1 của câu trả lời. Trên màn hình cảm ứng, công cụ mặc định là **Cuộn** để vuốt trang không vẽ nhầm.

**Đánh dấu tài liệu**: bút, tô sáng và tẩy vẽ ngay trên trang; nét lưu cùng sổ nên mở lại tài liệu vẫn còn.

**Word, Excel, PowerPoint, HTML** được LibreOffice chuyển một lần sang PDF (`chuyen_pdf.py`) rồi đi đúng con đường của PDF: xem trang, khoanh để hỏi, đánh dấu, tải về. Bản PDF được nhớ trong `ban_pdf_tam/` nên mở lại không phải chuyển lại. Tệp người dùng tải lên có thể trỏ tới địa chỉ nội bộ của máy chủ, nên trên Linux LibreOffice chạy trong vùng mạng cô lập (`unshare -rn`), còn HTML được gỡ script, iframe và mọi đường dẫn ra ngoài trước khi chuyển. Máy chủ chưa cài LibreOffice thì sổ tay báo rõ lý do, PDF và ảnh vẫn đọc bình thường.

Sổ lưu trong IndexedDB của trình duyệt, khóa theo mã cuộc trò chuyện; đăng nhập thì lưu thêm trên máy chủ. Nút tải về xuất sổ ra Word (`.doc`, gồm ghi chú, ảnh vùng khoanh và bảng vẽ), bản in PDF hoặc ảnh bảng vẽ; khi đang đọc tài liệu có thêm **Tài liệu đang đọc (.pdf)**: PDF gốc kèm mọi nét bút, tô sáng, vùng khoanh, vẽ thành đường véc-tơ nên chữ của tài liệu vẫn chọn và tìm được.

## Dịch đa ngôn ngữ

Khung dịch hai cột như Google Translate, hỗ trợ 133 ngôn ngữ, mở từ nút **Dịch** dưới câu trả lời hoặc khi bôi đen một đoạn (thanh trên cùng không còn nút Dịch riêng):

- Mỗi chiều hiện **Phát hiện ngôn ngữ** (bên nguồn) và ba ngôn ngữ dùng gần đây. Nút mũi tên cuối hàng mở bảng đủ 133 ngôn ngữ, tìm được theo tên tiếng Việt, tên bản địa hoặc mã (`phap`, `français`, `fr`), gõ không dấu cũng được, `Enter` chọn kết quả đầu, `Esc` đóng bảng.
- Nút đổi chiều, đọc to (giọng có sẵn của hệ điều hành), sao chép và ghi bản dịch vào sổ tay. `Ctrl + Enter` dịch ngay.
- Dưới mỗi câu trả lời có nút **Dịch**: chọn ngôn ngữ (có ô tìm) để xem bản dịch ngay dưới câu trả lời. Bôi đen một đoạn trong câu trả lời rồi chọn **Dịch** để mở khung dịch với đoạn đó.

Công cụ dịch:

| Cấu hình | Công cụ | Ghi chú |
|---|---|---|
| Đặt `RAG_GOOGLE_TRANSLATE_KEY` | Google Cloud Translation | Chất lượng như Google Translate. Văn bản được gửi sang Google, giao diện có ghi rõ. Key cần bật *Cloud Translation API* |
| Không có key, hoặc Google lỗi | Mô hình trên máy (`RAG_MO_HINH_DICH`) | Cặp không có tiếng Anh thì dịch qua tiếng Anh làm trung gian. Chỉ để tham khảo; với ngôn ngữ ngoài khoảng 19 ngôn ngữ phổ biến, giao diện báo trước bản dịch có thể sai nhiều |

Khi dịch bằng mô hình trên máy, ngôn ngữ nguồn được nhận diện theo bảng chữ (Hàn, Nhật, Trung, Thái, Nga, Ả Rập, Hindi...) và theo các từ thông dụng với ngôn ngữ viết chữ Latinh, không gọi mô hình.

## Nói thay vì gõ

Nút **Nói** trong khung hỏi ghi âm câu hỏi:

1. Bấm **Nói** rồi nói; nút chuyển màu đỏ thành **Dừng**, dòng gợi ý bên cạnh đếm giờ.
2. Bấm **Dừng** khi nói xong (tự dừng sau 60 giây, `Esc` để huỷ).
3. Máy chủ chuyển giọng nói thành chữ bằng faster-whisper (cùng model `RAG_WHISPER_MODEL` dùng phiên âm video) và **tự nhận ra người dùng nói tiếng gì**, không cần chọn trước. Chữ được chèn vào ô câu hỏi tại vị trí con trỏ, kèm dòng báo ngôn ngữ đã nhận ra; xem lại rồi nhấn `Enter` để gửi.

Âm thanh chỉ gửi về máy chủ của mình, không qua dịch vụ ngoài. Trên máy chỉ có CPU, 10 giây nói mất khoảng 6 giây để ra chữ; lần đầu sau khi khởi động chậm hơn vì phải nạp model. Trình duyệt chỉ cho dùng micro khi trang mở qua `https` hoặc `localhost`: mở bằng địa chỉ `http://` trong mạng LAN thì nút bị mờ kèm giải thích. Lần đầu bấm, trình duyệt hỏi quyền dùng micro.

## Tài liệu trên Google Drive

Thư mục Drive dùng chung là nguồn dữ liệu chính thức; người phụ trách chỉ cần upload lên đó. Máy chạy chatbot tự tải phần thay đổi về `data_giao_duc` rồi tự nạp vào chỉ mục — mặc định kiểm tra mỗi 15 phút, hoặc quản trị viên bấm **Đồng bộ Google Drive** trên thanh bên để làm ngay.

Tệp bị xoá trên Drive được chuyển khỏi kho vào `tep_go_khoi_drive/` chứ không xoá hẳn, gỡ nhầm thì chép ngược lại là xong. Một lượt đồng bộ định gỡ nhiều hơn 20 tệp (`RAG_DRIVE_GO_TOI_DA`) hoặc 10% số tệp đã đồng bộ, tùy số nào lớn hơn, thì dừng lại không gỡ tệp nào - nhiều khả năng danh sách Drive bị thiếu (liệt kê hỏng giữa chừng, manifest cũ) chứ không phải bị xoá thật.

Vì embedding và tìm kiếm chạy 100% cục bộ nên nội dung vẫn phải nằm trên máy; điều khác biệt là không ai phải tải tay hay chạy lại script nào.

Hai chế độ hoạt động:

| Chế độ | Cấu hình cần | Phát hiện file mới trên Drive |
|---|---|---|
| API key *(khuyến nghị)* | đặt `RAG_DRIVE_API_KEY` | Tự động, kể cả file và thư mục con mới thêm |
| Manifest | dùng `drive_manifest.json` có sẵn | Chỉ các file đã có trong manifest |

Tạo API key một lần (khoảng 5 phút, miễn phí, không cần màn hình xin quyền vì thư mục đã chia sẻ công khai theo liên kết):

1. Vào [console.cloud.google.com](https://console.cloud.google.com) → tạo project mới.
2. **APIs & Services → Library** → tìm *Google Drive API* → **Enable**.
3. **APIs & Services → Credentials → Create credentials → API key** → sao chép key.
4. Đặt biến môi trường rồi chạy lại ứng dụng:

```powershell
setx RAG_DRIVE_API_KEY "AIza...key-cua-ban"
```

Sau khi có key, xuất lại danh sách file dự phòng bất cứ lúc nào:

```powershell
.venv\Scripts\python.exe drive_sync.py --xuat-manifest
```

Các lệnh đồng bộ chạy tay:

```powershell
.venv\Scripts\python.exe drive_sync.py --thu
.venv\Scripts\python.exe drive_sync.py
```

## Video và âm thanh

Video được phiên âm offline bằng faster-whisper, cắt đoạn theo mốc thời gian, nên câu trả lời trích dẫn được đúng phút trong video và giao diện phát ngay tại đoạn đó.

Nên phiên âm trước khi lập chỉ mục để xem được tiến độ từng file (bản phiên âm lưu cache theo nội dung file, lần sau không làm lại):

```powershell
.venv\Scripts\python.exe phien_am_video.py
```

Tốc độ đo trên máy chỉ có CPU: nhanh hơn khoảng 4 lần thời gian thực với model `small` (video 1 phút 45 giây mất 24 giây). Muốn chính xác hơn thì dùng `--model medium`, đổi lại chậm hơn khoảng 3 lần. Nếu file media có sẵn phụ đề `.srt`/`.vtt` cùng tên đặt cạnh nó, hệ thống dùng phụ đề và bỏ qua bước phiên âm.

## PDF bản scan (OCR)

Phần lớn văn bản quy phạm trong kho là bản scan ảnh: mỗi trang chỉ có một tấm ảnh, không có lớp chữ nào để trích xuất. Những file này được nhận diện tự động và đưa qua Tesseract OCR, kết quả lưu cache theo hash nội dung nên chỉ chạy một lần cho mỗi tài liệu.

Cài một lần:

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
```

Gói ngôn ngữ tiếng Việt `vie.traineddata` đặt trong thư mục `tessdata/` của dự án. Nên dùng bản `tessdata_best` (tải từ <https://github.com/tesseract-ocr/tessdata_best>), cho dấu tiếng Việt chính xác hơn bản thường. Thư mục này không nằm trong repository, bản sao mới phải tải về.

OCR trước toàn bộ PDF scan, có tiến độ từng trang:

```powershell
.venv\Scripts\python.exe ocr_pdf.py
```

Tốc độ đo thực tế trên máy 8 lõi: khoảng 2,8 giây/trang khi chạy 6 trang song song (so với 12 giây/trang nếu chạy tuần tự). Văn bản in ra sạch, riêng phần con dấu và chữ ký nháy có thể lẫn ký tự nhiễu — đây là giới hạn chung của OCR với tài liệu hành chính đã đóng dấu.

## Hồ sơ văn bản và cảnh báo hiệu lực

Kho chứa cả văn bản cũ lẫn văn bản mới thay thế nó. Hai văn bản đó gần như giống hệt nhau về mặt ngữ nghĩa, nên một chatbot chỉ so khớp nội dung sẽ trích dẫn bản đã hết hiệu lực mà không hề biết.

Khi nạp chỉ mục, hệ thống đọc chính nội dung đã lập chỉ mục để rút ra:

- **Hồ sơ từng văn bản**: số hiệu, loại, cơ quan ban hành, ngày ban hành.
- **Quan hệ giữa các văn bản**: A thay thế / bãi bỏ / sửa đổi B.

Kết quả dùng vào ba việc: hiện số hiệu ngay trên mỗi nguồn trích dẫn, cảnh báo khi câu trả lời dựa trên văn bản đã bị thay thế hoặc sửa đổi bởi văn bản khác **có trong kho**, và hạ bậc văn bản hết hiệu lực khi xếp hạng truy hồi.

Dựng lại hồ sơ và xem thống kê:

```powershell
.venv\Scripts\python.exe van_ban_meta.py
```

Kết quả lưu ở `ho_so_van_ban.json`. Số hiệu nào hệ thống không chắc (số trong tên file khác số OCR được, hoặc bản dự thảo chưa điền số) sẽ hiện kèm dấu `(?)` thay vì khẳng định.

Ba quy tắc giúp tránh kết luận sai — đều rút ra từ dữ liệu thật của kho:

| Bẫy | Cách xử lý |
|---|---|
| Thông tư nào cũng "Căn cứ Nghị định 37/2025/NĐ-CP" | Chỉ đọc số hiệu trong khối tiêu đề, cắt trước chữ "Căn cứ" |
| Bản hợp nhất chú thích "Điều này **được** sửa đổi **theo quy định tại** Nghị định 311/2025" | Nhận ra thể bị động để không kết luận ngược chiều |
| "Nghị định số 311/2025/NĐ-CP thay thế Nghị định 71/2020" nằm trong văn bản khác | Bỏ qua khi chủ ngữ là một văn bản khác, không phải văn bản đang đọc |

## Kiểm tra câu trả lời tự động

Sau mỗi câu trả lời, hệ thống đối chiếu lại bằng chuỗi (không gọi thêm mô hình):

- Mọi số trích dẫn `[n]` phải ứng với một khối EVIDENCE có thật.
- Mọi con số trong câu trả lời phải xuất hiện trong đoạn tài liệu được đưa vào.

Nếu lệch, giao diện hiện dải cảnh báo vàng ngay dưới câu trả lời để người đọc đối chiếu lại, thay vì để thông tin sai trôi qua.
