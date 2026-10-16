"""Ghép phán định đọc trực tiếp mới và xuất báo cáo; không gọi model chấm."""
import csv
import json
from pathlib import Path
import sys

import tong_hop_sau_loc_nguon as collect

ROOT, OUT = collect.ROOT, collect.OUT
OLD = ROOT / "nhat_ky_do_test" / "thuc_nghiem_20261015"
read, save = collect.read, collect.save


def frac(a, b):
    return f"{a}/{b} ({100*a/b:.1f}%)" if b else "Không có mẫu"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    collect.main()
    sheet = read(OUT / "phieu_cham_50_cau.json")
    rag = read(OUT / "cham_rag_truc_tiep.json")
    raw = read(OUT / "cham_khong_rag_truc_tiep.json")
    plan = read(OUT / "ke_hoach_cham.json")
    expected = set(map(str, plan["stt_du_dieu_kien"]))
    assert set(rag) == set(raw) == expected and len(expected) == 30
    old_sheet = read(OLD / "phieu_cham_50_cau.json")
    excluded = {r["stt"]:r["nhan_xet"] for r in old_sheet["cap_cau_tra_loi"] if not r["du_dieu_kien_so_sanh"]}
    for row in sheet["cap_cau_tra_loi"]:
        key = str(row["stt"])
        if row["du_dieu_kien_so_sanh"]:
            row.update(rag[key])
            row.update(raw[key])
            row["nhan_xet"] = "RAG: " + row.pop("nhan_xet_rag") + " Không RAG: " + row.pop("nhan_xet_khong_rag")
            for k in ("cham_rag", "cham_khong_rag"):
                assert row[k] in (0, 1)
            for k in ("ao_giac_rag", "ao_giac_khong_rag", "tu_choi_rag", "tu_choi_khong_rag"):
                assert type(row[k]) is bool
        else:
            row["nhan_xet"] = excluded[row["stt"]]
    sheet["luu_y"] = "Giữ cùng mẫu 50 và cùng 30 cặp đủ căn cứ của lượt trước, xác lập trước khi đọc đáp án mới. Mọi điểm của hai nhánh đều chấm lại.20 cặp chưa xác nhận nguồn giữ nguyên và không tính điểm chính. Đây là chấm bởi trợ lý AI, chưa có người chấm độc lập."
    save("phieu_cham_50_cau.json", sheet)
    rows = sheet["cap_cau_tra_loi"]
    with (OUT / "bang_cham_50_cau.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    use = [r for r in rows if r["du_dieu_kien_so_sanh"]]
    scores = {"so_cap_sinh":50,"so_cap_doi_chieu":30,"so_cap_chua_xac_nhan_nguon":20}
    for key in ("rag", "khong_rag"):
        scores[key] = {"dung":sum(r["cham_"+key] for r in use),
            "co_phat_bieu_sai_hoac_thieu_can_cu":sum(r["ao_giac_"+key] for r in use),
            "tu_choi_hoan_toan":sum(r["tu_choi_"+key] for r in use),
            "stt_co_phat_bieu_sai":[r["stt"] for r in use if r["ao_giac_"+key]]}
    scores["rag_cai_thien_diem"] = sum(r["cham_rag"] > r["cham_khong_rag"] for r in use)
    scores["rag_kem_hon_diem"] = sum(r["cham_rag"] < r["cham_khong_rag"] for r in use)
    save("thong_ke_cham_50_cau.json", scores)
    stats = read(OUT / "thong_ke_tu_dong.json")
    before = read(OLD / "thong_ke_tu_dong.json")
    old_scores = read(OLD / "thong_ke_cham_50_cau.json")
    refusal = read(OUT / "doi_chieu_30_ngoai_pham_vi.json")
    assert stats["hoan_tat_200"] and len(refusal["ket_qua"]) == 30
    n = 30
    a, b = scores["rag"], scores["khong_rag"]
    fmt = lambda x: frac(x["tu_so"], x["mau_so"])
    warning_ids = ", ".join(str(r["thu_tu"]) for r in stats["cau_bi_canh_bao"])
    manifest = read(OUT / "manifest.json")
    text = f"""# Benchmark đầy đủ sau lọc nguồn — 16/10/2026

Đã hoàn tất 200/200 câu test ở chế độ đầy đủ và sinh lại 50/50 câu không RAG. Model giữ nguyên **{manifest['model']}**, embedding bge-m3, kho 111.152 vector; bộ lọc nguồn bật, cache trả lời và tác vụ tự cập nhật kho tắt trong lượt đo. Không chỉnh mã hoặc ngưỡng theo kết quả lượt test này.

**Điểm nội dung dưới đây do trợ lý AI đọc và đối chiếu trực tiếp, chưa phải chấm tay độc lập của con người.** Mọi đáp án, nguồn, điểm và nhận xét được lưu để tác giả xác nhận. Đây là đánh giá lặp trên tập test đã được xem trước, không phải holdout hoàn toàn mới.

## Kết quả đầy đủ 200 câu

| Chỉ số | Lượt trước | Sau lọc nguồn |
|---|---:|---:|
| Phản hồi hoàn tất hợp lệ |200/200|200/200|
| Ngoài phạm vi: cờ tự động nhận diện từ chối |{fmt(before['tu_choi_dung_ngoai_pham_vi'])}|{fmt(stats['tu_choi_dung_ngoai_pham_vi'])}|
| Ngoài phạm vi: từ chối hoàn toàn sau đọc trực tiếp |25/30 (83,3%)|{frac(refusal['tu_choi_hoan_toan'],30)}|
| Trong phạm vi: cờ tự động nhận diện từ chối |{fmt(before['tu_choi_trong_pham_vi'])}|{fmt(stats['tu_choi_trong_pham_vi'])}|
| Câu có cảnh báo hậu kiểm |{fmt(before['co_canh_bao_hau_kiem'])}|{fmt(stats['co_canh_bao_hau_kiem'])}|
| Câu có cảnh báo chỉ mục trích dẫn |{fmt(before['canh_bao_trich_dan'])}|{fmt(stats['canh_bao_trich_dan'])}|
| Câu có cảnh báo số liệu |{fmt(before['canh_bao_so_lieu'])}|{fmt(stats['canh_bao_so_lieu'])}|
| Câu có [n], mọi chỉ mục trong phạm vi nguồn |{fmt(before['trich_dan_khong_vuot_so_nguon_tren_cau_co_trich_dan'])}|{fmt(stats['trich_dan_khong_vuot_so_nguon_tren_cau_co_trich_dan'])}|

Các câu bị cảnh báo ở lượt mới: **{warning_ids}**. Xem `thong_ke_tu_dong.json` và từng `cau_NNN.json` để biết số nào bị gắn cờ. Cảnh báo số liệu chỉ yêu cầu đối chiếu, không tự chứng minh câu đó bịa; số thứ tự/dẫn chiếu cũng có thể bị gắn cờ.

Hậu kiểm trích dẫn chỉ nhận dạng [n], không kiểm tra tính đúng của từng phát biểu so với điều khoản nguồn. Có 10/200 câu dùng [n] (5% toàn test); trong 89 câu không gắn cờ từ chối, độ bao phủ là 10/89 (11,2%). Các cách viết như EVIDENCE 1 không được bộ hậu kiểm hiện có kiểm tra. Vì thế 100% trên 10 câu có [n] không có nghĩa 200 câu đều có trích dẫn đúng về ngữ nghĩa. Câu không có [n] vẫn mặc định qua cờ kiểm tra chỉ mục.

Cờ từ chối tự động đạt 28/30 nhưng đọc trực tiếp chỉ 27/30 từ chối hoàn toàn. Câu 50 vừa nói thiếu thông tin Montessori vừa tiếp tục cung cấp nội dung; câu 43 cung cấp mã Python; câu 65 thừa nhận thiếu thông tin nhưng vẫn liệt kê ý lạc đề. Nhãn câu Python xung đột với sách Tin học thực sự có trong kho; giữ nguyên nhãn để bảo toàn test. Chi tiết trong `doi_chieu_ngoai_pham_vi.md`.

83/170 là số câu trong phạm vi **bị gắn cờ từ chối**, chưa phải 83 từ chối oan đã xác nhận: có câu pha trộn nội dung và từ chối, có nguồn đáp án chưa đủ định danh. Không dùng chỉ số truy hồi hoặc hậu kiểm để thay cho độ đúng nội dung.

## LLM gốc so với toàn pipeline RAG

Giữ nguyên mẫu 50 câu, seed 20261015 và cùng 30 cặp đủ căn cứ như lượt trước; danh sách được đóng băng trước khi đọc đáp án mới. Sinh lại cả hai nhánh, chấm lại từng đáp án.20 cặp chưa xác nhận nguồn được giữ trong bảng 50 nhưng không tính điểm chính. Không thay mẫu theo đáp án đúng/sai.

Thang 1: đúng ý chính, đủ trả lời, không có sai sót thực chất. Thang 0: sai, thiếu ý cốt lõi hoặc từ chối khi nguồn đối chiếu có đáp án. Đánh riêng phát biểu thực chất sai/không được nguồn đối chiếu hỗ trợ; thiếu ý và từ chối không tự động là ảo giác. Chấm theo nội dung nguồn lưu trong kho, chưa phải xác minh pháp lý độc lập về hiệu lực của mọi nguồn.

| Chỉ số trên cùng 30 cặp | LLM gốc mới | LLM+RAG sau lọc | RAG lượt trước |
|---|---:|---:|---:|
| Đúng và đủ |{frac(b['dung'],n)}|{frac(a['dung'],n)}|{frac(old_scores['rag_dung'],n)}|
| Có phát biểu sai/không được nguồn đối chiếu hỗ trợ |{frac(b['co_phat_bieu_sai_hoac_thieu_can_cu'],n)}|{frac(a['co_phat_bieu_sai_hoac_thieu_can_cu'],n)}|{frac(old_scores['rag_phat_bieu_sai_hoac_khong_can_cu'],n)}|
| Từ chối hoàn toàn |{frac(b['tu_choi_hoan_toan'],n)}|{frac(a['tu_choi_hoan_toan'],n)}|10/30 (33,3%)|

Theo điểm 0/1, RAG tốt hơn ở {scores['rag_cai_thien_diem']} cặp và kém hơn ở {scores['rag_kem_hon_diem']} cặp. Không suy độ đúng của 30 câu thành độ đúng toàn 200 câu. Các câu đúng vẫn có thể dài hoặc chép thêm đoạn lạc đề; lỗi trình bày được ghi riêng.

**Câu hỏi nghiên cứu RAG có giảm ảo giác không:** trên mẫu đối chiếu hiện tại, toàn pipeline RAG có {a['co_phat_bieu_sai_hoac_thieu_can_cu']}/30 câu có phát biểu sai/thiếu căn cứ, so với {b['co_phat_bieu_sai_hoac_thieu_can_cu']}/30 ở LLM gốc. Chênh lệch là {100*(b['co_phat_bieu_sai_hoac_thieu_can_cu']-a['co_phat_bieu_sai_hoac_thieu_can_cu'])/n:.1f} điểm phần trăm. Đây là bằng chứng sơ bộ do AI đối chiếu trên mẫu nhỏ; pipeline còn gồm cổng chặn, quản lý hiệu lực và công cụ, nên chưa tách được riêng tác dụng truy hồi.

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
"""
    (OUT / "bao_cao_ket_qua_cuoi.md").write_text(text,encoding="utf-8")
    word = f"""# Nội dung bổ sung báo cáo sau lọc nguồn

Đo lại chế độ đầy đủ benchmark_chatbot.py trên 200 câu test, giữ model {manifest['model']}, bật bộ lọc nguồn, tắt cache trả lời và tác vụ cập nhật kho trong lượt đo.200/200 phản hồi hoàn tất hợp lệ. Bộ nhận diện tự động gắn cờ từ chối 28/30 câu ngoài phạm vi (93,3%); đọc trực tiếp toàn bộ30 câu xác nhận 27/30 từ chối hoàn toàn (90%). Trong phạm vi, 83/170 câu bị gắn cờ từ chối (48,8%); chưa đồng nghĩa mọi câu đó là từ chối oan.

Hậu kiểm cảnh báo 16/200 câu (8%), đều về số liệu; 0/200 cảnh báo chỉ mục trích dẫn. Có 10 câu dùng [n], các chỉ mục đều nằm trong phạm vi nguồn:10/10 (100%). Độ bao phủ[n] chỉ10/200 câu (5%), hoặc10/89 câu không gắn cờ từ chối (11,2%). Kiểm tra này không xác nhận ngữ nghĩa trích dẫn; không dùng0 cảnh báo để khẳng định mọi câu đều có căn cứ.

So sánh cùng model trên mẫu 50 câu cố định;30 cặp đủ căn cứ được chấm 0/1,20 cặp thiếu định danh nguồn giữ riêng. Theo đối chiếu trực tiếp của trợ lý AI, LLM gốc đúng và đủ {b['dung']}/30; LLM+RAG đúng và đủ {a['dung']}/30. Số câu có phát biểu thực chất sai hoặc không được nguồn đối chiếu hỗ trợ là {b['co_phat_bieu_sai_hoac_thieu_can_cu']}/30 ở LLM gốc và {a['co_phat_bieu_sai_hoac_thieu_can_cu']}/30 ở toàn pipeline RAG. Từ chối hoặc thiếu ý không tự động tính là ảo giác. Cần người chấm độc lập xác nhận, chưa gọi đây là chấm tay chuyên gia. Không gán điểm 30 cặp cho toàn bộ200 câu.

So với lượt RAG trước lọc nguồn, đúng và đủ giảm 6 xuống 4/30; phát biểu sai/thiếu căn cứ tăng 7 lên 10/30. Do đó chưa có bằng chứng lọc nguồn đơn lẻ cải thiện chất lượng trả lời cuối. Mẫu nhỏ, tập test đã dùng trước và model không cố định seed sinh là các giới hạn của đánh giá lặp. Nhánh RAG gồm toàn pipeline nên chưa tách riêng tác dụng của truy hồi.
"""
    (OUT / "noi_dung_bo_sung_Word.md").write_text(word,encoding="utf-8")
    save("kiem_tra_ban_giao.json", {"du_200":True,"du_50_doi_chung":True,"du_30_cap_cham_moi":True,
        "nguoi_cham":"AI, chưa độc lập", "hash_khop":manifest["ma_va_kho_khong_doi"]})
    print(json.dumps(scores,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
