# Chương 3. Thực nghiệm và đánh giá

> **Bản khung.** Phương pháp, bộ dữ liệu và chỉ số dưới đây đã viết xong và khớp với mã nguồn hiện tại. Các ô **[điền]** chờ số liệu của lần đo cuối cùng: chạy `benchmark_chatbot.py --ir --tap test` và `--nhanh --tap test` **một lần** sau khi đã đóng băng tham số (mục 3.4), rồi chép số từ `bang_chi_so_ir_test.md` và màn hình tổng kết. Số chương có thể cần đổi cho khớp mục lục của đề án.

Chương này trả lời ba câu hỏi về hệ thống đã xây dựng ở chương 2. Thứ nhất, khối truy hồi có đưa đúng tài liệu chứa câu trả lời lên đầu danh sách hay không. Thứ hai, cổng chặn lạc đề có từ chối đúng những câu hỏi mà kho tài liệu không trả lời được, đồng thời không từ chối oan câu hỏi hợp lệ hay không. Thứ ba, câu trả lời do mô hình ngôn ngữ sinh ra có trích dẫn hợp lệ và có số liệu bám sát nguồn hay không. Ba câu hỏi tương ứng với ba tầng của pipeline và được đo bằng ba nhóm chỉ số khác nhau, vì một hệ thống RAG có thể hỏng ở tầng này trong khi các tầng còn lại vẫn đúng.

## 3.1. Bộ dữ liệu đánh giá

### 3.1.1. Cấu trúc và cách gán nhãn

Bộ câu hỏi đánh giá nằm trong tệp `bo_cau_hoi_benchmark.json`, gồm 280 câu hỏi tiếng Việt chia thành tám nhóm theo loại tài liệu nguồn. Mỗi câu hỏi mang một trong hai loại nhãn. Câu hỏi **trong phạm vi** mang trường `nguon_mong_doi`: danh sách các chuỗi là một phần tên tệp của tài liệu chứa câu trả lời. Một tài liệu được coi là đúng khi tên tệp của nó chứa chuỗi nhãn, so khớp không phân biệt hoa thường. Câu hỏi **ngoài phạm vi** mang trường `mong_doi_tu_choi`: kho không có câu trả lời, hệ thống phải nói không tìm thấy thay vì tự bịa.

Nhóm ngoài phạm vi được xây dựng có chủ đích gồm hai loại. Loại thứ nhất là câu lạc đề hoàn toàn (giá vàng, thời tiết, công thức nấu ăn), dùng để kiểm tra trường hợp dễ. Loại thứ hai là câu **gần phạm vi**: dùng đúng từ vựng của kho tài liệu giáo dục nhưng hỏi điều kho không có, chẳng hạn điểm chuẩn của một trường cụ thể hay lương giáo viên ở nước ngoài. Loại câu thứ hai mới đo được cổng chặn có bị nới quá tay hay không, vì một câu hỏi khớp nhiều từ khóa với kho sẽ vượt qua được các tín hiệu từ vựng đơn giản.

**Bảng 3.1. Phân bố bộ câu hỏi đánh giá**

| Nhóm | Loại tài liệu nguồn | Tổng | Dev | Test | Thêm sau khi chia |
|---|---|---|---|---|---|
| `chinh_sach_pdf` | Văn bản quy phạm, chính sách (PDF) | 98 | 59 | 39 | 48 |
| `trinh_chieu` | Bài giảng trình chiếu (PPTX) | 32 | 19 | 13 | 18 |
| `tai_lieu_docx` | Giáo án, ma trận đề, sổ tay (DOCX) | 29 | 17 | 12 | 15 |
| `van_ban_doc` | Văn bản định dạng Word cũ (DOC) | 24 | 14 | 10 | 18 |
| `bang_excel` | Thời khóa biểu, bảng biểu (XLSX) | 17 | 10 | 7 | 9 |
| `sach_giao_khoa` | Sách giáo khoa, sách giáo viên (PDF) | 17 | 10 | 7 | 17 |
| `video` | Video bài giảng có lời thoại (MP4) | 9 | 5 | 4 | 4 |
| `ngoai_pham_vi` | Không có trong kho | 54 | 32 | 22 | 24 |
| **Tổng** | | **280** | **166** | **114** | **153** |

