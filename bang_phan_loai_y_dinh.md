# Bộ phân loại ý định câu hỏi (KNN)

Đo lúc 2026-10-06 20:21 · model nhúng `bge-m3` · 482 câu train · 202 câu test · k = 7.
Sinh bởi `python phan_loai_y_dinh.py danh_gia`; tập test là câu thật (bộ benchmark, lịch sử chat, câu trong test của các công cụ tính), không trùng câu nào với tập train.

## Chọn k (kiểm định chéo bỏ-một trên tập train)

| k | 3 | 5 | 7 | 9 | 11 | 15 |
|---|---|---|---|---|---|---|
| macro-F1 | 0,947 | 0,943 | 0,954 | 0,950 | 0,944 | 0,940 |

## Kết quả trên tập test

Accuracy **0,896** · macro-F1 **0,865**

| Nhãn | Precision | Recall | F1 | Số câu |
|---|---|---|---|---|
| Tra cứu văn bản, quy định | 0,957 | 0,902 | 0,929 | 123 |
| Tính lương | 0,615 | 1,000 | 0,762 | 8 |
| Định mức tiết dạy | 0,706 | 0,923 | 0,800 | 13 |
| Đánh giá, xếp loại học sinh | 0,600 | 1,000 | 0,750 | 6 |
| Tính toán | 1,000 | 1,000 | 1,000 | 11 |
| Chào hỏi | 1,000 | 1,000 | 1,000 | 11 |
| Ngoài phạm vi | 0,917 | 0,733 | 0,815 | 30 |

Theo nguồn câu hỏi: benchmark: 0,882 (127 câu) · lich_su_chat: 1,000 (11 câu) · test_cong_cu: 0,889 (54 câu) · tu_soan_test: 1,000 (10 câu)

### Ma trận nhầm lẫn (hàng: nhãn thật, cột: nhãn đoán)

| | Tra cứu văn bản, quy định | Tính lương | Định mức tiết dạy | Đánh giá, xếp loại học sinh | Tính toán | Chào hỏi | Ngoài phạm vi |
|---|---|---|---|---|---|---|---|
| Tra cứu văn bản, quy định | 111 | 3 | 5 | 2 | 0 | 0 | 2 |
| Tính lương | 0 | 8 | 0 | 0 | 0 | 0 | 0 |
| Định mức tiết dạy | 0 | 1 | 12 | 0 | 0 | 0 | 0 |
| Đánh giá, xếp loại học sinh | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| Tính toán | 0 | 0 | 0 | 0 | 11 | 0 | 0 |
| Chào hỏi | 0 | 0 | 0 | 0 | 0 | 11 | 0 |
| Ngoài phạm vi | 5 | 1 | 0 | 2 | 0 | 0 | 22 |

## Ngưỡng tự hành động

Câu được đoán là ngoài phạm vi / chào hỏi với độ tin cậy từ ngưỡng trở lên thì được trả lời ngay, không qua truy hồi và mô hình ngôn ngữ. Cột *nhầm* là số câu lẽ ra phải đi đường thường mà bị chặn - cần bằng 0. Dấu * là ngưỡng đang dùng.

| Ngưỡng | Chặn ngoài phạm vi đúng | Chặn nhầm | Đáp lời chào đúng | Đáp nhầm |
|---|---|---|---|---|
| 0,5 | 22/30 | 1 | 11/11 | 0 |
| 0,6 | 20/30 | 0 | 11/11 | 0 |
| 0,7 | 20/30 * | 0 | 11/11 | 0 |
| 0,8 | 17/30 | 0 | 11/11 | 0 |
| 0,9 | 11/30 | 0 | 11/11 * | 0 |
| 1,0 | 11/30 | 0 | 11/11 | 0 |

## So sánh với mô hình khác (cùng tập train/test)

