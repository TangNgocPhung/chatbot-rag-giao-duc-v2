# Hướng dẫn sử dụng Chatbot RAG Giáo dục

*Dành cho người mới bắt đầu, không cần biết nhiều về tin học.*

**Địa chỉ trang web:** <https://chatbot.148-113-237-209.sslip.io/>

> **Giới thiệu ngắn**
>
> **Chatbot RAG Giáo dục** là trợ lý tra cứu tài liệu giáo dục bằng tiếng Việt. Bạn gõ câu hỏi như khi nhắn tin, trợ lý tìm trong kho hơn một nghìn văn bản và tài liệu giáo dục (luật, nghị định, thông tư, chương trình giáo dục, tài liệu chuyên môn…) rồi trả lời ngắn gọn, **kèm theo nguồn**: tên tài liệu và đúng trang chứa thông tin, để bạn tự kiểm tra lại. Trợ lý còn cảnh báo khi văn bản đã bị thay thế hoặc chỉ là bản dự thảo, và tính sẵn lương nhà giáo, định mức tiết dạy theo đúng văn bản quy định.
>
> Sản phẩm do học viên Khoa Công nghệ thông tin, Trường Đại học Sư phạm Thành phố Hồ Chí Minh thực hiện, dưới sự hướng dẫn của TS. Nguyễn Minh Hải.

---

## Mục lục

