# Phương án cập nhật tri thức khi có văn bản mới

Tài liệu này trả lời câu hỏi của thầy hướng dẫn: **khi có tài liệu hoặc văn bản mới đưa vào hệ thống thì làm gì**, cụ thể là có huấn luyện lại mô hình không, và xử lý văn bản cũ ra sao khi văn bản mới thay thế nó. Mọi chỗ nói "hệ thống đang làm" đều chỉ tới mã nguồn cụ thể trong repository.

## 1. Kết luận

| Câu hỏi | Phương án của nhóm |
|---|---|
| Có huấn luyện lại mô hình không? | **Không.** Cả mô hình nhúng (`bge-m3`) lẫn mô hình ngôn ngữ (`qwen3.5:4b`) giữ nguyên trọng số. Tri thức nằm ở kho tài liệu, không nằm trong trọng số mô hình. |
| Train lại từ đầu, huấn luyện tiếp hay học tăng cường? | Không chọn cách nào. Lý do ở mục 2. |
| Xử lý ở mức dữ liệu thế nào? | Cập nhật chỉ mục tăng dần theo băm SHA-256, rồi dựng lại **hồ sơ văn bản** và **đồ thị quan hệ văn bản** (thay thế, bãi bỏ một phần, sửa đổi, hướng dẫn thi hành, ban hành kèm theo) ngay lúc nạp. |
| Văn bản cũ bị thay thế thì xóa, ghi đè hay kết hợp? | **Kết hợp: giữ trong kho, gắn tình trạng hiệu lực, chọn theo thời điểm câu hỏi.** Hỏi quy định hiện hành thì văn bản đã hết hiệu lực bị lọc khỏi câu trả lời. Hỏi quy định trước đây hoặc tại một mốc thì văn bản cũ được mở lại. Chỉ khi **cùng một tệp** được sửa thì mới ghi đè. |

Phạm vi đề tài: **văn bản quy phạm pháp luật ngành giáo dục Việt Nam** (Luật, Nghị định, Thông tư, Quyết định, Công văn) và tài liệu dạy học đi kèm. Chọn phạm vi này vì văn bản quy phạm có cấu trúc định danh rõ ràng (số hiệu, ngày ban hành, câu "Thông tư này thay thế Thông tư số ...") nên quan hệ cũ - mới rút ra được bằng quy tắc, không phải đoán.

## 2. Vì sao không huấn luyện lại

### Trực giác

RAG tách hai việc: mô hình ngôn ngữ lo **cách đọc và diễn đạt**, kho tài liệu lo **nội dung**. Văn bản mới chỉ làm thay đổi nội dung, không làm thay đổi cách đọc tiếng Việt hay cách trả lời có trích dẫn. Huấn luyện lại là sửa nhầm chỗ.

### So sánh bốn phương án

| Tiêu chí | Train lại từ đầu | Huấn luyện tiếp (fine-tune) | Học tăng cường (RLHF, DPO) | Cập nhật kho (RAG) |
|---|---|---|---|---|
| Thời gian khi có 1 văn bản mới | Hàng tuần, cần cụm GPU | Hàng giờ, cần GPU | Hàng giờ, cần dữ liệu đánh giá của người | Vài giây đến vài phút, chạy CPU |
| Trả lời đúng nội dung mới | Không bảo đảm | Không bảo đảm (xem dưới) | Không nhắm tới việc này | Có, vì đoạn văn bản mới được đưa thẳng vào prompt |
| Trích dẫn được nguồn, số trang | Không | Không | Không | Có |
| Quên văn bản cũ đã bị thay thế | Phải dựng lại tập dữ liệu | Không xóa được tri thức cũ khỏi trọng số | Không | Đổi tình trạng trong đồ thị, có hiệu lực ngay |
| Rủi ro phụ | | Quên thảm họa (catastrophic forgetting), ảo giác tăng | Mô hình học cách chiều người chấm | Phụ thuộc chất lượng truy hồi và trích quan hệ |