Có 226 câu trong phạm vi, cùng nhắm tới 117 tài liệu khác nhau (đếm theo nhãn đầu tiên của mỗi câu). Trước khi đo, toàn bộ nhãn được đối chiếu tự động với kho bằng `kiem_tra_nhan_benchmark.py`. Script báo những nhãn không khớp tệp nào, những tệp có trên đĩa nhưng chưa được lập chỉ mục, và những nhãn khớp quá nhiều tệp. Bước kiểm tra này tách lỗi gán nhãn ra khỏi lỗi truy hồi: một nhãn gõ sai sẽ làm câu hỏi luôn bị chấm trượt, và nếu không kiểm tra trước thì lỗi đó bị tính nhầm thành chất lượng truy hồi kém.

### 3.1.2. Chia tập dev và tập test

Hệ thống không huấn luyện hay tinh chỉnh trọng số của mô hình nào, nhưng vẫn có tham số được **chọn theo kết quả đo**: trọng số của bộ xếp hạng lại, ngưỡng của cổng chặn lạc đề và số đoạn bằng chứng đưa vào prompt. Chọn tham số trên bộ câu hỏi nào thì điểm đo trên chính bộ đó là ước lượng lạc quan. Vì vậy bộ câu hỏi được chia thành hai tập, đóng vai trò tương tự tập validation và tập test trong học máy. Tập **dev** dùng để thử và chọn tham số, chạy bao nhiêu lần cũng được. Tập **test** chỉ được chạy một lần, sau khi tham số đã đóng băng, và chỉ số liệu trên tập test được dùng để kết luận.

Việc chia tập do `chia_tap_benchmark.py` thực hiện, theo ba nguyên tắc. Thứ nhất, **phân tầng theo nhóm**: mỗi nhóm góp khoảng 40% số câu vào tập test. Tỷ lệ 40% thay vì 20–30% thông thường là vì bộ câu hỏi nhỏ; với tỷ lệ 20%, nhóm video chỉ còn một câu test và Hit@1 của nhóm chỉ nhận được hai giá trị 0% hoặc 100%. Thứ hai, **tất định**: hạt giống ngẫu nhiên cố định, nên chạy lại cho đúng kết quả cũ. Thứ ba, **câu đã gán tập không bao giờ đổi tập**, vì chuyển một câu từ test sang dev sau khi đã thấy kết quả test chính là rò rỉ thông tin.

Với các câu thêm vào sau khi chia, một nguyên tắc nữa được áp dụng: câu nào hỏi cùng một điều khoản, hoặc cùng một bài hay một chương, với một câu đã có thì được xếp vào **cùng tập** với câu đó. Hai câu cùng trúng một đoạn văn bản có kết quả tương quan chặt. Nếu một câu nằm ở dev và câu kia ở test, việc tinh chỉnh trên câu dev sẽ ngầm nâng điểm câu test. Nguyên tắc này cùng tinh thần với cách chia theo nhóm (group split) trong học máy.

## 3.2. Các chỉ số đánh giá

### 3.2.1. Chỉ số xếp hạng của khối truy hồi

Khối truy hồi được đo ở mức **tài liệu**: danh sách đoạn văn trả về được khử trùng theo tên tệp trước khi xét thứ hạng, nên hai đoạn văn của cùng một tệp chỉ chiếm một hạng. Gọi Q là tập câu hỏi có nhãn và rank_q là hạng của tài liệu đúng đầu tiên với câu q. Các chỉ số được tính trong `chi_so_ir.py`:

- **MRR@10** (Mean Reciprocal Rank) = (1/|Q|) Σ 1/rank_q, trong đó số hạng bằng 0 nếu rank_q > 10. Chỉ số chính, phản ánh tài liệu đúng được xếp gần đầu đến mức nào.
- **Hit@K**: tỷ lệ câu hỏi có ít nhất một tài liệu đúng trong K kết quả đầu, với K ∈ {1, 3, 5, 10}.
- **Recall@K**: tỷ lệ nhãn tìm được trong top-K, trung bình trên các câu hỏi. Chỉ khác Hit@K ở những câu có nhiều hơn một tài liệu đúng.
- **nDCG@10**: lợi ích tích lũy có chiết khấu log₂(hạng + 1), chuẩn hóa về [0, 1], với mức liên quan nhị phân.
- **MAP@10**: trung bình precision tại mỗi vị trí có tài liệu đúng. Khác MRR ở chỗ phạt việc tìm ra tài liệu đúng thứ hai quá muộn.

