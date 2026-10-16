"""Tổng hợp lượt đo sau lọc; tạo phiếu mới, không tái sử dụng điểm cũ."""
import csv
import json
from pathlib import Path
import sys

from tong_hop_thuc_nghiem import summarize

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "nhat_ky_do_test" / "sau_loc_nguon_20261016"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    stats, audits = summarize(OUT)
    assert stats["hoan_tat_200"], "Chưa hoàn tất 200 câu hợp lệ."
    manifest = read(OUT / "manifest.json")
    assert manifest.get("hoan_tat_sinh") and manifest.get("ma_va_kho_khong_doi")
    sample = read(OUT / "mau_50_cau.json")
    baseline = read(OUT / "ket_qua_llm_khong_rag.json")
    assert len(sample) == len(baseline["ket_qua"]) == 50
    assert baseline["model"] == manifest["model"]
    assert all(a["cau_hoi"] == b["cau_hoi"] and not b["loi"]
               for a, b in zip(sample, baseline["ket_qua"]))
    rag = {a["cau_hoi"]: a for a in audits}
    plan = read(OUT / "ke_hoach_cham.json")
    target = OUT / "phieu_cham_50_cau.json"
    previous = read(target) if target.exists() else {}
    scores = {p["stt"]: p for p in previous.get("cap_cau_tra_loi", [])}
    pairs = []
    for i, (q, b) in enumerate(zip(sample, baseline["ket_qua"]), 1):
        a = rag[q["cau_hoi"]]
        p = {"stt": i, **q, "du_dieu_kien_so_sanh": i in plan["stt_du_dieu_kien"],
             "tra_loi_rag": a["ket_qua"]["tra_loi"],
             "tra_loi_khong_rag": b["tra_loi_khong_rag"],
             "tep_bang_chung_rag": f"cau_{a['thu_tu']:03d}.json",
             "tep_nguon_doi_chieu": f"nguon_chuan_50_cau/nguon_{i:02d}.json"}
        for key in ("cham_rag", "cham_khong_rag", "ao_giac_rag", "ao_giac_khong_rag",
                    "tu_choi_rag", "tu_choi_khong_rag", "nhan_xet"):
            p[key] = scores.get(i, {}).get(key)
        pairs.append(p)
    save("phieu_cham_50_cau.json", {
        "nguoi_cham": "Trợ lý AI đối chiếu trực tiếp; cần người chấm độc lập xác nhận.",
        "quy_tac": plan["quy_tac"], "cap_cau_tra_loi": pairs})
    with (OUT / "bang_cham_50_cau.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    outside = [a for a in audits if a["ket_qua"].get("mong_doi_tu_choi")]
    # Nhãn nằm ở bộ câu hỏi, không suy từ cờ từ chối được mô hình nhận diện.
    labels = {r["cau_hoi"]: r for r in read(ROOT / "bo_cau_hoi_benchmark.json")["cau_hoi"]}
    outside = [a for a in audits if labels[a["cau_hoi"]].get("mong_doi_tu_choi")]
    save("can_doc_30_ngoai_pham_vi.json", [{"thu_tu":a["thu_tu"],
        "cau_hoi":a["cau_hoi"], "tra_loi":a["ket_qua"]["tra_loi"],
        "co_tu_choi_tu_dong":a["ket_qua"]["da_tu_choi"]} for a in outside])
    print(json.dumps({k:v for k,v in stats.items() if k not in ("cau_bi_canh_bao","gioi_han")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