Ba điểm cần nói rõ khi bảo vệ:

- **Học tăng cường không phải công cụ nạp tri thức.** RLHF và DPO tối ưu *hành vi* theo tín hiệu thưởng (trả lời lịch sự, đúng định dạng, biết từ chối), không dạy mô hình một Thông tư mới. Dùng nó cho bài toán này là nhầm mục đích.
- **Fine-tune để nạp kiến thức mới kém hơn RAG và làm tăng ảo giác.** Ovadia và cộng sự (2023) so sánh trực tiếp hai cách nạp tri thức và thấy RAG vượt fine-tune không giám sát, nhất là với kiến thức mới hoàn toàn. Gekhman và cộng sự (2024) cho thấy fine-tune trên dữ kiện mô hình chưa biết khiến mô hình học chậm các dữ kiện đó và bịa nhiều hơn.
- **Trọng số không có nút "xóa".** Khi Thông tư cũ bị thay thế, phải làm mô hình *quên* nội dung cũ, tức bài toán machine unlearning, đến nay vẫn chưa có lời giải đáng tin. Với RAG, "quên" là đổi tình trạng một nút trong đồ thị.

Huấn luyện chỉ đáng cân nhắc khi cần đổi **năng lực** chứ không phải nội dung, ví dụ mô hình nhúng không hiểu thuật ngữ ngành. Việc đó nằm ngoài phạm vi đề tài và không liên quan tới việc có văn bản mới.

## 3. Quy trình khi có văn bản mới

```
Tệp mới / sửa / xóa trong kho
  │
  ├─ 1. Phát hiện thay đổi     băm SHA-256, so với sổ ghi chép          capnhat_tailieu_moi.py
  ├─ 2. Đọc, OCR, cắt đoạn      theo Chương / Điều, gắn metadata           chunking_utils.py
  ├─ 3. Nhúng và ghi chỉ mục    chỉ tệp đổi; tệp sửa thì xóa vector cũ     capnhat_tailieu_moi.py
  │                             theo chunk_id rồi thêm vector mới
  ├─ 4. Lập hồ sơ văn bản       số hiệu (cả từ tên tệp), ngày ban hành,     van_ban_meta.py
  │                             quan hệ đọc được từ nội dung
  │                             dự thảo, ngày có hiệu lực                  hieu_luc_bo_sung.py
  ├─ 5. Dựng đồ thị quan hệ     nút là SỐ HIỆU, cạnh là quan hệ; bổ sung    quan_he_van_ban.py
  │                             bằng sổ nhập tay so_quan_he_van_ban.json
  ├─ 6. Gắn cờ xuống từng đoạn  hết hiệu lực, ngày văn bản                 rag_service._lap_ho_so_van_ban
  ├─ 7. Phân loại môn, cấp, lớp                                             phan_loai_giao_duc.py
  ├─ 8. Dựng lại BM25           sau bước 6, 7 vì BM25 chép metadata
  └─ 9. Xóa cache câu trả lời   vân tay gồm cả nội dung kho                cache_ngu_nghia.py
```

Bước 3 ghi chỉ mục mới ra đĩa trong khi câu hỏi vẫn dùng chỉ mục cũ trong RAM, ghi xong mới nạp lại, nên cập nhật không làm gián đoạn hỏi đáp.

Bước 4 và 5 là phần "tổ chức, gán nhãn ngay từ đầu" mà thầy gợi ý. Quan hệ được rút từ **chính nội dung văn bản**, không cần ai khai báo. Sổ nhập tay chỉ dùng cho hai việc: bổ sung quan hệ máy đọc sót (ảnh quét hỏng), và gỡ quan hệ máy đọc sai (mục `loai_bo`).

Nút của đồ thị là **số hiệu văn bản**, không phải tên tệp. Nhờ vậy văn bản cũ đã rời khỏi kho vẫn là một nút: hệ thống vẫn biết nó đã bị văn bản nào thay, và trả lời theo văn bản mới khi người dùng nhắc tới số hiệu cũ.

