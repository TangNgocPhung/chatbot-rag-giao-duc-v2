"""Thống kê bản đo đầy đủ và chuẩn bị phiếu chấm đối chứng; không gọi LLM."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from statistics import mean, median
import time
import sys

ROOT = Path(__file__).resolve().parent
DEFAULT = ROOT / "nhat_ky_do_test" / "thuc_nghiem_20261015"


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def ratio(n, d):
    return {"tu_so": n, "mau_so": d, "ty_le": n / d if d else None}


def summarize(folder):
    labels = {r["cau_hoi"]: r for r in read(ROOT / "bo_cau_hoi_benchmark.json")["cau_hoi"] if r.get("tap") == "test"}
    audits = [read(p) for p in sorted(folder.glob("cau_*.json"))]
    seen = [a["cau_hoi"] for a in audits]
    if len(seen) != len(set(seen)) or any(q not in labels for q in seen):
        raise ValueError("Kết quả trùng câu hoặc có câu ngoài tập test")
    valid = [a for a in audits if a["done"] and not a["ket_qua"]["loi"] and a["ket_qua"]["tra_loi"].strip()]
    outside = [a for a in valid if labels[a["cau_hoi"]].get("mong_doi_tu_choi")]
    inside = [a for a in valid if not labels[a["cau_hoi"]].get("mong_doi_tu_choi")]
    answers = [a for a in valid if not a["ket_qua"]["da_tu_choi"]]
    cited = [a for a in answers if re.search(r"\[\d{1,2}\]", a["ket_qua"]["tra_loi"])]
    warnings = [a for a in valid if any(e["type"] == "warning" for e in a["su_kien"])]
    result = {
        "hoan_tat_200": len(audits) == len(labels) == len(valid) == 200,
        "so_cau_da_chay": len(audits), "so_cau_hop_le": len(valid),
        "so_cau_loi_hoac_khong_done": len(audits) - len(valid),
        "so_cau_test": len(labels),
        "so_cau_ngoai_pham_vi_trong_test": sum(bool(r.get("mong_doi_tu_choi")) for r in labels.values()),
        "tu_choi_dung_ngoai_pham_vi": ratio(sum(a["ket_qua"]["da_tu_choi"] for a in outside), len(outside)),
        "tu_choi_trong_pham_vi": ratio(sum(a["ket_qua"]["da_tu_choi"] for a in inside), len(inside)),
        "co_canh_bao_hau_kiem": ratio(len(warnings), len(valid)),
        "trich_dan_khong_vuot_so_nguon_tren_cau_co_trich_dan": ratio(sum(a["ket_qua"]["trich_dan_hop_le"] for a in cited), len(cited)),
        "co_trich_dan_tren_cau_tra_loi_noi_dung": ratio(len(cited), len(answers)),
        "co_trich_dan_va_khong_vuot_so_nguon_tren_cau_tra_loi_noi_dung": ratio(sum(a["ket_qua"]["trich_dan_hop_le"] for a in cited), len(answers)),
        "canh_bao_trich_dan": ratio(sum(not a["ket_qua"]["trich_dan_hop_le"] for a in valid), len(valid)),
        "canh_bao_so_lieu": ratio(sum(not a["ket_qua"]["so_lieu_co_can_cu"] for a in valid), len(valid)),
        "thoi_gian_giay_tb": mean(a["ket_qua"]["giay"] for a in valid) if valid else None,
        "thoi_gian_giay_trung_vi": median(a["ket_qua"]["giay"] for a in valid) if valid else None,
        "cau_bi_canh_bao": [{"thu_tu": a["thu_tu"], "cau_hoi": a["cau_hoi"], "canh_bao": [e for e in a["su_kien"] if e["type"] == "warning"]} for a in warnings],
        "gioi_han": ["Hậu kiểm chỉ kiểm tra chỉ mục [n] và sự xuất hiện của số; không xác nhận phát biểu được nguồn hỗ trợ về ngữ nghĩa.",
                     "Số liệu được đối chiếu với mọi evidence, không chỉ evidence gắn với từng phát biểu.",
                     "Câu không có [n] vẫn có thể được cờ trich_dan_hop_le=True; vì vậy báo riêng độ bao phủ trích dẫn.",
                     "Lỗi thực thi không được tính thành từ chối đúng.",
                     "Tỉ lệ từ chối trong phạm vi là dấu hiệu thiếu trả lời; cần chấm nội dung để xác định có thực sự từ chối oan."]
    }
    (folder / "thong_ke_tu_dong.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result, audits


def paired_sheet(folder, audits):
    sample = read(folder / "mau_40_cau.json", [])
    base = read(ROOT / "ket_qua_llm_khong_rag.json", {}).get("ket_qua", [])
    rag = {a["cau_hoi"]: a for a in audits}
    raw = {r["cau_hoi"]: r for r in base}
    existing = read(folder / "phieu_cham_40_cau.json", {})
    scores = {r["cau_hoi"]: r for r in existing.get("cap_cau_tra_loi", [])}
    review = read(folder / "cham_doi_chieu_ai.json", {})
    reviewed = {r["stt"]: r for r in review.get("cap_cau_tra_loi", [])}
    pairs = []
    for i, label in enumerate(sample, 1):
        q = label["cau_hoi"]
        a, b = rag.get(q, {}), raw.get(q, {})
        old = {**scores.get(q, {}), **reviewed.get(i, {})}
        pairs.append({"stt": i, **label,
                      "tra_loi_rag": a.get("ket_qua", {}).get("tra_loi"),
                      "tra_loi_khong_rag": b.get("tra_loi_khong_rag"),
                      "tep_bang_chung": f"cau_{a['thu_tu']:03d}.json" if a else None,
                      "loi_khong_rag": b.get("loi"),
                      "cham_rag": old.get("cham_rag"), "cham_khong_rag": old.get("cham_khong_rag"),
                      "ao_giac_rag": old.get("ao_giac_rag"), "ao_giac_khong_rag": old.get("ao_giac_khong_rag"),
                      "can_cu_doi_chieu": old.get("can_cu_doi_chieu", ""),
                      "nhan_xet": old.get("nhan_xet", "")})
    sheet = {"nguoi_cham": review.get("nguoi_cham") or existing.get("nguoi_cham", None),
             "thang_diem": {"1": "Đúng ý chính, đủ trả lời câu hỏi, không có sai sót thực chất khi đối chiếu nguồn chuẩn.",
                             "0": "Sai, thiếu ý cốt lõi, lạc câu hỏi hoặc từ chối câu có đáp án trong nguồn chuẩn.",
                             "null": "Chưa chấm hoặc không đủ bằng chứng chuẩn; không được tính là 0."},
             "ao_giac": "Đánh riêng true/false: có phát biểu thực chất sai hoặc tự tạo căn cứ; từ chối không tự động là ảo giác. Thiếu chứng cứ để kết luận thì null.",
             "yeu_cau": "Đọc văn bản nguồn chuẩn, ghi điều/khoản hoặc đoạn đối chiếu. Không dùng kết quả truy hồi đúng nguồn thay cho điểm nội dung. Nguồn truy hồi có thể sai; cần kiểm tra nguồn mong đợi.",
             "cap_cau_tra_loi": pairs}
    (folder / "phieu_cham_40_cau.json").write_text(json.dumps(sheet, ensure_ascii=False, indent=2), encoding="utf-8")
    scored = [p for p in pairs if p["cham_rag"] in (0, 1) and p["cham_khong_rag"] in (0, 1)]
    if scored:
        stats = {"so_cap_da_cham": len(scored), "rag_dung": sum(p["cham_rag"] for p in scored),
                 "khong_rag_dung": sum(p["cham_khong_rag"] for p in scored)}
        (folder / "thong_ke_cham_noi_dung.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


def markdown_report(folder, stats):
    final = folder / "bao_cao_ket_qua_cuoi.md"
    if final.exists():
        (folder / "bao_cao_thuc_nghiem.md").write_text(final.read_text(encoding="utf-8"), encoding="utf-8")
        return
    def fmt(value):
        return (f"{value['tu_so']}/{value['mau_so']} ({100 * value['ty_le']:.1f}%)"
                if value["ty_le"] is not None else "Chưa có mẫu hợp lệ")
    sheet = read(folder / "phieu_cham_40_cau.json", {})
    pairs = sheet.get("cap_cau_tra_loi", [])
    n_base = sum(p["tra_loi_khong_rag"] is not None for p in pairs)
    n_rag_scored = sum(p["cham_rag"] in (0, 1) for p in pairs)
    n_paired_scored = sum(p["cham_rag"] in (0, 1) and p["cham_khong_rag"] in (0, 1) for p in pairs)
    text = ["# Kết quả thực nghiệm bổ sung", "",
            f"Đã xử lý {stats['so_cau_da_chay']}/200 câu; {stats['so_cau_hop_le']} lượt có phản hồi hoàn tất hợp lệ. "
            + ("Đã hoàn tất bộ 200 câu." if stats["hoan_tat_200"] else "**Đang chạy, chưa được dùng làm số đo cuối.**"), "",
            "| Chỉ số | Kết quả |", "|---|---|",
            f"| Ngoài phạm vi: được bộ nhận diện gắn cờ từ chối | {fmt(stats['tu_choi_dung_ngoai_pham_vi'])} |",
            f"| Trong phạm vi: được bộ nhận diện gắn cờ từ chối | {fmt(stats['tu_choi_trong_pham_vi'])} |",
            f"| Câu có cảnh báo hậu kiểm | {fmt(stats['co_canh_bao_hau_kiem'])} |",
            f"| Cảnh báo trích dẫn | {fmt(stats['canh_bao_trich_dan'])} |",
            f"| Cảnh báo số liệu | {fmt(stats['canh_bao_so_lieu'])} |",
            f"| Trích dẫn không vượt số nguồn, trong số câu có trích dẫn | {fmt(stats['trich_dan_khong_vuot_so_nguon_tren_cau_co_trich_dan'])} |",
            f"| Câu có ký hiệu [n], trong số câu không gắn cờ từ chối | {fmt(stats['co_trich_dan_tren_cau_tra_loi_noi_dung'])} |", "",
            f"Đối chứng: đã có {n_base}/40 câu trả lời không RAG. Phiếu `phieu_cham_40_cau.json` lưu từng cặp và thang 0/1. "
            f"Đã đối chiếu {n_rag_scored}/40 câu RAG, {n_paired_scored}/40 cặp đầy đủ. "
            "Đây là điểm do trợ lý AI đối chiếu trực tiếp, cần người chấm độc lập xác nhận. "
            "Chưa kết luận RAG giảm ảo giác khi chưa đủ cặp.", "",
            "**Giới hạn cách đo:**", ""]
    text.extend(f"- {line}" for line in stats["gioi_han"])
    if (folder / "doi_chieu_ngoai_pham_vi.md").exists():
        text += ["", "**Kiểm tra trực tiếp toàn bộ 30 câu ngoài phạm vi:** 25/30 (83,3%) từ chối hoàn toàn; "
                 "1/30 thừa nhận thiếu thông tin nhưng diễn giải lạc đề; 4/30 vẫn cung cấp nội dung. "
                 "Hai câu vừa từ chối vừa đưa ra thông tin không có căn cứ đã bị bộ nhận diện đếm vào 27/30. "
                 "Xem [bảng đối chiếu nội dung](doi_chieu_ngoai_pham_vi.md). Đây là đối chiếu do trợ lý AI thực hiện, "
                 "chưa phải đánh giá độc lập của người chấm."]
    text += ["", "LLM+RAG là toàn pipeline hiện tại (cổng chặn, công cụ và kiểm tra hiệu lực). "
             "So với LLM gốc, chênh lệch phản ánh cả pipeline; chưa tách riêng đóng góp của truy hồi.", ""]
    (folder / "bao_cao_thuc_nghiem.md").write_text("\n".join(text), encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--thu-muc", type=Path, default=DEFAULT)
    parser.add_argument("--theo-doi", action="store_true", help="cập nhật báo cáo khi tiến trình đo đang chạy")
    args = parser.parse_args()
    while True:
        result, audits = summarize(args.thu_muc)
        paired_sheet(args.thu_muc, audits)
        markdown_report(args.thu_muc, result)
        if not args.theo_doi:
            print(json.dumps({k: v for k, v in result.items() if k not in ("cau_bi_canh_bao", "gioi_han")}, ensure_ascii=False, indent=2))
            break
        progress = read(args.thu_muc / "tien_do.json", {})
        if progress.get("giai_doan") in ("cho_cham_noi_dung", "loi"):
            break
        time.sleep(15)


if __name__ == "__main__":
    main()
