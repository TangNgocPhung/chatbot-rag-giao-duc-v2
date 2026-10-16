# Kết quả lọc nguồn và làm sạch kho — 16/10/2026

Đã bật lọc nguồn mặc định trong dịch vụ RAG, giữ nguyên model. Làm sạch bằng cách ly khỏi truy hồi; không xóa bản gốc, không ghi lại chỉ mục FAISS. Thay đổi áp dụng khi khởi động tiến trình ứng dụng mới.

## Kiểm kho

| Trạng thái tự động | Số tệp |
| --- | ---: |
| Đủ điều kiện qua bộ lọc hiện tại | 1.127 |
| Dự thảo | 67 |
| Cần xác minh thông tin ban hành | 90 |
| Bản trùng nội dung | 3 |
| Tổng | 1.287 |

Danh sách và lý do theo từng tệp nằm trong `danh_sach_kiem_kho.csv` và `danh_muc_nguon.json` cùng thư mục. Đây là phân loại tự động theo nội dung đã trích xuất, không phải xác nhận pháp lý hoặc xác thực chữ ký số. Quy ước tên `.signed` cũ vẫn được giữ; nguồn OCR hỏng cần kiểm tra riêng.

## Các lỗi đã xử lý

- Không lấy số hiệu từ tên tệp để lấp ô trống trong phần đầu văn bản hành chính.
- Cách ly dự thảo và nguồn cần xác minh khỏi câu hỏi thông thường; vẫn cho tìm dự thảo khi câu hỏi yêu cầu rõ.
- Gộp bản trùng có cùng tập nội dung đoạn sau chuẩn hóa, giữ một bản chuẩn để truy hồi.
- Chặn nguồn mâu thuẫn rõ về cấp học, môn và lớp; dùng tiêu đề thực trong nội dung khi tên tệp thiếu thông tin.
- Chặn nguồn chưa tới ngày hiệu lực theo mốc thời gian câu hỏi, trừ câu hỏi yêu cầu tìm nguồn tương lai/dự thảo rõ ràng.
- Áp dụng lọc trước khi chọn các kết quả cuối; kiểm tra cả nguồn được kéo vào theo quan hệ văn bản. Văn bản hướng dẫn phải phù hợp chủ đề; quan hệ sửa đổi bắt buộc vẫn được giữ nếu nguồn qua kiểm tra trạng thái/ngày.
- Đổi dấu nhận diện bộ nhớ đệm theo chính sách và danh mục nguồn, tránh dùng lại câu trả lời từ nguồn vừa cách ly.
- Tránh nhận nhầm sách/bài tập có mẫu để trống hoặc trích dẫn thông tư thành một dự thảo hành chính.

## Đối chiếu trên 50 câu dev

Lấy ngẫu nhiên cố định 50 câu có nhãn nguồn từ tập dev, seed `20261016`. So bật/tắt bộ lọc trên cùng dịch vụ và cùng hồ sơ nguồn mới. Không gọi model sinh câu trả lời, không đo lại tập test và không sửa mã trong suốt lượt đo (đã đối chiếu SHA256 trước/sau).

| Chỉ số | Tắt bộ lọc | Bật bộ lọc |
| --- | ---: | ---: |
| Câu có ít nhất một nguồn bị chính sách gắn cờ trong ngữ cảnh, kể cả nguồn đi kèm | 30/50 | 0/50 |
| Số lượt đoạn nguồn bị gắn cờ trong ngữ cảnh | 72 | 0 |
| Tìm trúng nhãn nguồn trên 32 câu có nguồn nhãn đủ điều kiện sử dụng | 28/32 (87,5%) | 29/32 (90,6%) |
| Tìm trúng nhãn nguồn trên toàn bộ 50 câu | 44/50 | 29/50 |

Không có lỗi thực thi. Trong nhóm 32 câu đủ điều kiện, không có câu đang tìm trúng trở thành trượt; một câu chuyển từ trượt thành trúng. Nhóm 18 câu còn lại không có nguồn khớp nhãn thỏa đồng thời trạng thái sử dụng và điều kiện hiệu lực hiện có. Vì thế chỉ số toàn mẫu giảm khi cách ly nguồn không đủ điều kiện; không được diễn giải nó như chất lượng trả lời tổng thể. Nhãn nguồn cũng chưa được xác minh pháp lý độc lập.

Kết quả 0/50 phản ánh việc tuân thủ chính sách lọc của chính bộ kiểm tra này; không chứng minh mọi nguồn còn lại đều đúng chủ đề hay mọi phát biểu đều đúng. So sánh bật/tắt cũng không phải chạy lại nguyên trạng phiên bản lịch sử trước thay đổi hồ sơ nguồn.

Dữ liệu chi tiết: `doi_chieu_50_dev.json`; tổng hợp: `tong_ket_50_dev.json`; dấu phiên bản: `phien_ban_do_dev.json`.

## Kiểm thử và giới hạn

210 kiểm thử và 19 kiểm thử con đạt, gồm bộ lọc nguồn, siêu dữ liệu văn bản, hiệu lực, quan hệ văn bản, truy hồi, phân loại và bộ nhớ đệm. Có một cảnh báo ngừng hỗ trợ thư viện có sẵn.

Chưa đo lại tỉ lệ ảo giác của câu trả lời sau thay đổi, nên chưa thể khẳng định con số 7/30 trước đây đã giảm. Các kết quả benchmark lịch sử được giữ nguyên. Vẫn cần rà soát thủ công 90 nguồn cần xác minh, xử lý lỗi OCR và bổ sung quan hệ hiệu lực còn thiếu; bộ lọc không thay thế các việc đó.

Có thể tái lập kiểm kho bằng `lam_sach_kho.py`, đối chiếu dev bằng `do_loc_nguon_dev.py`. Cờ `RAG_LOC_NGUON=0` cho phép tắt bộ lọc để đối chiếu; mặc định là bật.
