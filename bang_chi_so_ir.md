# Chỉ số IR/QA của khối truy hồi

Đo ngày 27/09/2026 trên 97 câu hỏi có nhãn nguồn, kho 30432 vector, truy hồi sâu 24 chunk (4 chunk đi vào prompt).

| Nhóm câu hỏi | Số câu | MRR | Hit@1 | Hit@3 | Hit@5 | Hit@10 | nDCG@10 |
|---|---|---|---|---|---|---|---|
| bang_excel | 8 | 0.699 | 62.5% | 62.5% | 87.5% | 100.0% | 0.704 |
| chinh_sach_pdf | 50 | 0.890 | 88.0% | 90.0% | 90.0% | 90.0% | 0.893 |
| tai_lieu_docx | 14 | 0.821 | 78.6% | 85.7% | 85.7% | 85.7% | 0.776 |
| trinh_chieu | 14 | 0.595 | 42.9% | 78.6% | 78.6% | 78.6% | 0.610 |
| van_ban_doc | 6 | 0.889 | 83.3% | 100.0% | 100.0% | 100.0% | 0.917 |
| video | 5 | 0.467 | 40.0% | 60.0% | 60.0% | 60.0% | 0.423 |
| **Toàn bộ** | 97 | 0.800 | 75.3% | 84.5% | 86.6% | 87.6% | 0.797 |

MRR@10 = 0.800, khoảng tin cậy 95% (bootstrap) 0.723 – 0.871. Trong cửa sổ 4 chunk thực sự đi vào prompt, 85% câu có tài liệu đúng.

Lưu ý khi đọc Hit@10: sau khử trùng nội dung và giới hạn 2 chunk mỗi nguồn, mỗi lượt chỉ còn trung bình 9.6 tài liệu riêng biệt - Hit@10 vì thế gần như đã chạm trần cấu trúc của rổ ứng viên, không phải trần chất lượng xếp hạng.