## 4. Quan hệ giữa văn bản cũ và mới

### Phân loại quan hệ

Văn bản mới không chỉ có một kiểu tác động lên văn bản cũ. Gộp chung tất cả vào "thay thế" là sai về pháp lý:

| Quan hệ | Ví dụ câu trong văn bản mới | Tình trạng văn bản cũ |
|---|---|---|
| Thay thế / bãi bỏ **toàn bộ** | "Thông tư này thay thế Thông tư số 17/2012/TT-BGDĐT"; "Thông tư số 17/2012/TT-BGDĐT ... hết hiệu lực kể từ ngày Thông tư này có hiệu lực" | Hết hiệu lực (hoặc *sắp hết* nếu văn bản mới chưa tới ngày có hiệu lực) |
| **Bãi bỏ một phần** | "Bãi bỏ khoản 2 Điều 5 của Thông tư số ..." | Hết hiệu lực một phần, phần còn lại vẫn áp dụng |
| **Sửa đổi, bổ sung** | "Sửa đổi, bổ sung Điều 3 ..."; "Thay thế Phụ lục I ban hành kèm theo ..."; "Thay thế cụm từ ..." | Còn hiệu lực, nhưng phải đọc kèm văn bản sửa đổi |
| **Hướng dẫn thi hành** | "Thông tư này hướng dẫn thi hành Nghị định số ..." | Không đổi hiệu lực; hai văn bản đi cùng nhau |
| **Ban hành kèm theo** | "(Ban hành kèm theo Thông tư số ...)" ở Quy chế / Phụ lục tách tệp | Chung số phận với văn bản chính |

Ngoài ra còn tình trạng không đến từ quan hệ: **dự thảo** (ô số hiệu còn trống) và **chưa tới ngày hiệu lực**.

Có hai chỗ dễ sai khi trích quan hệ, cả hai đều đã có test:

- "Thay thế **Điều lệ** trường trung học ban hành kèm theo Thông tư số 12/2011" là thay thế **toàn bộ**. "Điều lệ" không phải "Điều 5", nên chỉ tính là một phần khi Điều / khoản / Chương / Mục có kèm số thứ tự.
- "Bãi bỏ Thông tư số A và khoản 2 Điều 5 Thông tư số B": mỗi số hiệu phải được xét riêng. Nếu chỉ nhìn số hiệu đầu tiên thì B cũng thành "thay thế toàn bộ", và ở chế độ hiện hành cả văn bản B bị lọc khỏi câu trả lời.

### Hai chế độ theo thời điểm câu hỏi

`quan_he_van_ban.che_do_thoi_gian` quyết định câu hỏi thuộc chế độ nào:

| | **Hiện hành** (mặc định) | **Lịch sử** |
|---|---|---|
| Khi nào | Câu hỏi không nêu mốc, hoặc mốc từ hôm nay trở đi | Có mốc quá khứ ("năm 2020" → 31/12/2020, "tháng 3/2024", "ngày 5/9/2020", "trước năm 2020" → 31/12/2019, "sau năm 2020" → 1/1/2021), hoặc có từ như "trước đây", "quy định cũ", "trước khi có Thông tư X" |
| Văn bản hết hiệu lực | **Lọc bỏ** khỏi rổ ứng viên (`RAG_LOC_HIEU_LUC=1`) | Được giữ lại, không bị phạt |
| Văn bản mới hơn | Được cộng điểm khi trùng phạm vi với văn bản cũ hơn (Jaccard ≥ 0,35) | Không cộng |
| Văn bản không áp dụng tại mốc | (không áp dụng) | Không phạt; phạt 0,015 nếu bật `RAG_HA_BAC_NGOAI_MOC=1` |
| Nhãn, cảnh báo | Tính tại hôm nay | Tính tại mốc được hỏi |
| Prompt | Luật prompt cấm dựa vào khối hết hiệu lực | Dòng đầu "CÂU HỎI VỀ QUY ĐỊNH TRƯỚC ĐÂY (tại ngày …)": được dùng văn bản cũ nhưng phải nói rõ nó đã bị văn bản nào thay |
| Cache ngữ nghĩa | Dùng | Bỏ qua ("năm 2023" và "năm 2025" gần như trùng nghĩa mà đáp án khác nhau) |
| Công cụ tính lương, định mức | Dùng | Bỏ qua khi mốc đã qua (công cụ chỉ biết quy định hiện hành); số học thuần vẫn tính |