| Mô hình | Accuracy | macro-F1 |
|---|---|---|
| KNN tự cài k=7 (bge-m3, phiếu theo độ tương đồng) | 0,896 | 0,865 |
| Logistic Regression (bge-m3) | 0,931 | 0,927 |
| SVM tuyến tính (bge-m3) | 0,946 | 0,941 |
| Naive Bayes Gauss (bge-m3) | 0,871 | 0,873 |
| KNN của scikit-learn k=7 (bge-m3, đối chứng) | 0,896 | 0,865 |
| KNN k=7 (TF-IDF n-gram ký tự) | 0,866 | 0,837 |
| Naive Bayes đa thức (TF-IDF từ) | 0,896 | 0,879 |

## Câu đoán sai trên tập test

| Câu hỏi | Nhãn thật | Đoán | Tin cậy |
|---|---|---|---|
| Tiêu chuẩn thăng hạng giáo viên THPT hạng II là gì? | Tra cứu văn bản, quy định | Tính lương | 0,560 |
| Giáo viên THPT hạng III cần trình độ đào tạo như thế nào? | Tra cứu văn bản, quy định | Tính lương | 0,862 |
| trách nhiệm của giáo viên chủ nhiệm | Tra cứu văn bản, quy định | Định mức tiết dạy | 0,571 |
| giáo viên hạng II hệ số lương bao nhiêu | Tra cứu văn bản, quy định | Tính lương | 1,000 |
| tiết dạy của GV THPT cấp 3 | Định mức tiết dạy | Tính lương | 0,573 |
| điểm trung bình môn tính ra sao | Tra cứu văn bản, quy định | Đánh giá, xếp loại học sinh | 1,000 |
| Thời khóa biểu học phần 3 lớp cao học khóa 35 học trong khoảng thời gian nào? | Tra cứu văn bản, quy định | Định mức tiết dạy | 0,438 |
| Lịch học học phần 3 khóa 35 có bao nhiêu buổi mỗi tuần? | Tra cứu văn bản, quy định | Định mức tiết dạy | 0,858 |
| Phân phối chương trình Tin học lớp 5 dành bao nhiêu tiết cho bài Cây thư mục? | Tra cứu văn bản, quy định | Định mức tiết dạy | 0,555 |
| Ma trận đặc tả đề kiểm tra lớp 4 theo chủ đề gồm những mức độ nào? | Tra cứu văn bản, quy định | Đánh giá, xếp loại học sinh | 0,673 |
| Phân phối chương trình lớp 3 chia thành bao nhiêu tuần học? | Tra cứu văn bản, quy định | Định mức tiết dạy | 0,857 |
| Bài phần cứng và phần mềm máy tính phân biệt hai khái niệm này thế nào? | Tra cứu văn bản, quy định | Ngoài phạm vi | 0,579 |
| Bài gõ bàn phím đúng cách hướng dẫn đặt tay ra sao? | Tra cứu văn bản, quy định | Ngoài phạm vi | 0,441 |
| Giá thuê chung cư hai phòng ngủ ở quận Cầu Giấy khoảng bao nhiêu? | Ngoài phạm vi | Tính lương | 0,852 |
| Hệ thống giáo dục của Phần Lan tổ chức các cấp học như thế nào? | Ngoài phạm vi | Tra cứu văn bản, quy định | 1,000 |
| Điểm chuẩn ngành Y đa khoa Đại học Y Hà Nội năm 2025 là bao nhiêu? | Ngoài phạm vi | Đánh giá, xếp loại học sinh | 0,717 |
| Kỳ thi IELTS có mấy kỹ năng và thang điểm tính thế nào? | Ngoài phạm vi | Đánh giá, xếp loại học sinh | 0,854 |
| Chương trình giáo dục phổ thông của Singapore khác gì chương trình của Nhật Bản? | Ngoài phạm vi | Tra cứu văn bản, quy định | 1,000 |
| Học phí trường quốc tế tại Thành phố Hồ Chí Minh trung bình bao nhiêu một năm? | Ngoài phạm vi | Tra cứu văn bản, quy định | 0,438 |
| Phương pháp Montessori trong giáo dục mầm non có những nguyên tắc nào? | Ngoài phạm vi | Tra cứu văn bản, quy định | 0,858 |
| Lịch nghỉ Tết Nguyên đán của học sinh Hà Nội năm nay bắt đầu từ ngày nào? | Ngoài phạm vi | Tra cứu văn bản, quy định | 0,572 |
