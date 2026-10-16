# Benchmark đầy đủ sau lọc nguồn — 16/10/2026

Bản xuất công khai: [bảng chấm điểm và nhận xét](bang_cham_cong_khai.csv), [phiếu chấm JSON](phieu_cham_cong_khai.json), [cấu hình và mã băm](cau_hinh_do_cong_khai.json). Các tệp đáp án nguyên văn, nguồn chuẩn và nhật ký kiểm toán được nhắc bên dưới chỉ lưu cục bộ; không nằm trong bản xuất này.

Đã hoàn tất 200/200 câu test ở chế độ đầy đủ và sinh lại 50/50 câu không RAG. Model giữ nguyên **llama3.2:3b**, embedding bge-m3, kho 111.152 vector; bộ lọc nguồn bật, cache trả lời và tác vụ tự cập nhật kho tắt trong lượt đo. Không chỉnh mã hoặc ngưỡng theo kết quả lượt test này.

**Điểm nội dung dưới đây do trợ lý AI đọc và đối chiếu trực tiếp, chưa phải chấm tay độc lập của con người.** Mọi đáp án, nguồn, điểm và nhận xét được lưu để tác giả xác nhận. Đây là đánh giá lặp trên tập test đã được xem trước, không phải holdout hoàn toàn mới.

## Kết quả đầy đủ 200 câu

| Chỉ số | Lượt trước | Sau lọc nguồn |
|---|---:|---:|
| Phản hồi hoàn tất hợp lệ |200/200|200/200|
| Ngoài phạm vi: cờ tự động nhận diện từ chối |27/30 (90.0%)|28/30 (93.3%)|
| Ngoài phạm vi: từ chối hoàn toàn sau đọc trực tiếp |25/30 (83,3%)|27/30 (90.0%)|
| Trong phạm vi: cờ tự động nhận diện từ chối |80/170 (47.1%)|83/170 (48.8%)|
| Câu có cảnh báo hậu kiểm |15/200 (7.5%)|16/200 (8.0%)|
| Câu có cảnh báo chỉ mục trích dẫn |0/200 (0.0%)|0/200 (0.0%)|
| Câu có cảnh báo số liệu |15/200 (7.5%)|16/200 (8.0%)|
| Câu có [n], mọi chỉ mục trong phạm vi nguồn |10/10 (100.0%)|10/10 (100.0%)|

Các câu bị cảnh báo ở lượt mới: **10, 11, 35, 73, 85, 88, 89, 91, 93, 97, 120, 124, 154, 160, 161, 171**. Xem `thong_ke_tu_dong.json` và từng `cau_NNN.json` để biết số nào bị gắn cờ. Cảnh báo số liệu chỉ yêu cầu đối chiếu, không tự chứng minh câu đó bịa; số thứ tự/dẫn chiếu cũng có thể bị gắn cờ.

Hậu kiểm trích dẫn chỉ nhận dạng [n], không kiểm tra tính đúng của từng phát biểu so với điều khoản nguồn. Có 10/200 câu dùng [n] (5% toàn test); trong 89 câu không gắn cờ từ chối, độ bao phủ là 10/89 (11,2%). Các cách viết như EVIDENCE 1 không được bộ hậu kiểm hiện có kiểm tra. Vì thế 100% trên 10 câu có [n] không có nghĩa 200 câu đều có trích dẫn đúng về ngữ nghĩa. Câu không có [n] vẫn mặc định qua cờ kiểm tra chỉ mục.

Cờ từ chối tự động đạt 28/30 nhưng đọc trực tiếp chỉ 27/30 từ chối hoàn toàn. Câu 50 vừa nói thiếu thông tin Montessori vừa tiếp tục cung cấp nội dung; câu 43 cung cấp mã Python; câu 65 thừa nhận thiếu thông tin nhưng vẫn liệt kê ý lạc đề. Nhãn câu Python xung đột với sách Tin học thực sự có trong kho; giữ nguyên nhãn để bảo toàn test. Chi tiết trong `doi_chieu_ngoai_pham_vi.md`.

83/170 là số câu trong phạm vi **bị gắn cờ từ chối**, chưa phải 83 từ chối oan đã xác nhận: có câu pha trộn nội dung và từ chối, có nguồn đáp án chưa đủ định danh. Không dùng chỉ số truy hồi hoặc hậu kiểm để thay cho độ đúng nội dung.

## LLM gốc so với toàn pipeline RAG

Giữ nguyên mẫu 50 câu, seed 20261015 và cùng 30 cặp đủ căn cứ như lượt trước; danh sách được đóng băng trước khi đọc đáp án mới. Sinh lại cả hai nhánh, chấm lại từng đáp án.20 cặp chưa xác nhận nguồn được giữ trong bảng 50 nhưng không tính điểm chính. Không thay mẫu theo đáp án đúng/sai.

Thang 1: đúng ý chính, đủ trả lời, không có sai sót thực chất. Thang 0: sai, thiếu ý cốt lõi hoặc từ chối khi nguồn đối chiếu có đáp án. Đánh riêng phát biểu thực chất sai/không được nguồn đối chiếu hỗ trợ; thiếu ý và từ chối không tự động là ảo giác. Chấm theo nội dung nguồn lưu trong kho, chưa phải xác minh pháp lý độc lập về hiệu lực của mọi nguồn.

