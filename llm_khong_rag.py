"""
LLM gốc (không RAG) trên một mẫu câu hỏi của tập test, để so với LLM + RAG.

Cùng model, cùng tham số sinh (main.tao_llm) với chatbot; chỉ khác là KHÔNG có
bằng chứng truy hồi và không qua cổng chặn/hậu kiểm. Mẫu lấy từ các câu trong
phạm vi của tập test, hạt giống cố định. Kết quả: ket_qua_llm_khong_rag.json.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

import main as ung_dung
from rag_service import RAGService

SO_CAU = int(os.getenv("SO_CAU_KHONG_RAG", "40"))
RA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ket_qua_llm_khong_rag.json")
HE_THONG = ("Bạn là trợ lý giải đáp về giáo dục và pháp luật giáo dục Việt Nam. "
            "Trả lời ngắn gọn, bằng tiếng Việt.")


def chon_mau() -> list[dict]:
    with open("bo_cau_hoi_benchmark.json", encoding="utf-8") as f:
        bo = json.load(f)["cau_hoi"]
    trong = [m for m in bo if m.get("tap") == "test" and m.get("nhom") != "ngoai_pham_vi"]
    return random.Random(20261015).sample(trong, min(SO_CAU, len(trong)))


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        luong.reconfigure(encoding="utf-8", errors="replace")
    ten_model = RAGService._tai_lua_chon_model()
    llm = ung_dung.tao_llm(ten_model)
    mau = chon_mau()
    ket_qua = []
    for i, muc in enumerate(mau, 1):
        t0 = time.perf_counter()
        try:
            tra_loi = llm.invoke([("system", HE_THONG), ("human", muc["cau_hoi"])]).content
            loi = ""
        except Exception as exc:
            tra_loi, loi = "", f"{type(exc).__name__}: {exc}"
        ket_qua.append({"cau_hoi": muc["cau_hoi"], "nhom": muc["nhom"],
                        "nguon_mong_doi": muc.get("nguon_mong_doi", []),
                        "tra_loi_khong_rag": tra_loi, "giay": round(time.perf_counter() - t0, 1),
                        "loi": loi})
        with open(RA + ".tmp", "w", encoding="utf-8") as f:
            json.dump({"model": ten_model, "chay_luc": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "ket_qua": ket_qua}, f, ensure_ascii=False, indent=1)
        os.replace(RA + ".tmp", RA)
        print(f"[{i}/{len(mau)}] {ket_qua[-1]['giay']}s {muc['cau_hoi'][:60]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
