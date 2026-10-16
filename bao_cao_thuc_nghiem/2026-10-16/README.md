# Thực nghiệm sau lọc nguồn — 16/10/2026

Đã chạy chế độ đầy đủ trên 200 câu test và sinh lại 50 đáp án không RAG,
giữ model llama3.2:3b và embedding bge-m3. Mẫu 50 câu giữ nguyên như lượt
trước; 30 cặp đủ căn cứ được chấm, 20 cặp chưa xác nhận nguồn giữ riêng.

**Phần chấm nội dung do trợ lý AI đọc và đối chiếu trực tiếp, chưa có người
chấm độc lập xác nhận.** Đây là đánh giá lặp trên tập test đã từng xem.

| Kết quả | Sau lọc nguồn |
|---|---:|
| Phản hồi hoàn tất hợp lệ | 200/200 |
| Từ chối hoàn toàn câu ngoài phạm vi, sau đọc trực tiếp | 27/30 (90%) |
| Câu có cảnh báo hậu kiểm | 16/200 (8%) |
| Câu có cảnh báo chỉ mục trích dẫn | 0/200 |
| Câu dùng `[n]`, mọi chỉ mục trong phạm vi nguồn | 10/10 |
| Độ bao phủ `[n]` trên toàn test | 10/200 (5%) |
| Đúng và đủ: LLM gốc → toàn pipeline RAG | 0/30 → 4/30 |
| Có phát biểu sai/thiếu căn cứ: LLM gốc → RAG | 19/30 → 10/30 |

So với RAG lượt trước lọc nguồn, số câu đúng và đủ giảm 6 xuống 4/30,
câu có phát biểu sai/thiếu căn cứ tăng 7 lên 10/30. **Chưa có bằng chứng
lọc nguồn đơn lẻ cải thiện chất lượng câu trả lời cuối.** Mẫu nhỏ, biến động
sinh và việc đánh giá cả pipeline hạn chế kết luận nhân quả.

## Hồ sơ công khai

- [Báo cáo đầy đủ](bao_cao_ket_qua_cuoi.md).
- [Bảng điểm và nhận xét 50 câu — CSV](bang_cham_cong_khai.csv).
- [Phiếu chấm và quy tắc — JSON](phieu_cham_cong_khai.json).
- [Nội dung bổ sung Word](noi_dung_bo_sung_Word.md); tệp Word gốc chưa được sửa.
- [Đọc trực tiếp 30 câu ngoài phạm vi](doi_chieu_ngoai_pham_vi.md).
- [Số liệu tự động 200 câu](thong_ke_tu_dong.json).
- [Tổng hợp điểm đối chiếu](thong_ke_cham_50_cau.json).
- [Cấu hình, digest model và SHA256](cau_hinh_do_cong_khai.json).
- [Kiểm kho và kết quả 50 câu dev](bao_cao_lam_sach_kho.md).
- [Số liệu tự động trước lọc](thong_ke_tu_dong_truoc_loc.json),
  [điểm đối chiếu trước lọc](thong_ke_cham_truoc_loc.json).

Không diễn giải 100% chỉ mục hợp lệ trên 10 câu có `[n]` thành mọi phát biểu
đều có căn cứ. Hậu kiểm hiện có chỉ kiểm tra chỉ mục và sự xuất hiện của số,
không xác minh ngữ nghĩa. Từ chối hoặc thiếu ý không tự động là ảo giác.

## Dữ liệu chỉ lưu cục bộ

Đáp án nguyên văn, các đoạn nguồn đưa vào prompt, nguồn chuẩn, bảng kiểm kho
theo từng tệp, hồ sơ lỗi hạ tầng và cấu hình riêng không được đưa lên GitHub.
Các tên tệp nhật ký được nhắc trong báo cáo là tài liệu kiểm toán trên máy
thực nghiệm. Bảng công khai giữ câu hỏi, điểm và nhận xét, không chứa nội dung
tài liệu nguồn đầy đủ hoặc nguyên văn các đáp án.

Các công cụ chạy và tổng hợp nằm ở thư mục gốc của repository. Để tái lập cần
có kho và chỉ mục tương ứng, model cục bộ, cùng dữ liệu nhật ký khi chấm lại;
bản repository công khai không tự chứa toàn bộ dữ liệu thực nghiệm. Các công
cụ lưu theo tên thư mục lượt đo và chặn ghi đè manifest đã có.

54 lượt lỗi hạ tầng do cập nhật Ollama được giữ riêng, không tính là câu trả
lời hoặc từ chối đúng. Chỉ sinh lại câu chưa hoàn tất bằng runtime chính thức
0.40.4, giữ nguyên digest model sinh và embedding. Chi tiết trong báo cáo.
