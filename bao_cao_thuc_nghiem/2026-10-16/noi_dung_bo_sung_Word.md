# Nội dung bổ sung báo cáo sau lọc nguồn

Đo lại chế độ đầy đủ benchmark_chatbot.py trên 200 câu test, giữ model llama3.2:3b, bật bộ lọc nguồn, tắt cache trả lời và tác vụ cập nhật kho trong lượt đo.200/200 phản hồi hoàn tất hợp lệ. Bộ nhận diện tự động gắn cờ từ chối 28/30 câu ngoài phạm vi (93,3%); đọc trực tiếp toàn bộ30 câu xác nhận 27/30 từ chối hoàn toàn (90%). Trong phạm vi, 83/170 câu bị gắn cờ từ chối (48,8%); chưa đồng nghĩa mọi câu đó là từ chối oan.

Hậu kiểm cảnh báo 16/200 câu (8%), đều về số liệu; 0/200 cảnh báo chỉ mục trích dẫn. Có 10 câu dùng [n], các chỉ mục đều nằm trong phạm vi nguồn:10/10 (100%). Độ bao phủ[n] chỉ10/200 câu (5%), hoặc10/89 câu không gắn cờ từ chối (11,2%). Kiểm tra này không xác nhận ngữ nghĩa trích dẫn; không dùng0 cảnh báo để khẳng định mọi câu đều có căn cứ.

So sánh cùng model trên mẫu 50 câu cố định;30 cặp đủ căn cứ được chấm 0/1,20 cặp thiếu định danh nguồn giữ riêng. Theo đối chiếu trực tiếp của trợ lý AI, LLM gốc đúng và đủ 0/30; LLM+RAG đúng và đủ 4/30. Số câu có phát biểu thực chất sai hoặc không được nguồn đối chiếu hỗ trợ là 19/30 ở LLM gốc và 10/30 ở toàn pipeline RAG. Từ chối hoặc thiếu ý không tự động tính là ảo giác. Cần người chấm độc lập xác nhận, chưa gọi đây là chấm tay chuyên gia. Không gán điểm 30 cặp cho toàn bộ200 câu.

So với lượt RAG trước lọc nguồn, đúng và đủ giảm 6 xuống 4/30; phát biểu sai/thiếu căn cứ tăng 7 lên 10/30. Do đó chưa có bằng chứng lọc nguồn đơn lẻ cải thiện chất lượng trả lời cuối. Mẫu nhỏ, tập test đã dùng trước và model không cố định seed sinh là các giới hạn của đánh giá lặp. Nhánh RAG gồm toàn pipeline nên chưa tách riêng tác dụng của truy hồi.