Khi đo xếp hạng, hệ thống truy hồi sâu 24 đoạn văn, nhiều hơn 4 đoạn thực sự đưa vào prompt, để biết tài liệu đúng nằm ở hạng nào kể cả khi nó rơi khỏi cửa sổ prompt. Chỉ số bổ sung "tỷ lệ câu có tài liệu đúng trong cửa sổ 4 đoạn" phản ánh trải nghiệm thật của người dùng.

### 3.2.2. Chỉ số của cổng chặn lạc đề

Cổng chặn được đánh giá như một bộ phân loại nhị phân, với hai chỉ số báo cáo riêng:

- **Tỷ lệ chặn đúng**: tỷ lệ câu ngoài phạm vi bị chặn (tương tự recall của lớp "từ chối").
- **Tỷ lệ từ chối oan**: tỷ lệ câu trong phạm vi bị chặn nhầm (tỷ lệ dương tính giả).

Hai chỉ số này không được gộp thành một "độ chính xác chung". Lý do: một hệ thống từ chối mọi câu hỏi vẫn đạt độ chính xác bằng tỷ lệ câu ngoài phạm vi trong bộ đề (54/280 ≈ 19%), và độ chính xác chung che mất sự đánh đổi giữa hai loại lỗi. Khi chọn ngưỡng, hai ngưỡng được hiệu chỉnh là `RAG_DO_PHU_IDF_TOI_THIEU` (độ phủ từ khóa có trọng số IDF) và `RAG_KHOANG_CACH_DENSE_TOI_DA` (khoảng cách vector nhỏ nhất). Điểm được chọn là điểm còn chừa biên an toàn với câu hợp lệ khó nhất, chứ không phải điểm chặn được nhiều nhất.

### 3.2.3. Chỉ số chất lượng câu trả lời

Ở chế độ đầy đủ (`--bo`), hệ thống gọi mô hình ngôn ngữ cho từng câu hỏi và đo thêm hai chỉ số tự động. **Trích dẫn hợp lệ** kiểm tra mọi ký hiệu [n] trong câu trả lời có ứng với một đoạn bằng chứng thật hay không. **Số liệu có căn cứ** kiểm tra mọi con số trong câu trả lời có xuất hiện nguyên văn trong đoạn được trích hay không. Hai chỉ số này đo hiện tượng ảo giác ở mức có thể kiểm chứng máy móc, nhưng không đo được câu trả lời có trả lời đúng ý câu hỏi hay không. Phần đó cần chấm tay (mục 3.6).

### 3.2.4. Khoảng tin cậy

Bộ câu hỏi có quy mô hàng trăm câu, nên chênh lệch vài điểm phần trăm giữa hai cấu hình thường nằm trong sai số lấy mẫu. MRR được báo cáo kèm khoảng tin cậy 95% bằng phương pháp bootstrap (2000 lần lấy mẫu lại, phân vị 2,5% và 97,5%) theo hai cách. Cách thứ nhất lấy mẫu lại **theo câu hỏi**. Cách thứ hai lấy mẫu lại **theo tài liệu** (cluster bootstrap), trong đó mỗi lần bốc nguyên một cụm gồm mọi câu hỏi cùng nhắm tới một tài liệu. Các câu hỏi cùng một tài liệu không độc lập: tài liệu được chia đoạn tốt thì cả loạt câu cùng trúng, chia hỏng thì cả loạt cùng trượt. Khoảng theo tài liệu vì thế rộng hơn và phản ánh trung thực hơn độ bất định, nên đây là khoảng được dùng để kết luận.

## 3.3. Thiết lập thực nghiệm

**Bảng 3.2. Cấu hình hệ thống khi đo**

