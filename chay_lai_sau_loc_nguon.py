"""Chạy benchmark gốc, lưu bằng chứng kiểm toán, rồi chạy baseline 50 câu.

Không thay đổi tham số của pipeline. Chỉ tắt cache và tác vụ cập nhật kho
trong tiến trình đo. Các tệp cũ được giữ riêng trước khi bắt đầu.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "nhat_ky_do_test" / "sau_loc_nguon_20261016"
OUT.mkdir(parents=True, exist_ok=True)
os.chdir(ROOT)
os.environ["RAG_BAT_CACHE"] = "0"
os.environ["RAG_DRIVE_AUTO_SYNC_PHUT"] = "0"
os.environ["RAG_TU_NAP_CHI_MUC"] = "0"
os.environ["SO_CAU_KHONG_RAG"] = "50"
os.environ["RAG_LOC_NGUON"] = "1"


def now():
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat()


def save(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def hashes():
    names = ["benchmark_chatbot.py", "rag_service.py", "main.py", "hybrid_retrieval.py",
             "kiem_tra_tra_loi.py", "tu_vung_kho.py", "bo_cau_hoi_benchmark.json",
             "cai_dat.json", "loc_nguon.py", "van_ban_meta.py", "hieu_luc_bo_sung.py", "faiss_index_data_giao_duc/index.faiss",
             "faiss_index_data_giao_duc/index.pkl"]
    result = {}
    for name in names:
        path = ROOT / name
        if path.exists():
            h = hashlib.sha256()
            with path.open("rb") as f:
                for block in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(block)
            result[name] = h.hexdigest()
    return result


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    import benchmark_chatbot as bench
    import llm_khong_rag as baseline
    import requests

    for name in ("ket_qua_benchmark_day_du_test.json", "ket_qua_llm_khong_rag.json"):
        old = ROOT / name
        backup = OUT / (name + ".truoc_lan_do")
        if old.exists() and not backup.exists():
            shutil.copy2(old, backup)
    if (OUT / "manifest.json").exists():
        raise RuntimeError("Thư mục đo đã có manifest; không ghi đè một lần đo đang chạy.")
    manifest = {"bat_dau": now(), "tap": "test", "so_cau": 200,
                "so_cau_so_sanh": 50, "loc_nguon": True, "seed_mau": 20261015,
                "cache": False, "hash_truoc": hashes(),
                "cau_lenh": "benchmark_chatbot.py --bo --tap test",
                "ghi_chu": "Đo lại sau lọc nguồn; giữ model, không tinh chỉnh theo kết quả test. Tập test đã được sử dụng trong lượt trước nên đây là đánh giá lặp, không phải holdout chưa từng xem. LLM+RAG là toàn pipeline hiện tại, gồm cổng chặn và công cụ; không phải ablation thuần truy hồi."}
    manifest["ollama_models"] = requests.get("http://localhost:11434/api/tags", timeout=10).json()
    save(OUT / "manifest.json", manifest)
    save(OUT / "mau_50_cau.json", baseline.chon_mau())
    save(OUT / "tien_do.json", {"giai_doan": "khoi_tao", "luc": now()})

    # Giữ nguyên phép đo của benchmark; bọc quan sát để lưu đầy đủ sự kiện và
    # đúng những Document được đưa vào prompt, phục vụ chấm nội dung sau đó.
    original_initialize = bench.RAGService.initialize
    def initialize(service, *args, **kwargs):
        service.start_drive_auto_sync = lambda: None
        service.start_quet_thu_muc_nong = lambda: None
        original_initialize(service, *args, **kwargs)
        if service.status.state == "ready":
            manifest["model"] = service.llm_model
            manifest["tham_so_sinh"] = service._llm_tom_tat(service.llm_model).model_dump()
            save(OUT / "manifest.json", manifest)
    bench.RAGService.initialize = initialize
    original_run = bench.chay_mot_cau
    count = 0
    def run(service, item):
        nonlocal count
        count += 1
        audit = {"cau_hoi": item["cau_hoi"], "thu_tu": count, "bat_dau": now(),
                 "evidence": [], "su_kien": [], "done": False}
        save(OUT / "tien_do.json", {"giai_doan": "rag", "dang_chay": count, "tong": 200, "luc": now(), "cau_hoi": item["cau_hoi"]})
        original_stream = service.stream_answer
        original_format = service.format_docs
        def format_docs(docs):
            audit["evidence"] = [{"page_content": d.page_content, "metadata": d.metadata} for d in docs]
            return original_format(docs)
        def stream(*args, **kwargs):
            for event in original_stream(*args, **kwargs):
                if event["type"] not in ("token", "goi_y"):
                    audit["su_kien"].append(event)
                if event["type"] == "done":
                    audit["done"] = True
                yield event
        service.format_docs = format_docs
        service.stream_answer = stream
        try:
            result = original_run(service, item)
        finally:
            service.format_docs = original_format
            service.stream_answer = original_stream
        audit["ket_qua"] = bench.asdict(result)
        audit["ket_thuc"] = now()
        save(OUT / f"cau_{count:03d}.json", audit)
        return result
    bench.chay_mot_cau = run
    sys.argv = ["benchmark_chatbot.py", "--bo", "--tap", "test"]
    if bench.main() != 0:
        raise RuntimeError("Benchmark không hoàn tất")
    shutil.copy2(ROOT / "ket_qua_benchmark_day_du_test.json", OUT / "ket_qua_benchmark_day_du_test.json")
    save(OUT / "tien_do.json", {"giai_doan": "khong_rag", "luc": now()})
    if baseline.main() != 0:
        raise RuntimeError("Baseline không hoàn tất")
    shutil.copy2(ROOT / "ket_qua_llm_khong_rag.json", OUT / "ket_qua_llm_khong_rag.json")
    manifest.update({"ket_thuc": now(), "hash_sau": hashes(), "hoan_tat_sinh": True})
    manifest["ma_va_kho_khong_doi"] = manifest["hash_truoc"] == manifest["hash_sau"]
    save(OUT / "manifest.json", manifest)
    assert manifest["ma_va_kho_khong_doi"], "Mã hoặc kho đổi trong lúc đo; cần kiểm tra."
    save(OUT / "tien_do.json", {"giai_doan": "cho_cham_noi_dung", "luc": now()})
    print("ĐÃ SINH XONG 200 câu RAG + 50 câu không RAG. Cần chấm nội dung từng cặp.")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        save(OUT / "tien_do.json", {"giai_doan": "loi", "luc": now(), "loi": repr(exc)})
        raise