Năm là một phần **tên văn bản** thì không phải mốc: "Luật Giáo dục năm 2019", "Chương trình giáo dục phổ thông năm 2018", "Thông tư ban hành ngày 30/12/2024". Nếu coi là mốc thì "Luật Giáo dục năm 2019" bị tra tại 31/12/2019, khi Luật 2019 chưa có hiệu lực (1/7/2020), và câu trả lời lại theo Luật 2005. Có giới từ thời gian đứng trước, hoặc có từ hỏi / động từ chen giữa tên và năm, thì vẫn là mốc: "Luật Giáo dục quy định thế nào **vào** năm 2019", "Văn bản **nào quy định** định mức năm 2020".

Ở cả hai chế độ, câu trả lời còn được **kéo thêm văn bản đi kèm** theo đồ thị: văn bản thay thế, văn bản sửa đổi, phụ lục, văn bản hướng dẫn (tối đa `RAG_SO_DOAN_DI_KEM` đoạn). Lý do: đoạn "khoản 2 Điều 5 được sửa đổi như sau" không giống câu hỏi bằng chính Điều 5 của văn bản gốc, nên truy hồi theo ngữ nghĩa hay bỏ sót nó.

### Vì sao không xóa và không ghi đè văn bản cũ

- **Bãi bỏ một phần và sửa đổi là trường hợp phổ biến.** Xóa văn bản cũ là mất mọi điều khoản còn hiệu lực. Ghi đè cũng không được, vì văn bản mới không chứa lại nội dung các điều khoản không bị sửa.
- **Người dùng vẫn có quyền hỏi về quy định cũ**: "năm 2020 định mức tiết dạy là bao nhiêu", "Thông tư mới khác Thông tư cũ ở điểm nào". Chế độ lịch sử chỉ làm được vì văn bản cũ còn trong kho.
- **Trích quan hệ tự động có thể sai.** Xóa theo kết quả trích sai là mất dữ liệu không lấy lại được. Gắn tình trạng sai thì sửa sổ nhập tay rồi dựng lại đồ thị.
- **Truy vết.** Câu trả lời trước đây dựa trên văn bản nào vẫn kiểm tra lại được.

Về mặt kỹ thuật, đây là cùng ý tưởng với *Slowly Changing Dimension loại 2* trong kho dữ liệu hay *bảng thời gian hợp lệ (valid time)* trong cơ sở dữ liệu: không cập nhật tại chỗ mà thêm phiên bản mới, đánh dấu khoảng hiệu lực của phiên bản cũ, rồi truy vấn *as-of* một thời điểm.

### Ví dụ đầy đủ

Kho đang có Thông tư 17/2012 về dạy thêm. Quản trị viên thêm Thông tư 29/2024. Điều khoản thi hành của Thông tư 29/2024 viết: "Thông tư số 17/2012/TT-BGDĐT ... hết hiệu lực kể từ ngày Thông tư này có hiệu lực thi hành", và Thông tư này có hiệu lực từ 14/2/2025.

