"""So bật/tắt bộ lọc trên 50 câu DEV cố định, không gọi mô hình trả lời."""
import json
import os
from pathlib import Path
import random
import sys
import time
import hashlib

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "nhat_ky_lam_sach_kho"
OUT.mkdir(exist_ok=True)
os.chdir(ROOT)
os.environ["RAG_BAT_CACHE"] = "0"
os.environ["RAG_DRIVE_AUTO_SYNC_PHUT"] = "0"
os.environ["RAG_TU_NAP_CHI_MUC"] = "0"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    import benchmark_chatbot as bench
    import chi_so_ir
    import loc_nguon
    from rag_service import RAGService
    code_files = ("loc_nguon.py", "rag_service.py", "van_ban_meta.py", "hieu_luc_bo_sung.py")
    hashes = lambda: {n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in code_files}
    before = hashes()
    service = RAGService()
    service.start_drive_auto_sync = lambda: None
    service.start_quet_thu_muc_nong = lambda: None
    service._ham_nong_model = lambda: None
    for name in ("_lap_ho_so_van_ban", "_lap_phan_loai"):
        original = getattr(service, name)
        def phase(original=original, label=name):
            start = time.perf_counter()
            print(f"Bắt đầu {label}", flush=True)
            result = original()
            print(f"Xong {label}: {time.perf_counter()-start:.1f}s", flush=True)
            return result
        setattr(service, name, phase)
    service.initialize()
    if service.status.state != "ready":
        raise RuntimeError(service.status.message)
    population = [r for r in bench._nap_danh_sach(None, None, "dev") if r.get("nguon_mong_doi")]
    sample = random.Random(20261016).sample(population, min(50, len(population)))
    rows = []
    for i, item in enumerate(sample, 1):
        q = item["cau_hoi"]
        row = {"stt": i, **item}
        usable = [name for name, info in service.danh_muc_nguon.items()
                  if info["trang_thai"] == "su_dung"
                  and any(chi_so_ir.khop_nhan(name, tag) for tag in item["nguon_mong_doi"])
                  and not service.so_quan_he.het_hieu_luc(name)
                  and not (service.tinh_trang_hieu_luc.get(name)
                           and service.tinh_trang_hieu_luc[name].chua_toi_ngay_hieu_luc())]
        row["co_nguon_nhan_dung_duoc_dung"] = bool(usable)
        for enabled, key in (("0", "tat"), ("1", "bat")):
            os.environ["RAG_LOC_NGUON"] = enabled
            start = time.perf_counter()
            try:
                docs = service._retrieve(q)
                # Kiểm cả đường kéo nguồn đi kèm, không chỉ top-k truy hồi.
                prompt_docs, _ = service._them_van_ban_di_kem(docs, q)
                names = [d.metadata.get("source_file","") for d in docs]
                ranks = chi_so_ir.thu_hang_lien_quan(chi_so_ir.xep_hang_tai_lieu(names), item["nguon_mong_doi"])
                reasons = [loc_nguon.ly_do_loai(d, q, service.danh_muc_nguon, service.tinh_trang_hieu_luc,
                           di_kem=bool(d.metadata.get("_di_kem")) and "hướng dẫn" not in
                           d.metadata.get("_di_kem",{}).get("vai_tro","").lower()) for d in prompt_docs]
                row[key] = {"nguon": names, "nguon_prompt": [d.metadata.get("source_file","") for d in prompt_docs],
                            "trung_nguon": bool(ranks), "thu_hang": ranks,
                            "ly_do_can_loai_trong_prompt": [r for r in reasons if r],
                            "giay": round(time.perf_counter()-start,2), "loi": ""}
            except Exception as exc:
                row[key] = {"loi": f"{type(exc).__name__}: {exc}"}
        rows.append(row)
        tmp = OUT / "doi_chieu_50_dev.json.tmp"
        tmp.write_text(json.dumps({"tap":"dev","seed":20261016,"ket_qua":rows},ensure_ascii=False,indent=2),encoding="utf-8")
        tmp.replace(OUT / "doi_chieu_50_dev.json")
        print(f"[{i}/{len(sample)}] {q[:65]}", flush=True)
    good = [r for r in rows if not r["tat"]["loi"] and not r["bat"]["loi"]]
    eligible = [r for r in good if r["co_nguon_nhan_dung_duoc_dung"]]
    stats = {"so_cau":len(rows),"loi":len(rows)-len(good),"co_nguon_nhan_dung_duoc_dung":len(eligible)}
    for key in ("tat","bat"):
        stats[key] = {"trung_nguon_toan_mau":sum(r[key]["trung_nguon"] for r in good),
                      "trung_nguon_nguon_duoc_dung":sum(r[key]["trung_nguon"] for r in eligible),
                      "cau_prompt_co_nguon_can_loai":sum(bool(r[key]["ly_do_can_loai_trong_prompt"]) for r in good),
                      "so_nguon_can_loai_trong_prompt":sum(len(r[key]["ly_do_can_loai_trong_prompt"]) for r in good)}
    (OUT / "tong_ket_50_dev.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding="utf-8")
    after = hashes()
    (OUT / "phien_ban_do_dev.json").write_text(json.dumps({"truoc":before,"sau":after,"khong_doi":before==after},indent=2),encoding="utf-8")
    assert before == after, "Mã đã đổi trong lúc đo; không dùng số này làm kết quả cuối."
    print(json.dumps(stats,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
