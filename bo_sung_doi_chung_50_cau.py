"""Mở rộng mẫu 40 thành 50 bằng cùng seed, giữ nguyên toàn bộ 40 lượt cũ."""
import json
import os
from pathlib import Path
import pickle
import random
import sys
import time

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "nhat_ky_do_test" / "thuc_nghiem_20261015"


def save(path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def main():
    os.chdir(ROOT)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    import chi_so_ir
    import main as app
    import llm_khong_rag
    labels = json.loads((ROOT / "bo_cau_hoi_benchmark.json").read_text(encoding="utf-8"))["cau_hoi"]
    population = [r for r in labels if r.get("tap") == "test" and r.get("nhom") != "ngoai_pham_vi"]
    sample = random.Random(20261015).sample(population, 50)
    assert sample[:40] == json.loads((OUT / "mau_40_cau.json").read_text(encoding="utf-8"))
    save(OUT / "mau_50_cau.json", sample)
    save(OUT / "ly_do_mo_rong_mau.json", {
        "ngay": "2026-10-16", "seed": 20261015, "so_cau": 50,
        "ly_do": "Một số nguồn gắn nhãn thiếu số hiệu/ngày trong nội dung trích. Mở rộng trước khi sinh 10 baseline mới để vẫn có khoảng 30–50 cặp đủ cơ sở đối chiếu.",
        "bao_toan": "40 câu đầu trùng khớp mẫu ban đầu; không thay câu theo kết quả đúng/sai; giữ tất cả 50, nêu riêng nguồn chưa xác nhận; tái sử dụng câu RAG của lượt 200 đã đóng băng."
    })
    with (ROOT / "faiss_index_data_giao_duc" / "index.pkl").open("rb") as f:
        store, _ = pickle.load(f)
    docs = list(store._dict.items())
    dest = OUT / "nguon_chuan_50_cau"
    dest.mkdir(exist_ok=True)
    for i, item in enumerate(sample, 1):
        refs = [{"chunk_id": key, "metadata": doc.metadata, "page_content": doc.page_content}
                for key, doc in docs if any(chi_so_ir.khop_nhan(doc.metadata.get("source_file", ""), k)
                                          for k in item.get("nguon_mong_doi", []))]
        save(dest / f"nguon_{i:02d}.json", {"stt": i, **item, "doan_nguon": refs})
    old = json.loads((OUT / "ket_qua_llm_khong_rag.json").read_text(encoding="utf-8"))
    target = OUT / "ket_qua_llm_khong_rag_50.json"
    result = json.loads(target.read_text(encoding="utf-8")) if target.exists() else old
    assert result["ket_qua"][:40] == old["ket_qua"]
    assert all(r["cau_hoi"] == q["cau_hoi"] for r, q in zip(result["ket_qua"], sample))
    model = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))["model"]
    assert result["model"] == model
    llm = app.tao_llm(model)
    for i, item in enumerate(sample[len(result["ket_qua"]):], len(result["ket_qua"]) + 1):
        t0 = time.perf_counter()
        try:
            answer = llm.invoke([("system", llm_khong_rag.HE_THONG), ("human", item["cau_hoi"])]).content
            error = ""
        except Exception as exc:
            answer, error = "", f"{type(exc).__name__}: {exc}"
        result["ket_qua"].append({"cau_hoi": item["cau_hoi"], "nhom": item["nhom"],
                                 "nguon_mong_doi": item.get("nguon_mong_doi", []),
                                 "tra_loi_khong_rag": answer, "giay": round(time.perf_counter() - t0, 1), "loi": error})
        result["mo_rong_luc"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save(target, result)
        print(f"[{i}/50] {result['ket_qua'][-1]['giay']}s {error or 'OK'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