1. [Trang web này là gì?](#1-trang-web-này-là-gì)
2. [Bắt đầu nhanh trong 3 bước](#2-bắt-đầu-nhanh-trong-3-bước)
3. [Làm quen với màn hình](#3-làm-quen-với-màn-hình)
4. [Đặt câu hỏi](#4-đặt-câu-hỏi)
5. [Đọc hiểu câu trả lời](#5-đọc-hiểu-câu-trả-lời)
6. [Thu hẹp phạm vi tìm kiếm](#6-thu-hẹp-phạm-vi-tìm-kiếm)
7. [Nói thay vì gõ](#7-nói-thay-vì-gõ)
8. [Xem lại các cuộc trò chuyện cũ](#8-xem-lại-các-cuộc-trò-chuyện-cũ)
9. [Tài khoản: có cần đăng ký không?](#9-tài-khoản-có-cần-đăng-ký-không)
10. [Hỏi về tài liệu của riêng bạn](#10-hỏi-về-tài-liệu-của-riêng-bạn)
11. [Kho tài liệu](#11-kho-tài-liệu)
12. [Sổ tay: ghi chú, vẽ, đọc tài liệu](#12-sổ-tay-ghi-chú-vẽ-đọc-tài-liệu)
13. [Dịch sang ngôn ngữ khác](#13-dịch-sang-ngôn-ngữ-khác)
14. [Tùy chỉnh khác](#14-tùy-chỉnh-khác)
15. [Phím tắt](#15-phím-tắt)
16. [Câu hỏi thường gặp và cách xử lý khi gặp trục trặc](#16-câu-hỏi-thường-gặp-và-cách-xử-lý-khi-gặp-trục-trặc)
17. [Những điều cần nhớ](#17-những-điều-cần-nhớ)

---

## 1. Trang web này là gì?

Hãy hình dung đây là **một thủ thư am hiểu văn bản giáo dục**: bạn hỏi, thủ thư lật đúng tài liệu trong kho, đọc đoạn liên quan rồi tóm tắt lại cho bạn, đồng thời chỉ rõ "thông tin này nằm ở trang mấy của văn bản nào".

Kho tài liệu bao quát:

- Giáo dục **mầm non, phổ thông, thường xuyên, nghề nghiệp, đại học**;
- **Chính sách, quy định** về quản lý giáo dục và đội ngũ nhà giáo;
- Chương trình giáo dục, tài liệu chuyên môn, kế hoạch bài dạy…

Số lượng tài liệu hiện có luôn hiển thị ngay trên nút **Kho tài liệu** ở thanh bên trái.

### Ai nên dùng, và dùng để làm gì?

Trợ lý chỉ trả lời được những gì **có trong kho**: văn bản quy định, chương trình giáo dục và học liệu. Bảng dưới đây nói rõ mỗi nhóm người dùng hỏi được gì, và những việc nên tìm ở chỗ khác, để bạn khỏi mất công hỏi.

| Bạn là | Hỏi được, ví dụ | Chưa làm được, nên tìm ở đâu |
|---|---|---|
| **Giáo viên, giảng viên** | Mỗi tuần phải dạy bao nhiêu tiết; lương theo hạng và bậc; cách tính điểm trung bình môn và xếp loại học sinh; khung kế hoạch bài dạy theo Công văn 5512; cách lập ma trận, bản đặc tả đề kiểm tra; phụ cấp, chuẩn nghề nghiệp | Không soạn thay bạn cả giáo án hay đề thi. Trợ lý chỉ ra quy định và mẫu có trong kho để bạn tự soạn. |
| **Cán bộ quản lý** | Chức năng, nhiệm vụ của các cơ quan quản lý; trường học an toàn; tự chủ của cơ sở giáo dục; tiêu chuẩn thiết bị; văn bản nào đã bị thay thế, văn bản nào đang có hiệu lực | Số liệu riêng của trường hay của địa phương (sĩ số, ngân sách…) không có trong kho. |
| **Sinh viên, học viên** | Sinh viên sư phạm (nhất là khi đi thực tập): chương trình giáo dục phổ thông 2018, khung kế hoạch bài dạy, ma trận đề. Sinh viên mọi ngành: học bổng, liên thông, điều kiện dự tuyển sau đại học | Không giải bài tập hay giảng lại môn học ở đại học: kho không có giáo trình đại học. |
| **Học sinh** | Cách tính điểm trung bình môn học kì; học sinh được xếp loại theo những mức nào; miễn học phí; các bậc học sau trung học phổ thông và đường liên thông; nội dung sách giáo khoa nếu kho có (lọc theo môn, lớp ở [mục 6](#6-thu-hẹp-phạm-vi-tìm-kiếm)) | Không phải công cụ giải bài từng bước: trợ lý chạy mô hình AI nhỏ trên máy chủ riêng nên dễ sai với bài toán nhiều bước. Hãy dùng trợ lý để tra cứu, còn giải bài thì hỏi thầy cô. |
| **Phụ huynh** | Trường có được dạy thêm và thu tiền dạy thêm không; con có được miễn học phí, hỗ trợ tiền ăn trưa không; điểm trung bình môn và xếp loại của con được tính thế nào; học bạ số | **Điểm chuẩn** các năm, danh sách trường, **chỗ học thêm**: đây không phải văn bản quy định nên không có trong kho. Hãy xem trên trang của sở giáo dục và đào tạo hoặc của trường. |

Hỏi ngoài những gì kho có, trợ lý sẽ nói là **không tìm thấy** thay vì tự đoán.

**Cho trợ lý biết bạn là ai.** Lần đầu vào trang, hộp giới thiệu hỏi *"Bạn là…"*. Chọn một mục thì màn hình chào đưa nhóm câu gợi ý hợp với bạn lên đầu. Muốn đổi, dùng ô **Gợi ý dành cho** ngay trên các câu gợi ý. Lựa chọn này **chỉ đổi câu gợi ý**: bạn vẫn hỏi được mọi thứ trong kho, và trợ lý vẫn tìm trên toàn bộ kho như nhau với mọi người. Vai trò bạn chọn được ghi kèm câu hỏi trên máy chủ để nhóm thực hiện thống kê mỗi nhóm người dùng hay hỏi gì, từ đó bổ sung đúng tài liệu còn thiếu.

### Khác gì so với các chatbot trò chuyện thông thường?

| Chatbot trò chuyện thông thường | Trợ lý này |
|---|---|
| Trả lời theo kiến thức chung đã học, thường không nói rõ lấy từ đâu | **Chỉ** trả lời dựa trên tài liệu có trong kho |
| Hiếm khi đưa nguồn cụ thể | Luôn ghi nguồn, mở được đúng trang, **tô vàng** đoạn được trích |
| Không biết văn bản nào đã hết hiệu lực | **Cảnh báo** khi văn bản đã bị thay thế, bị sửa đổi, còn là dự thảo hoặc chưa tới ngày có hiệu lực |
| Tự làm toán, dễ sai | Tính lương, định mức tiết dạy **bằng công thức chính xác**, ghi rõ văn bản căn cứ |

Câu hỏi, giọng nói và tài liệu của bạn được xử lý ngay trên máy chủ của trang web, không gửi sang dịch vụ trí tuệ nhân tạo (AI) bên ngoài. Đó là ý nghĩa của dòng *"Dữ liệu được xử lý trên máy này"* ở thanh bên trái.

---

## 2. Bắt đầu nhanh trong 3 bước

1. **Mở trang web.** Dùng trình duyệt quen thuộc (Chrome, Edge, Cốc Cốc, Firefox, Safari…) trên máy tính hoặc điện thoại, gõ địa chỉ ở đầu tài liệu này. Không cần cài đặt gì.
2. **Kiểm tra trạng thái.** Ở thanh trên cùng (dưới chữ *Trợ lý giáo dục*) và ở ô trạng thái bên trái, thấy **chấm xanh** kèm chữ **Sẵn sàng** là dùng được.
3. **Đặt câu hỏi.** Gõ câu hỏi vào ô **"Nhập câu hỏi về tài liệu..."** ở cuối màn hình rồi nhấn phím **Enter**. Nếu chưa biết hỏi gì, kéo xuống và bấm một **thẻ gợi ý** trên màn hình chào.

> Cần xem lại hướng dẫn này? Bấm nút **Hướng dẫn** (biểu tượng dấu hỏi) ở thanh trên cùng.
>
> **Không cần đăng nhập** để hỏi đáp. Chỉ khi muốn dùng thêm tính năng (xem kho tài liệu, sổ tay, hỏi về tệp của mình) bạn mới cần tạo tài khoản. Xem [mục 9](#9-tài-khoản-có-cần-đăng-ký-không).

---

## 3. Làm quen với màn hình

Màn hình chia thành bốn vùng: **thanh bên trái**, **thanh trên cùng**, **vùng giữa** và **khung hỏi ở dưới cùng**.

### Thanh bên trái

| Bạn thấy | Dùng để |
|---|---|
| **+ Cuộc trò chuyện mới** (nút màu xanh đậm) | Mở một cuộc hỏi đáp mới, trống. Nên bấm mỗi khi chuyển sang chủ đề khác. |
| **Kho tài liệu** (kèm một con số) | Xem toàn bộ tài liệu mà trợ lý đang dùng. Con số là số tài liệu trong kho. |
| **Gần đây** | Danh sách các cuộc trò chuyện trước đó. Bấm vào một dòng để mở lại. |
| Biểu tượng **kính lúp** và **thùng rác** cạnh chữ *Gần đây* | Tìm một cuộc trò chuyện cũ; xóa toàn bộ lịch sử. |
| Ô trạng thái (**Sẵn sàng**) | Cho biết hệ thống có đang hoạt động không. Bấm vào để xem thông tin chi tiết về kho. Các con số kỹ thuật ở đây bạn có thể bỏ qua. |
| Dòng *"Chưa đồng bộ lần nào · tự kiểm tra mỗi 15 phút"* | Thông tin cập nhật tài liệu mới vào kho, dành cho người quản trị. Bạn không cần làm gì. |
| **Nhóm thực hiện** | Thông tin về nhóm tác giả. |
| Tên của bạn (dưới cùng) | Mở menu tài khoản. Nếu chưa đăng nhập, ở đây có nút **Đăng ký** và **Đăng nhập**. |

### Thanh trên cùng

| Bạn thấy | Dùng để |
|---|---|
| Biểu tượng khung chữ nhật ở góc trái | Ẩn hoặc hiện thanh bên trái cho rộng chỗ đọc. Trên điện thoại, đây là nút **☰** để mở thanh bên. |
| **Trợ lý giáo dục · Sẵn sàng** | Trạng thái hoạt động của trợ lý. |
| **Hướng dẫn** (biểu tượng dấu hỏi) | Mở tài liệu hướng dẫn này ngay trên trang, lúc nào cần cũng xem lại được. |
| **Sổ tay** | Mở cuốn sổ ghi chú bên phải màn hình ([mục 12](#12-sổ-tay-ghi-chú-vẽ-đọc-tài-liệu)). |
| Biểu tượng **mặt trời / mặt trăng** | Đổi giao diện sáng hoặc tối. |
| Tên mô hình, ví dụ `qwen3.5:9b` | Chọn "bộ não" AI dùng để trả lời. **Người mới nên để nguyên** ([mục 14](#14-tùy-chỉnh-khác)). |

### Vùng giữa

Khi mới mở trang, vùng giữa hiện lời chào, thông tin nhóm thực hiện và **4 thẻ gợi ý theo chủ đề**: *Mầm non & phổ thông*, *Giáo dục nghề nghiệp*, *Giáo dục đại học*, *Chính sách giáo dục*. Bên dưới là mục **Câu hỏi gợi ý theo chủ đề**; bấm một câu là gửi luôn. Ô **Gợi ý dành cho** ở đầu mục này cho bạn chọn mình là học sinh, sinh viên, giáo viên, cán bộ quản lý hay phụ huynh, để nhóm câu hợp với bạn hiện lên đầu (xem [mục 1](#1-trang-web-này-là-gì)). Sau khi bạn hỏi, cuộc hội thoại hiện ở đây.

### Khung hỏi ở dưới cùng

| Bạn thấy | Dùng để |
|---|---|
| **Hỏi trên cả kho** | Giới hạn phạm vi tìm theo môn, cấp học, lớp ([mục 6](#6-thu-hẹp-phạm-vi-tìm-kiếm)). |
| Ô **"Nhập câu hỏi về tài liệu..."** | Gõ câu hỏi. |
| **Đính kèm tệp** | Gửi tệp của bạn để hỏi riêng về tệp đó ([mục 10](#10-hỏi-về-tài-liệu-của-riêng-bạn)). |
| **Nói** | Hỏi bằng giọng nói thay vì gõ ([mục 7](#7-nói-thay-vì-gõ)). |
| Nút **mũi tên** ở góc phải | Gửi câu hỏi (giống nhấn Enter). |

> **Nút bị mờ?** Đó là tính năng cần đăng nhập hoặc cần xác minh email. Cứ bấm vào, trang sẽ hướng dẫn bạn làm bước còn thiếu.

---

## 4. Đặt câu hỏi

### Cách gửi câu hỏi

- Gõ câu hỏi rồi nhấn **Enter** để gửi.
- Muốn **xuống dòng** mà chưa gửi: nhấn **Shift + Enter**.
- Mỗi câu hỏi dài tối đa 2.000 ký tự.
- Trong lúc trợ lý đang trả lời, nếu thấy hỏi nhầm, bấm **Dừng trả lời**.

### Phải chờ bao lâu?

Trợ lý chạy trên máy chủ riêng, không dùng dịch vụ AI trả phí bên ngoài, nên mỗi câu trả lời **thường mất khoảng một phút**, có khi lâu hơn khi nhiều người cùng hỏi. Trong lúc chờ, trang báo trợ lý đang làm gì (*Đang tìm tài liệu liên quan*, *Đang soạn câu trả lời*), rồi chữ hiện dần ra. Hãy kiên nhẫn và **đừng tải lại trang** giữa chừng.

Nếu bạn hỏi một câu gần giống câu đã có người hỏi trước đó, trợ lý có thể trả lời **ngay lập tức** và ghi chú *"Trả lời tức thì từ câu hỏi tương tự đã hỏi"*. Rê chuột vào dòng chú thích đó để xem câu hỏi cũ.

### Mẹo để có câu trả lời tốt

1. **Hỏi cụ thể, mỗi câu một ý.** Hỏi hai ba việc một lúc dễ nhận được câu trả lời thiếu.
2. **Nêu rõ đối tượng**: cấp học, môn học, lớp, loại giáo viên…
3. **Ghi số hiệu văn bản nếu biết**, ví dụ *Công văn 5512/BGDĐT-GDTrH*.
4. **Nên gõ tiếng Việt có dấu** để trợ lý hiểu chính xác nhất. Các chữ viết tắt thông dụng như *GV*, *HS*, *THCS*, *THPT* vẫn được hiểu.
5. **Hỏi nối tiếp trong cùng cuộc trò chuyện.** Trợ lý nhớ vài câu gần nhất, nên bạn có thể hỏi tiếp kiểu *"Còn giáo viên THCS thì sao?"*. Khi chuyển sang chủ đề hoàn toàn khác, hãy bấm **Cuộc trò chuyện mới** để trợ lý không bị lẫn.

| Câu hỏi chưa tốt | Câu hỏi tốt hơn |
|---|---|
| *dạy thêm* | *Theo quy định mới, giáo viên có được dạy thêm có thu tiền cho học sinh lớp mình đang dạy không?* |
| *kế hoạch bài dạy* | *Khung kế hoạch bài dạy theo Công văn 5512/BGDĐT-GDTrH gồm những phần nào?* |
| *chương trình* | *Yêu cầu cần đạt môn Ngữ văn lớp 6 trong Chương trình giáo dục phổ thông 2018 gồm những gì?* |

### Câu hỏi cần tính toán

Trợ lý có sẵn **công cụ tính chính xác** (không để AI tự nhẩm) cho các việc sau. Kết quả luôn kèm công thức và văn bản căn cứ.

| Việc cần tính | Ví dụ câu hỏi |
|---|---|
| Lương nhà giáo | *Tính lương giáo viên THPT hạng III bậc 1* |
| Định mức tiết dạy (phổ thông, GDTX) | *Giáo viên THPT chủ nhiệm dạy bao nhiêu tiết?* |
| Phép tính thông thường | *12% của 2.340.000 là bao nhiêu?* |

### Hỏi về một trang web

Bạn có thể dán **đường link một trang web** vào câu hỏi (ví dụ *"Tóm tắt thông báo ở trang https://…"*). Trợ lý sẽ đọc trang đó để trả lời. Cách này dùng được với trang web thông thường; link trực tiếp tới tệp PDF thì chưa đọc được, khi đó hãy tải tệp về rồi dùng **Đính kèm tệp**.

---

## 5. Đọc hiểu câu trả lời

### Các con số trong ngoặc vuông

Trong câu trả lời, bạn sẽ thấy các ký hiệu như **[1]**, **[2]**. Chúng cho biết câu đó được lấy từ **nguồn số 1**, **nguồn số 2**… trong danh sách nguồn bên dưới.

### Danh sách nguồn

Dưới mỗi câu trả lời là danh sách tài liệu đã được dùng: tên tài liệu, số hiệu văn bản, số trang. Với tài liệu PDF hoặc ảnh, còn có **ảnh thu nhỏ của trang gốc**:

- Phần **tô vàng** là đoạn trợ lý đã đọc;
- Phần **viền đỏ** là câu sát với câu hỏi của bạn nhất.

**Bấm vào một nguồn** để mở tài liệu gốc:

- **Tài khoản đã xác minh email:** tài liệu mở ngay trong Sổ tay bên cạnh, đúng trang, các dòng được trích đã tô sáng. Muốn mở ở thẻ trình duyệt mới thì giữ **Ctrl** khi bấm.
- **Đã đăng nhập nhưng chưa xác minh email:** tài liệu mở ở một thẻ trình duyệt mới.
- **Khách chưa đăng nhập:** chỉ xem được tên nguồn và đoạn trích (rê chuột vào nguồn), không mở được tệp gốc.

Nếu nguồn là **video hoặc bản ghi âm**, bấm vào sẽ phát ngay từ đúng đoạn được trích dẫn.

### Các khung cảnh báo

Đôi khi bên dưới câu trả lời có **khung cảnh báo**. Đừng bỏ qua chúng:

| Cảnh báo có nội dung | Ý nghĩa và bạn nên làm gì |
|---|---|
| *"… đã bị thay thế bởi …"* | Văn bản được trích **đã có văn bản mới thay thế**. Hãy hỏi lại hoặc tìm theo văn bản mới được nêu tên. |
| *"… đã bị … sửa đổi hoặc bãi bỏ …"* | Đoạn được trích **đã bị sửa**, chữ trong đoạn là bản cũ. Đọc thêm văn bản sửa đổi. |
| *"… là BẢN DỰ THẢO …"* | Tài liệu mới là dự thảo, **chưa phải văn bản chính thức**, không dùng làm căn cứ. |
| *"… phải tới … mới có hiệu lực thi hành"* | Văn bản đã ban hành nhưng **chưa tới ngày áp dụng**. |
| *"Cần đối chiếu lại: …"* | Hệ thống tự kiểm tra và thấy một con số hoặc một trích dẫn **không khớp** với tài liệu. Hãy mở nguồn để kiểm tra trước khi dùng. |

### Các nút dưới câu trả lời

| Nút | Công dụng |
|---|---|
| **Sao chép** | Chép câu trả lời để dán vào Word, Zalo, email… |
| **Nghe** | Máy đọc to câu trả lời. Bấm **Dừng đọc** để tắt. |
| **Ghi vào sổ** | Chép câu hỏi và câu trả lời vào Sổ tay của cuộc trò chuyện. |
| **Dịch** | Dịch câu trả lời sang ngôn ngữ khác ([mục 13](#13-dịch-sang-ngôn-ngữ-khác)). |

Dòng *"Hoàn tất sau … giây"* cho biết trợ lý đã mất bao lâu để trả lời. Bên dưới, mục **Hỏi tiếp** gợi ý vài câu hỏi liên quan; bấm vào để hỏi luôn.

### Bôi đen một đoạn

Dùng chuột (hoặc giữ ngón tay trên điện thoại) **bôi đen một đoạn** trong câu trả lời, một thanh nhỏ sẽ hiện ra với ba lựa chọn:

- **Ghi vào sổ**: chép riêng đoạn đó vào Sổ tay;
- **Dịch**: mở khung dịch với đoạn đó;
- **Hỏi về đoạn này**: hỏi tiếp về đúng đoạn vừa chọn.

### Khi trợ lý nói "không tìm thấy"

Nếu trợ lý trả lời *"Tôi không tìm thấy thông tin này trong tài liệu hiện có."*, điều đó có nghĩa là **kho chưa có tài liệu phù hợp**. Trợ lý được thiết kế để nói thật thay vì bịa ra câu trả lời. Bạn có thể:

- Hỏi lại bằng cách diễn đạt khác, dùng từ ngữ giống trong văn bản hành chính hơn;
- Bỏ bộ lọc phạm vi nếu đang lọc ([mục 6](#6-thu-hẹp-phạm-vi-tìm-kiếm));
- Nếu bạn có sẵn tài liệu đó, dùng **Đính kèm tệp** để hỏi trực tiếp ([mục 10](#10-hỏi-về-tài-liệu-của-riêng-bạn)).

---

## 6. Thu hẹp phạm vi tìm kiếm

Mặc định trợ lý tìm trên **toàn bộ kho**. Khi câu hỏi dễ bị lẫn giữa các cấp học hay môn học (ví dụ *"yêu cầu cần đạt"* của môn nào, lớp nào?), bạn có thể giới hạn lại:

1. Bấm nút **Hỏi trên cả kho** ngay phía trên ô nhập câu hỏi.
2. Trong khung **Chỉ tìm trong**, chọn **Môn học**, **Cấp học**, **Lớp** hoặc **Loại tài liệu** (chỉ cần chọn mục nào bạn quan tâm).
3. Tên nút đổi theo lựa chọn của bạn. Từ giờ các câu hỏi chỉ tìm trong nhóm tài liệu đó.
4. Muốn tìm lại trên cả kho, bấm **Bỏ lọc**.

> **Lưu ý:** Một số tài liệu chưa được gắn nhãn môn, lớp nên sẽ **không được xét** khi đang lọc. Nếu lọc mà trợ lý báo không tìm thấy, hãy bấm **Bỏ lọc** rồi hỏi lại.

---

## 7. Nói thay vì gõ

1. Bấm nút **Nói** trong khung hỏi.
2. Lần đầu, trình duyệt sẽ hỏi **cho phép dùng micro**, hãy chọn **Cho phép** (*Allow*).
3. Nói câu hỏi của bạn. Nút chuyển sang màu đỏ với chữ **Dừng** và có đồng hồ đếm giờ.
4. Nói xong, bấm **Dừng**. Sau vài giây, lời nói được chuyển thành chữ và điền vào ô câu hỏi.
5. **Đọc lại** cho chắc rồi nhấn **Enter** để gửi.

Mẹo và lưu ý:

- Trợ lý **tự nhận ra bạn nói tiếng gì**, không cần chọn ngôn ngữ trước.
- Ghi âm tự dừng sau **60 giây**. Muốn hủy giữa chừng, nhấn phím **Esc**.
- Nên nói ở nơi yên tĩnh, rõ ràng, tốc độ vừa phải.
- Nếu nút **Nói** bị mờ hoặc không ghi được âm, xem [mục 16](#16-câu-hỏi-thường-gặp-và-cách-xử-lý-khi-gặp-trục-trặc).

---

## 8. Xem lại các cuộc trò chuyện cũ

- **Mở lại:** bấm vào tên cuộc trò chuyện trong mục **Gần đây** ở thanh bên trái.
- **Tìm kiếm:** bấm biểu tượng **kính lúp** cạnh chữ *Gần đây* (hoặc nhấn **Ctrl + K**) rồi gõ vài chữ trong tên cuộc trò chuyện.
- **Xóa một cuộc trò chuyện:** rê chuột vào dòng đó, bấm biểu tượng **thùng rác** nhỏ bên phải rồi xác nhận.
- **Xóa toàn bộ lịch sử:** bấm biểu tượng **thùng rác** cạnh chữ *Gần đây*.
- **Đổi chiều cao danh sách:** kéo thanh ngang bên dưới danh sách *Gần đây*; nhấp đúp để trở về như cũ.

> Cuộc trò chuyện đã xóa **không khôi phục được**.

**Lịch sử được lưu ở đâu?**

Dù đăng nhập hay không, **máy chủ của trang web đều lưu lại mỗi lượt hỏi đáp**. Khác nhau ở chỗ bạn xem lại được từ đâu:

- **Chưa đăng nhập:** danh sách *Gần đây* chỉ hiện trên **trình duyệt của máy đang dùng**. Máy chủ vẫn giữ một bản, gắn với một mã ngẫu nhiên của trình duyệt đó chứ không gắn với tên hay email của bạn. Đổi máy hoặc đổi trình duyệt thì không xem lại được.
- **Đã đăng nhập:** lịch sử gắn với tài khoản, **mở ở máy nào cũng thấy**.

**Máy chủ lưu những gì, ai xem được?**

- **Lưu:** câu hỏi, câu trả lời, các nguồn được trích, thời gian trả lời và vai trò bạn đã chọn ở mục *Gợi ý dành cho* (nếu có).
- **Ai xem được:** trên giao diện, chỉ bạn thấy lịch sử của mình. Quản trị viên của trang xem được **số liệu thống kê**, gồm cả nội dung các câu hay được hỏi hoặc hay bị từ chối, nhưng thống kê không ghi câu nào của ai. Người quản lý máy chủ có quyền truy cập trực tiếp vào cơ sở dữ liệu thì đọc được toàn bộ.
- **Dùng để làm gì:** để bạn mở lại cuộc trò chuyện, và để nhóm thực hiện biết người dùng hay hỏi gì, câu nào trả lời chưa tốt, từ đó bổ sung tài liệu. Dữ liệu không được gửi sang dịch vụ trí tuệ nhân tạo bên ngoài.
- **Lưu bao lâu:** mỗi lượt hỏi đáp **tự xóa hẳn khỏi máy chủ sau 12 tháng** kể từ lúc hỏi. Một cuộc trò chuyện kéo dài qua mốc đó thì chỉ mất phần cũ hơn 12 tháng.
- **Xóa:** bấm thùng rác (một cuộc hoặc toàn bộ) là xóa **cả trên trình duyệt lẫn trên máy chủ**. Nếu chưa đăng nhập, hãy xóa lịch sử **trước** khi xóa dữ liệu duyệt web. Mất mã của trình duyệt rồi thì trang không còn biết bản nào trên máy chủ là của bạn để xóa giúp.

> Vì vậy, **đừng gõ thông tin cá nhân nhạy cảm** (số căn cước, số điện thoại, điểm số kèm họ tên học sinh…) vào câu hỏi. Trợ lý trả lời theo văn bản, không cần những thông tin đó.

---

## 9. Tài khoản: có cần đăng ký không?

**Không bắt buộc.** Khách vẫn hỏi đáp bình thường. Tạo tài khoản sẽ mở thêm tính năng:

| Tính năng | Khách | Đã đăng ký | Đã đăng ký **và xác minh email** |
|---|:---:|:---:|:---:|
| Hỏi đáp | ✓ | ✓ | ✓ |
| Lưu lịch sử, mở ở máy khác vẫn thấy | | ✓ | ✓ |
| Xem **Kho tài liệu**, mở tài liệu gốc | | ✓ | ✓ |
| Dùng **Sổ tay** | | | ✓ |
| **Đính kèm tệp** để hỏi, tải tài liệu riêng lên kho | | | ✓ |

### Đăng ký tài khoản

1. Bấm **Đăng ký** ở cuối thanh bên trái (hoặc nút **Đăng nhập** ở thanh trên cùng, rồi chọn **Đăng ký**).
2. Điền **Tên hiển thị** (ví dụ *Cô Lan*), **Email** và **Mật khẩu** (ít nhất 8 ký tự). Bấm **Hiện** để xem lại mật khẩu vừa gõ.
3. Bấm **Tạo tài khoản**.

Các cuộc trò chuyện bạn đã hỏi trước khi đăng ký sẽ được chuyển sang tài khoản mới, không bị mất.

### Xác minh email

1. Ngay sau khi đăng ký, hộp **Xác minh email** hiện ra và trang gửi một **mã gồm 6 chữ số** tới email của bạn.
2. Mở hộp thư, tìm thư chứa mã. **Không thấy thì kiểm tra thư mục Thư rác (Spam) hoặc Quảng cáo.**
3. Nhập mã vào ô **Mã xác minh** rồi bấm **Xác minh**.

Lưu ý:

- Mã chỉ có hiệu lực **15 phút**. Hết hạn thì bấm **Gửi lại mã** để nhận mã mới (phải chờ 60 giây giữa hai lần gửi).
- Chưa muốn xác minh ngay thì đóng hộp lại. Lúc nào muốn, mở menu tài khoản và chọn **Xác minh email**.
- Nếu gõ nhầm email, bấm **Nhập sai email? Sửa lại**.

### Menu tài khoản

Bấm vào **tên của bạn** ở cuối thanh bên trái để:

- **Xác minh email** (nếu chưa xác minh);
- **Tải ảnh đại diện** hoặc gỡ ảnh;
- **Sửa họ tên / email** (đổi email phải xác minh lại email mới);
- **Đổi mật khẩu** (các máy khác đang đăng nhập tài khoản này sẽ bị đăng xuất);
- **Đăng xuất**, nhất là khi dùng máy chung.

> **Quên mật khẩu?** Trang chưa có chức năng tự lấy lại mật khẩu. Hãy liên hệ **quản trị viên** của trang để được đặt lại.
>
> **Nhập sai mật khẩu nhiều lần?** Sau 10 lần sai liên tiếp, tài khoản bị khóa tạm **15 phút** để chống dò mật khẩu. Hãy chờ rồi thử lại.

---

## 10. Hỏi về tài liệu của riêng bạn

Bạn có một tệp (giáo án, đề thi, văn bản, bài báo, video bài giảng…) và muốn hỏi về nội dung của chính tệp đó? *(Cần tài khoản đã xác minh email.)*

1. Bấm **Đính kèm tệp** trong khung hỏi, chọn tệp trên máy. Có thể chọn **tối đa 4 tệp** cùng lúc, mỗi tệp tối đa khoảng **40 MB**.
2. Tệp hiện phía trên ô nhập kèm trạng thái *"Đang đọc nội dung tệp..."*. **Chờ tới khi tệp sẵn sàng.** Tệp PDF dạng scan (ảnh chụp) hoặc video có thể mất vài phút vì máy phải "đọc chữ trong ảnh" hoặc "nghe" lời nói.
3. Khi tệp sẵn sàng, ô nhập đổi thành *"Hỏi về <tên tệp>..."*. Giờ bạn có thể:
   - Bấm **Tóm tắt** để trợ lý tóm tắt tệp;
   - Bấm **Đọc** để mở tệp trong Sổ tay;
   - Hoặc gõ câu hỏi của bạn như bình thường.
4. Muốn bỏ tệp, bấm dấu **×** trên tệp đó.

**Các loại tệp hỗ trợ:**

| Loại | Ví dụ |
|---|---|
| Văn bản | PDF (cả bản scan), Word, TXT, trang web đã lưu (HTML), sách điện tử EPUB |
| Bảng tính, trình chiếu | Excel, CSV, PowerPoint |
| Ảnh chụp | JPG, PNG… (ví dụ ảnh chụp trang sách) |
| Âm thanh, video | MP3, WAV, M4A, MP4, MOV… (máy tự chuyển lời nói thành chữ) |
| Phụ đề | SRT, VTT |

> Tệp bạn đính kèm được lưu vào mục **Của tôi** trong Kho tài liệu và **chỉ bạn thấy**. Tệp không tự vào kho chung ([mục 11](#11-kho-tài-liệu)).
>
> Không nên tải lên tài liệu chứa thông tin cá nhân nhạy cảm (số CCCD, hồ sơ học sinh, thông tin sức khỏe…).

---

## 11. Kho tài liệu

Bấm **Kho tài liệu** ở thanh bên trái *(cần đăng nhập)*. Cửa sổ kho có các thẻ:

### Kho chung

Toàn bộ tài liệu mà trợ lý dùng để trả lời mọi người.

- **Tìm theo tên hoặc thư mục** bằng ô tìm kiếm.
- **Lọc theo loại tài liệu** bằng các nút lọc bên dưới ô tìm.
- Bấm **Mở** (hoặc **Đọc**) trên một tài liệu để xem nội dung.

### Của tôi

Tài liệu riêng của bạn: các tệp đã đính kèm khi hỏi, hoặc tải lên bằng nút **+** ở góc trên cửa sổ kho. **Chỉ bạn thấy**, kể cả quản trị viên cũng không xem được trên trang.

- Bấm **Hỏi** để hỏi đáp riêng trong tài liệu đó, không phải chờ.
- Mỗi tài khoản giữ được tối đa **100 tài liệu riêng**.

### Muốn đóng góp tài liệu cho mọi người?

Trong thẻ **Của tôi**, bấm **Đề xuất** trên tài liệu muốn đóng góp. Tài liệu sẽ chờ **quản trị viên duyệt**. Trạng thái hiện ngay trên tài liệu: *chờ duyệt*, *đã vào kho chung*, *kho chung đã có* hoặc *không được duyệt*.

Sau khi được duyệt, tài liệu cần thêm một khoảng thời gian để hệ thống xử lý, rồi mới được dùng trong câu trả lời cho mọi người.

*(Các thẻ **Chờ duyệt** và **Thùng rác** chỉ dành cho quản trị viên.)*

---

## 12. Sổ tay: ghi chú, vẽ, đọc tài liệu

Mỗi cuộc trò chuyện có **một cuốn sổ riêng** nằm bên phải màn hình, giúp bạn vừa hỏi vừa ghi chép. *(Cần tài khoản đã xác minh email.)*

**Mở sổ:** bấm nút **Sổ tay** ở thanh trên cùng (hoặc nhấn **Ctrl + /**). Muốn sổ rộng hơn hoặc hẹp hơn, kéo mép trái của sổ.

> Trên màn hình không quá rộng (ví dụ máy tính xách tay nhỏ), mở sổ thì **thanh bên trái tự thu gọn** để khung trò chuyện đủ rộng; đóng sổ là thanh bên hiện lại.

Sổ có ba thẻ:

### Ghi chú

- Gõ tự do như trong Word, có **chữ đậm**, *nghiêng*, gạch chân, **tô vàng**, tiêu đề, danh sách và ô đánh dấu "việc cần ôn".
- Chép nhanh từ cuộc trò chuyện bằng nút **Ghi vào sổ** (dưới câu trả lời hoặc khi bôi đen một đoạn).

### Bảng vẽ

Vẽ tay sơ đồ, công thức bằng **bút**, **bút tô sáng**, **tẩy**; chọn màu, độ đậm nét; có nút **hoàn tác** khi vẽ nhầm.

### Tài liệu: đọc và "khoanh để hỏi"

Mở tài liệu ngay cạnh khung chat bằng một trong các cách:

- Bấm **Mở tài liệu hoặc ảnh** để chọn tệp trên máy (PDF, Word, Excel, PowerPoint, HTML, ảnh chụp trang sách);
- Bấm **Mở từ Kho tài liệu**;
- Hoặc bấm vào một **nguồn** dưới câu trả lời.

Dùng các nút trên đầu trang để chuyển trang, phóng to, thu nhỏ.

**Khoanh để hỏi**, tính năng hữu ích nhất khi đọc tài liệu khó:

1. Chọn công cụ **Khoanh để hỏi** trên thanh công cụ.
2. Nhấn chuột ở một góc đoạn chưa hiểu, kéo sang góc đối diện để vẽ khung chữ nhật (giống công cụ chụp màn hình).
3. Một hộp nhỏ hiện ra với chữ đã đọc được trong khung (có thể sửa lại nếu sai). Chọn:
   - **Giải thích**: trợ lý giải thích đúng đoạn đó;
   - **Hỏi câu khác**: tự gõ câu hỏi về đoạn đó;
   - **Ghi vào sổ**: lưu đoạn đó (kèm ảnh) vào ghi chú.

Bạn cũng có thể **đánh dấu** ngay trên trang bằng bút, bút tô sáng và tẩy. Nét vẽ được lưu lại, lần sau mở tài liệu vẫn còn.

> Trên điện thoại hoặc máy tính bảng, công cụ mặc định là **Cuộn** để vuốt trang không bị vẽ nhầm.

### Tải sổ tay về máy

Bấm biểu tượng **tải về** ở góc trên của sổ và chọn:

- **Word (.doc)**: ghi chú, ảnh vùng đã khoanh và bảng vẽ;
- **In hoặc lưu PDF**;
- **Ảnh bảng vẽ (.png)**;
- **Tài liệu đang đọc (.pdf)**: tài liệu kèm mọi nét bút, tô sáng và vùng khoanh của bạn.

---

## 13. Dịch sang ngôn ngữ khác

Có hai cách:

- **Dịch cả câu trả lời:** bấm **Dịch** dưới câu trả lời, chọn ngôn ngữ (có ô tìm, gõ *Anh*, *Pháp*, *Nhật*… đều được). Bản dịch hiện ngay bên dưới.
- **Dịch một đoạn:** bôi đen đoạn cần dịch, bấm **Dịch** trên thanh nổi. Khung dịch hai cột mở ra, tại đây bạn có thể sửa văn bản, **đổi chiều dịch**, **nghe đọc to**, **sao chép** hoặc **ghi bản dịch vào sổ tay**.

> Đây là **bản dịch máy**, chỉ để tham khảo. Hãy kiểm tra lại trước khi dùng chính thức, đặc biệt với ngôn ngữ ít phổ biến.

---

## 14. Tùy chỉnh khác

- **Giao diện sáng / tối:** bấm biểu tượng mặt trời/mặt trăng ở thanh trên cùng. Chế độ tối dễ chịu hơn khi dùng buổi tối.
- **Thu gọn thanh bên:** bấm biểu tượng khung chữ nhật ở góc trên bên trái để có thêm chỗ đọc.
- **Chọn mô hình trả lời:** bấm vào tên mô hình ở góc trên bên phải (ví dụ `qwen3.5:9b`).
  - Hiểu đơn giản, con số trước chữ **b** càng lớn thì mô hình càng "to": thường trả lời kỹ hơn nhưng **chậm hơn**; mô hình nhỏ nhanh hơn nhưng có thể kém chính xác hơn.
  - Lựa chọn **chỉ áp dụng cho bạn** trên trình duyệt đang dùng, không ảnh hưởng người khác.
  - **Người mới nên giữ nguyên mô hình mặc định.**
- **Trên điện thoại:** bấm nút **☰** ở góc trên bên trái để mở thanh bên; bấm ra ngoài để đóng lại.

---

## 15. Phím tắt

Dành cho người dùng máy tính muốn thao tác nhanh:

| Phím | Tác dụng |
|---|---|
| **Enter** | Gửi câu hỏi |
| **Shift + Enter** | Xuống dòng trong ô câu hỏi |
| **Ctrl + K** | Tìm cuộc trò chuyện cũ |
| **Ctrl + /** | Mở hoặc đóng Sổ tay |
| **Esc** | Hủy ghi âm, đóng hộp thoại đang mở |
| **Ctrl + B / I / U** | Chữ đậm / nghiêng / gạch chân trong Ghi chú |

---

## 16. Câu hỏi thường gặp và cách xử lý khi gặp trục trặc

### Trợ lý trả lời rất lâu
Mỗi câu trả lời thường mất khoảng một phút, lâu hơn khi nhiều người cùng dùng. Hãy chờ và đừng tải lại trang. Nếu lâu bất thường, bấm **Dừng trả lời** rồi hỏi lại bằng câu ngắn gọn hơn.

### Trạng thái không phải "Sẵn sàng" (chấm không xanh) hoặc báo mất kết nối
Kiểm tra mạng Internet của bạn, rồi bấm **Thử kết nối lại** trong ô trạng thái ở thanh bên trái, hoặc tải lại trang (phím **F5**). Nếu trạng thái là *Đang khởi tạo*, hệ thống đang khởi động, hãy chờ vài phút.

### Nút bị mờ, bấm vào thì bị yêu cầu đăng nhập hoặc xác minh email
Tính năng đó cần tài khoản ([mục 9](#9-tài-khoản-có-cần-đăng-ký-không)). Làm theo hướng dẫn hiện ra là mở được.

### Không nhận được mã xác minh email
Kiểm tra thư mục **Thư rác (Spam)** và **Quảng cáo**; kiểm tra lại email đã gõ đúng chưa (bấm *Nhập sai email? Sửa lại*); chờ 60 giây rồi bấm **Gửi lại mã**. Vẫn không được thì nhờ quản trị viên xác minh hộ.

### Nút "Nói" bị mờ hoặc không ghi âm được
- Khi trình duyệt hỏi quyền micro, phải chọn **Cho phép**. Nếu lỡ chọn *Chặn*: bấm biểu tượng **ổ khóa** bên trái thanh địa chỉ, tìm mục **Micro**, đổi sang **Cho phép**, rồi tải lại trang.
- Kiểm tra máy đã cắm hoặc có micro, và micro không bị ứng dụng khác (Zoom, Meet…) chiếm dụng.

### Đổi máy thì không thấy lịch sử cũ
Lịch sử của khách chỉ lưu trên trình duyệt đã dùng. Hãy **đăng nhập** để lịch sử đi theo tài khoản.

### Trợ lý trả lời sai hoặc thiếu
Bấm vào nguồn để đọc văn bản gốc; hỏi lại cụ thể hơn (nêu cấp học, số hiệu văn bản); dùng bộ lọc phạm vi. Nếu thấy sai rõ ràng, hãy báo cho nhóm thực hiện kèm câu hỏi bạn đã hỏi.

### Tệp đính kèm báo lỗi hoặc đọc mãi không xong
Kiểm tra tệp không quá lớn (khoảng 40 MB) và đúng định dạng hỗ trợ ([mục 10](#10-hỏi-về-tài-liệu-của-riêng-bạn)). PDF scan nhiều trang hoặc video dài cần vài phút. Nếu vẫn lỗi, hãy thử lưu tệp sang định dạng khác (ví dụ Word sang PDF) rồi đính kèm lại.

### Quên mật khẩu
Liên hệ quản trị viên để được đặt lại mật khẩu.

### Dùng trên điện thoại được không?
Được. Giao diện tự co giãn theo màn hình. Bấm **☰** để mở thanh bên.

---

## 17. Những điều cần nhớ

1. **Trợ lý có thể sai.** Với việc quan trọng (ra quyết định, làm hồ sơ, trích dẫn trong văn bản chính thức), hãy **bấm vào nguồn và đọc lại văn bản gốc**.
2. **Trợ lý chỉ biết những gì có trong kho.** Câu trả lời *"không tìm thấy"* là trợ lý trung thực, không phải lỗi.
3. **Chú ý các khung cảnh báo** về văn bản bị thay thế, sửa đổi, dự thảo hoặc số liệu cần đối chiếu.
4. Câu trả lời mang tính **tham khảo**, không thay thế văn bản chính thức hay ý kiến tư vấn pháp lý.
5. **Đăng xuất** khi dùng máy tính chung.

---

*Chúc bạn tra cứu hiệu quả! Mọi góp ý xin gửi về nhóm thực hiện (xem mục **Nhóm thực hiện** ở thanh bên trái của trang web).*