| Thành phần | Giá trị |
|---|---|
| Phần cứng | **[điền: CPU, RAM, có/không GPU]** |
| Mô hình nhúng | bge-m3 (1024 chiều), qua Ollama |
| Mô hình sinh câu trả lời | qwen3.5:4b, temperature 0,15, num_ctx 4096 |
| Kho tri thức | **[điền: số tệp, số vector tại lần đo]** |
| Chia đoạn | 1200 ký tự, chồng lấn 150 ký tự, ưu tiên ranh giới Điều |
| Truy hồi | FAISS + BM25, hợp nhất bằng RRF (k = 60), xếp hạng lại |
| Trọng số xếp hạng lại | nội dung 0,025; tên tài liệu 0,035; tên tài liệu theo IDF 0,040 |
| Giới hạn | tối đa 2 đoạn mỗi tài liệu; 4 đoạn vào prompt; 24 đoạn khi đo IR |
| Ngưỡng cổng chặn | tỷ lệ từ lạ ≤ 0,30; độ phủ IDF ≥ 0,60; khoảng cách dense ≤ 1,00 |

## 3.4. Quy trình thực nghiệm

Thực nghiệm tuân theo trình tự cố định để số liệu trên tập test không bị ảnh hưởng bởi việc chọn tham số:

1. Đối chiếu nhãn với kho bằng `kiem_tra_nhan_benchmark.py`; sửa hoặc loại các câu có nhãn hỏng.
2. Tinh chỉnh tham số **chỉ trên tập dev** (`--ir`, `--nhanh --do-nguong`).
3. Đóng băng tham số bằng một commit Git, ghi lại mã commit: **[điền mã commit]**.
4. Chạy tập test đúng một lần: `--ir --tap test` cho chỉ số xếp hạng, `--nhanh --tap test` cho cổng chặn.
5. Không thay đổi tham số theo kết quả test. Mọi thay đổi sau bước 4 được ghi nhận riêng trong mục hạn chế.

## 3.5. Kết quả

### 3.5.1. Chất lượng truy hồi trên tập test

**Bảng 3.3. Chỉ số xếp hạng trên tập test** (chép từ `bang_chi_so_ir_test.md`)

| Nhóm | Số câu | MRR@10 | Hit@1 | Hit@3 | Hit@5 | Hit@10 | nDCG@10 |
|---|---|---|---|---|---|---|---|
| `chinh_sach_pdf` | 39 | **[điền]** | | | | | |
| `trinh_chieu` | 13 | **[điền]** | | | | | |
| `tai_lieu_docx` | 12 | **[điền]** | | | | | |
| `van_ban_doc` | 10 | **[điền]** | | | | | |
| `bang_excel` | 7 | **[điền]** | | | | | |
| `sach_giao_khoa` | 7 | **[điền]** | | | | | |
| `video` | 4 | **[điền]** | | | | | |
| **Toàn bộ** | 92 | **[điền]** | | | | | |

Số câu ở bảng là số câu có nhãn trong tập test **trước** bước 1 của mục 3.4; cập nhật nếu có câu bị loại. MRR@10 toàn bộ = **[điền]**, khoảng tin cậy 95% theo tài liệu **[điền]**. Riêng các câu thêm vào sau khi chia tập (chưa từng dùng để chọn tham số): MRR@10 = **[điền]**, khoảng tin cậy **[điền]**. Đây là ước lượng ít thiên lệch nhất mà bộ dữ liệu cho được. Tỷ lệ câu có tài liệu đúng trong cửa sổ 4 đoạn đưa vào prompt: **[điền]**.

Không rút kết luận riêng cho các nhóm có dưới 10 câu test (`bang_excel`, `sach_giao_khoa`, `video`), vì khoảng tin cậy của chúng quá rộng để phân biệt với các nhóm khác.

### 3.5.2. Cổng chặn lạc đề trên tập test

**Bảng 3.4. Kết quả cổng chặn trên tập test**

| Chỉ số | Kết quả |
|---|---|
| Chặn đúng câu ngoài phạm vi | **[điền]** / 22 |
| Từ chối oan câu trong phạm vi | **[điền]** / 92 |

**[điền: liệt kê các câu bị từ chối oan và tín hiệu đã chặn chúng — in sẵn trong màn hình tổng kết.]**

### 3.5.3. Quá trình cải tiến khối truy hồi

Các số liệu dưới đây đo **trước khi** chia tập dev/test, trên các bộ câu hỏi cũ, và các tham số được chọn khi nhìn chính các bộ đó. Vì vậy chúng chỉ minh họa hướng cải tiến, không phải ước lượng khách quan về chất lượng. Số liệu lấy từ `HUONG_DAN_BAN_GIAO_UI.md` và `bang_chi_so_ir.md`.