1. Lượt cập nhật chỉ mục nhúng Thông tư 29/2024. Thông tư 17/2012 không bị động tới.
2. `van_ban_meta` đọc câu trên và ghi quan hệ "29/2024 thay thế 17/2012". `quan_he_van_ban` thêm cạnh vào đồ thị.
3. Hỏi "Những trường hợp nào không được dạy thêm?": chế độ hiện hành, Thông tư 17/2012 bị lọc bỏ, câu trả lời theo Thông tư 29/2024.
4. Hỏi "Năm 2020, những trường hợp nào không được dạy thêm?": chế độ lịch sử tại 31/12/2020. Tại mốc đó Thông tư 29/2024 chưa ban hành, nên Thông tư 17/2012 là văn bản đang áp dụng. Câu trả lời dựa vào nó và nói rõ nay nó đã bị Thông tư 29/2024 thay.
5. Hỏi "Thông tư 17/2012 quy định gì về dạy thêm?" ở chế độ hiện hành: hệ thống ghi chú "đã hết hiệu lực, bị thay thế bởi Thông tư 29/2024" và kéo Thông tư 29/2024 vào câu trả lời.

## 5. Giới hạn hiện tại

Những điểm dưới đây là giới hạn thật của hệ thống, nên nói trước khi hội đồng hỏi:

- **Quan hệ chỉ nhận ra từ một số dạng câu.** Đang nhận được hai dạng: "Văn bản này thay thế / bãi bỏ / sửa đổi văn bản số X", và "Văn bản số X … hết hiệu lực kể từ ngày văn bản này có hiệu lực" (dạng hay gặp nhất ở điều khoản thi hành). Ở dạng thứ hai chỉ lấy số hiệu **đầu mệnh đề**, vì các số theo sau thường là luật sửa đổi của nó và vẫn còn hiệu lực ("Luật GDĐH số 08/2012 đã được sửa đổi theo Luật số 74/2014 … hết hiệu lực"). Đổi lại, câu liệt kê hai văn bản cùng hết hiệu lực chỉ ghi nhận được văn bản đầu. Câu ghi ngày cụ thể ("Thông tư số X hết hiệu lực kể từ ngày 14/02/2025") thì chưa nhận, vì không chắc chính văn bản đang đọc là nguyên nhân. Chỗ máy đọc sót thì bổ sung ở `so_quan_he_van_ban.json`.
- **Mốc thời gian là một ngày, không phải một khoảng.** "Năm 2020" được tra tại 31/12/2020, "năm học 2020-2021" cũng vậy; "sau năm 2020" và "từ năm 2021" được tra tại 1/1/2021. Nếu văn bản mới có hiệu lực giữa kỳ thì câu hỏi về cả kỳ chỉ thấy một phiên bản.
- **Chế độ lịch sử mặc định chưa hạ bậc văn bản không áp dụng tại mốc.** Hỏi "năm 2020" thì văn bản 2025 vẫn đứng trong rổ ứng viên và có thể xếp trên văn bản cũ; nó chỉ bị gắn nhãn "chưa hiệu lực" tại mốc, và prompt nhắc mô hình. Đã có tuỳ chọn `RAG_HA_BAC_NGOAI_MOC=1` để hạ bậc các văn bản chưa tồn tại hoặc đã bị thay tại mốc (văn bản câu hỏi gọi đích danh thì không hạ). Tuỳ chọn này đang **tắt** cho tới khi nhánh thứ ba của benchmark ở mục 6 cho thấy nó giúp mà không hại.
- **Công cụ tính (lương, định mức, đánh giá học sinh) chỉ biết quy định hiện hành.** Câu có mốc quá khứ ("lương năm 2020") vì vậy không được tính mà chuyển sang RAG ở chế độ lịch sử: có trích dẫn văn bản đúng thời điểm, nhưng không có phiếu tính từng bước.
- **Chưa dựng bản hợp nhất tự động.** Khi A bị sửa một phần, hệ thống kéo văn bản sửa đổi vào cùng câu trả lời, nhưng chưa ghép thành một văn bản hợp nhất.
- **Phụ thuộc chất lượng trích số hiệu.** Số hiệu đọc sai từ bản scan thì quan hệ bị bỏ lỡ. Đã có ba lớp giảm rủi ro: số hiệu ghi trong tên tệp, đối chiếu tên tệp với số OCR, và trích lại bằng mô hình ngôn ngữ cho văn bản regex không chắc (`trich_meta_llm.py`).

