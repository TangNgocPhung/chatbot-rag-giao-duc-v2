"""Xuất các phán định đã đối chiếu trực tiếp; không dùng LLM tự động chấm."""
import csv
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "nhat_ky_do_test" / "thuc_nghiem_20261015"

# Mỗi dòng là phán định đọc trực tiếp của trợ lý, không suy từ cờ hậu kiểm.
# stt: (điểm RAG, điểm gốc, phát biểu sai/không căn cứ RAG, ...gốc, căn cứ và nhận xét)
GRADES = {
1: (0,0,True,True,"Điều 4 TT01/2024 có 12 thành phần cấu trúc; RAG đổi thành hai khối THPT/chuyên môn. Gốc còn dựng thời gian học nhiều giai đoạn 2–3 năm, trái thời gian khóa học Điều 5. Cả hai sai cấu trúc theo nguồn."),
2: (0,0,False,True,"Điều 4 NĐ57/2017: mẫu giáo 30%, học sinh 40%, bán trú 60%, nội trú và một số nhóm 100%; thời gian hưởng. RAG đúng 40/60% nhưng thiếu mẫu giáo và nội trú. Gốc thay chính sách cụ thể bằng các tên chương trình không được nguồn gắn nhãn hỗ trợ."),
3: (1,0,False,True,"Điều 13–15 TT19/2025: tiểu học nhắc nhở/xin lỗi; ngoài tiểu học nhắc nhở/phê bình/tự kiểm điểm. RAG nêu đủ bốn biện pháp nhưng trình bày chưa rõ hai nhóm. Gốc nêu giam giữ, đánh giá lại điểm như kỷ luật, không có trong danh mục nguồn."),
4: (0,0,False,True,"Điều 3 NĐ188/2026: nội trú 15 kg/tháng, tối đa 9 tháng/năm; Điều 6 quy trình cấp gạo. RAG từ chối. Gốc nói 50 kg/tháng và nhóm hộ nghèo/cận nghèo đặc biệt, sai mức và đối tượng."),
5: (0,0,False,True,"Điều 4–6 QĐ39/2026: 8 bậc; nguồn mô tả từng bậc và quan hệ trình độ. RAG nêu đúng có 8 bậc nhưng không cho biết những bậc nào như câu hỏi. Gốc nói 3 bậc và phân bậc sơ cấp/THPT/đại học sai."),
6: (0,0,True,True,"Luật Giáo dục Điều 2–3: mục tiêu phát triển toàn diện, dân trí/nhân lực/nhân tài; tính nhân dân, dân tộc, khoa học, hiện đại... RAG lấy mục tiêu mầm non gán cho toàn nền giáo dục và Điều 104. Gốc diễn giải các cấp học thành tính chất nền giáo dục."),
9: (0,0,True,True,"Điều 5 NĐ361/2026: quy hoạch, đất, tài chính, thiết bị... RAG lẫn điều kiện phân hiệu (25%) và quy định vốn nước ngoài với thành lập nói chung; bỏ điều kiện tài chính chính. Gốc tự đặt ngưỡng 50/20 học sinh làm điều kiện thành lập."),
12: (0,0,False,True,"Điều 42 Quy chế thi THPT và sửa đổi TT13/2026 có các diện ưu tiên và điều kiện cụ thể. RAG từ chối. Gốc coi điểm thi cao hoặc có khả năng đặc biệt là đối tượng ưu tiên, không được nguồn hỗ trợ."),
14: (0,0,False,True,"Điều 8 NĐ04/2021: các nhóm 10–20, 20–30, 30–40, 40–60 triệu. RAG chỉ nêu đúng nhóm đầu, thiếu các nhóm cốt lõi. Gốc nêu 1–3 đến 10 triệu, trái nguồn. Chấm theo văn bản lưu, chưa thẩm định sửa đổi ngoài kho."),
16: (1,0,False,True,"Điều 7 NĐ88/2026: hệ thống CSDL quốc gia/chuyên ngành, thủ tục hành chính, học liệu số và nền tảng chung, liên thông và bảo mật. RAG đúng ý chính, có phần thêm dài. Gốc đồng nhất nền tảng quốc gia với MOOC."),
17: (0,0,False,True,"Quyết định sáp nhập Điều 1–3 do Thủ tướng ký; bàn giao nguyên trạng người học/nhân sự/tài chính/tài sản, bảo đảm quyền lợi. RAG từ chối. Gốc cũng chưa biết sự kiện nhưng khẳng định thẩm quyền sáp nhập đại học thuộc Bộ trưởng, trái căn cứ quyết định này."),
18: (0,0,False,False,"TT10/2020 Quy chế tổ chức/hoạt động đại học vùng: quan hệ đại học vùng và thành viên, hội đồng, giám đốc, tổ chức và cơ chế hoạt động. RAG từ chối; gốc chỉ định nghĩa rất ngắn, thiếu cơ chế tổ chức/hoạt động. Không đủ bằng chứng để gọi phần tổng quát đó là bịa."),
20: (0,0,True,True,"Điều 1 và 3 NĐ143/2013: người học ngân sách/hiệp định, không chấp hành điều động trong 12 tháng hoặc chưa đủ thời gian làm việc; loại trừ cử tuyển. RAG trả lời riêng chế độ cử tuyển NĐ141/2020 mà không nêu giới hạn, không trả lời phạm vi theo nhãn. Gốc đặt các trường hợp thiếu sức khỏe/ngoại ngữ/chuyên môn không có trong nguồn."),
24: (1,0,False,True,"Luật Trẻ em 102/2016 Điều 11: tháng 6. RAG trả lời đúng tháng 6; phần hỗ trợ tiền và dẫn NĐ còn để trống là lạc đề và căn cứ không sử dụng được, ghi lỗi trình bày/nguồn riêng; không kết luận các mức tiền đó sai khi chưa kiểm tra nguồn khác. Gốc nói tháng 11, sai trực tiếp."),
25: (0,0,True,True,"TT22/2019 ban hành 20/12/2019, Điều 8 quy định tiêu chuẩn theo cấp. RAG gán hiệu lực 01/09/2019 trước ngày ban hành, còn thiếu tiêu chuẩn cụ thể. Gốc dựng mốc 1/7/2003, 5 năm và hoàn thành 2 kỳ thi THPT thành điều kiện thi chủ nhiệm giỏi."),
26: (0,0,False,False,"TT26/2019 Điều 5, 6–14: tài khoản, cập nhật/cung cấp/khai thác dữ liệu, phân công Bộ/Sở/Phòng/cơ sở. RAG từ chối. Gốc nêu nguyên tắc chung hợp lý nhưng không mô tả quản lý/vận hành và trách nhiệm cụ thể. Không đánh thiếu chi tiết thành ảo giác."),
27: (1,0,False,False,"TT05/2026 Điều 9: nghỉ hè theo Chính phủ; lễ/tết theo lao động/BHXH; xử lý nghỉ thai sản trùng hè và chế độ nhà giáo nam. RAG nêu đúng loại nghỉ, nguyên tắc nghỉ hè và phần lớn trường hợp nữ; thiếu đoạn cuối/nam, kèm nội dung lạc đề nên cần biên tập, vẫn đủ ý chính. Gốc thừa nhận không biết, không trả lời."),
28: (0,0,False,True,"NĐ14/2020 Điều 3–4: điều kiện và trợ cấp một lần = lương hưu tháng x 10% x số năm tính trợ cấp. RAG từ chối. Gốc dựng tên Luật Lương hưu bổng và phụ cấp thâm niên 2019, các mức 50/30/20% và khoảng ngày tự mâu thuẫn."),
30: (0,0,False,True,"Luật Viên chức lưu trong nguồn: Điều 11–14 có quyền nghề nghiệp, lương/thưởng, nghề nghiệp/kinh doanh, nghỉ ngơi và quyền khác. RAG từ chối. Gốc thiếu lương/nghỉ ngơi, khẳng định quyền danh tính/chức vụ và giữ bí mật công việc như danh mục quyền của luật, không được các điều khoản nguồn hỗ trợ; dựa luật 2010 trong khi nguồn theo nhãn là 129/2025."),
31: (1,0,False,True,"QĐ38/2026 Điều 4 và Luật Giáo dục Điều 6 trong cau_001.json: chính quy/thường xuyên, mầm non/phổ thông/nghề nghiệp/đại học, các cấp chính. RAG liệt kê đúng các nhóm/cấp chính; thừa nhiều đoạn học bổng và chưa cập nhật đầy đủ chi tiết nghề mới, không nên coi là đáp án mẫu. Gốc gộp lớp 6–12 thành THPT, bỏ mầm non/nghề nghiệp."),
34: (0,0,True,False,"TT13/2026 Điều 1–22 sửa các Điều 1,8,14,20,21,28,31,34,36,37,40,42,47,52,55,59,60,61,63,64 và phụ lục. RAG chỉ đúng bỏ thanh tra, rồi gán nội dung điều khoản thi hành của văn bản khác thành sửa đổi quy chế, bỏ phần chính. Gốc từ chối, không bịa."),
35: (0,0,False,False,"NQ218/2025 Điều 2: đến 2030 có 100% tỉnh/thành đạt chuẩn phổ cập 3–5 tuổi, bảo đảm nguồn lực và lộ trình. RAG từ chối. Gốc nói mục tiêu phát triển trẻ nói chung, không nêu đích phổ cập và mốc thời gian; thiếu nội dung chứ chưa chứng minh sai các ý phát triển trẻ."),
38: (0,0,False,False,"TT56/2021 Điều 3–4: chuyên gia, in ấn, điều tra/minh chứng/báo cáo, đánh giá ngoài, cách chi và trần cụ thể. RAG chỉ lặp tên thông tư. Gốc liệt kê chi phí chung, không nêu mức chi/cách chi; cả hai không trả lời đủ. Không quy phần thiếu thành bịa."),
39: (0,0,False,False,"Tệp theo nhãn TT38/2019, Điều 3–9: môi trường/ứng xử/tuyên truyền, phòng ngừa, hỗ trợ khi có nguy cơ, xử lý khi xảy ra; phối hợp gia đình và cơ quan chức năng. RAG từ chối. Gốc có phòng ngừa/kế hoạch/an toàn nhưng bỏ hỗ trợ và xử lý vụ việc, thiếu hai nhánh cốt lõi."),
40: (0,0,False,False,"Phụ lục 3 CV2345/2021 phần B: yêu cầu cần đạt, đồ dùng, hoạt động dạy học, điều chỉnh sau bài dạy; thông tin môn/lớp/bài/thời gian. RAG bỏ đồ dùng và điều chỉnh; gốc đưa mẫu giáo án chung, bỏ điều chỉnh và không thể hiện đúng khung. Thiếu chứ chưa đủ cơ sở gọi là bịa."),
41: (0,0,False,False,"TT02/2020: các tiêu chuẩn mục tiêu/đầu ra, bản mô tả, cấu trúc/nội dung, tiếp cận dạy học, đánh giá, đội ngũ, hỗ trợ, cơ sở vật chất, nâng cao chất lượng, kết quả... RAG từ chối; gốc chỉ nói năng lực giáo viên, không mô tả bộ tiêu chuẩn đánh giá chương trình. Các ý chung có liên hệ, không kết luận bịa nếu chỉ thiếu."),
42: (1,0,False,False,"NĐ308/2026 Điều 6: đào tạo sơ cấp cho người yếu thế, đào tạo ngành nghề ưu tiên/khó xã hội hóa; nhu cầu/danh mục/phê duyệt và phương thức hỗ trợ. RAG nêu đúng hai nhóm chính và căn cứ; gốc nêu đào tạo lao động nói chung, không chỉ ra hai nhóm, thiếu điều kiện nên không đủ."),
44: (0,0,False,True,"NĐ176/2026 Điều 7: các chuyên ngành điện hạt nhân/liên quan vận hành nhà máy do Bộ GDĐT thống nhất chủ đầu tư và thông báo hằng năm trước tuyển sinh; không ấn định danh sách trong nghị định. RAG nhắc loại ngành nhưng thiếu cơ chế xác định và lại từ chối phần thời gian. Gốc tự nêu ngành và gói tiền nhà/đi lại/khám chữa bệnh không được nguồn hỗ trợ."),
47: (0,0,False,True,"TT45/2020 Điều 7 khoản 1: Mẫu01a, 3 báo cáo Mẫu04, bộ minh chứng/đăng ký nhiệm vụ theo điều kiện, hồ sơ điện tử. RAG bị rút gọn mục c và bỏ hồ sơ điện tử của giảng viên, rồi lạc sang sinh viên. Gốc đặt thêm CV/vị trí cũ/bằng cấp/hợp đồng lao động thành thành phần bắt buộc, không có trong nguồn."),
49: (0,0,True,False,"PhanPhoi-ChuongTrinh-Tin4: Máy tính và em; Mạng máy tính/Internet; tổ chức lưu trữ/tìm kiếm/trao đổi; đạo đức/pháp luật/văn hóa số; ứng dụng; giải quyết vấn đề. RAG ghép giáo dục địa phương lớp10 và chuyên Tin thành nội dung Tin4. Gốc chỉ nêu thao tác/phần mềm chung, bỏ tổ chức lưu trữ, đạo đức/pháp luật/văn hóa số và giải quyết vấn đề; thiếu khung chủ đề theo nguồn, không khẳng định các thao tác chung tự thân là bịa.")
}