- Trên bộ 30 câu cố định, qua năm phiên bản từ truy hồi vector thuần (V1) tới phân loại câu hỏi đơn/đa đối tượng (V5), bản V5 trả lời đúng 18/30 câu với 3 trường hợp ảo giác. Phép so sánh mô hình 3B và 8B cho kết quả 17–18/30 so với 18/30.
- Trên 97 câu có nhãn của bộ 127 câu, đo ngày 15/09/2026: bổ sung tín hiệu khớp tên tài liệu có trọng số IDF vào bộ xếp hạng lại nâng MRR@10 từ 0,757 lên 0,806 (khoảng tin cậy 95% theo câu: 0,735 – 0,875) và Hit@1 từ 68% lên 74%. Mức tăng tập trung ở hai nhóm: `bang_excel` (Hit@1 từ 38% lên 62%) và `trinh_chieu` (Hit@1 từ 29% lên 43%).

## 3.6. Phân tích lỗi

**[điền sau khi đo: chọn khoảng 10 câu xếp hạng kém nhất mà `--ir` in ra, phân loại theo nguyên nhân.]** Gợi ý các loại nguyên nhân để phân loại:

- **Không lọt vào rổ ứng viên** (Hit@10 trượt): lỗi ở khâu chia đoạn, mô hình nhúng hoặc BM25; xếp hạng lại không cứu được.
- **Lọt rổ nhưng xếp sai** (Hit@10 trúng, Hit@1 trượt): lỗi ở bộ xếp hạng lại.
- **Nhầm văn bản cùng chủ đề**: ví dụ định mức tiết dạy phổ thông (Thông tư 05/2025) và giáo dục thường xuyên (Thông tư 04/2026) dùng gần như cùng từ vựng nhưng khác con số.
- **Tài liệu không có lớp chữ**: PDF chưa OCR, video không lời thoại. Đây là giới hạn của dữ liệu, không phải của thuật toán truy hồi.

## 3.7. Hạn chế của phương pháp đánh giá

1. **Tập test cũ đã bị nhìn thấy.** Các tham số hiện có được chọn khi nhìn 127 câu đầu tiên, trước khi chia tập. Phần test tách từ 127 câu này chỉ sạch đối với những lần tinh chỉnh về sau. Số liệu riêng của 153 câu thêm sau khi chia (mục 3.5.1) được báo cáo để bù cho hạn chế này.
2. **Nhãn ở mức tài liệu.** Một tài liệu đúng nhưng đoạn văn được truy hồi sai vẫn được tính là đúng, nên chỉ số xếp hạng có thể cao hơn chất lượng thật của đoạn bằng chứng đưa vào prompt.
3. **Nhãn có thể chưa đầy đủ.** Mỗi câu chỉ ghi những tài liệu chắc chắn liên quan. Sách giáo khoa và bài giảng cùng một bài, hay văn bản cũ và văn bản thay thế nó, thường cùng trả lời được một câu hỏi. Hệ thống lấy lên tài liệu đúng mà không có trong nhãn sẽ bị chấm trượt, nên các chỉ số có xu hướng bị đánh giá thấp.
4. **Một người gán nhãn.** Bộ câu hỏi chưa được gán nhãn độc lập bởi người thứ hai, nên chưa có số đo độ đồng thuận giữa người gán nhãn (Cohen's κ).
5. **Câu ngoài phạm vi phụ thuộc vào kho.** Một câu ngoài phạm vi hôm nay có thể trở thành câu trong phạm vi khi kho được bổ sung tài liệu. Ví dụ, câu về hàm đệ quy trong Python có thể đã được sách Tin học 11 trả lời. Nhãn của nhóm này cần rà lại mỗi khi kho thay đổi lớn.
6. **Chỉ số tự động về câu trả lời có giới hạn.** Trích dẫn hợp lệ và số liệu có căn cứ không đo được câu trả lời có đúng ý câu hỏi hay không. **[điền nếu có làm: kết quả chấm tay trên mẫu ngẫu nhiên N câu của tập test.]**

## 3.8. Kết luận chương

**[điền sau khi có số liệu: tóm tắt trong 1–2 đoạn chất lượng truy hồi trên tập test kèm khoảng tin cậy, sự đánh đổi của cổng chặn, nhóm tài liệu mạnh và yếu nhất, và hướng cải tiến rút ra từ phân tích lỗi.]**