## 6. Cách chứng minh phương án đúng

Đề xuất năm phép đo, đều chạy được trên kho hiện tại. Ba phép đầu đã có công cụ.

1. **Độ chính xác trích quan hệ**: `python danh_gia_trich_quan_he.py xuat` lấy mẫu câu có động từ quan hệ và số hiệu. Mẫu được chọn theo từ khóa, không theo kết quả của hệ thống, để đo được recall. Gán nhãn mù ba cột (thay thế / bãi bỏ một phần / sửa đổi), rồi `python danh_gia_trich_quan_he.py cham` cho P/R/F1 kèm khoảng tin cậy Wilson và ma trận nhầm lẫn. Muốn so trước/sau một thay đổi mã nguồn trên **cùng bộ nhãn**, thêm `--ma-nguon <git worktree của phiên bản cũ>`.
2. **Trả lời đúng mốc**: `python benchmark_moc_thoi_gian.py` chạy bộ `bo_cau_hoi_moc_thoi_gian.json` (45 câu, 20 cặp văn bản cũ - mới, 14 cặp có nhãn đã đối chiếu với sổ quan hệ nhập tay). Mỗi câu truy hồi ba lần trên cùng chỉ mục: tắt chế độ thời gian, bật, và bật kèm hạ bậc văn bản ngoài mốc. Đo bản đúng mốc có xếp trước bản sai mốc không, kèm kiểm định McNemar chính xác cho từng bước. Script cũng in đồ thị có nhận ra quan hệ thay thế của từng cặp không.
3. **Không ảnh hưởng câu hỏi thường**: `python benchmark_chatbot.py --ir` trên bộ 127 câu, so MRR và Hit@K trước và sau.

   Phép đo 2 và 3 chạy chung bằng `python chay_do_luong.py`. Script kiểm tra trước chỉ mục và Ollama, rồi ghi kết quả của cả hai cùng phiên bản mã nguồn và cấu hình vào `ket_qua_do_luong.md`.
4. **Tỉ lệ trả lời bằng văn bản hết hiệu lực mà không cảnh báo**: trên tập câu hỏi hiện hành có cặp cũ - mới, đếm câu trả lời có bằng chứng từ văn bản đã hết hiệu lực. Mục tiêu là 0.
5. **Thời gian cập nhật**: thời gian từ lúc thêm một văn bản tới lúc hỏi được, so với chi phí fine-tune ước tính cho cùng văn bản.

Nhãn ở phép đo 1 và 2 phải **viết tay từ văn bản gốc**, không suy ra từ hồ sơ hệ thống tự trích. Nếu suy nhãn từ chính hồ sơ đó thì phép đo thành vòng tròn: hệ thống trích sai ngày thì nhãn cũng sai theo, mà điểm vẫn đẹp.

## Tài liệu tham khảo

- Lewis, P. và cộng sự (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS.
- Ovadia, O. và cộng sự (2023). *Fine-Tuning or Retrieval? Comparing Knowledge Injection in LLMs*. arXiv:2312.05934.
- Gekhman, Z. và cộng sự (2024). *Does Fine-Tuning LLMs on New Knowledge Encourage Hallucinations?* EMNLP.
- Kirkpatrick, J. và cộng sự (2017). *Overcoming catastrophic forgetting in neural networks*. PNAS.
- Ouyang, L. và cộng sự (2022). *Training language models to follow instructions with human feedback*. NeurIPS.
- Cormack, G. V., Clarke, C. L. A., Büttcher, S. (2009). *Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods*. SIGIR.
- Snodgrass, R. T. (1999). *Developing Time-Oriented Database Applications in SQL*. Morgan Kaufmann.
- Kimball, R., Ross, M. (2013). *The Data Warehouse Toolkit*, 3rd ed., chương về Slowly Changing Dimensions.
- Wilson, E. B. (1927). *Probable inference, the law of succession, and statistical inference*. JASA.