EXCLUDED = {7,8,10,11,13,15,19,21,22,23,29,32,33,36,37,43,45,46,48,50}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    sample = load(OUT / "mau_50_cau.json")
    baseline = load(OUT / "ket_qua_llm_khong_rag_50.json")
    assert len(baseline["ket_qua"]) == 50 and not any(r["loi"] for r in baseline["ket_qua"])
    base = {r["cau_hoi"]: r for r in baseline["ket_qua"]}
    audits = {a["cau_hoi"]: a for a in (load(p) for p in OUT.glob("cau_*.json"))}
    rows = []
    for i, label in enumerate(sample, 1):
        audit = audits[label["cau_hoi"]]
        gold = load(OUT / "nguon_chuan_50_cau" / f"nguon_{i:02d}.json")
        eligible = i not in EXCLUDED
        if eligible:
            sr, sb, hr, hb, note = GRADES[i]
        else:
            sr = sb = hr = hb = None
            note = ("Không có đoạn khớp nhãn nguồn mong đợi." if i == 43 else
                    "Bản trích nguồn gắn nhãn thiếu số hiệu/ngày xác định ở phần đầu; chưa xác nhận được bản dùng làm đáp án. Không tự coi từ chối là sai hoặc lời khẳng định là đúng.")
        rows.append({"stt": i, **label, "du_dieu_kien_so_sanh": eligible,
                     "tra_loi_rag": audit["ket_qua"]["tra_loi"], "tra_loi_khong_rag": base[label["cau_hoi"]]["tra_loi_khong_rag"],
                     "cham_rag": sr, "cham_khong_rag": sb, "ao_giac_rag": hr, "ao_giac_khong_rag": hb,
                     "tep_bang_chung_rag": f"cau_{audit['thu_tu']:03d}.json",
                     "tep_nguon_doi_chieu": f"nguon_chuan_50_cau/nguon_{i:02d}.json",
                     "nhan_xet": note})
    record = {"nguoi_cham": "Trợ lý AI đọc/đối chiếu trực tiếp; chưa được người chấm độc lập xác nhận.",
              "quy_tac": "1: đúng ý chính và đủ trả lời, không có sai sót thực chất; 0: sai, thiếu ý cốt lõi hoặc không trả lời khi nguồn có đáp án. Không yêu cầu nguyên văn hoặc đủ mọi chi tiết phụ. Phát biểu sai/không có căn cứ được đánh riêng; từ chối/thiếu không tự động là ảo giác.",
              "kiem_soat_nguon": "Kiểm tra thông tin định danh ở bản trích, không theo tên tệp. Không có số hiệu ở phần đầu hoặc không có đoạn khớp nhãn thì ghi chưa xác nhận và không tính trong mẫu số chính. OCR có chữ số nhưng nhận dạng xấu vẫn cần tác giả kiểm tra; đây không phải thẩm định hiệu lực pháp lý.",
              "mo_rong": "Mẫu50 cùng seed20261015, 40 câu đầu giữ nguyên. Mở rộng vì vấn đề nhận diện nguồn trước khi sinh baseline10 bổ sung; không loại theo đáp án đúng/sai. Bảng đủ50 giữ nguyên mọi cặp.",
              "cap_cau_tra_loi": rows}
    (OUT / "phieu_cham_50_cau.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT / "bang_cham_50_cau.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    use = [r for r in rows if r["du_dieu_kien_so_sanh"]]
    assert len(use) == 30
    stats = {"so_cap_sinh":50, "so_cap_doi_chieu":len(use), "so_cap_chua_xac_nhan_nguon":len(rows)-len(use),
             "rag_dung":sum(r["cham_rag"] for r in use), "goc_dung":sum(r["cham_khong_rag"] for r in use),
             "rag_phat_bieu_sai_hoac_khong_can_cu":sum(r["ao_giac_rag"] for r in use),
             "goc_phat_bieu_sai_hoac_khong_can_cu":sum(r["ao_giac_khong_rag"] for r in use),
             "rag_cai_thien":sum(r["cham_rag"]>r["cham_khong_rag"] for r in use),
             "rag_kem_hon":sum(r["cham_rag"]<r["cham_khong_rag"] for r in use),
             "stt_tinh": [r["stt"] for r in use], "stt_chua_tinh":sorted(EXCLUDED)}
    stats["rag_tu_choi_hoan_toan"] = [4,12,17,18,26,28,30,35,39,41]
    stats["goc_tu_choi_hoan_toan"] = [27,34]
    stats["stt_rag_co_phat_bieu_sai"] = [r["stt"] for r in use if r["ao_giac_rag"]]
    stats["stt_goc_co_phat_bieu_sai"] = [r["stt"] for r in use if r["ao_giac_khong_rag"]]
    (OUT / "thong_ke_cham_50_cau.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