| Chỉ số trên cùng 30 cặp | LLM gốc mới | LLM+RAG sau lọc | RAG lượt trước |
|---|---:|---:|---:|
| Đúng và đủ |0/30 (0.0%)|4/30 (13.3%)|6/30 (20.0%)|
| Có phát biểu sai/không được nguồn đối chiếu hỗ trợ |19/30 (63.3%)|10/30 (33.3%)|7/30 (23.3%)|
| Từ chối hoàn toàn |2/30 (6.7%)|11/30 (36.7%)|10/30 (33,3%)|

Theo điểm 0/1, RAG tốt hơn ở 4 cặp và kém hơn ở 0 cặp. Không suy độ đúng của 30 câu thành độ đúng toàn 200 câu. Các câu đúng vẫn có thể dài hoặc chép thêm đoạn lạc đề; lỗi trình bày được ghi riêng.

**Câu hỏi nghiên cứu RAG có giảm ảo giác không:** trên mẫu đối chiếu hiện tại, toàn pipeline RAG có 10/30 câu có phát biểu sai/thiếu căn cứ, so với 19/30 ở LLM gốc. Chênh lệch là 30.0 điểm phần trăm. Đây là bằng chứng sơ bộ do AI đối chiếu trên mẫu nhỏ; pipeline còn gồm cổng chặn, quản lý hiệu lực và công cụ, nên chưa tách được riêng tác dụng truy hồi.

**So với chính RAG lượt trước, lọc nguồn chưa cho thấy cải thiện chất lượng trả lời:** điểm đúng giảm 6 xuống 4/30; câu có phát biểu sai/thiếu căn cứ tăng 7 lên 10/30. Không được chỉ đưa kết quả lọc nguồn dev tốt hơn để kết luận tỉ lệ ảo giác test đã giảm. Lượt sinh không cố định seed model, nên khác biệt còn có biến động sinh; chưa đủ để quy toàn bộ chênh lệch cho bộ lọc. Không thay model hoặc tinh chỉnh tiếp trên test trong lượt này.

Ví dụ còn sai: gọi Khung trình độ quốc gia là 9 bậc 0–8 thay vì 8 bậc; dùng kỷ luật sinh viên để trả lời kỷ luật học sinh; ghép quy định quản lý văn bằng vào Thông tư sửa quy chế thi. Câu về nền tảng số giáo dục quốc gia, Tháng hành động vì trẻ em, hỗ trợ doanh nghiệp đào tạo và chuyên ngành điện hạt nhân trả lời đủ ý chính theo nguồn lưu. Xem lý do từng điểm trong bảng chấm.

## Kiểm soát lượt chạy và hồ sơ

Mã nguồn, cấu hình và hai tệp chỉ mục có SHA256 trước/sau khớp. Digest model sinh và embedding được kiểm tra khi tiếp tục.145 câu đầu đã lưu trước gián đoạn được giữ nguyên. Bản cập nhật Ollama toàn máy lên 0.40.5 lúc 12:43 làm thiếu llama-server.exe; 54 lượt lỗi hạ tầng được giữ riêng trong `loi_ha_tang/cap_nhat_ollama_1257`, không tính là đáp án hay từ chối đúng. Một câu qua cổng chặn không cần model vẫn hoàn tất và được giữ. Chỉ sinh lại các câu chưa hoàn tất.

Đã phục hồi [runtime chính thức 0.40.4](https://github.com/ollama/ollama/releases/tag/v0.40.4), cùng phiên bản nhật ký trước gián đoạn, trong `.runtime/ollama-0.40.4` trên cổng 11435. Không cài đè dịch vụ toàn máy, không tải lại/đổi trọng số model. Hồ sơ tải từng thành phần và SHA256 nằm ở `provenance.json` của runtime. Thay đổi cổng và lịch sử tiếp tục được ghi trong `manifest.json`; tham số sinh còn lại giữ nguyên. Thời gian trung bình 47,92 giây/câu phản ánh các lượt hoàn tất, không gồm thời gian gián đoạn/khôi phục và không phải phép so tốc độ được kiểm soát riêng.

- `ket_qua_benchmark_day_du_test.json`: đủ 200 câu mới.
- `ket_qua_llm_khong_rag.json`: đủ 50 đối chứng mới.
- `bang_cham_50_cau.csv`, `phieu_cham_50_cau.json`: nguyên văn đáp án, điểm, lý do và nguồn.
- `nguon_chuan_50_cau/`: nguồn đáp án đối chiếu theo nhãn, độc lập nguồn truy hồi.
- `thong_ke_tu_dong.json`, `thong_ke_cham_50_cau.json`: số liệu có thể kiểm tra lại.
- `doi_chieu_30_ngoai_pham_vi.json`: đủ 30 phán định từ chối.
- `noi_dung_bo_sung_Word.md`: nội dung để bổ sung báo cáo; chưa sửa tệp Word gốc.

Kết quả lượt trước được giữ riêng, không ghi đè báo cáo lịch sử. Cần tác giả/người chấm độc lập xác nhận bảng điểm trước khi gọi đây là kết quả chấm tay chính thức.
