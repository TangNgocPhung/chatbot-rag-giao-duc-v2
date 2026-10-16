"""Tiếp tục từ checkpoint, giữ nguyên mọi lượt đã hoàn tất và cấu hình đo."""
import json
import os
import shutil
import sys
import time

import chay_lai_sau_loc_nguon as run

OUT, ROOT, save, now = run.OUT, run.ROOT, run.save, run.now


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    import benchmark_chatbot as bench
    import llm_khong_rag as baseline
    import main as app
    import requests

    manifest = read(OUT / "manifest.json")
    assert run.hashes() == manifest["hash_truoc"], "Mã/cấu hình/kho đã đổi; không tự nối lượt đo."
    old_models = {r["name"]: r["digest"] for r in manifest["ollama_models"]["models"]}
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    current = {r["name"]: r["digest"] for r in requests.get(base_url + "/api/tags", timeout=10).json()["models"]}
    assert current.get(manifest["model"]) == old_models[manifest["model"]]
    assert current.get("bge-m3:latest") == old_models["bge-m3:latest"]
    for endpoint, payload in (("/api/embed", {"model":"bge-m3", "input":"Kiểm tra dịch vụ"}),
                              ("/api/generate", {"model":manifest["model"], "prompt":"Xin chào", "stream":False, "options":{"num_predict":1}})):
        response = requests.post(base_url + endpoint, json=payload, timeout=180)
        response.raise_for_status()
    manifest.setdefault("runtime", []).append({"luc":now(),"base_url":base_url,
        "version":requests.get(base_url + "/api/version",timeout=10).json(),
        "ghi_chu":"Khôi phục bản0.40.4 từ gói chính thức trong workspace sau lỗi cập nhật toàn máy; giữ nguyên digest model sinh và embedding. Đổi cổng dịch vụ, không đổi tham số sinh."})
    items = bench._nap_danh_sach(None, None, "test")
    completed = {}
    for f in sorted(OUT.glob("cau_*.json")):
        a = read(f)
        assert a["thu_tu"] not in completed
        assert a["cau_hoi"] == items[a["thu_tu"] - 1]["cau_hoi"]
        assert a["done"] and not a["ket_qua"]["loi"]
        completed[a["thu_tu"]] = a
    manifest.setdefault("tiep_tuc", []).append({"luc": now(), "giu_nguyen_cau_da_xong": len(completed),
        "ly_do": "Tiến trình của phiên trước dừng khi phiên bị ngắt. Nối từ checkpoint; không chọn/chạy lại đáp án đã hoàn tất."})
    save(OUT / "manifest.json", manifest)
    original_initialize = bench.RAGService.initialize

    def initialize(service, *args, **kwargs):
        service.start_drive_auto_sync = lambda: None
        service.start_quet_thu_muc_nong = lambda: None
        original_initialize(service, *args, **kwargs)
        assert service.llm_model == manifest["model"]
        params = service._llm_tom_tat(service.llm_model).model_dump()
        expected = dict(manifest["tham_so_sinh"])
        expected["base_url"] = base_url
        assert params == expected

    bench.RAGService.initialize = initialize
    original_run = bench.chay_mot_cau
    count = 0

    def one(service, item):
        nonlocal count
        count += 1
        if count in completed:
            return bench.KetQuaMotCau(**completed[count]["ket_qua"])
        save(OUT / "tien_do.json", {"giai_doan": "rag", "dang_chay": count, "tong": 200, "luc": now(), "cau_hoi": item["cau_hoi"]})
        audit = {"cau_hoi": item["cau_hoi"], "thu_tu": count, "bat_dau": now(), "evidence": [], "su_kien": [], "done": False}
        old_format, old_stream = service.format_docs, service.stream_answer

        def formatted(docs):
            audit["evidence"] = [{"page_content": d.page_content, "metadata": d.metadata} for d in docs]
            return old_format(docs)

        def stream(*args, **kwargs):
            for e in old_stream(*args, **kwargs):
                if e["type"] not in ("token", "goi_y"):
                    audit["su_kien"].append(e)
                if e["type"] == "done":
                    audit["done"] = True
                yield e

        service.format_docs, service.stream_answer = formatted, stream
        try:
            result = original_run(service, item)
        finally:
            service.format_docs, service.stream_answer = old_format, old_stream
        audit.update({"ket_qua": bench.asdict(result), "ket_thuc": now()})
        if result.loi or not audit["done"]:
            failures = OUT / "loi_ha_tang"
            failures.mkdir(exist_ok=True)
            save(failures / f"cau_{count:03d}_{int(time.time())}.json", audit)
            raise RuntimeError(f"Dừng ở câu {count}: chưa hoàn tất, không ghi vào kết quả chính: {result.loi}")
        save(OUT / f"cau_{count:03d}.json", audit)
        return result

    if len(completed) < 200:
        bench.chay_mot_cau = one
        sys.argv = ["benchmark_chatbot.py", "--bo", "--tap", "test"]
        assert bench.main() == 0
        shutil.copy2(ROOT / "ket_qua_benchmark_day_du_test.json", OUT / "ket_qua_benchmark_day_du_test.json")
    baseline.SO_CAU = 50
    sample = read(OUT / "mau_50_cau.json")
    assert sample == baseline.chon_mau()
    dest = OUT / "ket_qua_llm_khong_rag.json"
    result = read(dest) if dest.exists() else {"model": manifest["model"], "chay_luc": now(), "ket_qua": []}
    assert result["model"] == manifest["model"]
    assert all(r["cau_hoi"] == q["cau_hoi"] and not r["loi"] for r, q in zip(result["ket_qua"], sample))
    llm = app.tao_llm(manifest["model"])
    for i in range(len(result["ket_qua"]), 50):
        item = sample[i]
        save(OUT / "tien_do.json", {"giai_doan": "khong_rag", "dang_chay": i + 1, "tong": 50, "luc": now()})
        start = time.perf_counter()
        answer = llm.invoke([("system", baseline.HE_THONG), ("human", item["cau_hoi"])]).content
        result["ket_qua"].append({"cau_hoi": item["cau_hoi"], "nhom": item["nhom"], "nguon_mong_doi": item.get("nguon_mong_doi", []), "tra_loi_khong_rag": answer, "giay": round(time.perf_counter() - start, 1), "loi": ""})
        save(dest, result)
        print(f"Không RAG [{i+1}/50]", flush=True)
    shutil.copy2(dest, ROOT / "ket_qua_llm_khong_rag.json")
    manifest.update({"ket_thuc": now(), "hash_sau": run.hashes(), "hoan_tat_sinh": True})
    manifest["ma_va_kho_khong_doi"] = manifest["hash_truoc"] == manifest["hash_sau"]
    save(OUT / "manifest.json", manifest)
    assert manifest["ma_va_kho_khong_doi"]
    save(OUT / "tien_do.json", {"giai_doan": "cho_cham_noi_dung", "luc": now()})
    import tong_hop_sau_loc_nguon
    tong_hop_sau_loc_nguon.main()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        save(OUT / "tien_do.json", {"giai_doan": "loi", "luc": now(), "loi": repr(exc)})
        raise
